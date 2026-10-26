"""Create only the explicitly authorized Tiny224 ablation batch artifacts."""
from pathlib import Path
import copy
import json
import sys

OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[2]
AREA = PROJECT/'資料治理與泛化修復'
sys.path.insert(0, str(AREA/'scripts'))
import v2_tiny224_ablation_contract as c
from training_state import atomic_json, file_sha256

authorization = '''# 2026-10-26 使用者直接授權：Tiny224兩組單變因各三Seed

來源：本B對話使用者完整直接指令；授權必要最小實作／驗證、通過後依序正式訓練，不含額外候選或無限重試。
固定單GPU：A ReLU-only Seeds1→2→3，再B Stage-Dropout-only Seeds1→2→3；僅Tiny224 RGB。
A僅18個Block GELU→非inplace ReLU，無Stage Dropout；B保留全部原GELU、四完整Stage輸出後一般元素Dropout .1（Stage4於原global average pool前），eval關閉。Block/head Dropout0、DropPath0、GRN／原深寬／卷積／殘差／pooling不變，不加pooling。
原224基準配置：資料治理與泛化修復/configs/five_model_baseline_20261019_v1/convnextv2_tiny_imagenet.json；其三Seed結果直接引用、不重訓。
原governed_18979_20261018_v1：Train18919／原Monitor1500／Validation3611／七類順序／完整Train和Validation前處理／原有放回抽樣與Seed策略不變，封存Test不讀。
原本機釘選FCMAE ImageNet1K source／revision／SHA不變，不下載。每Run新RunID、新七類head、空AdamW／新scheduler／scaler，原預訓練backbone獨立初始化；不接512、任何best/last或前檢模型。
micro32×累積2＝effective64；AdamW LR1e-4 WD.05 LayerDecay1 alpha.5 LS.1 MixUp.2 RE.15 clip norm1 AMP；Workers4 prefetch4 persistent；全部training dict與原224完全相同。
Min12 Max30 Patience5 MinDelta0、CosineTmax30 eta_min1e-6；每輪完整評估、首次最高Validation Robust選best。
最多6新Run／180完整Epoch、無時間硬上限；各Job只允許一次新初始化，不因前兩Seed分數取消第三個，不追加研究。
沿共用trainer／原train_epoch loss÷累積、AMP／clip／optimizer、CheckpointStore；不新增AMP前梯度強停、分數／資源門檻或執行中強停。真正CUDA／原Loss非有限／Checkpoint／契約等異常保存即停，無自動重試／Resume／換batch或調參。
只補新候選CPU架構／載入與原流程GPU更新必要驗證；先用隔離微型CPU資料覆蓋六Run最長正式路徑的Checkpoint／best／雙代／原子替換讀回，舊已適用保護直接引用。
保留原啟動資源檢查；每15秒真實MONITOR，保存完整命令／版本／有效設定／run_inputs／metrics／best／雙代Checkpoint／失敗與計帳。
兩組各自與原224同Seed比較Robust／Accuracy／MacroF1／來源BA／疾病TP/N/Recall；各組三Seed齊全後mean／sampleSD(ddof1)與配對差，交總控供D，不擅加採納門檻／換網站。
512 restart3仍paused、STOP保留、Base不啟動；不安裝下載、不改Windows、不干擾F、不聯絡其他Thread；共用索引由總控更新。
'''


