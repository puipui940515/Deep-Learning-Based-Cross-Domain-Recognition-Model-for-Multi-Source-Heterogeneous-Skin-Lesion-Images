"""Necessary CPU-only checks of this execution admission and native-call linkage."""
from pathlib import Path
import ast,copy,json,os,sys
from types import SimpleNamespace
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[3];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_relu_dropout_contract as c
from training_state import atomic_json

def rejected(fn):
    try:fn()
    except RuntimeError:return
    raise AssertionError('Invalid contract admitted')

def main():
    target=OUT/'CPU_DISPATCH_CHECKS.json'
    if target.exists():raise RuntimeError('Existing CPU checks retained')
    checks=[];tree=ast.parse((OUT/'gpu_compatibility.py').read_text(encoding='utf-8'))
    calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
    native=[n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='train_epoch']
    assert len(native)==1
    for node in ast.walk(tree):
        if isinstance(node,ast.Attribute):assert node.attr not in ('backward','unscale_','clip_grad_norm_','grad')
    assert ast.unparse(native[0].args[7])=="cfg['training']['gradient_accumulation']"
    checks.append('exactly one native train_epoch call; no custom backward, clipping, unscale or preAMP gradient policy')
    for path in [OUT/'gpu_compatibility.py',OUT/'run_gpu_checks.py',AREA/'scripts/train_regularized.py',AREA/'scripts/model_profiles.py',AREA/'scripts/v2_relu_dropout_contract.py',AREA/'scripts/run_v2_relu_dropout.py']:
        ast.parse(path.read_text(encoding='utf-8-sig'))
    checks.append('new dispatch and precheck syntax passed')
    reused=c.read(OUT/'CPU_REUSE.json');proofs={size:dict(architecture_audit=reused['evidence'][size]['architecture_audit'],
        initial_classifier_sha256=c.read(Path(reused['evidence'][size]['receipt']))['initial_classifier_sha256']) for size in ('tiny','base')}
    real_read,real_gate=c.read,c.gate;env={key:os.environ.get(key) for key in ('SKINDETECT_OPT_TOKEN','SKINDETECT_OPT_VERSION')}
    os.environ.update(SKINDETECT_OPT_TOKEN='cpu_fixture_only',SKINDETECT_OPT_VERSION=c.VERSION)
    try:
        c.gate=lambda:None
        for job,candidate,seed,size in c.JOBS:
            config=real_read(c.CONFIG/(candidate+'.json'));c.validate_candidate(config)
            active=dict(job=job,candidate=candidate,seed=seed,token='cpu_fixture_only',execution_revision=c.EXECUTION_REV)
            def fixture_read(path):
                path=Path(path)
                if path==c.RESULTS/'state.json':return {'active':active}
                if path.parent==c.RESULTS/'preflight':return proofs[path.stem]
                return real_read(path)
            c.read=fixture_read
            args=SimpleNamespace(formal=True,require_cuda=True,resume=False,seed=seed,config=c.CONFIG/(candidate+'.json'),output_root=c.RESULTS/'runs'/candidate)
            c.validate_execution(config,args)
            for key,value in [('seed',17),('resume',True),('formal',False),('require_cuda',False),('output_root',c.STUDY_RESULTS/'runs'/candidate)]:
                wrong=copy.copy(args);setattr(wrong,key,value);rejected(lambda:c.validate_execution(config,wrong))
            active['execution_revision']='restart1_20261026_v1';rejected(lambda:c.validate_execution(config,args));active['execution_revision']=c.EXECUTION_REV
            active['token']='wrong';rejected(lambda:c.validate_execution(config,args))
            fixture=copy.deepcopy(real_read(c.reference_folder(size,seed)/'run_inputs.json'))
            fixture.update(seed=seed,initial_optimizer_state_entries=0,effective_training_config=config['training'],architecture_audit=proofs[size]['architecture_audit'],
                initial_classifier_sha256=proofs[size]['initial_classifier_sha256'] if seed==1 else 'a'*64)
            fixture['contract'].update(experiment_id=candidate,seed=seed,pretrained_sha256=config['experiment']['weights']['sha256'])
            c.verify_initialization(fixture)
            wrong=copy.deepcopy(fixture);wrong['initial_optimizer_state_entries']=1;rejected(lambda:c.verify_initialization(wrong))
            checks.append(job+': exact seed/revision/token/output; fresh head/empty optimizer; Resume and wrong execution rejected')
    finally:
        c.read,c.gate=real_read,real_gate
        for key,value in env.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    root,summary=c.RESULTS,c.budget_summary;scratch=OUT/'cpu_budget_fixture';scratch.mkdir();(scratch/'budget').mkdir()
    previous=os.environ.get('SKINDETECT_OPT_TOKEN');os.environ['SKINDETECT_OPT_TOKEN']='cpu_fixture_only'
    try:
        c.RESULTS=scratch
        config=real_read(c.CONFIG/'v2in_tiny512_relu_stage_dropout.json');budget=c.EpochBudget(config,1,'cpu_fixture_run')
        assert budget.begin(1);rejected(lambda:budget.begin(1));budget.finish(dict(epoch=1,file='fixture',sha256='fixture'))
        rejected(lambda:budget.begin(1));rejected(lambda:budget.begin(3));(scratch/'STOP').touch();assert budget.begin(2) is False
        c.budget_summary=lambda:dict(active=[],completed_epoch_segments=180,events=[]);rejected(lambda:budget.begin(2))
        checks.append('180 complete epoch cap, single active lease, sequence/repeat protection and STOP in CPU-only fixture')
    finally:
        c.RESULTS,c.budget_summary=root,summary
        if previous is None:os.environ.pop('SKINDETECT_OPT_TOKEN',None)
        else:os.environ['SKINDETECT_OPT_TOKEN']=previous
    assert 'torch' not in sys.modules and 'timm' not in sys.modules
    atomic_json(target,dict(status='passed',checks=checks,no_models_or_GPU_reexecuted=True,CPU_architecture_reused=True))
    print(json.dumps(dict(status='passed',groups=len(checks)),ensure_ascii=False))

if __name__=='__main__':main()
