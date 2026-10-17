const state = {
  variant: ["A", "B", "C"].includes(new URLSearchParams(location.search).get("variant")) ? new URLSearchParams(location.search).get("variant") : "A",
  config: null,
  models: [],
  siteModel: null,
  selectedModel: "mixed_convnext",
  imageDataUrl: "",
  imageName: "",
  result: null,
  history: [],
  experimentLibrary: null,
  experimentStage: "全部",
  includeHeatmap: true,
  includeSite: false,
  experimentTag: "UI_manual_test",
  manualSite: "",
  imageWidth: 0,
  imageHeight: 0,
  imageBytes: 0,
  fileReadId: 0,
  libraryError: "",
  busy: false,
  error: "",
};

const variantNames = { A: "實驗工作台", B: "單張檢測流程", C: "研究審查台" };

async function apiJson(url, options) {
  let response;
  try { response = await fetch(url, options); }
  catch { throw new Error("無法連線到本機服務，請確認啟動 UI 的視窗仍在執行。"); }
  let result;
  try { result = await response.json(); }
  catch { throw new Error(`服務回傳非預期內容（HTTP ${response.status}）。`); }
  if (!response.ok) throw new Error(result.error || `操作失敗（HTTP ${response.status}）。`);
  return result;
}

async function bootstrap() {
  const [config, models] = await Promise.all([apiJson("/api/config"), apiJson("/api/models")]);
  state.config = config;
  state.models = models.models;
  state.siteModel = models.site_model;
  const [historyResult, libraryResult] = await Promise.allSettled([apiJson("/api/history"), apiJson("/api/experiments")]);
  state.history = historyResult.status === "fulfilled" ? historyResult.value : [];
  state.experimentLibrary = libraryResult.status === "fulfilled" ? libraryResult.value : null;
  state.libraryError = libraryResult.status === "rejected" ? libraryResult.reason.message : "";
  state.selectedModel = models.default_model || state.selectedModel;
  if (!state.models.find(model => model.id === state.selectedModel && model.available)) {
    state.selectedModel = state.models.find(model => model.kind === "real" && model.available)?.id || "demo";
  }
  render();
  window.refreshTrainingStatus?.();
}

function shell(content, className) {
  return `
    <div class="shell ${className}">
      <header class="topbar">
        <div class="brand">
          <div class="brand-mark">SD</div>
          <div><h1>SkinDetect</h1><p>皮膚病影像研究與推論介面</p></div>
        </div>
        <div class="status-row">
          <span class="badge ok">本機服務已連線</span>
          <span class="badge">${state.models.filter(model => model.kind === "real" && model.available).length} 個可用模型</span>
          <span class="badge">${state.experimentLibrary?.experiment_count || 0} 組實驗</span>
          <span class="badge">${variantNames[state.variant]}</span>
        </div>
      </header>
      <nav class="workspace-nav" aria-label="功能導覽">
        <a href="#inference-workspace">影像推論</a><a href="#training-console-host">模型訓練</a>
        <a href="#experiment-library">實驗紀錄</a><a href="/manual" target="_blank" rel="noopener">使用手冊 ↗</a>
      </nav>
      <div class="notice">研究用途。輸出是在模型已學習類別中的相對機率，不等於確診機率；未學習的疾病或正常皮膚也可能被分到既有類別。</div>
      <section id="training-console-host">${window.trainingPanel ? window.trainingPanel() : ""}</section>
      <section id="inference-workspace">${content}</section>
      ${experimentLibrary()}
    </div>`;
}

function modelOptions() {
  const groups = [...new Set(state.models.map(model => model.group || "其他"))];
  return groups.map(group => `<optgroup label="${escapeHtml(group)}">${state.models.filter(model => (model.group || "其他") === group).map(model =>
    `<option value="${escapeHtml(model.id)}" ${model.id === state.selectedModel ? "selected" : ""} ${model.available ? "" : "disabled"}>${escapeHtml(model.name)}${model.available ? "" : "（檔案不存在或不支援）"}</option>`
  ).join("")}</optgroup>`).join("");
}

