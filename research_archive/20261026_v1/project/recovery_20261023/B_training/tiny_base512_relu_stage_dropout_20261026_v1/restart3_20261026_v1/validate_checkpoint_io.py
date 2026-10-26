"""Tiny CPU payloads only, at isolated paths deeper than all six formal jobs."""
import os
os.environ['CUDA_VISIBLE_DEVICES']='-1'
from pathlib import Path
import copy,json,random,sys,time,traceback
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[3];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_relu_dropout_contract as c
import training_state as ts

def main():
    receipt=OUT/'IO_VALIDATION.json'
    if receipt.exists():raise RuntimeError('Existing IO test retained; do not repeat')
    isolated=c.RESULTS/'io_validation'
    if isolated.exists():raise RuntimeError('Existing isolated fixture retained')
    isolated.mkdir();started=time.perf_counter()
    data=dict(status='failed',no_images=True,no_models=True,no_GPU=True,no_formal_checkpoints_overwritten=True,cases=[])
    real_fsync,real_replace=ts.os.fsync,ts.os.replace
    syncs=[];replaces=[]
    def observe_fsync(fd):
        result=real_fsync(fd);syncs.append(fd);return result
    def observe_replace(source,target):
        source,target=Path(source),Path(target)
        assert source.parent==target.parent and source.name.startswith('.atomic-')
        assert len(source.name)==44 and len(str(source.absolute()))<260
        result=real_replace(source,target)
        replaces.append(dict(source=str(source),target=str(target),temporary_chars=len(str(source.absolute()))));return result
    try:
        import torch,numpy as np
        ts.os.fsync,ts.os.replace=observe_fsync,observe_replace
        class ExpectedWriteFailure(Exception):pass
        for job,candidate,seed,size in c.JOBS:
            formal=c.folder(candidate,seed);folder=isolated/formal.relative_to(c.RESULTS)
            assert folder.is_relative_to(isolated) and folder!=formal and not formal.exists()
            folder.mkdir(parents=True,exist_ok=False)
            probe=folder/'atomic_probe.json';ts.atomic_json(probe,{'value':1});ts.atomic_json(probe,{'value':2})
            assert json.loads(probe.read_text(encoding='utf-8'))=={'value':2}
            def fail_mid_write(handle):
                handle.write(b'intentional incomplete CPU fixture');raise ExpectedWriteFailure()
            try:ts.atomic_write(probe,fail_mid_write)
            except ExpectedWriteFailure:pass
            else:raise AssertionError('Expected fixture write failure not raised')
            assert json.loads(probe.read_text(encoding='utf-8'))=={'value':2} and not list(folder.glob('.atomic-*.tmp'))
            contract=dict(run_id='io_fixture_'+job,seed=seed,architecture='io_fixture_7_class',initialization='CPU_fixture',data={'fixture_only':True})
            generator=torch.Generator().manual_seed(seed)
            def payload(epoch):
                best_epoch=min(epoch,2)
                return dict(format_version=1,contract=contract,run_id=contract['run_id'],epoch=epoch,
                    model={'weight':torch.tensor([float(epoch),float(seed)])},best_model={'weight':torch.tensor([float(best_epoch),float(seed)])},
                    optimizer={'state':{0:{'step':torch.tensor(float(epoch)),'exp_avg':torch.tensor([.1]),'exp_avg_sq':torch.tensor([.01])}},'param_groups':[{'params':[0],'lr':1e-4}]},
                    scheduler={'last_epoch':epoch,'T_max':30,'eta_min':1e-6},scaler={'scale':65536.},
                    history=[{'epoch':e} for e in range(1,epoch+1)],best_score=.5,best_record={'epoch':best_epoch},bad_epochs=max(0,epoch-2),stop_reason=None,
                    rng={'python':random.getstate(),'numpy':np.random.get_state(),'torch_cpu':torch.get_rng_state(),'torch_cuda':[]},
                    sampler_generator_state=generator.get_state(),loader_generator_states={'train':generator.get_state()},elapsed_seconds=.01*epoch)
            store=ts.CheckpointStore(folder);descriptors=[]
            for epoch in (1,2,3):
                state=payload(epoch);descriptors.append(store.commit(state));ts.export_best(folder,state)
                index=json.loads((folder/'checkpoints/index.json').read_text(encoding='utf-8'))
                assert [item['epoch'] for item in index['generations']]==([1] if epoch==1 else [epoch,epoch-1])
            checkpoint_dir=folder/'checkpoints';index_path=checkpoint_dir/'index.json'
            index_bytes=index_path.read_bytes()
            assert len(list(checkpoint_dir.glob('epoch-*.pt')))==2 and not (checkpoint_dir/descriptors[0]['file']).exists()
            loaded_store=ts.CheckpointStore(folder);loaded=loaded_store.load(contract)
            assert loaded['epoch']==3 and loaded_store.loaded_descriptor==descriptors[2]
            assert torch.equal(loaded['model']['weight'],torch.tensor([3.,float(seed)]))
            assert int(loaded['optimizer']['state'][0]['step'])==3 and loaded['scheduler']['last_epoch']==3
            best=torch.load(folder/'best.pt',map_location='cpu',weights_only=False)
            assert best['epoch']==2 and torch.equal(best['model']['weight'],torch.tensor([2.,float(seed)]))
            wrong=copy.deepcopy(contract);wrong['seed']=17
            try:ts.CheckpointStore(folder).load(wrong)
            except RuntimeError as error:assert 'contract mismatch' in str(error)
            else:raise AssertionError('Contract mismatch was accepted')
            assert index_path.read_bytes()==index_bytes
            # Corrupt only this tiny isolated fixture, verify original fallback,
            # then restore its exact bytes atomically for the final readback.
            latest=checkpoint_dir/descriptors[2]['file'];valid=latest.read_bytes()
            ts.atomic_write(latest,lambda handle:handle.write(b'intentional isolated checksum fault'))
            fallback=ts.CheckpointStore(folder);previous=fallback.load(contract)
            assert previous['epoch']==2 and fallback.recovery_warning and fallback.loaded_descriptor==descriptors[1]
            ts.atomic_write(latest,lambda handle:handle.write(valid))
            assert ts.CheckpointStore(folder).load(contract)['epoch']==3 and ts.file_sha256(latest)==descriptors[2]['sha256']
            assert not list(checkpoint_dir.glob('.atomic-*.tmp')) and not list(folder.glob('.atomic-*.tmp'))
            formal_checkpoint_dir=formal/'checkpoints'
            assert len(str(checkpoint_dir.absolute()))>=len(str(formal_checkpoint_dir.absolute()))
            legacy=len(str((formal_checkpoint_dir/(descriptors[2]['file']+'.'+'0'*32+'.tmp')).absolute()))
            observed=[row['temporary_chars'] for row in replaces if Path(row['target']).is_relative_to(folder)]
            data['cases'].append(dict(job=job,formal_folder=str(formal),isolated_folder=str(folder),
                formal_checkpoint_dir_chars=len(str(formal_checkpoint_dir.absolute())),isolated_checkpoint_dir_chars=len(str(checkpoint_dir.absolute())),
                original_formal_temporary_chars=legacy,max_new_isolated_temporary_chars=max(observed),
                atomic_write_replace=True,failed_writer_preserves_old_target=True,two_generations_retained=[3,2],
                oldest_removed_after_index=True,index_readback=True,best_export_and_replace=True,full_CPU_payload_readback=True,
                original_contract_mismatch_rejected=True,original_checksum_fallback_verified=True,fixture_latest_restored=True))
        data.update(status='passed',case_count=len(data['cases']),all_six_formal_paths_covered=len(data['cases'])==6,
            actual_fsync_calls=len(syncs),same_directory_atomic_replace_calls=len(replaces),
            maximum_formal_legacy_temporary_chars=max(row['original_formal_temporary_chars'] for row in data['cases']),
            maximum_isolated_new_temporary_chars=max(row['max_new_isolated_temporary_chars'] for row in data['cases']))
        assert data['all_six_formal_paths_covered'] and len(syncs)>0 and len(replaces)>0
    except BaseException as error:
        data.update(error=repr(error),traceback=traceback.format_exc());(c.RESULTS/'STOP').touch(exist_ok=True)
    finally:
        ts.os.fsync,ts.os.replace=real_fsync,real_replace
        data.update(seconds=time.perf_counter()-started,command=sys.argv,python=sys.executable,training_state_sha256=ts.file_sha256(AREA/'scripts/training_state.py'))
        ts.atomic_json(receipt,data)
    print(json.dumps({key:data.get(key) for key in ('status','case_count','actual_fsync_calls','same_directory_atomic_replace_calls','maximum_formal_legacy_temporary_chars','maximum_isolated_new_temporary_chars','seconds','error')},ensure_ascii=False))
    return 0 if data['status']=='passed' else 1

if __name__=='__main__':sys.exit(main())