def main():
    auth = c.CONFIG/'AUTHORIZATION.md'
    if auth.exists(): raise RuntimeError('Preparation already consumed; existing files retained')
    auth.write_text(authorization, encoding='utf-8')
    original = c.read(c.BASE_CONFIG)
    differences = {}
    for candidate in c.CANDIDATES:
        config = c.expected_config(candidate)
        assert config['training'] == original['training']
        differences[candidate] = {key: dict(original=original.get(key), candidate=value)
            for key, value in config.items() if value != original.get(key)}
        assert set(differences[candidate]) == {'pipeline_id','experiment','architecture_modification','optimization'}
        atomic_json(c.CONFIG/(candidate+'.json'), config)
    atomic_json(c.CONFIG/'CONFIG_DIFF.json', differences)
    atomic_json(c.CONFIG/'COMPARISON_CONTRACT.json', dict(version=c.VERSION,
        scientific_groups={'relu':'only18BlockGELU_to_noninplaceReLU',
                           'dropout':'only4completeStage_elementwiseDropout0.1_originalGELU'},
        references=str(c.BASE_RESULTS), seeds=[1,2,3], paired_same_seed=True,
        original_training=original['training'], original_class_names=original['class_names'],
        data_version=original['formal_suite']['manifest_release'], train=18919, monitor=1500, validation=3611,
        pinned_weights=original['experiment']['weights'], selection='first strictly highest full Validation Robust',
        metrics=['robust','accuracy','macro_f1','all_source_balanced_accuracy','all_supported_source_disease_TP_support_recall'],
        unsupported_PAD_DF_VASC='N/A, never zero-filled into supported-disease comparison',
        aggregation='each group separately after its 3 completed Seeds; mean/sampleSD(ddof=1), paired deltas',
        incomplete_seeds_not_complete_three_seed_evidence=True, no_new_acceptance_thresholds=True,
        adoption='master to D; no automatic model adoption', test_used=False, limits=c.LIMITS))
    old = (OUT/'before/run_v2_relu_dropout.py').read_text(encoding='utf-8-sig')
    replacements = {
        'import v2_relu_dropout_contract as c':'import v2_tiny224_ablation_contract as c',
        'Serial fresh-only three-job followup; original trainer and passive monitoring.':'Serial fresh-only six-job Tiny224 ablation; original trainer and passive monitoring.',
        'Tiny／Base512 ReLU＋Stage Dropout：即時監控':'Tiny224 單變因比較：即時監控',
        '單GPU固定Tiny Seed1→2→3，再Base Seed1→2→3。':'單GPU固定ReLU-only Seed1→2→3，再Stage-Dropout-only Seed1→2→3。',
        '512 RGB／Train18919、Monitor1500、Validation3611':'224 RGB／Train18919、Monitor1500、Validation3611',
        'Tiny8×8／Base2×32／effective64':'兩組32×2／effective64',
        '只改Block ReLU＋四Stage後元素Dropout=.1':'A僅18Block ReLU；B僅四Stage後元素Dropout=.1並保留原GELU',
        '各模型新三Seed對原架構同Seed':'兩組各自三Seed對原224同Seed',
        'v2_tiny_base512_relu_stage_dropout_20261026_v1':'v2_tiny224_activation_dropout_ablation_20261026_v1',
        "for size in ('tiny','base'):":"for size in ('relu','dropout'):",
        "state['references'][f'original_{size}_seed{seed}']":"state['references'][f'original_224_seed{seed}']",
        'combination_not_separate_causal_effects=True':'single_variable_per_group=True',
        "references={f'original_{size}_seed{seed}':reference(c.reference_folder(size,seed),c.MICRO[size],64//c.MICRO[size]) for size in ('tiny','base') for seed in (1,2,3)}":
        "references={f'original_224_seed{seed}':reference(c.reference_folder('224',seed),32,2) for seed in (1,2,3)}",
    }
    for before, after in replacements.items():
        if before not in old: raise RuntimeError('Controller adapter anchor missing: '+before)
        old = old.replace(before, after)
    begin = old.index('def finalize(state):'); end = old.index('\ndef run_job(', begin)
    finalizer = '''def finalize(state):
    attempts=[c.read(p) for p in (ROOT/'attempts').glob('attempt_*.json')]
    atomic_json(ROOT/'FINAL_RESULTS.json',dict(version=c.VERSION,status=state['status'],rows=state['runs'],references=state['references'],
        formal_complete_epochs=c.budget_summary()['completed_epoch_segments'],total_formal_attempt_seconds=sum(a.get('seconds',0) for a in attempts),
        failed_attempt_seconds=sum(a.get('seconds',0) for a in attempts if a['status']=='failed'),attempts=attempts,
        comparison_contract=str(c.CONFIG/'COMPARISON_CONTRACT.json'),relu_summary_exists=(ROOT/'RELU_COMPARISON.json').exists(),
        dropout_summary_exists=(ROOT/'DROPOUT_COMPARISON.json').exists(),automatic_model_adoption=False,test_used=False,
        original_model_seed_tasks=6,max_formal_starts=6,wall_clock_cap_seconds=None,
        accounting_note='This224 batch only; phase/epoch seconds are included in attempts, never added twice;512 and baseline costs excluded.'))
    (ROOT/'B_HANDOFF.md').write_text('本批原生狀態：'+state['status']+'。Tiny224 ReLU-only三Seed後Stage-Dropout-only三Seed，各組只一科學變因、其餘沿原224。RunID／完整最佳Epoch／停止與計帳見FINAL_RESULTS；各組三Seed齊全才有RELU_COMPARISON／DROPOUT_COMPARISON，對原224同Seedmean/sampleSD及來源疾病TP/N/Recall，交總控供D判讀，不自行採納。完整命令／有效配置／run_inputs／逐輪metrics／best與雙代Checkpoint保留；512維持paused與STOP，不啟Base。',encoding='utf-8')

'''
    old = old[:begin] + finalizer + old[end:]
    (c.AREA/'scripts/run_v2_tiny224_ablation.py').write_text(old, encoding='utf-8')
    atomic_json(OUT/'PREPARATION.json', dict(status='prepared_not_validated_not_launched',
        authorization_id=c.DISPATCH_TOKEN,version=c.VERSION,jobs=c.JOBS,limits=c.LIMITS,
        baseline_sha256=file_sha256(c.BASE_CONFIG),scientific_training_dict_unchanged=True))
    print('Two separate single-variable configs and finite controller prepared; not launched')


if __name__ == '__main__': main()
