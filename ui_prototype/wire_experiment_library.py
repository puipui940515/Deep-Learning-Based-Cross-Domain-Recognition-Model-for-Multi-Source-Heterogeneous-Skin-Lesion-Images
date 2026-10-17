from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"找不到預期接線位置：{path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    index = ROOT / "ui_prototype" / "static" / "index.html"
    replace_once(index, '  <link rel="stylesheet" href="/styles.css">', '  <link rel="stylesheet" href="/styles.css">\n  <link rel="stylesheet" href="/experiments.css">')
    replace_once(index, '  <script src="/app.js" defer></script>', '  <script src="/experiments.js" defer></script>\n  <script src="/app.js" defer></script>')

    app = ROOT / "ui_prototype" / "static" / "app.js"
    replace_once(app, '  history: [],\n  busy: false,', '  history: [],\n  experimentLibrary: null,\n  experimentStage: "全部",\n  busy: false,')
    replace_once(app, '  const [config, models, history] = await Promise.all([', '  const [config, models, history, experiments] = await Promise.all([')
    replace_once(app, '    fetch("/api/history").then(r => r.json()),\n  ]);', '    fetch("/api/history").then(r => r.json()),\n    fetch("/api/experiments").then(r => r.json()),\n  ]);')
    replace_once(app, '  state.history = history;\n  if (!state.models.find', '  state.history = history;\n  state.experimentLibrary = experiments;\n  if (!state.models.find')
    replace_once(app, '          <span class="badge ok">本機服務</span>\n          <span class="badge">${variantNames[state.variant]}</span>', '          <span class="badge ok">本機服務</span>\n          <span class="badge">${state.experimentLibrary?.experiment_count || 0} 組實驗</span>\n          <span class="badge">${variantNames[state.variant]}</span>')
    replace_once(app, '      ${content}\n    </div>`;', '      ${content}\n      ${experimentLibrary()}\n    </div>`;')
    replace_once(app, 'function bindInteractions() {\n  const fileInput', 'function bindInteractions() {\n  bindExperimentLibrary();\n  const fileInput')

    server = ROOT / "ui_prototype" / "server.py"
    replace_once(server, 'from urllib.parse import urlparse', 'from urllib.parse import unquote, urlparse')
    replace_once(server, 'STATIC_DIR = BASE_DIR / "static"', 'STATIC_DIR = BASE_DIR / "static"\nEXPERIMENT_LIBRARY_DIR = PROJECT_ROOT / "實驗紀錄庫"\nEXPERIMENT_REGISTRY = EXPERIMENT_LIBRARY_DIR / "registry.json"')
    static_tail = '''        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:'''
    experiment_method = '''        self.end_headers()
        self.wfile.write(data)

    def _serve_experiment_file(self, request_path: str) -> None:
        relative = unquote(request_path.removeprefix("/experiment-files/")).lstrip("/")
        target = (EXPERIMENT_LIBRARY_DIR / relative).resolve()
        if not target.is_relative_to(EXPERIMENT_LIBRARY_DIR.resolve()) or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix.lower() in {".json", ".csv", ".md"}:
            content_type += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:'''
    replace_once(server, static_tail, experiment_method)
    get_tail = '''        if path == "/api/history":
            with self.server.history_lock:
                self._json(list(reversed(self.server.history[-20:])))
            return
        self._serve_static(path)'''
    get_with_experiments = '''        if path == "/api/history":
            with self.server.history_lock:
                self._json(list(reversed(self.server.history[-20:])))
            return
        if path == "/api/experiments":
            if not EXPERIMENT_REGISTRY.is_file():
                self._json({
                    "fixed_folder": EXPERIMENT_LIBRARY_DIR.name,
                    "experiment_count": 0,
                    "file_count": 0,
                    "total_bytes": 0,
                    "experiments": [],
                    "notice": "尚未建立 registry.json，請執行實驗紀錄庫同步指令。",
                })
            else:
                self._json(json.loads(EXPERIMENT_REGISTRY.read_text(encoding="utf-8-sig")))
            return
        if path.startswith("/experiment-files/"):
            self._serve_experiment_file(path)
            return
        self._serve_static(path)'''
    replace_once(server, get_tail, get_with_experiments)

    readme = ROOT / "實驗紀錄庫" / "README.md"
    readme.write_text('''# SkinDetect 實驗紀錄庫

此資料夾是 UI 使用的固定實驗紀錄入口。只收納 JSON、CSV、Markdown 與曲線圖快照，不複製資料集或模型權重。

## 內容

- `registry.json`：UI 讀取的實驗群組、摘要指標與檔案索引。
- `records/`：由既有階段資料夾同步而來的唯讀小型紀錄快照。
- `sync_registry.py`：在新增實驗後重新同步索引。

## 更新指令

```powershell
python ".\\實驗紀錄庫\\sync_registry.py"
```

同步程式只會複製 `.json`、`.csv`、`.md`、`.png`，排除資料集、設定、程式碼、煙霧測試目錄與模型權重。原始實驗檔仍保留在原位置。
''', encoding="utf-8")
    print("實驗紀錄庫接線完成")


if __name__ == "__main__":
    main()
