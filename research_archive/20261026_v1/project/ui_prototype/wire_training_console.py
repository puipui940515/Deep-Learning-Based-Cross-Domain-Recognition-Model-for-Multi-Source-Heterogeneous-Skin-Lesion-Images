from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"找不到預期接線位置：{path}\n{old[:120]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


server = ROOT / "server.py"
replace_once(
    server,
    "from model_runtime import build_model_from_definition, load_model_registry\n",
    "from model_runtime import build_model_from_definition, load_model_registry\nfrom training_runtime import TrainingManager\n",
)
replace_once(
    server,
    '''class SkinDetectServer(ThreadingHTTPServer):
    def __init__(self, address, handler, predictor: Predictor, environment: str) -> None:
        super().__init__(address, handler)
        self.predictor = predictor
        self.environment = environment
''',
    '''class SkinDetectServer(ThreadingHTTPServer):
    def __init__(self, address, handler, predictor: Predictor, training_manager: TrainingManager, environment: str) -> None:
        super().__init__(address, handler)
        self.predictor = predictor
        self.training_manager = training_manager
        self.environment = environment
''',
)
replace_once(
    server,
    '''        if path == "/api/experiments":
''',
    '''        if path == "/api/training/status":
            self._json(self.server.training_manager.status())
            return
        if path == "/api/experiments":
''',
)
replace_once(
    server,
    '''    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/predict":
''',
    '''    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path in {"/api/training/start", "/api/training/stop"}:
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length < 0 or content_length > 64 * 1024:
                    raise ValueError("訓練設定內容過大。")
                payload = json.loads(self.rfile.read(content_length).decode("utf-8")) if content_length else {}
                result = (
                    self.server.training_manager.start(payload)
                    if path.endswith("/start")
                    else self.server.training_manager.stop()
                )
                self._json(result)
            except (ValueError, RuntimeError) as error:
                self._json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            except Exception as error:
                self._json({"error": f"訓練控制失敗：{error}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if path != "/api/predict":
''',
)
replace_once(
    server,
    '''    server = SkinDetectServer((args.host, args.port), Handler, predictor, args.environment)
''',
    '''    training_manager = TrainingManager(PROJECT_ROOT)
    server = SkinDetectServer((args.host, args.port), Handler, predictor, training_manager, args.environment)
''',
)

html = ROOT / "static" / "index.html"
replace_once(
    html,
    '  <link rel="stylesheet" href="/experiments.css">\n',
    '  <link rel="stylesheet" href="/experiments.css">\n  <link rel="stylesheet" href="/training.css">\n',
)
replace_once(
    html,
    '  <script src="/experiments.js" defer></script>\n  <script src="/app.js" defer></script>\n',
    '  <script src="/experiments.js" defer></script>\n  <script src="/training.js" defer></script>\n  <script src="/app.js" defer></script>\n',
)

app = ROOT / "static" / "app.js"
replace_once(
    app,
    '''      <div class="notice">研究用途輸出，不構成醫療診斷；正式上線前仍需完成臨床驗證、權限控管與資料治理。</div>
      ${content}
''',
    '''      <div class="notice">研究用途輸出，不構成醫療診斷；正式上線前仍需完成臨床驗證、權限控管與資料治理。</div>
      <section id="training-console-host">${window.trainingPanel ? window.trainingPanel() : ""}</section>
      ${content}
''',
)
replace_once(
    app,
    '''function bindInteractions() {
  bindExperimentLibrary();
''',
    '''function bindInteractions() {
  bindExperimentLibrary();
  window.bindTrainingPanel?.();
''',
)

train = PROJECT / "資料治理與泛化修復" / "scripts" / "train_regularized.py"
replace_once(
    train,
    '''    parser.add_argument("--epochs", type=int)
    parser.add_argument("--resume", action="store_true")
''',
    '''    parser.add_argument("--epochs", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--weight-decay", type=float)
    parser.add_argument("--label-smoothing", type=float)
    parser.add_argument("--mixup-alpha", type=float)
    parser.add_argument("--early-stopping-patience", type=int)
    parser.add_argument("--resume", action="store_true")
''',
)
replace_once(
    train,
    '''    train_config = config["training"]
    gate_path = ROOT / "reports" / "pipeline_gate.json"
''',
    '''    train_config = dict(config["training"])
    overrides = {
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "label_smoothing": args.label_smoothing,
        "mixup_alpha": args.mixup_alpha,
        "early_stopping_patience": args.early_stopping_patience,
    }
    train_config.update({key: value for key, value in overrides.items() if value is not None})
    gate_path = ROOT / "reports" / "pipeline_gate.json"
''',
)

print("training console wired")
