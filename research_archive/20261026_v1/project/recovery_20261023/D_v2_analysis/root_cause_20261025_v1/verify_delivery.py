import hashlib, json, re
from pathlib import Path
P=Path(__file__).resolve().parent
j=json.loads((P/'NUMERIC_ANALYSIS.json').read_text(encoding='utf-8'))
q=json.loads((P/'NUMERIC_QA.json').read_text(encoding='utf-8'))
im=json.loads((P/'images/selection.json').read_text(encoding='utf-8'))
report=(P/'REPORT.md').read_text(encoding='utf-8')
checks={
 'numeric_100_checks_passed':q['passed'] and q['count']==100,
 '31_original_atomic_conditions':len(j['rules'])==31,
 'seven_conditions_failed':sum(not x['passed'] for x in j['rules'])==7,
 'not_adopted':j['adopt'] is False,
 'zero_Robust_improved_seeds':j['strict_robust_improved_seeds']==0,
 'sixteen_original_images_under_24':len(im['selected'])==16 and len(im['selected'])<=24,
 'image_splits_not_Test':all(x['split'] in ('train','validation') for x in im['selected']),
 'source_small_files_unchanged_at_delivery':all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in q['sources_sha256'].items()),
 'required_outputs':all((P/x).is_file() for x in ['REPORT.md','B_DIAGNOSTIC_TASK.md','bottleneck_summary.png','bottleneck_summary.svg','static_audit/REPORT.md','curves/REPORT.md','images/REPORT.md']),
 'one_unexecuted_B_task':(P/'B_DIAGNOSTIC_TASK.md').read_text(encoding='utf-8').count('## 給B的可完整複製指令')==1,
}
for label,target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',report):
    if target.startswith('http'):continue
    checks['report_link_'+label]=(P/target).is_file()
if not all(checks.values()):raise RuntimeError(checks)
artifact_hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in P.rglob('*') if f.is_file() and 'mpl_cache' not in str(f) and f.suffix in ['.md','.json','.csv','.png','.svg','.py','.jpg'] and f.name!='DELIVERY_QA.json'}
result={'status':'passed','checks':checks,'artifact_sha256':artifact_hashes,'limits':['CPU only; saved metrics arithmetic, static code and 16 original nonTest image views','No model/GPU/inference/training/PT payload/Test access; no package installs','No common index/formal source edits; controller records delivery separately','Proposed B inference not executed or authorized by this receipt']}
(P/'DELIVERY_QA.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':result['status'],'checks':len(checks),'artifacts':len(artifact_hashes),'images':len(im['selected'])}))