function modelDescription() {
  const model = state.models.find(item => item.id === state.selectedModel);
  if (!model) return "";
  if (model.kind === "demo") return `<p class="mode-notice">目前是展示模式：數值為假資料，不代表模型判斷。</p>`;
  return `<p class="model-description">${escapeHtml(model.name)}<br>${escapeHtml(model.group)} · ${escapeHtml(model.architecture)} · 輸入 ${model.image_size} × ${model.image_size} · ${model.class_count || 7} 類<br>${selectedModelSupportsHeatmap() ? "支援 Grad-CAM" : "無空間卷積特徵，不支援 Grad-CAM"}</p>`;
}

function selectedModelSupportsHeatmap() {
  const model = state.models.find(item => item.id === state.selectedModel);
  return Boolean(model && model.kind === "real" && model.architecture !== "mlp");
}

function controls(compact = false) {
  const heatmapSupported = selectedModelSupportsHeatmap();
  return `
    <div class="${compact ? "compact-controls" : ""}">
      <div class="field"><label for="model-select">疾病模型</label><select id="model-select" ${state.busy ? "disabled" : ""}>${modelOptions()}</select>${modelDescription()}</div>
      <div class="field"><label for="experiment-tag">實驗標記</label><input id="experiment-tag" value="${escapeHtml(state.experimentTag)}" maxlength="200" placeholder="例如 v2_external_check"></div>
      <div class="field"><label for="manual-site">拍攝部位（人工紀錄，可選）</label>
        <select id="manual-site">
          <option value="">未提供</option><option>頭頸</option><option>軀幹</option>
          <option>上肢</option><option>下肢</option><option>手／足</option>
        </select>
      </div>
    </div>
    <label class="check-row">
      <input id="include-site" type="checkbox" ${state.includeSite && state.siteModel?.available ? "checked" : ""} ${state.siteModel?.available && !state.busy ? "" : "disabled"}>
      同時輸出探索性 DensePose 部位預測
    </label>
    <p class="small muted">人工部位只寫入紀錄；勾選部位預測是額外輸出，不會改變疾病模型。</p>
    <label class="check-row heatmap-control">
      <input id="include-heatmap" type="checkbox" ${state.includeHeatmap && heatmapSupported ? "checked" : ""} ${heatmapSupported ? "" : "disabled"}>
      產生最高機率疾病的 Grad-CAM 熱力圖
    </label>
    <button id="run-button" class="primary" ${state.busy || !state.imageDataUrl ? "disabled" : ""}>
      ${state.busy ? "模型載入／推論中…" : "執行推論"}
    </button>
    ${state.error ? `<p class="error">${escapeHtml(state.error)}</p>` : ""}
  `;
}

function uploadArea() {
  if (state.imageDataUrl) {
    return `<label class="dropzone upload-label" id="dropzone" tabindex="0" aria-label="更換輸入影像">
      <img src="${state.imageDataUrl}" alt="待推論影像">
      <input id="file-input" type="file" accept="image/jpeg,image/png,image/webp" ${state.busy ? "disabled" : ""}>
    </label>
    <p class="small muted">${escapeHtml(state.imageName)} · ${state.imageWidth} × ${state.imageHeight} · ${(state.imageBytes / 1024 / 1024).toFixed(2)} MB<br>點擊圖片可更換</p>`;
  }
  return `<label class="dropzone upload-label" id="dropzone" tabindex="0" aria-label="選擇輸入影像">
    <div><div class="upload-icon">＋</div><strong>選擇或拖放皮膚影像</strong><p class="small muted">JPG、PNG、WEBP；單張最多 20 MB</p></div>
    <input id="file-input" type="file" accept="image/jpeg,image/png,image/webp">
  </label>`;
}

function probabilityBars(items, className = "") {
  return `<div class="bars ${className}">${items.map(item => `
    <div class="bar-row">
      <span title="模型內部標籤：${escapeHtml(item.code)}">${escapeHtml(item.label)}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${(item.probability * 100).toFixed(1)}%"></div></div>
      <strong>${(item.probability * 100).toFixed(1)}%</strong>
    </div>`).join("")}</div>`;
}

