/* 真實 API adapter：不直接操作畫面，失敗時不替換成 mock。 */
(() => {
  "use strict";
  const order = ["AKIEC", "BCC", "BKL", "DF", "NV", "VASC", "MEL"];
  // 中文類名沿用正式七類，禁止把其他名稱（例如正常皮膚）包成既有 code 顯示。
  const labels = ["日光性角化症／表皮內癌", "基底細胞癌", "良性角化症樣病灶", "皮膚纖維瘤", "黑色素細胞痣", "血管性病灶", "黑色素瘤"];
  const seeds = { v2_imagenet_seed1: [1], v2_imagenet_ensemble123: [1, 2, 3] };
  function validateResult(result, mode) {
    const expected = seeds[mode];
    if (!expected || result?.is_mock !== false || result.model_id !== mode || result.calibrated !== false ||
        JSON.stringify(result.class_order) !== JSON.stringify(order) || !Array.isArray(result.disease) || result.disease.length !== 7 ||
        !Array.isArray(result.members) || result.members.length !== expected.length) {
      throw new Error("服務回應與選定的原 V2 模型契約不符，未顯示結果。");
    }
    const scores = result.disease;
    if (new Set(scores.map(item => item.code)).size !== 7 || scores.some(item => !order.includes(item.code) ||
        !Number.isFinite(item.probability) || item.probability < 0 || item.probability > 1 || item.label !== labels[order.indexOf(item.code)]) ||
        Math.abs(scores.reduce((sum, item) => sum + item.probability, 0) - 1) > 1e-5 ||
        result.members.some((item, i) => item.seed !== expected[i] || !Number.isFinite(item.weight) || Math.abs(item.weight - 1 / expected.length) > 1e-12 ||
          !/^[a-f0-9]{64}$/.test(item.checkpoint_sha256))) {
      throw new Error("服務的七類分數或等權 Seed 成員不符，未顯示結果。");
    }
    return { ...result, disease: [...scores].sort((a, b) => b.probability - a.probability || order.indexOf(a.code) - order.indexOf(b.code)) };
  }
  async function request(url, options = {}, externalSignal, timeout = 120000) {
    const controller = new AbortController();
    const cancel = () => controller.abort();
    if (externalSignal?.aborted) controller.abort();
    externalSignal?.addEventListener("abort", cancel, { once: true });
    let expired = false;
    const timer = setTimeout(() => { expired = true; controller.abort(); }, timeout);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal, cache: "no-store" });
      let result;
      try { result = await response.json(); }
      catch { throw new Error("本機服務回應無效；請確認使用的是新版前端服務，而非舊靜態伺服器。"); }
      if (!response.ok) throw new Error(result.error || `本機服務失敗（HTTP ${response.status}）。`);
      return result;
    } catch (error) {
      if (expired) throw new Error("推論等待逾時；本機已送出的工作可能仍會完成，請勿連續重送。");
      if (error.name === "AbortError") throw error;
      if (error instanceof TypeError) throw new Error("無法連線到本機 V2 服務，請確認已使用新版 start_frontend.ps1 啟動。");
      throw error;
    } finally {
      clearTimeout(timer);
      externalSignal?.removeEventListener("abort", cancel);
    }
  }
  function dataUrl(file, signal) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      const cancel = () => reader.abort();
      const finish = () => signal?.removeEventListener("abort", cancel);
      reader.onload = () => { finish(); resolve(reader.result); };
      reader.onerror = () => { finish(); reject(new Error("無法讀取上傳影像。")); };
      reader.onabort = () => { finish(); reject(new DOMException("已取消", "AbortError")); };
      if (signal?.aborted) { reject(new DOMException("已取消", "AbortError")); return; }
      signal?.addEventListener("abort", cancel, { once: true });
      reader.readAsDataURL(file);
    });
  }
  window.SkinDetectApi = Object.freeze({
    validateResult,
    async catalog() {
      const catalog = await request("/api/v2/models", {}, null, 5000);
      if (catalog.api_version !== "v2-ensemble-v1" || !Array.isArray(catalog.models)) throw new Error("不是新版 V2 推論服務。");
      return catalog;
    },
    async predict(file, mode, signal) {
      const image_data_url = await dataUrl(file, signal);
      const result = await request("/api/v2/predict", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: mode, image_name: file.name.slice(0, 200), image_data_url }) }, signal);
      return validateResult(result, mode);
    },
  });
})();
