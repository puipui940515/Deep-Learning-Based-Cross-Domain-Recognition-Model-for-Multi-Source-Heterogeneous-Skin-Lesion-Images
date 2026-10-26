"""Close out from saved small JSON/text only; no model/weight loading or hashing."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

PROJECT = Path('D:/SkinDetect_base')
B = PROJECT / 'recovery_20261023/B_training/alpha025_retry1_20261024_v1'
AREA = PROJECT / '資料治理與泛化修復'
ROOT = AREA / 'results/v2_512_alpha025_20261024_v1/executions/retry1_20261024_v1'
CONFIG = AREA / 'configs/v2_512_alpha025_20261024_v1'
BASE = AREA / 'results/v2_resolution_20261021_v1/runs/v2in_res512'
MARKER = '<!-- B-ALPHA025-CLOSEOUT:20261025:v1 -->'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def table(headers, rows):
    return ['|' + '|'.join(headers) + '|', '|' + '|'.join(['---'] * len(headers)) + '|'] + [
        '|' + '|'.join(str(v) for v in row) + '|' for row in rows]


def local(value):
    return datetime.fromisoformat(value).astimezone(timezone(timedelta(hours=8))).isoformat()


state = read(ROOT / 'state.json')
final = read(ROOT / 'FINAL_RESULTS.json')
resource = read(B / 'CLOSEOUT_RESOURCES_20261025_v1.json')
assert state['status'] == final['status'] == 'completed' and state['active'] is None
assert not final['test_used'] and not final['automatic_model_adoption']
assert not resource['matching_alpha025_processes'] and not resource['historical_pid_current_matches']
config = read(CONFIG / 'v2in_res512_alpha025.json')
old_config = read(AREA / 'configs/v2_resolution_20261021_v1/v2in_res512.json')
diff = {k: [old_config['training'].get(k), config['training'].get(k)]
        for k in set(old_config['training']) | set(config['training'])
        if old_config['training'].get(k) != config['training'].get(k)}
assert diff == {'class_balance_alpha': [0.5, 0.25]}
summaries, metric_rows, time_rows, artifact_lines = [], [], [], []
totals = {key: 0.0 for key in ('train_seconds', 'evaluation_seconds', 'checkpoint_seconds',
                             'epoch_seconds', 'data_wait_seconds', 'batch_processing_seconds')}
identity_checks, missing = {}, []
for row in final['rows']:
    seed = row['seed']
    folder = ROOT / 'runs/v2in_res512_alpha025' / f'regularized_seed{seed}'
    result, inputs = read(folder / 'result.json'), read(folder / 'run_inputs.json')
    old_inputs = read(BASE / f'regularized_seed{seed}/run_inputs.json')
    assert result['status'] == 'completed' and result['stop_reason'] == 'early_stopping'
    assert result['epochs_completed'] == row['epochs_completed'] and not result['test_used']
    assert row['run_id'] == result['run_id'] == inputs['run_id'] and not row['resume'] and row['exit_code'] == 0
    identities = dict(effective_config=inputs['effective_training_config'] == config['training'],
        class_order=inputs['data']['class_names'] == old_inputs['data']['class_names'],
        manifest=inputs['data']['manifest_sha256'] == old_inputs['data']['manifest_sha256'],
        train_ids=inputs['selected_train_record_ids'] == old_inputs['selected_train_record_ids'],
        val_ids=inputs['selected_validation_record_ids'] == old_inputs['selected_validation_record_ids'],
        initialization_head=inputs['initial_classifier_sha256'] == old_inputs['initial_classifier_sha256'],
        initialization_backbone=inputs['contract']['pretrained_sha256'] == old_inputs['contract']['pretrained_sha256'],
        empty_optimizer=inputs['initial_optimizer_state_entries'] == 0,
        transforms=inputs['contract']['effective_transforms'] == old_inputs['contract']['effective_transforms'],
        recorded_versions=inputs['contract']['versions'] == old_inputs['contract']['versions'],
        python_version=inputs['contract']['python'] == old_inputs['contract']['python'],
        worker_rng_policy=inputs['contract']['worker_rng_policy'] == old_inputs['contract']['worker_rng_policy'])
    assert all(identities.values())
    identity_checks[str(seed)] = identities
    index = read(folder / 'checkpoints/index.json')
    assert len(index['generations']) == 2
    assert max(cp['epoch'] for cp in index['generations']) == result['epochs_completed']
    metric_files = list(folder.glob('metrics_*.jsonl'))
    metrics = [json.loads(line) for file in metric_files for line in file.read_text(encoding='utf-8').splitlines() if line]
    assert len(metrics) == result['epochs_completed'] == len(result['history'])
    required = [folder / name for name in ('run_inputs.json', 'result.json', 'best.pt', 'checkpoints/index.json')]
    required += [folder / 'checkpoints' / cp['file'] for cp in index['generations']]
    required += metric_files + [Path(row['stdout']), Path(row['stderr']), Path(row['attempt_receipt'])]
    missing += [str(path) for path in required if not path.is_file()]
    values = row['metrics']['values']  # Copy saved summary; do not recompute Accuracy/F1 from confusion matrices.
    assert values['robust'] == result['best']['robust_selection_score']
    summaries.append([seed, row['run_id'], result['epochs_completed'], result['best']['epoch'],
                      'completed / early_stopping', result['history'][-1]['bad_epochs']])
    metric_rows.append([seed] + [f'{values[key] * 100:.4f}%' for key in
                       ('robust', 'accuracy', 'macro_f1', 'HAM10000:ba', 'BCN20000:ba', 'PAD-UFES-20:ba')])
    times = {key: sum(m[key] for m in metrics) for key in ('train_seconds', 'evaluation_seconds', 'checkpoint_seconds', 'epoch_seconds')}
    times['data_wait_seconds'] = sum(m['batch_timing']['data_wait_including_iterator_tqdm_seconds'] for m in metrics)
    times['batch_processing_seconds'] = sum(m['batch_timing']['batch_processing_seconds_with_existing_loss_sync'] for m in metrics)
    for key, value in times.items():
        totals[key] += value
    time_rows.append([seed] + [f'{times[key]:.6f}' for key in totals])
    artifact_lines += [f'- Seed{seed} 完整目錄：`{folder}`。',
        '  既有檔案：`run_inputs.json`（設定／來源／初始化／環境）、`result.json`（best／完整history／停止原因）、',
        f"  `{metric_files[0].name}`（逐輪）、`best.pt`、`checkpoints/index.json`；完整Checkpoint實檔：",
        '  ' + '、'.join(f"`{cp['file']}`" for cp in index['generations']) + '（均位於上述目錄的checkpoints/）。',
        f"  標準輸出：`{row['stdout']}`；錯誤／進度：`{row['stderr']}`。",
        f"  同Seed原512對照：`{BASE / f'regularized_seed{seed}'}`，使用其`result.json`及`run_inputs.json`，不重選Epoch。"]

parent = ROOT.parent.parent
parent_state = read(parent / 'state.json')
assert parent_state['status'] == 'failed' and (parent / 'STOP').exists()
assert len(final['rows']) == 3 and sum(row['epochs_completed'] for row in final['rows']) == 45
required_global = [ROOT / name for name in ('FINAL_RESULTS.json', 'state.json', 'EXPERIMENT_STATE.md',
    'EXECUTION_GATE.json', 'resource_samples.jsonl', 'C_HANDOFF.md')]
required_global += [CONFIG / 'EVALUATION_CONTRACT.json', CONFIG / 'DIFF_AND_SOURCES.json']
missing += [str(path) for path in required_global if not path.is_file()]
assert not missing, missing
budget = [read(path) for path in (ROOT / 'budget').glob('*.json')]
assert len(budget) == 45 and all(x['committed'] and x['status'] == 'completed' for x in budget)
attempts = [read(path) for path in (ROOT / 'attempts').glob('*.json')]
assert len(attempts) == 3 and all(x['exit_code'] == 0 and not x['resume'] for x in attempts)
wall = (datetime.fromisoformat(state['ended_utc']) - datetime.fromisoformat(state['created_utc'])).total_seconds()
result_time = sum(read(ROOT / f'runs/v2in_res512_alpha025/regularized_seed{s}/result.json')['elapsed_seconds'] for s in (1, 2, 3))
now = datetime.now(timezone(timedelta(hours=8))).isoformat()

lines = ['', MARKER, '## 2026-10-25 正式結案：三 Seed 完成，尚未判定採納', '',
    f"結案記錄時間：{now}；完成時間：{local(state['ended_utc'])}。本段取代上文首輪／第11輪等歷史進度的現況判讀，歷史內容保留。",
    '**訓練完成，尚未判定採納。** 三個新初始化run皆completed、無Resume、exit_code=0、stop_reason=early_stopping；45/90完整Epoch，沒有以分數取消Seed3。', '']
lines += table(['Seed', 'Run ID', '完整Epoch', '最佳Epoch', '狀態／停止原因', '結束未改善輪數'], summaries)
lines += ['', 'Seed3最佳Epoch5後累積7輪未改善，在Min12限制下於Epoch12結束；沿用原早停規則，沒有跳Seed或增加預算。', '',
    '### 已保存的最佳 Validation 摘要', '',
    '以下直接抄自FINAL_RESULTS.rows[].metrics.values（已保存全Validation合併Accuracy／Macro-F1，不是三來源指標的簡單平均；BA按原來源定義）。本次沒有重新評估或重算混淆矩陣。', '']
lines += table(['Seed', 'Robust', 'Accuracy', 'Macro-F1', 'HAM10000 BA', 'BCN20000 BA', 'PAD-UFES-20 BA'], metric_rows)
lines += ['', '完整疾病TP／N／Recall、合併MEL、混淆矩陣與流向：FINAL_RESULTS的`rows[].metrics.diseases`／`merged_confusion_matrix`／`validation_by_source`，及各result的`best.validation_by_source`。PAD無支持的DF／VASC為N/A，不能讀成Recall0。B不另算配對差值或判斷採納。', '',
    '### 生效配方、初始化及與原512的差異', '',
    '三份run_inputs均與C核定training一致：ConvNeXt V2-Tiny ImageNet、512、alpha=.25、Seeds1/2/3、微批8×累積8（有效64）、LR1e-4；AdamW／WD.05／LD1／LS.1／MixUp.2／clip1／RE.15／AMP／workers4／prefetch4、原增強與ImageNet正規化。Min12/Max30、Patience5、MinDelta0、Tmax30、cosine eta_min1e-6；以首次最高0.5×mean來源BA+0.5×最差來源BA選模。',
    '原governed_18979_20261018_v1：Train18919、Monitor1500、Val3611；類序AKIEC/BCC/BKL/DF/NV/VASC/MEL。正式入口由manifest-release指定，不把歷史data_definition字串當生效資料入口。三Seed已存manifest身分、Train/Val record IDs、類序與原512同Seed一致。',
    f"資料入口：`{AREA / 'data/governed_18979_20261018_v1/mixed_manifest.csv'}`；僅引用已保存的manifest身分，未重新讀資料清單或影像。",
    '各Seed由釘選`timm/convnextv2_tiny.fcmae_ft_in1k` revision `508caf1bc24fd02c69d15778b994e808670dbc28`的同一本機backbone獨立初始化，從未接續舊best。已存初始head身分與原512同Seed一致、Optimizer state entries=0、backbone身分與前處理相同；本次只比較JSON中既有身分，不重hash權重。',
    f"初始化快取：`{PROJECT / '.venv-skindetect/hf_cache/hub/models--timm--convnextv2_tiny.fcmae_ft_in1k/snapshots/508caf1bc24fd02c69d15778b994e808670dbc28/model.safetensors'}`。",
    '讀取原／新training JSON確認唯一核定科學變因為class_balance_alpha .5→.25。執行差異另列，不能宣稱所有位元與執行環境條件完全相同：',
    '- 新candidate／pipeline／optimization授權與retry1 execution身分、新gate／輸出根目錄、新ID與512/8×8相容註冊、有限3run/90Epoch計帳；時間上限明確null，未沿用舊resolution時間預算。',
    '- 使用recovery venv及D槽Python；已存Python3.12.10、torch2.11.0+cu128、torchvision0.26.0+cu128、timm1.0.30、numpy1.26.4、Pillow10.4.0的版本值與原512記錄相同，環境路徑及系統pagefile恢復狀態另有差異。48GiB分頁檔由使用者先行套用，B未改Windows。',
    '- 按使用者還原原啟動前Commit8GiB／GPU≤10%／顯存6500MiB／磁碟10GiB與程序衝突檢查；無新增RAM4GiB或執行中資源／程序強停，無新增每批Loss／梯度停止。保留原整輪非有限、STOP、Checkpoint與異常退出；必要UTF-8相容修復、被動資源與資料等待計時另記。',
    '- 原失敗run保留，retry1是明確單次新初始化授權；不是Resume。persistent workers RNG政策原樣保留，不宣稱逐位元可重播。', '',
    '### 設定、結果與日誌完整入口', '',
    f"- C核定設定：`{CONFIG / 'v2in_res512_alpha025.json'}`；核定／差異：`{CONFIG / 'AUTHORIZATION.md'}`、`{CONFIG / 'DIFF_AND_SOURCES.json'}`。",
    f"- 評估契約：`{CONFIG / 'EVALUATION_CONTRACT.json'}`；D規則與v2／補充／v2.1：`{PROJECT / 'recovery_20261023/D_v2_analysis/resolution_decision_20261024_v1/DECISION.md'}`。",
    f"- 正式結果：`{ROOT / 'FINAL_RESULTS.json'}`；狀態：`{ROOT / 'state.json'}`、`{ROOT / 'EXPERIMENT_STATE.md'}`。",
    f"- 完整監控表（已完成並停更的最終快照）：`{B / '完整即時監控表.md'}`；最後更新2026-10-25 02:14:47，狀態completed／controller不在。",
    f"- 生效gate：`{ROOT / 'EXECUTION_GATE.json'}`；當時來源快照：`{ROOT / 'sources_runtime'}`；實際指令／每Seed排程：`{ROOT / 'attempts'}`，另見state.runs各command。",
    f"- 逐輪區段計帳：`{ROOT / 'budget'}`；被動資源：`{ROOT / 'resource_samples.jsonl'}`；原始controller日誌位於`{ROOT}`的`controller_20261024_213140_078.stdout.log`及`.stderr.log`。"]
lines += artifact_lines
lines += ['', '必要結果／設定／日誌／三份best.pt／各兩代完整Checkpoint實檔均存在，無缺項；本次只讀index及檔案存在性，未重新hash、載入權重或測試Resume。', '',
    '### 耗時計帳（秒，引用既有紀錄；不是新增benchmark）', '',
    f"- 新成功execution的三次attempt合計：**{final['total_attempt_seconds_including_initialization_and_failures']:.6f}秒（{final['total_attempt_seconds_including_initialization_and_failures']/3600:.4f}小時）**，含初始化與結束成本，三次exit0、均非Resume。",
    f"- 控制器從{local(state['created_utc'])}至{local(state['ended_utc'])}，牆鐘{wall:.6f}秒，另含Seed間核對／排程間隙，不與attempt相加。",
    f"- 已存budget／FINAL_RESULTS的45完整Epoch區段合計{final['budget']['used_epoch_seconds']:.6f}秒；各result.elapsed_seconds合計{result_time:.6f}秒；metrics.epoch_seconds合計{totals['epoch_seconds']:.6f}秒。三者是不同計時邊界、彼此包含，不相加，也不改寫成同一值。", '']
lines += table(['Seed', '訓練', '評估', '存檔', 'metrics整輪', '資料等待（訓練內）', '批次處理（訓練內）'],
               time_rows + [['合計'] + [f'{totals[k]:.6f}' for k in totals]])
lines += ['', '訓練內的資料等待含iterator/tqdm開銷，批次處理含原loss同步；兩者不是額外耗時，不再加至train_seconds。整輪還有日誌／fsync／記帳等邊界差，分項和不必逐位元等於整輪。',
    f"原父失敗attempt另列{final['prior_failed_attempt_seconds']:.6f}秒，原未完成Epoch區段13.761452秒包含其中、不再加一次；新成功attempt＋原失敗attempt合計{final['total_attempt_seconds_including_parent_failure']:.6f}秒。原失敗不是新的完整Epoch成果。",
    f"原失敗根目錄：`{parent}`，Run ID d87cb2eef21d47fc8a408aa16b70e641仍failed、0完整Epoch、無Checkpoint；STOP、來源gate、日誌與attempt／budget全部保留，不改寫或清零。", '',
    '### 程序／GPU釋放與後續交接', '',
    f"{resource['at']}唯讀CIM核對：本輪controller／三Seed trainer及其worker父鏈無存活匹配，歷史自身PID亦不在；未停止任何程序。RTX5070快照：GPU使用7%，1814/12227MiB已用、10130MiB空閒；本輪Python訓練佔用已釋放，桌面程式仍可使用GPU，不把全機用量必須為0當條件。",
    '仍有兩個顯式CPU API Python程序（PID15544／21688），未停止或更改F服務。nvidia-smi在Windows WDDM下多數每程序顯存顯示N/A且部分系統程序權限不足，不能用此聲稱所有程序顯存皆為0；程序退出＋總體顯存快照支持本輪訓練GPU資源已釋放。',
    f"實測metadata收據：`{B / 'CLOSEOUT_RESOURCES_20261025_v1.json'}`；檔案／既有身分／計帳核對：`{B / 'CLOSEOUT_CHECKS_20261025_v1.json'}`。",
    '下一步：交C依固定EVALUATION_CONTRACT整理候選減同Seed原512之完整指標、疾病TP/N/Recall、合併MEL與既存流向；224/320僅歷史次要參考。交D依既定v2／補充／v2.1規則判讀。B不作採納、不算新配對結果、不換網站模型；本段不是任何新訓練／推論／Test／新候選的授權。',
    '本次只追加本README及既有C_HANDOFF必要入口，另保存小型結案metadata／讀取腳本；未改共用研究索引、正式設定／來源／權重、網站或Windows，未啟動新實驗／通知其他Thread。結案後停止。', '',
    '實際工作目錄／環境及結案文件命令：', '', '```powershell', "Set-Location 'D:\\SkinDetect_base'",
    "& '.\\.venv-skindetect-recovery-20261023\\Scripts\\python.exe' -B -X utf8 'recovery_20261023\\B_training\\alpha025_retry1_20261024_v1\\closeout_20261025_v1.py'", '```',
    '資源快照另以PowerShell Get-CimInstance Win32_Process（僅metadata）及`nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,memory.free --format=csv,noheader,nounits`、`nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits`取得；未呼叫模型或benchmark。']

handoff = ['', MARKER, '## B正式結案交接｜2026-10-25', '',
    '**訓練完成，尚未判定採納。** Seed1=13/最佳8、Seed2=20/最佳15、Seed3=12/最佳5；45完整Epoch，均early_stopping、獨立新初始化、無Resume／Test。', '',
    f"- B完整結案（Run ID／既有指標／生效配方與執行差異／每Seed全路徑／耗時／GPU釋放）：`{B / 'README.md'}`末尾B-ALPHA025-CLOSEOUT:20261025:v1。",
    f"- 正式結果與完整疾病數值：`{ROOT / 'FINAL_RESULTS.json'}`，`rows[].metrics.values/diseases/validation_by_source/merged_confusion_matrix`；best選定輪請用各result.best。",
    f"- 唯一科學變因／核定配置：`{CONFIG / 'v2in_res512_alpha025.json'}`；`{CONFIG / 'DIFF_AND_SOURCES.json'}`；固定評估契約：`{CONFIG / 'EVALUATION_CONTRACT.json'}`。",
    f"- 所有Seed結果根目錄：`{ROOT / 'runs/v2in_res512_alpha025'}`；各regularized_seed1/2/3有result.json、run_inputs.json、metrics_*.jsonl、best.pt、雙代完整checkpoints/index.json及.pt。",
    f"- 原512同Seed對照根目錄：`{BASE}`（regularized_seed1/2/3的result.json及run_inputs.json；精確路徑亦在EVALUATION_CONTRACT.comparators）。",
    f"- 實際指令／失敗保留與資源紀錄：`{ROOT / 'state.json'}`、`{ROOT / 'attempts'}`、`{ROOT / 'budget'}`、`{ROOT / 'resource_samples.jsonl'}`、`{ROOT / 'EXECUTION_GATE.json'}`。",
    f"- 原失敗Run／STOP保留：`{parent}`。新成功attempt16968.875167秒、原失敗24.779381秒分列；包含區段不再重複加總。",
    f"- B程序／GPU已釋放，F CPU API未動；唯讀收據：`{B / 'CLOSEOUT_RESOURCES_20261025_v1.json'}`。",
    '- C下一步：按固定同Seed差值／mean及sampleSD(ddof=1)／完整疾病與來源保護整理，不重選Epoch、不推論、不讀Test；PAD無支持DF/VASC列N/A；無逐張配對資料不作修正／新增病例宣稱。',
    f"- D下一步：依`{PROJECT / 'recovery_20261023/D_v2_analysis/resolution_decision_20261024_v1/DECISION.md'}`的v2／補充／v2.1判讀；訓練完成不等於採納，未授權網站換模或新實驗。",
    '- 本文件補齊交接入口，不發跨Thread訊息；C/D的後續執行與分工依各自適用授權。']

checks = dict(at=now, formal_completed=True, runs=3, completed_epochs=45, missing_artifacts=missing,
    each_seed_has_two_checkpoint_files=True, existing_record_identity_checks=identity_checks,
    scientific_training_diff=diff, new_attempt_seconds=final['total_attempt_seconds_including_initialization_and_failures'],
    parent_failed_attempt_seconds=final['prior_failed_attempt_seconds'], parent_STOP_preserved=True,
    saved_metric_timing_totals=totals, budget_epoch_seconds=final['budget']['used_epoch_seconds'],
    own_process_matches=[], test_used=False, model_or_checkpoint_loaded=False, large_weights_hashed=False,
    quality_metrics_recomputed=False, adopted=False)
(B / 'CLOSEOUT_CHECKS_20261025_v1.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for path, addition in ((B / 'README.md', lines), (ROOT / 'C_HANDOFF.md', handoff)):
    original = path.read_bytes()
    if MARKER not in original.decode('utf-8-sig'):
        with path.open('a', encoding='utf-8') as stream:
            stream.write('\n'.join(addition) + '\n')
        assert path.read_bytes().startswith(original), 'Append-only preservation failed'
print(json.dumps(dict(status='B_closeout_appended', completed_runs=3, epochs=45,
                     README=str(B / 'README.md'), C_HANDOFF=str(ROOT / 'C_HANDOFF.md'),
                     missing=missing), ensure_ascii=False))