function heatmapPanel() {
  const heatmap = state.result?.heatmap;
  if (!heatmap?.requested) return "";
  if (!heatmap.available) {
    return `<div class="heatmap-unavailable"><strong>熱力圖未產生</strong><span>${escapeHtml(heatmap.notice || "此模型不支援空間熱力圖。")}</span></div>`;
  }
  return `
    <hr class="section-rule">
    <section class="heatmap-section">
      <div class="heatmap-heading">
        <div><div class="prediction-code">模型注意區域</div><h3>${escapeHtml(heatmap.target_class_label)}</h3></div>
        <span class="badge">${escapeHtml(heatmap.method)}</span>
      </div>
      <figure class="heatmap-figure">
        <img src="${escapeHtml(heatmap.overlay_data_url)}" alt="${escapeHtml(heatmap.target_class_label)}的 Grad-CAM 熱力圖">
        <figcaption>
          <div class="heatmap-legend"><span>影響較低</span><i></i><span>影響較高</span></div>
          <p>${escapeHtml(heatmap.notice)}</p>
          <p>計算層：${escapeHtml((heatmap.layers || []).join("、"))}</p>
        </figcaption>
      </figure>
    </section>`;
}

function resultPanel() {
  if (!state.result) {
    return `<div class="result-empty"><div><strong>尚未執行推論</strong><p>上傳影像並選擇模型後，結果會顯示在這裡。</p></div></div>`;
  }
  const top = state.result.disease[0];
  return `
    ${state.result.model_id === "demo" ? `<p class="mode-notice">展示模式結果（假資料）</p>` : ""}
    ${state.result.model_id !== state.selectedModel ? `<p class="mode-notice">下方保留上次模型的結果；按「執行推論」取得目前所選模型的輸出。</p>` : ""}
    <div class="prediction-head">
      <div><div class="prediction-code">最高機率類別</div><div class="prediction-name">${escapeHtml(top.label)}</div></div>
      <div class="confidence">${(top.probability * 100).toFixed(1)}%</div>
    </div>
    ${probabilityBars(state.result.disease)}
    <p class="small muted">各類機率合計約 100%；最高機率只表示模型在已知類別中的偏好。</p>
    ${heatmapPanel()}
    ${state.result.site.length ? `
      <hr class="section-rule"><h3 class="panel-title">探索性部位輸出</h3>
      ${probabilityBars(state.result.site, "site")}
      <p class="small muted">${escapeHtml(state.result.site_output_notice)}</p>` : ""}
    <hr class="section-rule">
    <div class="meta-grid">
      <div class="meta-item">模型<strong>${escapeHtml(state.result.model_label)}</strong></div>
      <div class="meta-item">耗時<strong>${state.result.elapsed_ms} ms</strong></div>
      <div class="meta-item">裝置<strong>${escapeHtml(state.result.device)}</strong></div>
      <div class="meta-item">實驗標記<strong>${escapeHtml(state.result.experiment_tag)}</strong></div>
      <div class="meta-item">拍攝部位（人工）<strong>${escapeHtml(state.result.manual_site || "未提供")}</strong></div>
      <div class="meta-item">輸入影像<strong>${escapeHtml(state.result.image_name || state.imageName)}<br>${state.result.image.width} × ${state.result.image.height}</strong></div>
    </div>`;
}

function historyPanel() {
  if (!state.history.length) return `<p class="small muted">本次啟動尚無推論紀錄。</p>`;
  return `<div class="history-list">${state.history.slice(0, 8).map(item => `
    <div class="history-item">
      <strong>${escapeHtml(item.experiment_tag)} · ${escapeHtml(item.top_disease.label || item.top_disease.code)}</strong>
      <span>${escapeHtml(item.model_label)}${item.model_id === "demo" && !item.model_label.includes("假資料") ? "（假資料）" : ""}</span><br>
      ${(item.top_disease.probability * 100).toFixed(1)}% · ${item.elapsed_ms} ms · ${escapeHtml(new Date(item.created_at).toLocaleString("zh-TW"))}
    </div>`).join("")}</div>`;
}

function variantA() {
  return shell(`
    <section class="workspace">
      <aside class="panel controls"><h2 class="panel-title">實驗設定</h2>${controls()}</aside>
      <section class="panel preview"><h2 class="panel-title">輸入影像</h2>${uploadArea()}</section>
      <section class="panel results"><h2 class="panel-title">模型輸出</h2>${resultPanel()}</section>
    </section>
    <section class="panel history"><h2 class="panel-title">本次啟動紀錄</h2>${historyPanel()}</section>
  `, "variant-a");
}

