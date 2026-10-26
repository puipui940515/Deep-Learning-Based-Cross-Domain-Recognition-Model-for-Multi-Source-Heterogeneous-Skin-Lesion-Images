三Seed完成；原result/run_inputs/metrics/checkpoint及FINAL_RESULTS保留。請C依核定EVALUATION_CONTRACT整理同Seed原512差值，D判讀。B不作採納，不讀Test。

<!-- B-ALPHA025-CLOSEOUT:20261025:v1 -->
## B正式結案交接｜2026-10-25

**訓練完成，尚未判定採納。** Seed1=13/最佳8、Seed2=20/最佳15、Seed3=12/最佳5；45完整Epoch，均early_stopping、獨立新初始化、無Resume／Test。

- B完整結案（Run ID／既有指標／生效配方與執行差異／每Seed全路徑／耗時／GPU釋放）：`recovery_20261023\B_training\alpha025_retry1_20261024_v1\README.md`末尾B-ALPHA025-CLOSEOUT:20261025:v1。
- 正式結果與完整疾病數值：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\FINAL_RESULTS.json`，`rows[].metrics.values/diseases/validation_by_source/merged_confusion_matrix`；best選定輪請用各result.best。
- 唯一科學變因／核定配置：`資料治理與泛化修復\configs\v2_512_alpha025_20261024_v1\v2in_res512_alpha025.json`；`資料治理與泛化修復\configs\v2_512_alpha025_20261024_v1\DIFF_AND_SOURCES.json`；固定評估契約：`資料治理與泛化修復\configs\v2_512_alpha025_20261024_v1\EVALUATION_CONTRACT.json`。
- 所有Seed結果根目錄：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\runs\v2in_res512_alpha025`；各regularized_seed1/2/3有result.json、run_inputs.json、metrics_*.jsonl、best.pt、雙代完整checkpoints/index.json及.pt。
- 原512同Seed對照根目錄：`資料治理與泛化修復\results\v2_resolution_20261021_v1\runs\v2in_res512`（regularized_seed1/2/3的result.json及run_inputs.json；精確路徑亦在EVALUATION_CONTRACT.comparators）。
- 實際指令／失敗保留與資源紀錄：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\state.json`、`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\attempts`、`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\budget`、`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\resource_samples.jsonl`、`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\EXECUTION_GATE.json`。
- 原失敗Run／STOP保留：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1`。新成功attempt16968.875167秒、原失敗24.779381秒分列；包含區段不再重複加總。
- B程序／GPU已釋放，F CPU API未動；唯讀收據：`recovery_20261023\B_training\alpha025_retry1_20261024_v1\CLOSEOUT_RESOURCES_20261025_v1.json`。
- C下一步：按固定同Seed差值／mean及sampleSD(ddof=1)／完整疾病與來源保護整理，不重選Epoch、不推論、不讀Test；PAD無支持DF/VASC列N/A；無逐張配對資料不作修正／新增病例宣稱。
- D下一步：依`recovery_20261023\D_v2_analysis\resolution_decision_20261024_v1\DECISION.md`的v2／補充／v2.1判讀；訓練完成不等於採納，未授權網站換模或新實驗。
- 本文件補齊交接入口，不發跨Thread訊息；C/D的後續執行與分工依各自適用授權。
