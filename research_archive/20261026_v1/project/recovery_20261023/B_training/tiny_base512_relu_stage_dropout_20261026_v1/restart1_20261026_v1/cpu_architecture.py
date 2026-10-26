"""One architecture/mapping/serialization CPU check per model; no research images."""
import os
os.environ['CUDA_VISIBLE_DEVICES']='-1'
from pathlib import Path
import argparse,copy,hashlib,json,random,sys,time,traceback
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[3];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'));sys.path.insert(0,str(PROJECT/'第二階段/src'))
import v2_relu_dropout_contract as c
from training_state import atomic_json,CheckpointStore,export_best

def main(size):
    target=OUT/f'CPU_{size}.json'
    if target.exists():raise RuntimeError('Existing CPU receipt retained; no duplicate')
    receipt=dict(status='failed',size=size,no_images=True,no_gpu=True);started=time.perf_counter()
    try:
        import torch,numpy as np
        import model_profiles as profile
        from stage2.models import build_model
        from stage2.engine import seed_everything
        from safetensors import safe_open
        from timm.layers import get_act_layer
        torch.set_num_threads(1);torch.set_num_interop_threads(1)
        candidate=f'v2in_{size}512_relu_stage_dropout';cfg=c.read(c.CONFIG/(candidate+'.json'));profile.validate_profile(cfg,formal=True)
        old_cfg=c.read(c.BASE_CONFIGS[size]);profile.validate_profile(old_cfg,formal=True)
        original=build_model('convnextv2_'+size,False,7)
        depths=[3,3,9,3] if size=='tiny' else [3,3,27,3]
        assert [len(stage.blocks) for stage in original.stages]==depths
        original_blocks=[block for stage in original.stages for block in stage.blocks]
        assert len(original_blocks)==sum(depths) and all(type(block.mlp.act) is get_act_layer('gelu') for block in original_blocks)
        assert not any(isinstance(m,torch.nn.modules.dropout._DropoutNd) and m.p for m in original.modules())
        native_keys={name:tuple(value.shape) for name,value in original.state_dict().items()}
        native_shapes=[];handles=[stage.register_forward_hook(lambda m,a,y:native_shapes.append(tuple(y.shape))) for stage in original.stages]
        original.eval();x=torch.ones(1,3,64,64)
        with torch.inference_mode():native_output=original(x)
        for handle in handles:handle.remove()
        del original
        seed_everything(1);model=profile.construct_model(cfg,restore=False)
        assert native_keys=={name:tuple(value.shape) for name,value in model.state_dict().items()}
        identity=cfg['experiment']['weights'];head_keys={'head.fc.weight','head.fc.bias'}
        with safe_open(str(PROJECT/identity['path']),framework='pt',device='cpu') as weights:
            assert set(weights.keys())-head_keys==set(native_keys)-head_keys
            assert all(tuple(weights.get_slice(name).get_shape())==shape for name,shape in native_keys.items() if name not in head_keys)
        variant_shapes=[];order=[];handles=[]
        for i,stage in enumerate(model.stages):
            handles.append(stage.blocks[-2].register_forward_hook(lambda m,a,y,i=i:order.append(f'block_end_{i}')))
            handles.append(stage.blocks[-1].register_forward_hook(lambda m,a,y,i=i:order.append(f'dropout_{i}')))
            handles.append(stage.register_forward_hook(lambda m,a,y:variant_shapes.append(tuple(y.shape))))
            if i:handles.append(stage.downsample.register_forward_pre_hook(lambda m,a,i=i:order.append(f'downsample_{i}')))
        handles.append(model.head.global_pool.register_forward_pre_hook(lambda m,a:order.append('original_head_pool')))
        model.eval()
        with torch.inference_mode():a=model(x);b=model(x)
        assert torch.equal(a,b) and tuple(a.shape)==tuple(native_output.shape)==(1,7) and torch.isfinite(a).all()
        assert variant_shapes[:4]==native_shapes and variant_shapes[4:]==native_shapes
        expected=[]
        for i in range(4):
            if i:expected.append(f'downsample_{i}')
            expected += [f'block_end_{i}',f'dropout_{i}']
        expected.append('original_head_pool');assert order==expected*2
        for handle in handles:handle.remove()
        for stage in model.stages:
            dropout=stage.blocks[-1];dropout.eval();probe=torch.ones(10000);assert torch.equal(dropout(probe),probe)
            dropout.train();mask=dropout(probe);assert (mask==0).any() and (mask!=0).any();dropout.eval()
        audit=c.model_audit(model,cfg)
        optimizer,scheduler=profile.optimizer_and_scheduler(model,cfg);assert not optimizer.state
        state=dict(format_version=1,contract=dict(run_id='cpu_'+size,seed=1,architecture=c.architecture_name(cfg),initialization='imagenet',data={'CPU_fixture':True}),
            run_id='cpu_'+size,epoch=1,history=[dict(epoch=1)],best_score=.5,best_record={'epoch':1},bad_epochs=0,stop_reason=None,elapsed_seconds=0.,
            model=model.state_dict(),best_model=model.state_dict(),optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),scaler={},
            rng=dict(python=random.getstate(),numpy=np.random.get_state(),torch_cpu=torch.get_rng_state(),torch_cuda=[]),
            sampler_generator_state=torch.Generator().get_state(),loader_generator_states={'train':torch.Generator().get_state()})
        folder=OUT/('cpu_checkpoint_'+size);folder.mkdir()
        store=CheckpointStore(folder);descriptor=store.commit(state);loaded_store=CheckpointStore(folder);loaded=loaded_store.load(state['contract'])
        model.load_state_dict(loaded['model'],strict=True);optimizer.load_state_dict(loaded['optimizer']);scheduler.load_state_dict(loaded['scheduler']);export_best(folder,loaded)
        assert model._skindetect_variant_audit==audit and scheduler.state_dict()==loaded['scheduler']
        receipt.update(status='passed',architecture_audit=audit,native_candidate_unchanged=True,all_backbone_keys_shapes_matched=True,
            original_activation_type=get_act_layer('gelu').__module__+'.'+get_act_layer('gelu').__name__,
            state_keys_shapes_unchanged=True,stage_output_shapes=native_shapes,head_shape=[1,7],stage_execution_order=expected,
            dropout_train_active_eval_disabled=True,eval_deterministic=True,checkpoint_roundtrip=True,checkpoint=descriptor,
            model_state_only_no_method_overrides=True,initial_classifier_sha256=hashlib.sha256(profile.classifier(model,cfg['training']['model']).weight.detach().numpy().tobytes()).hexdigest())
    except BaseException as error:
        receipt.update(error=repr(error),traceback=traceback.format_exc());(c.RESULTS/'STOP').touch(exist_ok=True)
    receipt['seconds']=time.perf_counter()-started;receipt['command']=sys.argv;atomic_json(target,receipt)
    print(json.dumps({k:receipt.get(k) for k in ('size','status','seconds','error')},ensure_ascii=False))
    return 0 if receipt['status']=='passed' else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--size',choices=['tiny','base'],required=True);args=parser.parse_args();sys.exit(main(args.size))
