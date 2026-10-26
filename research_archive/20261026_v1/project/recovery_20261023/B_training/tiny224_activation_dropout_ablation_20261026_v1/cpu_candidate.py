"""Minimal CPU checks for each new single-variable architecture; no image/GPU."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
from pathlib import Path
import argparse, ast, hashlib, json, sys, time, traceback
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[2];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'));sys.path.insert(0,str(PROJECT/'第二階段/src'))
import v2_tiny224_ablation_contract as c
from training_state import atomic_json


def main(group):
    receipt=OUT/f'CPU_{group}.json'
    if receipt.exists() or (c.RESULTS/'STOP').exists(): raise RuntimeError('Validation already consumed/stopped')
    data=dict(status='failed',group=group,no_GPU=True,no_images=True);start=time.perf_counter()
    try:
        import torch
        import model_profiles as profile
        from stage2.models import build_model
        from stage2.engine import seed_everything
        from train_regularized import build_transform
        from safetensors import safe_open
        from timm.layers import get_act_layer
        torch.set_num_threads(1);torch.set_num_interop_threads(1)
        candidate=next(k for k,v in c.CANDIDATES.items() if v[0]==group)
        cfg=c.read(c.CONFIG/(candidate+'.json'));base=c.read(c.BASE_CONFIG)
        profile.validate_profile(cfg,formal=True);profile.validate_profile(base,formal=True)
        assert cfg['training']==base['training']
        invalid=json.loads(json.dumps(cfg));invalid['training']['learning_rate']=5e-5
        try:c.validate_candidate(invalid)
        except RuntimeError:pass
        else:raise AssertionError('Unexpected science change accepted')
        # Baseline path still yields the untouched original architecture.
        original=build_model('convnextv2_tiny',False,7)
        shapes={k:tuple(v.shape) for k,v in original.state_dict().items()}
        assert [len(stage.blocks) for stage in original.stages]==[3,3,9,3]
        assert sum(type(m) is get_act_layer('gelu') for m in original.modules())==18
        assert not any(isinstance(m,torch.nn.modules.dropout._DropoutNd) and m.p for m in original.modules())
        del original
        seed_everything(1);model=profile.construct_model(cfg,restore=False)
        assert shapes=={k:tuple(v.shape) for k,v in model.state_dict().items()}
        with safe_open(str(PROJECT/cfg['experiment']['weights']['path']),framework='pt',device='cpu') as pinned:
            head={'head.fc.weight','head.fc.bias'}
            assert set(pinned.keys())-head==set(shapes)-head
            state=model.state_dict()
            assert all(torch.equal(state[key],pinned.get_tensor(key)) for key in state if key not in head)
        order=[];stage_shapes=[];hooks=[]
        for i,stage in enumerate(model.stages):
            blocks=[m for m in stage.blocks if type(m).__name__=='ConvNeXtBlock']
            hooks.append(blocks[-1].register_forward_hook(lambda m,a,y,i=i:order.append(f'block_end_{i}')))
            if group=='dropout':hooks.append(stage.blocks[-1].register_forward_hook(lambda m,a,y,i=i:order.append(f'dropout_{i}')))
            if i:hooks.append(stage.downsample.register_forward_pre_hook(lambda m,a,i=i:order.append(f'downsample_{i}')))
            hooks.append(stage.register_forward_hook(lambda m,a,y:stage_shapes.append(list(y.shape))))
        hooks.append(model.head.global_pool.register_forward_pre_hook(lambda m,a:order.append('original_head_pool')))
        model.eval();x=torch.ones(1,3,64,64)
        with torch.inference_mode():first=model(x);second=model(x)
        assert torch.equal(first,second) and list(first.shape)==[1,7] and bool(torch.isfinite(first).all())
        expected=[]
        for i in range(4):
            if i:expected.append(f'downsample_{i}')
            expected.append(f'block_end_{i}')
            if group=='dropout':expected.append(f'dropout_{i}')
        expected.append('original_head_pool');assert order==expected*2
        for h in hooks:h.remove()
        reused=c.read(PROJECT/'recovery_20261023/B_training/tiny_base512_relu_stage_dropout_20261026_v1/restart1_20261026_v1/CPU_tiny.json')
        assert stage_shapes[:4]==reused['stage_output_shapes'] and stage_shapes[4:]==stage_shapes[:4]
        if group=='dropout':
            for stage in model.stages:
                dropout=stage.blocks[-1];probe=torch.ones(4096);dropout.eval();assert torch.equal(dropout(probe),probe)
                dropout.train();masked=dropout(probe);assert bool((masked==0).any()) and bool((masked!=0).any());dropout.eval()
        audit=c.model_audit(model,cfg)
        assert (audit['relu_count'],audit['gelu_count'],audit['stage_dropout_count'])==((18,0,0) if group=='relu' else (0,18,4))
        optimizer,scheduler=profile.optimizer_and_scheduler(model,cfg)
        assert not optimizer.state and scheduler.T_max==30 and scheduler.eta_min==1e-6
        def functions(path):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text(encoding='utf-8-sig')).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        before=functions(OUT/'before/train_regularized.py');after=functions(AREA/'scripts/train_regularized.py')
        for name in ['train_epoch','evaluate','build_transform','load_governed_release','sample_weights','stratified_limit']:assert before[name]==after[name],name
        before_profiles=functions(OUT/'before/model_profiles.py');after_profiles=functions(AREA/'scripts/model_profiles.py')
        for name in ['optimizer_and_scheduler','classifier','transform','weight_identity']:assert before_profiles[name]==after_profiles[name],name
        data.update(status='passed',candidate=candidate,architecture_audit=audit,training_dict_matches_original224=True,
            all_pretrained_backbone_values_match_pinned_file=True,parameter_keys_shapes_unchanged=True,
            original_candidate_untouched=True,eval_deterministic=True,output_shape=[1,7],
            stage_output_shapes=stage_shapes[:4],stage_execution_order=expected,original_pooling_preserved=True,
            stage_dropout_train_active_eval_identity=(group=='dropout'),
            initial_classifier_sha256=hashlib.sha256(model.get_classifier().weight.detach().numpy().tobytes()).hexdigest(),
            effective_transforms={'train':repr(build_transform(224,True)),'validation':repr(build_transform(224,False))},
            native_training_and_data_functions_AST_unchanged=True,
            reused_native_stage_shape_and_GRN_evidence='restart1/CPU_tiny.json',checkpoint_protection_test='separate_micro_CPU_IO_validation')
    except BaseException as e:
        data.update(error=repr(e),traceback=traceback.format_exc());(c.RESULTS/'STOP').touch(exist_ok=True)
    data.update(seconds=time.perf_counter()-start,command=sys.argv,python=sys.executable)
    atomic_json(receipt,data);print(json.dumps({k:data.get(k) for k in ['group','status','seconds','error']},ensure_ascii=False))
    return 0 if data['status']=='passed' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--group',choices=['relu','dropout'],required=True)
    sys.exit(main(p.parse_args().group))
