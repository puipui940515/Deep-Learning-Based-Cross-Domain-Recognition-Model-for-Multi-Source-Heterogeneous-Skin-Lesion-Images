const trainingState = {
  current: null,
  history: [],
  capabilities: null,
  error: "",
  starting: false,
  expanded: false,
  refreshing: false,
  statusError: "",
  values: {
    mode: "smoke", epochs: 1, seed: 17, batch_size: 16,
    learning_rate: 0.0001, weight_decay: 0.05,
    label_smoothing: 0.1, mixup_alpha: 0.2,
    early_stopping_patience: 4,
  },
};

const trainingStatusNames = {
  starting: "準備中", running: "訓練中", stopping: "停止中",
  stopped: "已停止", completed: "已完成", failed: "失敗",
};

function trainingField(id, label, type, min, max, step) {
  return `<div class="field training-field"><label for="train-${id}">${label}</label>
    <input id="train-${id}" type="${type}" min="${min}" max="${max}" step="${step}" required value="${escapeHtml(trainingState.values[id])}"></div>`;
}

function trainingPanel() {
  const job = trainingState.current;
  const running = ["starting", "running", "stopping"].includes(job?.status);
  const capability = trainingState.capabilities;
  const progress = job?.progress || { epoch: 0, total_epochs: trainingState.values.epochs, percent: 0 };
  const logs = job?.log_lines?.length
    ? job.log_lines.map(line => escapeHtml(line)).join("\n")
    : "尚無訓練輸出。";
  return `<details class="training-console panel" ${trainingState.expanded ? "open" : ""}>
    <summary>
      <span><strong>模型訓練控制台</strong><small>透過欄位啟動固定訓練流程，不執行自由文字命令</small></span>
      <span class="training-summary-status ${job?.status || "idle"}">${job ? trainingStatusNames[job.status] || job.status : "尚未啟動"}</span>
    </summary>
    <div class="training-body">
      <div class="training-intro">
        <div><span>模型</span><strong>${escapeHtml(capability?.model || "載入中…")}</strong></div>
        <div><span>資料</span><strong>${escapeHtml(capability?.dataset || "載入中…")}</strong></div>
        <div><span>資料閘門</span><strong>${!capability ? "讀取中…" : capability.gate_passed ? `通過 · ${capability.clean_rows || "—"} 筆` : "未通過"}</strong></div>
      </div>
      <p class="small muted">固定流程：${escapeHtml(capability?.pipeline || "讀取中")}</p>
      <p class="training-scope">此入口是既有三來源、七分類訓練。上方疾病模型選單只控制推論；此處不會啟動 CP-005 或 NoiseFilter v2 多日排程。</p>
      ${capability && !capability.available ? `<p class="error">訓練入口尚未就緒，請檢查既有資料治理報告與訓練腳本。</p>` : ""}
      <fieldset class="training-grid" ${running || trainingState.starting ? "disabled" : ""}><legend class="visually-hidden">訓練參數</legend>
        <div class="field training-field"><label for="train-mode">執行模式</label>
          <select id="train-mode" ${running ? "disabled" : ""}>
            <option value="smoke" ${trainingState.values.mode === "smoke" ? "selected" : ""}>煙霧測試（最多 280 張訓練影像）</option>
            <option value="formal" ${trainingState.values.mode === "formal" ? "selected" : ""}>正式訓練（此流程的全部合格資料）</option>
          </select></div>
        ${trainingField("epochs", "訓練輪數 Epoch", "number", 1, 100, 1)}
        ${trainingField("seed", "隨機種子 Seed", "number", 0, 2147483647, 1)}
        ${trainingField("batch_size", "批次大小 Batch size", "number", 1, 64, 1)}
        ${trainingField("learning_rate", "學習率", "number", 0.000001, 0.01, 0.000001)}
        ${trainingField("weight_decay", "權重衰減", "number", 0, 0.5, 0.001)}
        ${trainingField("label_smoothing", "標籤平滑", "number", 0, 0.4, 0.01)}
        ${trainingField("mixup_alpha", "MixUp 強度", "number", 0, 1, 0.05)}
        ${trainingField("early_stopping_patience", "提早停止耐心值", "number", 1, 20, 1)}
      </fieldset>
      <div class="training-actions">
        <button id="training-start" class="primary" ${running || !capability?.available || trainingState.starting ? "disabled" : ""}>${trainingState.starting ? "正在建立任務…" : "開始訓練"}</button>
        <button id="training-stop" class="danger-button" ${running ? "" : "disabled"}>停止目前任務</button>
      </div>
      ${trainingState.error ? `<p class="error">${escapeHtml(trainingState.error)}</p>` : ""}
      ${trainingState.statusError ? `<p class="error">狀態刷新失敗：${escapeHtml(trainingState.statusError)}</p>` : ""}
      <div class="training-progress-head"><strong>${job ? `任務 ${escapeHtml(job.job_id)}` : "尚無任務"}</strong><span>${progress.epoch}/${progress.total_epochs} epoch</span></div>
      <div class="training-progress" role="progressbar" aria-label="已完成訓練輪數" aria-valuenow="${Math.round(progress.percent)}" aria-valuemin="0" aria-valuemax="100"><span style="width:${Math.max(0, Math.min(100, progress.percent))}%"></span></div>
      <div class="training-meta">
        <span>狀態：${job ? trainingStatusNames[job.status] || job.status : "尚未啟動"}</span>
        <span>輸出：${escapeHtml(job?.output_directory || "啟動後建立固定資料夾")}</span>
        ${job?.exit_code != null ? `<span>結束代碼：${job.exit_code}</span>` : ""}
      </div>
      <p class="small muted">進度依日誌中已完成的輪數估算；完整批次進度請看下方輸出。停止按鈕會終止程序，當輪未存檔進度可能失去。</p>
      <pre class="training-log" aria-live="polite">${logs}</pre>
    </div>
  </details>`;
}

