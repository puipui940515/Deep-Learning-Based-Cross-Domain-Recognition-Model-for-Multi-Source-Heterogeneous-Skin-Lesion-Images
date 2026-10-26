/*
 * 【固定展示資料】只供前端閱讀流程使用，不是 ConvNeXt V2-Tiny 的推論。
 * 類別代碼與中文名稱沿用 ui_prototype/server.py。
 * 若練習調整分數：probability 用 0～1，七類總和應維持 1；0.624 就是 62.4%。
 */
(() => {
  "use strict";
  // 【01 七類原始範例】Object.freeze 避免互動過程意外改寫資料；排序在回應階段處理。
  const classes = Object.freeze([
    { code: "AKIEC", label: "日光性角化症／表皮內癌", probability: .048 },
    { code: "BCC", label: "基底細胞癌", probability: .091 },
    { code: "BKL", label: "良性角化症樣病灶", probability: .132 },
    { code: "DF", label: "皮膚纖維瘤", probability: .027 },
    { code: "NV", label: "黑色素細胞痣", probability: .624 },
    { code: "VASC", label: "血管性病灶", probability: .018 },
    { code: "MEL", label: "黑色素瘤", probability: .060 },
  ].map(Object.freeze));

  // 【02 建立回應】只帶入影像尺寸與名稱；不讀取像素，不隨影像內容改變分數。
  function createResult(image) {
    // 保留舊 API 的主要欄位形狀，方便後續另行審核的串接程式沿用。
    return {
      prediction_id: "mock-showcase-v1",
      is_mock: true,
      model_id: "demo",
      model_label: "固定 mock 資料（非 ConvNeXt V2-Tiny 推論）",
      image: { width: image.width, height: image.height, bytes: image.bytes },
      image_name: image.name,
      // 複製每筆資料，再按分數由高到低排序；原 classes 順序不變。
      disease: classes.map(item => ({ ...item })).sort((a, b) => b.probability - a.probability),
      // Grad-CAM 明確標記不可用；本版不生成假熱力圖。
      heatmap: { requested: false, available: false, method: "Grad-CAM", overlay_data_url: "", notice: "尚未串接；不產生模擬熱力圖。" },
      medical_notice: "研究展示用模擬資料，不構成醫療診斷。",
    };
  }

  // 【03 公開給 app.js】頁面先載入本檔，app.js 才能呼叫 createResult()。
  window.SkinDetectMock = Object.freeze({ createResult });
})();
