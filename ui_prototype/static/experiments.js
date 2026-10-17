function formatExperimentBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function experimentArtifacts(files) {
  if (!files.length) return `<p class="small muted">此群組目前沒有可讀取的快照。</p>`;
  return `<div class="artifact-list">${files.map(file => `
    <a href="${escapeHtml(file.url)}" target="_blank" rel="noopener" class="artifact-link">
      <span class="artifact-kind">${escapeHtml(file.kind.toUpperCase())}</span>
      <span><strong>${escapeHtml(file.name)}</strong><small>${escapeHtml(file.source_path)}</small></span>
      <span class="artifact-size">${formatExperimentBytes(file.size_bytes)}</span>
    </a>`).join("")}</div>`;
}

function experimentLibrary() {
  const library = state.experimentLibrary;
  if (!library) return `<section id="experiment-library" class="experiment-library"><h2>階段性實驗紀錄庫</h2><p class="error">${escapeHtml(state.libraryError || "實驗紀錄尚未讀取。")}</p></section>`;
  const stages = [...new Set(library.experiments.map(item => item.stage))];
  const selected = state.experimentStage || "全部";
  const visible = selected === "全部"
    ? library.experiments
    : library.experiments.filter(item => item.stage === selected);
  const megabytes = library.total_bytes / 1024 / 1024;

  return `
    <section id="experiment-library" class="experiment-library">
      <div class="library-heading">
        <div>
          <p class="eyebrow">固定資料夾：${escapeHtml(library.fixed_folder)}</p>
          <h2>階段性實驗紀錄庫</h2>
          <p class="muted">集中讀取過去階段的摘要、JSON、CSV、Markdown 與曲線圖；不複製資料集或模型權重。</p>
        </div>
        <div class="library-stats">
          <span><strong>${library.experiment_count}</strong> 組實驗</span>
          <span><strong>${library.file_count}</strong> 個檔案</span>
          <span><strong>${megabytes.toFixed(1)}</strong> MB</span>
        </div>
      </div>
      ${library.notice ? `<p class="small muted">${escapeHtml(library.notice)}</p>` : ""}
      ${!visible.length ? `<p class="small muted">此階段尚無實驗紀錄。</p>` : ""}
      <div class="library-toolbar">
        <label>依階段篩選
          <select id="experiment-stage-filter">
            <option ${selected === "全部" ? "selected" : ""}>全部</option>
            ${stages.map(stage => `<option ${selected === stage ? "selected" : ""}>${escapeHtml(stage)}</option>`).join("")}
          </select>
        </label>
        <span class="small muted">顯示 ${visible.length} 組；點開卡片即可讀取原始紀錄。</span>
      </div>
      <div class="experiment-grid">${visible.map(item => `
        <article class="experiment-card">
          <div class="experiment-card-top">
            <span class="stage-pill">${escapeHtml(item.stage)}</span>
            <span class="small muted">${item.file_count} 個檔案</span>
          </div>
          <h3>${escapeHtml(item.title)}</h3>
          <p>${escapeHtml(item.summary)}</p>
          ${item.metrics.length ? `<div class="metric-chips">${item.metrics.map(metric => `
            <span><small>${escapeHtml(metric.label)}</small><strong>${escapeHtml(metric.value)}</strong></span>`).join("")}</div>` : ""}
          <details>
            <summary>讀取實驗檔案</summary>
            ${experimentArtifacts(item.files)}
          </details>
        </article>`).join("")}
      </div>
    </section>`;
}

function bindExperimentLibrary() {
  const filter = document.querySelector("#experiment-stage-filter");
  if (!filter) return;
  filter.onchange = event => {
    state.experimentStage = event.target.value;
    render();
  };
}