function collectTrainingValues() {
  const integerFields = ["epochs", "seed", "batch_size", "early_stopping_patience"];
  const floatFields = ["learning_rate", "weight_decay", "label_smoothing", "mixup_alpha"];
  trainingState.values.mode = document.querySelector("#train-mode")?.value || trainingState.values.mode;
  integerFields.forEach(name => {
    const input = document.querySelector(`#train-${name}`);
    if (input) trainingState.values[name] = input.value;
  });
  floatFields.forEach(name => {
    const input = document.querySelector(`#train-${name}`);
    if (input) trainingState.values[name] = input.value;
  });
}

function captureTrainingUI() {
  collectTrainingValues();
  const panel = document.querySelector(".training-console");
  if (panel) trainingState.expanded = panel.open;
}

function renderTrainingPanelOnly() {
  const host = document.querySelector("#training-console-host");
  if (!host) return;
  captureTrainingUI();
  // Keep the active input intact while the user types; polling resumes rendering on blur.
  if (host.contains(document.activeElement) && document.activeElement.matches("input, select")) return;
  host.innerHTML = trainingPanel();
  bindTrainingPanel();
}

async function refreshTrainingStatus() {
  if (trainingState.refreshing) return;
  trainingState.refreshing = true;
  try {
    const response = await fetch("/api/training/status", { cache: "no-store" });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "無法讀取訓練狀態");
    trainingState.current = result.current;
    trainingState.history = result.history;
    trainingState.capabilities = result.capabilities;
    trainingState.statusError = "";
  } catch (error) {
    trainingState.statusError = error.message;
  } finally {
    trainingState.refreshing = false;
  }
  renderTrainingPanelOnly();
}

async function startTraining() {
  collectTrainingValues();
  const inputs = [...document.querySelectorAll("#training-console-host input")];
  if (inputs.some(input => !input.reportValidity())) return;
  const parameters = { mode: trainingState.values.mode };
  for (const [name, value] of Object.entries(trainingState.values)) {
    if (name !== "mode") parameters[name] = Number(value);
  }
  const formal = trainingState.values.mode === "formal";
  const message = formal
    ? `既有三來源七分類流程：全部合格資料，${parameters.epochs} 輪、seed ${parameters.seed}、batch ${parameters.batch_size}。確定開始？`
    : `既有三來源七分類流程：最多 280 張的煙霧測試，${parameters.epochs} 輪、seed ${parameters.seed}。確定開始？`;
  if (!window.confirm(message)) return;
  trainingState.starting = true;
  trainingState.error = "";
  renderTrainingPanelOnly();
  try {
    const response = await fetch("/api/training/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parameters),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "無法啟動訓練");
    trainingState.current = result;
  } catch (error) {
    trainingState.error = error.message;
  } finally {
    trainingState.starting = false;
    renderTrainingPanelOnly();
  }
}

async function stopTraining() {
  if (!window.confirm("確定停止目前訓練？已寫入的 checkpoint 與日誌會保留。")) return;
  try {
    const response = await fetch("/api/training/stop", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "無法停止訓練");
    trainingState.current = result;
    trainingState.error = "";
  } catch (error) {
    trainingState.error = error.message;
  }
  renderTrainingPanelOnly();
}

function bindTrainingPanel() {
  document.querySelectorAll("#training-console-host input, #training-console-host select").forEach(element => {
    element.oninput = collectTrainingValues;
    element.onchange = collectTrainingValues;
  });
  const panel = document.querySelector(".training-console");
  if (panel) panel.ontoggle = () => { trainingState.expanded = panel.open; };
  const start = document.querySelector("#training-start");
  const stop = document.querySelector("#training-stop");
  if (start) start.onclick = startTraining;
  if (stop) stop.onclick = stopTraining;
}

window.trainingPanel = trainingPanel;
window.bindTrainingPanel = bindTrainingPanel;
window.captureTrainingUI = captureTrainingUI;
window.refreshTrainingStatus = refreshTrainingStatus;
setInterval(refreshTrainingStatus, 2500);