function variantB() {
  return shell(`
    <div class="flow">
      <div class="hero"><h2>上傳一張影像，查看模型輸出</h2><p class="muted">簡化成未來一般使用者最容易理解的單張流程。</p></div>
      <section class="panel step"><div class="step-number">步驟 01</div><h3>選擇影像</h3>${uploadArea()}</section>
      <section class="panel step"><div class="step-number">步驟 02</div><h3>確認推論設定</h3>${controls(true)}</section>
      <section class="panel step"><div class="step-number">步驟 03</div><h3>查看結果</h3><div class="results-layout">
        <div>${resultPanel()}</div><div><h3 class="panel-title">本次啟動紀錄</h3>${historyPanel()}</div>
      </div></section>
    </div>
  `, "variant-b");
}

function variantC() {
  return shell(`
    <div class="console">
      <aside class="rail"><h2 class="panel-title">推論佇列</h2>${historyPanel()}</aside>
      <section class="canvas"><h2 class="panel-title">影像審查區</h2>${uploadArea()}
        <div class="run-strip">
          <div class="field"><label for="model-select">模型</label><select id="model-select" ${state.busy ? "disabled" : ""}>${modelOptions()}</select>${modelDescription()}</div>
          <div class="field"><label for="experiment-tag">實驗標記</label><input id="experiment-tag" value="${escapeHtml(state.experimentTag)}" maxlength="200"></div>
          <button id="run-button" class="primary" ${state.busy || !state.imageDataUrl ? "disabled" : ""}>${state.busy ? "推論中…" : "執行"}</button>
        </div>
        <div class="field"><label>拍攝部位（人工紀錄）</label><select id="manual-site"><option value="">未提供</option><option>頭頸</option><option>軀幹</option><option>上肢</option><option>下肢</option><option>手／足</option></select></div>
        <label class="check-row"><input id="include-site" type="checkbox" ${state.includeSite && state.siteModel?.available ? "checked" : ""} ${state.siteModel?.available && !state.busy ? "" : "disabled"}>輸出探索性部位預測</label>
        <p class="small muted">人工部位只記錄；探索性部位輸出不會改變疾病模型。</p>
        <label class="check-row heatmap-control"><input id="include-heatmap" type="checkbox" ${state.includeHeatmap && selectedModelSupportsHeatmap() ? "checked" : ""} ${selectedModelSupportsHeatmap() ? "" : "disabled"}>產生 Grad-CAM 熱力圖</label>
        ${state.error ? `<p class="error">${escapeHtml(state.error)}</p>` : ""}
      </section>
      <aside class="inspector"><h2 class="panel-title">輸出檢查器</h2>${resultPanel()}</aside>
    </div>
  `, "variant-c");
}

function render() {
  captureInputs();
  window.captureTrainingUI?.();
  const root = document.querySelector("#app");
  root.innerHTML = state.variant === "B" ? variantB() : state.variant === "C" ? variantC() : variantA();
  renderSwitcher();
  bindInteractions();
  const manual = document.querySelector("#manual-site");
  if (manual) manual.value = state.manualSite;
}

function captureInputs() {
  const tag = document.querySelector("#experiment-tag");
  const site = document.querySelector("#manual-site");
  const includeSite = document.querySelector("#include-site");
  if (tag) state.experimentTag = tag.value;
  if (site) state.manualSite = site.value;
  if (includeSite && !includeSite.disabled) state.includeSite = includeSite.checked;
}

function renderSwitcher() {
  const switcher = document.querySelector("#prototype-switcher");
  if (!state.config?.prototype_switcher) {
    switcher.hidden = true;
    return;
  }
  switcher.hidden = false;
  switcher.innerHTML = `
    <button id="variant-prev" aria-label="上一個版型">←</button>
    <span>${state.variant} — ${variantNames[state.variant]}</span>
    <button id="variant-next" aria-label="下一個版型">→</button>`;
  document.querySelector("#variant-prev").onclick = () => changeVariant(-1);
  document.querySelector("#variant-next").onclick = () => changeVariant(1);
}

function changeVariant(direction) {
  const variants = ["A", "B", "C"];
  const current = variants.indexOf(state.variant);
  state.variant = variants[(current + direction + variants.length) % variants.length];
  const url = new URL(location.href);
  url.searchParams.set("variant", state.variant);
  history.replaceState({}, "", url);
  render();
}

