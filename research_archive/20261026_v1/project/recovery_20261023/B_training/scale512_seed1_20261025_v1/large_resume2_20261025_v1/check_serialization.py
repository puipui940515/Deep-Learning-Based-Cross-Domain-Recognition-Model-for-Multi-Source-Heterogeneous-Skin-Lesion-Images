"""CPU-only regression of the actual Resume1 defect and native full checkpoint path."""
import ast
import copy
import io
import json
import os
from pathlib import Path
import pickle
import random
import sys
import time

os.environ['CUDA_VISIBLE_DEVICES']='-1'
OUT=Path(__file__).resolve().parent
PROJECT=OUT.parents[3]
sys.path.insert(0,str(PROJECT/'資料治理與泛化修復/scripts'))

def main():
    receipt=OUT/'SERIALIZATION_CHECK.json'
    if receipt.exists():print('Existing serialization check retained.');return
    started=time.perf_counter()
    import numpy as np
    import torch
    from training_state import CheckpointStore,atomic_json,file_sha256,export_best
    from resume_worker import observe_restored_objects
    checks=[]
    def objects(update=False):
        model=torch.nn.Linear(2,2)
        optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4,weight_decay=.05)
        scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=30,eta_min=1e-6)
        if update:
            model(torch.ones(1,2)).sum().backward();optimizer.step();scheduler.step();optimizer.zero_grad(set_to_none=True)
        return model,optimizer,scheduler
    # Execute precisely the prior nested factory body on tiny CPU objects.
    old_source=OUT.parent/'large_resume1_20261025_v1/resume_worker.py'
    old_tree=ast.parse(old_source.read_text(encoding='utf-8'))
    old_factory=next(n for n in ast.walk(old_tree) if isinstance(n,ast.FunctionDef) and n.name=='optimizer_for_restore')
    broken_model,broken_optimizer,broken_scheduler=objects(True)
    namespace=dict(original_optimizer_factory=lambda *_:(broken_optimizer,broken_scheduler),receipt={'restored_components':{}})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[old_factory],type_ignores=[])),str(old_source),'exec'),namespace)
    namespace['optimizer_for_restore'](broken_model,{})
    assert callable(broken_scheduler.state_dict()['load_state_dict'])
    old_error=None
    try:torch.save({'scheduler':broken_scheduler.state_dict()},io.BytesIO())
    except (AttributeError,pickle.PicklingError) as error:old_error=repr(error)
    assert old_error is not None
    checks.append('exact Resume1 factory reproduces scheduler serialization failure on CPU')
    model,optimizer,scheduler=objects(True)
    contract=dict(run_id='cpu_serialization_fixture',seed=1,architecture='linear_2x2_fixture',initialization='fixture_only',data={'source':'CPU fixture; no research data'})
    generator=torch.Generator().manual_seed(1)
    state=dict(format_version=1,contract=contract,run_id=contract['run_id'],epoch=13,
        model=copy.deepcopy(model.state_dict()),optimizer=copy.deepcopy(optimizer.state_dict()),scheduler=copy.deepcopy(scheduler.state_dict()),
        scaler={},rng=dict(python=random.getstate(),numpy=np.random.get_state(),torch_cpu=torch.get_rng_state(),torch_cuda=[]),
        sampler_generator_state=generator.get_state(),loader_generator_states={'train':generator.get_state()},
        history=[dict(epoch=e) for e in range(1,14)],best_score=.5,best_record={'epoch':11},
        best_model=copy.deepcopy(model.state_dict()),bad_epochs=2,stop_reason=None,elapsed_seconds=1.)
    fixture=OUT/'cpu_checkpoint_fixture_complete'
    if fixture.exists():raise RuntimeError('Fixture exists without complete receipt; do not overwrite')
    fixture.mkdir()
    store=CheckpointStore(fixture);descriptor13=store.commit(state)
    loaded_store=CheckpointStore(fixture);loaded=loaded_store.load(contract)
    restored_model,restored_optimizer,restored_scheduler=objects()
    restored_model.load_state_dict(loaded['model']);restored_optimizer.load_state_dict(loaded['optimizer']);restored_scheduler.load_state_dict(loaded['scheduler'])
    observed=observe_restored_objects(restored_model,restored_optimizer,restored_scheduler,loaded,expected_entries=2)
    assert all(observed.values())
    for name,tensor in restored_model.state_dict().items():assert torch.equal(tensor,loaded['model'][name])
    for actual,saved in zip(restored_optimizer.state_dict()['state'].values(),loaded['optimizer']['state'].values(),strict=True):
        assert actual.keys()==saved.keys()
        for key in actual:assert torch.equal(actual[key],saved[key])
    checks.append('new production observer verifies restored native objects without state_dict pollution')
    state14=copy.deepcopy(loaded);state14.update(epoch=14,history=loaded['history']+[dict(epoch=14)],
        model=restored_model.state_dict(),optimizer=restored_optimizer.state_dict(),scheduler=restored_scheduler.state_dict())
    descriptor14=loaded_store.commit(state14)
    final_store=CheckpointStore(fixture);final=final_store.load(contract);export_best(fixture,final)
    assert final['epoch']==14 and final_store.loaded_descriptor==descriptor14
    assert [g['epoch'] for g in final_store.index['generations']]==[14,13]
    assert final['best_record']['epoch']==11 and final['bad_epochs']==2
    checks.append('original CheckpointStore atomic commit/load, two generations and best export pass after observer')
    # Native scheduler state cannot acquire the former callable field.
    assert 'load_state_dict' not in final['scheduler']
    new_tree=ast.parse((OUT/'resume_worker.py').read_text(encoding='utf-8'))
    for node in ast.walk(new_tree):
        if isinstance(node,ast.Assign):
            for target in node.targets:
                assert not (isinstance(target,ast.Attribute) and isinstance(target.value,ast.Name)
                    and target.value.id in {'model','optimizer','scheduler'} and target.attr in {'load_state_dict','state_dict'})
    checks.append('no model/optimizer/scheduler state_dict or load_state_dict instance overwrite in new worker')
    atomic_json(receipt,dict(status='passed',checks=checks,old_failure=old_error,fixture='CPU Linear(2,2), four weights and two biases',
        expected_optimizer_entries=2,observer=observed,descriptor13=descriptor13,descriptor14=descriptor14,
        no_research_data=True,no_large_weight_load=True,no_gpu=True,old_source_sha256=file_sha256(old_source),
        new_worker_sha256=file_sha256(OUT/'resume_worker.py'),seconds=time.perf_counter()-started,
        command=sys.argv,python=sys.executable,torch=torch.__version__))
    print(json.dumps(dict(status='passed',checks=checks,seconds=time.perf_counter()-started),ensure_ascii=False))

if __name__=='__main__':main()
