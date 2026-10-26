/* 開發用文字定位器。ID只讀原始碼／固定登錄表，絕不按畫面順序編號。 */
(() => {
  "use strict";
  const local = ["127.0.0.1", "localhost", "[::1]"].includes(location.hostname);
  if (!local || new URLSearchParams(location.search).get("textids") !== "1") return;
  const style = document.createElement("link");
  style.rel = "stylesheet";
  style.href = "./text-locator.css";
  document.head.append(style);
  const script = document.createElement("script");
  script.src = "./text-registry.js";
  script.addEventListener("load", mount, { once: true });
  script.addEventListener("error", () => console.error("文字定位清單未載入；請檢查本機服務。"), { once: true });
  document.head.append(script);

  function mount() {
    const entries = new Map(window.SkinDetectTextRegistry.map(entry => [entry.id, entry]));
    const portal = document.createElement("div");
    portal.id = "text-locator";
    const layer = document.createElement("div");
    layer.className = "tl-layer";
    layer.setAttribute("aria-hidden", "true");
    const toolbar = document.createElement("section");
    toolbar.className = "tl-toolbar";
    toolbar.setAttribute("aria-label", "開發文字定位工具");
    const title = document.createElement("strong");
    title.textContent = "文字編號 · 開發預覽";
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.id = "tl-toggle";
    const search = document.createElement("form");
    search.className = "tl-search";
    const input = document.createElement("input");
    input.id = "tl-id-input";
    input.setAttribute("aria-label", "輸入文字編號");
    input.placeholder = "例如 F-009";
    input.maxLength = 10;
    const find = document.createElement("button");
    find.type = "submit";
    find.textContent = "定位";
    search.append(input, find);
    const hint = document.createElement("p");
    hint.className = "tl-hint";
    const detail = document.createElement("section");
    detail.id = "tl-detail";
    detail.setAttribute("aria-label", "文字編號詳情");
    detail.hidden = true;
    const number = document.createElement("strong");
    number.id = "tl-selected-id";
    const current = document.createElement("p");
    current.id = "tl-current";
    const source = document.createElement("p");
    source.id = "tl-source";
    const note = document.createElement("p");
    note.className = "tl-hint";
    detail.append(number, current, source, note);
    toolbar.append(title, toggle, search, hint, detail);
    portal.append(layer, toolbar);
    document.body.append(portal);
    let enabled = true;
    let selected = "";
    let frame = 0;
    function schedule() {
      if (!frame) frame = requestAnimationFrame(() => { frame = 0; draw(); });
    }
    function elementFor(id) {
      return document.querySelector(`[data-text-id="${id}"]`);
    }
    function isVisible(node) {
      if (!node || node.closest("[hidden]") || ["TITLE", "META", "OPTION"].includes(node.tagName)) return false;
      if (node.classList.contains("skip-link") && document.activeElement !== node) return false;
      const rect = node.getBoundingClientRect();
      const css = getComputedStyle(node);
      return rect.width > 2 && rect.height > 2 && css.display !== "none" && css.visibility !== "hidden";
    }
    function show(id, scroll = false) {
      const entry = entries.get(id);
      if (!entry) { hint.textContent = "找不到此編號，請查閱 TEXT_IDS.md。"; return; }
      selected = id;
      const node = elementFor(id);
      const live = node ? (entry.attribute ? node.getAttribute(entry.attribute) : node.textContent) : "";
      number.textContent = id;
      current.textContent = (live || entry.content || "〔此情境尚無文字〕").trim();
      source.textContent = `${entry.page} · ${entry.source}`;
      note.textContent = isVisible(node) ? "固定ID；修改文字或結果排序不會重新編號。" : "目前隱藏／尚未產生，或是頁籤、下拉選項、輔助文字；請先切換到對應情境。";
      detail.hidden = false;
      if (scroll && isVisible(node)) node.scrollIntoView({ block: "center", behavior: "auto" });
      schedule();
    }
    function draw() {
      layer.replaceChildren();
      if (!enabled) return;
      const width = document.documentElement.clientWidth;
      const height = innerHeight;
      const fragment = document.createDocumentFragment();
      document.querySelectorAll("[data-text-id]").forEach(node => {
        const id = node.dataset.textId;
        if (!entries.has(id) || !isVisible(node)) return;
        const rect = node.getBoundingClientRect();
        if (rect.bottom < 0 || rect.top > height || rect.right < 0 || rect.left > width) return;
        const outline = document.createElement("div");
        outline.className = "tl-outline" + (selected === id ? " tl-selected" : "");
        outline.style.left = `${Math.max(0, rect.left)}px`;
        outline.style.top = `${Math.max(0, rect.top)}px`;
        outline.style.width = `${Math.max(0, Math.min(rect.right, width) - Math.max(0, rect.left))}px`;
        outline.style.height = `${Math.max(0, Math.min(rect.bottom, height) - Math.max(0, rect.top))}px`;
        const badge = document.createElement("button");
        badge.type = "button";
        badge.tabIndex = -1;
        badge.className = "tl-badge";
        badge.dataset.locatorId = id;
        badge.textContent = id;
        badge.title = `查看 ${id}`;
        badge.style.left = `${Math.min(Math.max(0, rect.left), Math.max(0, width - 56))}px`;
        badge.style.top = `${Math.min(Math.max(0, rect.top - 9), height - 20)}px`;
        fragment.append(outline, badge);
      });
      layer.append(fragment);
    }
    function setEnabled(value) {
      enabled = value;
      toggle.textContent = enabled ? "關閉編號（恢復操作）" : "開啟編號";
      toggle.setAttribute("aria-pressed", String(enabled));
      hint.textContent = enabled ? "點文字或編號看來源；關閉編號後再選圖／推論。Esc 關閉。" : "編號已關閉，網頁操作正常。";
      if (!enabled) detail.hidden = true;
      schedule();
    }
    toggle.addEventListener("click", () => setEnabled(!enabled));
    search.addEventListener("submit", event => {
      event.preventDefault();
      if (!enabled) setEnabled(true);
      show(input.value.trim().toUpperCase(), true);
    });
    document.addEventListener("click", event => {
      if (!enabled) return;
      const badge = event.target.closest("[data-locator-id]");
      if (badge) { event.preventDefault(); event.stopImmediatePropagation(); show(badge.dataset.locatorId); return; }
      if (portal.contains(event.target)) return;
      const node = event.target.closest("[data-text-id]");
      if (!node || !entries.has(node.dataset.textId)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      show(node.dataset.textId);
    }, true);
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && enabled) { event.preventDefault(); setEnabled(false); }
    });
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule, { passive: true });
    const observer = new MutationObserver(records => {
      if (records.some(record => !portal.contains(record.target))) schedule();
    });
    observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true,
      attributeFilter: ["hidden", "data-text-id", "aria-selected"] });
    setEnabled(true);
  }
})();