function bindInteractions() {
  bindExperimentLibrary();
  window.bindTrainingPanel?.();
  const fileInput = document.querySelector("#file-input");
  const dropzone = document.querySelector("#dropzone");
  if (fileInput) fileInput.onchange = event => useFile(event.target.files[0]);
  if (dropzone) {
    dropzone.onkeydown = event => {
      if (["Enter", " "].includes(event.key)) { event.preventDefault(); fileInput?.click(); }
    };
    dropzone.ondragover = event => { event.preventDefault(); dropzone.classList.add("dragging"); };
    dropzone.ondragleave = () => dropzone.classList.remove("dragging");
    dropzone.ondrop = event => {
      event.preventDefault(); dropzone.classList.remove("dragging"); useFile(event.dataTransfer.files[0]);
    };
  }
  const modelSelect = document.querySelector("#model-select");
  if (modelSelect) modelSelect.onchange = event => {
    state.selectedModel = event.target.value;
    render();
  };
  const heatmapToggle = document.querySelector("#include-heatmap");
  if (heatmapToggle) heatmapToggle.onchange = event => { state.includeHeatmap = event.target.checked; };
  const runButton = document.querySelector("#run-button");
  if (runButton) runButton.onclick = runInference;
}

function useFile(file) {
  if (!file || state.busy) return;
  const readId = ++state.fileReadId;
  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
    state.error = "請選擇 JPG、PNG 或 WEBP 影像。";
    render();
    return;
  }
  if (file.size > 20 * 1024 * 1024) {
    state.error = "影像超過 20 MB，請選擇較小的檔案。";
    render();
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    const preview = new Image();
    preview.onload = () => {
      if (readId !== state.fileReadId) return;
      if (preview.naturalWidth * preview.naturalHeight > 64_000_000) {
        state.error = "影像超過 6,400 萬像素，請先縮小尺寸。"; render(); return;
      }
      state.imageDataUrl = reader.result;
      state.imageName = file.name;
      state.imageWidth = preview.naturalWidth; state.imageHeight = preview.naturalHeight;
      state.imageBytes = file.size;
      state.result = null; state.error = ""; render();
    };
    preview.onerror = () => {
      if (readId !== state.fileReadId) return;
      state.error = "無法讀取影像，檔案可能已損毀。"; render();
    };
    preview.src = reader.result;
  };
  reader.onerror = () => { state.error = "檔案讀取失敗，請重新選擇。"; render(); };
  reader.readAsDataURL(file);
}

async function runInference() {
  if (state.busy || !state.imageDataUrl) return;
  captureInputs();
  state.busy = true;
  state.error = "";
  state.selectedModel = document.querySelector("#model-select")?.value || state.selectedModel;
  const payload = {
    image_data_url: state.imageDataUrl,
    image_name: state.imageName,
    model_id: state.selectedModel,
    experiment_tag: document.querySelector("#experiment-tag")?.value || "",
    manual_site: document.querySelector("#manual-site")?.value || "",
    include_site: Boolean(document.querySelector("#include-site")?.checked),
    include_heatmap: Boolean(document.querySelector("#include-heatmap")?.checked),
  };
  render();
  try {
    const result = await apiJson("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.result = result;
    try { state.history = await apiJson("/api/history"); }
    catch { state.error = "推論已完成，但紀錄刷新失敗。"; }
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

document.addEventListener("keydown", event => {
  if (!state.config?.prototype_switcher) return;
  if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
  const target = event.target;
  if (target.matches("input, textarea, select, [contenteditable]")) return;
  changeVariant(event.key === "ArrowLeft" ? -1 : 1);
});

function initialize() {
  document.querySelector("#app").innerHTML = `<div class="startup-panel"><h1>SkinDetect</h1><p>正在讀取模型與實驗紀錄…</p></div>`;
  bootstrap().catch(error => {
    document.querySelector("#app").innerHTML = `<div class="startup-panel"><h1>SkinDetect</h1><p class="error">UI 初始化失敗：${escapeHtml(error.message)}</p><button class="primary" id="retry-bootstrap">重新連線</button><p>啟動指令：powershell -NoProfile -ExecutionPolicy Bypass -File ".\\start_ui.ps1"</p></div>`;
    document.querySelector("#retry-bootstrap").onclick = initialize;
  });
}
initialize();
