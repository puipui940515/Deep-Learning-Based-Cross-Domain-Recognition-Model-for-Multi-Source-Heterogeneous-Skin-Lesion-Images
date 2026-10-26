"""Micro CPU storage test, isolated paths deeper than every formal job path."""
import os
os.environ['CUDA_VISIBLE_DEVICES']='-1'
from pathlib import Path
import json,sys,time,traceback
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[2];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_tiny224_ablation_contract as c
import training_state as ts


def main():
    receipt=OUT/'IO_VALIDATION_fix1.json'
    if receipt.exists() or (c.RESULTS/'STOP').exists():raise RuntimeError('Validation already consumed/stopped')
    isolated=c.RESULTS/'io_validation';isolated.mkdir();start=time.perf_counter()
    data=dict(status='failed',micro_CPU_only=True,no_images_or_models_or_GPU=True,cases=[])
    fsync,replace=ts.os.fsync,ts.os.replace;sync_count=0;replace_paths=[]
    def sync(fd):
        nonlocal sync_count
        fsync(fd);sync_count+=1
    def atomic_replace(src,dst):
        src,dst=Path(src),Path(dst)
        assert src.parent==dst.parent and src.name.startswith('.atomic-') and len(src.name)==44
        assert len(str(src.absolute()))<260
        replace(src,dst);replace_paths.append(str(src.absolute()))
    try:
        import torch
        ts.os.fsync,ts.os.replace=sync,atomic_replace
        for job,candidate,seed,group in c.JOBS:
            formal=c.folder(candidate,seed);folder=isolated/formal.relative_to(c.RESULTS)
            assert not formal.exists() and folder!=formal;folder.mkdir(parents=True)
            contract=dict(run_id='io_'+job,seed=seed,architecture=candidate,initialization='CPU_fixture',data={'fixture':True})
            store=ts.CheckpointStore(folder);descriptors=[]
            for epoch in (1,2,3):
                state=dict(format_version=1,contract=contract,run_id=contract['run_id'],epoch=epoch,
                    model={'weight':torch.tensor([float(epoch)])},best_model={'weight':torch.tensor([float(min(epoch,2))])},
                    optimizer={'state':{0:{'step':torch.tensor(float(epoch)),'exp_avg':torch.tensor([.1]),'exp_avg_sq':torch.tensor([.01])}},'param_groups':[{'params':[0],'lr':1e-4}]},
                    scheduler={'last_epoch':epoch,'T_max':30,'eta_min':1e-6},scaler={'scale':65536.},
                    history=[{'epoch':e} for e in range(1,epoch+1)],best_score=.5,best_record={'epoch':min(epoch,2)},bad_epochs=0,stop_reason=None,
                    rng=ts.capture_rng(),
                    sampler_generator_state=torch.Generator(device='cpu').manual_seed(seed+4).get_state(),
                    loader_generator_states={name:torch.Generator(device='cpu').manual_seed(seed+100+i).get_state()
                        for i,name in enumerate(['train','monitor',*c.read(c.BASE_CONFIG)['sources']])},elapsed_seconds=.01)
                descriptors.append(store.commit(state));ts.export_best(folder,state)
                idx=c.read(folder/'checkpoints/index.json')
                assert [d['epoch'] for d in idx['generations']]==([1] if epoch==1 else [epoch,epoch-1])
            readback=ts.CheckpointStore(folder).load(contract);assert readback['epoch']==3
            assert int(readback['optimizer']['state'][0]['step'])==3
            torch.Generator(device='cpu').set_state(readback['sampler_generator_state'])
            for generator_state in readback['loader_generator_states'].values():
                torch.Generator(device='cpu').set_state(generator_state)
            ts.restore_rng(readback['rng'])
            best=torch.load(folder/'best.pt',map_location='cpu',weights_only=False)
            assert best['epoch']==2 and torch.equal(best['model']['weight'],torch.tensor([2.]))
            assert len(list((folder/'checkpoints').glob('epoch-*.pt')))==2
            assert not (folder/'checkpoints'/descriptors[0]['file']).exists()
            assert not list(folder.rglob('.atomic-*.tmp'))
            data['cases'].append(dict(job=job,formal_folder=str(formal),isolated_folder=str(folder),
                formal_checkpoint_directory_chars=len(str(formal/'checkpoints')),
                isolated_checkpoint_directory_chars=len(str(folder/'checkpoints')),
                max_temp_path_chars=max(len(x) for x in replace_paths if x.startswith(str(folder))),
                temporary_write_replace_and_fsync=True,index_readback=True,generations=[3,2],best_export_replace_readback=True,full_state_readback=True))
        data.update(status='passed',case_count=6,actual_fsync_calls=sync_count,actual_atomic_replace_calls=len(replace_paths),max_temporary_chars=max(map(len,replace_paths)),
            original_checksum_fallback_contract_rejection_and_write_failure_protection_reused='restart3/IO_VALIDATION.json; training_state.py byte-identical')
    except BaseException as e:
        data.update(error=repr(e),traceback=traceback.format_exc());(c.RESULTS/'STOP').touch(exist_ok=True)
    finally:
        ts.os.fsync,ts.os.replace=fsync,replace
        data.update(seconds=time.perf_counter()-start,command=sys.argv,training_state_sha256=ts.file_sha256(AREA/'scripts/training_state.py'))
        ts.atomic_json(receipt,data)
    print(json.dumps({k:data.get(k) for k in ['status','case_count','max_temporary_chars','seconds','error']},ensure_ascii=False))
    return 0 if data['status']=='passed' else 1


if __name__=='__main__':sys.exit(main())
