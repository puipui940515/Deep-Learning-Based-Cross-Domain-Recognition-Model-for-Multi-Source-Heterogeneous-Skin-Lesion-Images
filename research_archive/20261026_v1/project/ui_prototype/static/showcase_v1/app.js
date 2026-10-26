// 【01 程式入口】立即執行函式把變數包在自己的範圍，避免與其他腳本互相覆蓋。
(() => {
  "use strict";
  // 【元素查找與上傳規則】$(id) 找 HTML 中同名 id；容量是 bytes，像素數是寬 × 高。
  const $ = id => document.getElementById(id);
  const MAX_BYTES = 20 * 1024 * 1024;
  const MAX_PIXELS = 64_000_000;
  const TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
  // 【02 畫面狀態】image 是目前影像資訊；objectUrl 是本機預覽網址；busy 表示處理中。
  // operation 是操作序號，用來忽略過期的讀圖或結果；timer 用來取消等待。
  const state = { image: null, objectUrl: "", operation: 0, busy: false, controller: null, mode: $("model-select").value, service: null, serviceError: "" };
  // 【DOM 參照】先取得常用元素，後面的函式便可更新它們。
  const input = $("file-input");
  const dropzone = $("dropzone");
  const preview = $("image-preview");
  const run = $("run-button");

  // 【03 狀態通知】更新按鈕下方文字；HTML 的 aria-live 會通知輔助工具。
  function setStatus(message) { $("status").textContent = message; }
  // 【錯誤提示】傳入文字就顯示；空字串則清除並隱藏。
  function showError(message) {
    $("upload-error").textContent = message;
    $("upload-error").hidden = !message;
  }
  // 【處理中狀態】暫停換圖、選檔與重複執行，同步更新按鈕文字及 aria-busy。
  // 真實模式只有在服務明確開啟且成員契約可用時才能執行，不靜默降級成 mock。
  function canRun() {
    if (!state.image || state.busy) return false;
    if (state.mode === "demo") return true;
    return !state.image.isSample && Boolean(state.service?.models.find(model => model.id === state.mode)?.available);
  }
  function updateMode() {
    const mock = state.mode === "demo";
    const model = state.service?.models.find(item => item.id === state.mode);
    const verified = state.service?.pending_gpu_validation === false;
    $("service-badge").textContent = mock ? "MOCK 固定展示資料" : model?.available ? "研究推論 · 未校準" : verified ? "研究推論 · 預覽模式" : "研究推論 · 待 GPU 驗證";
    $("service-badge").className = "tag service-tag" + (mock || !model?.available ? " pending" : "");
    $("mode-help").textContent = mock ? "固定示範分數，不依影像計算，也不會呼叫模型。" :
      state.serviceError || model?.reason || (state.mode === "v2_imagenet_seed1" ? "使用原 Seed1 best.pt。分數未校準；GPU 輸出一致性狀態見驗證紀錄。" : "每個 Seed 的 softmax 機率各占 1/3，不平均 logits；尚未校準。");
    $("privacy-text").textContent = mock ? "Mock 影像留在瀏覽器，不傳送至服務。" : "執行時才傳至這台電腦的本機服務；不保存影像。";
    $("model-connection").textContent = model?.available ? "本機真實推論已開啟" : verified ? "GPU 已驗證 · 模型待啟動" : "介面已建立 · GPU 待驗證";
    run.disabled = !canRun();
    run.textContent = mock ? "產生展示結果 →" : "執行研究推論 →";
  }
  function setBusy(busy) {
    state.busy = busy;
    run.disabled = !canRun();
    run.textContent = busy ? (state.mode === "demo" ? "正在準備展示結果…" : "本機模型推論中…") : (state.mode === "demo" ? "產生展示結果 →" : "執行研究推論 →");
    $("model-select").disabled = busy;
    $("result-panel").setAttribute("aria-busy", String(busy));
    // 處理中仍允許「移除」以取消等待，但禁止換圖。
    input.disabled = busy;
    dropzone.disabled = busy;
    $("sample-button").disabled = busy;
  }
  // 【04 結果頁籤】切換分類分布/視覺解釋；tabIndex 決定 Tab 鍵停留的位置。
  function selectTab(name, focus = false) {
    ["probabilities", "visual"].forEach(key => {
      const selected = key === name;
      const tab = $("tab-" + key);
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
      $(key + "-panel").hidden = !selected;
      if (focus && selected) tab.focus();
    });
  }
  // 【清除結果】恢復空白面板、移除動態機率條並回到第一個頁籤。
  function clearResult() {
    $("result-content").hidden = true;
    $("result-empty").hidden = false;
    $("probability-bars").replaceChildren();
    $("result-notice").textContent = state.mode === "demo" ? "固定 Mock 僅供展示，不依影像內容計算。" :
      "研究用途；七類分數尚未校準，不代表醫療診斷機率。請依本機服務狀態執行。";
    selectTab("probabilities");
  }
  // 【釋放預覽記憶體】object URL 只是瀏覽器本機參照，不是伺服器網址；不用時須撤銷。
  function releaseImage() {
    if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);
    state.objectUrl = "";
  }
  // 【05 移除影像】取消未完成操作、清空預覽/錯誤/結果，讓使用者重新開始。
  function clearImage() {
    state.operation++;
    state.controller?.abort();
    state.controller = null;
    releaseImage();
    state.image = null;
    input.value = "";
    preview.removeAttribute("src");
    preview.hidden = true;
    $("upload-placeholder").hidden = false;
    $("preview-action").hidden = true;
    $("file-info").hidden = true;
    clearResult();
    showError("");
    setBusy(false);
    setStatus("已清除影像與結果，可重新選擇。");
    dropzone.focus();
  }
  // 【06 讀取影像】讓瀏覽器解碼圖片並回報尺寸；Promise 可供 chooseFile 用 await 等待。
  function decodeImage(url) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight });
      image.onerror = () => reject(new Error("無法讀取影像，檔案可能已損毀，請重新選擇。"));
      image.src = url;
    });
  }
  // 【07 選圖主流程】處理選檔、拖放與內建示意圖；順序是驗證 → 解碼 → 更新預覽 → 清理暫存。
  async function chooseFile(files, isSample = false) {
    if (state.busy || (!isSample && !files?.length)) return;
    const token = ++state.operation;
    showError("");
    let candidate = "";
    // 新檔即使不支援，也先移除舊分數，避免被誤認為新影像的結果。
    clearResult();
    try {
      let image;
      // 【選圖 1/4】示意圖用固定本機素材；使用者影像則檢查單檔、格式、空檔及容量。
      if (isSample) {
        candidate = "./assets/study.svg";
        image = { name: "研究示意影像（非臨床影像）", bytes: 0, isSample: true };
      } else {
        if (files.length !== 1) throw new Error("一次請只選擇一張影像。");
        const file = files[0];
        if (!TYPES.has(file.type)) throw new Error("請選擇 JPG、PNG 或 WebP 影像，不支援此檔案格式。");
        if (!file.size) throw new Error("檔案是空的，請重新選擇。");
        if (file.size > MAX_BYTES) throw new Error("影像超過 20 MB，請縮小後再選擇。");
        candidate = URL.createObjectURL(file);
        image = { name: file.name, bytes: file.size, isSample: false, file };
      }
      run.disabled = true;
      setStatus("正在讀取影像…");
      // 【選圖 2/4】讀取寬高；若期間又換圖或清除，就放棄這次過期的結果。
      const dimensions = await decodeImage(candidate);
      if (token !== state.operation) return;
      if (!dimensions.width || !dimensions.height || dimensions.width * dimensions.height > MAX_PIXELS) {
        throw new Error("影像尺寸無效或超過 6,400 萬像素，請先縮小尺寸。");
      }
      // 【選圖 3/4】驗證成功才替換原圖，更新預覽、檔名與容量；檔名用 textContent 當純文字。
      releaseImage();
      state.image = { ...image, ...dimensions };
      state.objectUrl = isSample ? "" : candidate;
      preview.src = candidate;
      preview.alt = isSample ? "研究示意圖，非臨床影像" : "已選擇的影像預覽";
      preview.hidden = false;
      $("upload-placeholder").hidden = true;
      $("preview-action").hidden = false;
      $("file-info").hidden = false;
      $("file-name").textContent = image.name;
      const size = image.bytes < 1024 * 1024 ? `${(image.bytes / 1024).toFixed(1)} KB` : `${(image.bytes / 1024 / 1024).toFixed(2)} MB`;
      $("file-meta").textContent = `${dimensions.width} × ${dimensions.height} px · ${isSample ? "內建示意圖 · 非臨床影像" : size}`;
      setStatus(state.mode === "demo" ? "影像已準備好。可產生固定 mock 展示結果。" : "檔案已可讀；適用性尚未自動確認。真實推論需本機服務開啟模型。");
    // 【選圖 4/4】失敗時顯示原因並保留原影像；finally 無論成功失敗都負責清理。
    } catch (error) {
      if (token === state.operation) {
        showError(error.message);
        setStatus(state.image ? "新影像未載入，保留原影像。" : "請重新選擇影像。");
      }
    } finally {
      if (candidate.startsWith("blob:") && candidate !== state.objectUrl) URL.revokeObjectURL(candidate);
      if (token === state.operation) {
        run.disabled = !canRun();
        input.value = "";
      }
    }
  }
  // 【08 繪製結果】真實回應先經 adapter 驗證，mock 明確標示；兩者共用既有機率條元件。
  function renderResult(result) {
    const mock = result.is_mock !== false;
    const top = result.disease[0];
    $("prediction-label").textContent = top.label;
    $("prediction-code").textContent = top.code + (mock ? " / MOCK PREDICTION" : " / V2 RESEARCH");
    $("prediction-score").textContent = (top.probability * 100).toFixed(1) + "%";
    // 【七類機率條】每筆 disease 建立一列 DOM；probability 介於 0～1，畫面乘 100 轉百分比。
    // 固定文案定位ID依類別代碼綁定，不依結果名次。
    const textIds = {"AKIEC": ["F-301", "F-302", "F-303"], "BCC": ["F-304", "F-305", "F-306"], "BKL": ["F-307", "F-308", "F-309"], "DF": ["F-310", "F-311", "F-312"], "NV": ["F-313", "F-314", "F-315"], "VASC": ["F-316", "F-317", "F-318"], "MEL": ["F-319", "F-320", "F-321"]};
    const rows = result.disease.map(item => {
      const row = document.createElement("div");
      row.className = "probability-row";
      const label = document.createElement("span");
      label.className = "class-label";
      label.dataset.textId = textIds[item.code][0];
      label.textContent = item.label;
      const code = document.createElement("span");
      code.className = "class-code";
      code.dataset.textId = textIds[item.code][1];
      code.textContent = item.code;
      label.append(code);
      const meter = document.createElement("meter");
      meter.min = 0;
      meter.max = 1;
      meter.value = item.probability;
      meter.setAttribute("aria-label", item.label + (mock ? " mock 相對機率" : " 未校準相對機率"));
      meter.setAttribute("aria-valuetext", (item.probability * 100).toFixed(1) + "%");
      const value = document.createElement("span");
      value.className = "probability-value";
      value.dataset.textId = textIds[item.code][2];
      value.textContent = (item.probability * 100).toFixed(1) + "%";
      row.append(label, meter, value);
      return row;
    });
    $("probability-bars").replaceChildren(...rows);
    // 【結果解釋】依真實／Mock 分開說明；不生成診斷理由，也不宣稱已辨識圖片適用性。
    $("result-kind").textContent = mock ? "模擬資料" : "真實模型 · 未校準";
    $("score-kind").textContent = mock ? "展示分數" : "未校準相對機率";
    $("distribution-kind").textContent = mock ? "相對機率（mock）" : "相對機率（未校準）";
    $("result-model-info").textContent = mock ? "固定 mock 範例，不使用模型權重。" :
      result.model_label + " · " + result.members.map(member => `Seed ${member.seed}（最佳輪 ${member.best_epoch}，權重 ${member.weight === 1 ? "1" : "1/3"}）`).join("／");
    $("result-notice").textContent = mock ? "本次是固定示範數值，不依影像內容計算，並非 ConvNeXt V2-Tiny 實際推論。" :
      "本次為原 V2 模型輸出；分數未校準，不代表醫療診斷機率。本版未驗證圖片適用性，不能判定正常皮膚或排除七類以外疾病。";
    $("explanation-text").textContent = mock ? "這份固定範例將「黑色素細胞痣」設為最高分，用來示範七類分布的閱讀方式。它不依你的影像計算，也不代表健康狀況；高分不等於確診。" :
      `在模型已學習的七個類別中，「${top.label}」的相對分數最高。${result.members.length === 3 ? "本結果由三個 Seed 的 softmax 機率各占 1/3 平均。" : "本結果使用原 ImageNet Seed1。"}分數尚未校準，高分不等於診斷正確；這是限定七類中的比較，未確認影像適用性；模糊、正常皮膚或七類外影像也可能得到高分，不能據此判定正常或排除其他疾病。`;
    $("result-empty").hidden = true;
    $("result-content").hidden = false;
    selectTab("probabilities");
  }

  // 【09 綁定基本事件】點擊上傳框開檔案選擇器，change 讀圖，示意圖/移除按鈕各呼叫對應函式。
  dropzone.addEventListener("click", () => input.click());
  input.addEventListener("change", () => chooseFile(input.files));
  $("sample-button").addEventListener("click", () => {
    state.mode = "demo";
    $("model-select").value = "demo";
    updateMode();
    chooseFile(null, true);
  });
  $("model-select").addEventListener("change", () => {
    state.operation++;
    state.mode = $("model-select").value;
    clearResult();
    showError("");
    updateMode();
    setStatus(state.image?.isSample && state.mode !== "demo" ? "示意圖不能作真實推論，請選擇 JPG、PNG 或 WebP。" : "模型版本已切換，前份結果已清除。");
  });
  $("clear-button").addEventListener("click", clearImage);
  // 【10 拖放事件】拖入/停留時高亮；離開/放下時移除高亮；preventDefault 避免瀏覽器直接開檔。
  ["dragenter", "dragover"].forEach(type => dropzone.addEventListener(type, event => {
    event.preventDefault();
    if (!state.busy) dropzone.classList.add("drag-over");
  }));
  ["dragleave", "drop"].forEach(type => dropzone.addEventListener(type, event => {
    event.preventDefault();
    dropzone.classList.remove("drag-over");
  }));
  dropzone.addEventListener("drop", event => {
    if (!state.busy) chooseFile(event.dataTransfer.files);
  });
  // 檔案落在上傳框以外時，也不要讓瀏覽器直接開檔而取代本頁。
  window.addEventListener("dragover", event => event.preventDefault());
  window.addEventListener("drop", event => event.preventDefault());
  // 【11 執行結果】真實模式送往同源 API；錯誤不以 mock 補結果，清除只取消前端等待。
  run.addEventListener("click", async () => {
    if (!canRun()) return;
    const token = ++state.operation;
    const mode = state.mode;
    const controller = new AbortController();
    state.controller = controller;
    clearResult();
    showError("");
    setBusy(true);
    setStatus(mode === "demo" ? "正在準備固定 mock 展示。" : "正在本機執行原 V2 推論；首次載入權重可能較久。");
    try {
      const result = mode === "demo" ? window.SkinDetectMock.createResult(state.image) :
        await window.SkinDetectApi.predict(state.image.file, mode, controller.signal);
      if (token !== state.operation) return;
      renderResult(result);
      setStatus(mode === "demo" ? "展示完成。固定模擬數值，非真實推論。" : "真實推論完成。分數未校準，僅供研究。");
    } catch (error) {
      if (token !== state.operation) return;
      clearResult();
      if (error.name !== "AbortError") showError(error.message);
      setStatus("本次沒有取得模型結果，不會自動改用 mock。");
    } finally {
      if (token === state.operation) { state.controller = null; setBusy(false); }
    }
  });
  // 【12 頁籤事件】滑鼠點擊、左右方向鍵、Home/End 都能切換；維持鍵盤焦點。
  ["probabilities", "visual"].forEach((name, index) => {
    const tab = $("tab-" + name);
    tab.addEventListener("click", () => selectTab(name));
    tab.addEventListener("keydown", event => {
      if (["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) {
        event.preventDefault();
        const next = event.key === "Home" ? 0 : event.key === "End" ? 1 : 1 - index;
        selectTab(["probabilities", "visual"][next], true);
      }
    });
  });
  // 【13 離開頁面】釋放尚在使用的預覽網址。
  window.addEventListener("pagehide", () => { releaseImage(); state.controller?.abort(); });
  // 啟動時只讀取小型服務狀態，不會載入模型或使用 GPU。
  updateMode();
  window.SkinDetectApi.catalog().then(service => { state.service = service; }).catch(error => {
    state.serviceError = error.message + "；仍可選擇 Mock 展示。";
  }).finally(updateMode);
})();
