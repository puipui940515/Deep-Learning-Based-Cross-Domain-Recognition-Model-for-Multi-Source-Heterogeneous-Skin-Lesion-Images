from __future__ import annotations

import argparse
import base64
import gc
import hashlib
import html
import io
import json
import mimetypes
import os
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from model_runtime import build_model_from_definition, load_model_registry
from heatmap_runtime import gradcam_prediction, overlay_data_url
from training_runtime import TrainingManager


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "static"
EXPERIMENT_LIBRARY_DIR = PROJECT_ROOT / "實驗紀錄庫"
EXPERIMENT_REGISTRY = EXPERIMENT_LIBRARY_DIR / "registry.json"
MODEL_LIBRARY_DIR = PROJECT_ROOT / "模型資產庫"
MANUAL_PATH = PROJECT_ROOT / "UI使用手冊.md"
MANUAL_IMAGES_DIR = PROJECT_ROOT / "UI使用手冊_圖片版"
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 64_000_000


def prediction_payload(payload: object, default_model: str) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("推論內容必須是 JSON 物件。")
    data_url = payload.get("image_data_url", "")
    if not isinstance(data_url, str) or "," not in data_url:
        raise ValueError("缺少影像資料。")
    header, encoded = data_url.split(",", 1)
    if header not in {"data:image/jpeg;base64", "data:image/png;base64", "data:image/webp;base64"}:
        raise ValueError("請上傳 JPG、PNG 或 WEBP 影像。")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise ValueError("影像編碼無效，請重新選擇檔案。") from error
    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("影像必須有內容且不超過 20 MB。")
    result = {"image_bytes": image_bytes}
    for name, default in [("model_id", default_model), ("manual_site", ""), ("experiment_tag", ""), ("image_name", "")]:
        value = payload.get(name, default)
        if not isinstance(value, str) or len(value) > 200:
            raise ValueError(f"{name} 必須是 200 字以內的文字。")
        result[name] = value
    for name, default in [("include_site", False), ("include_heatmap", True)]:
        value = payload.get(name, default)
        if not isinstance(value, bool):
            raise ValueError(f"{name} 必須是布林值。")
        result[name] = value
    return result


def render_manual(text: str) -> str:
    """Render the handbook's headings, paragraphs, lists and fenced commands."""
    parts = []
    in_code = False
    in_list = False
    for line in text.splitlines():
        if line.startswith("```"):
            if in_list: parts.append("</ul>"); in_list = False
            parts.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            parts.append(html.escape(line) + "\n")
            continue
        if line.startswith("- "):
            if not in_list: parts.append("<ul>"); in_list = True
            parts.append("<li>" + html.escape(line[2:]) + "</li>")
            continue
        if in_list: parts.append("</ul>"); in_list = False
        if line.startswith("#"):
            level = min(len(line) - len(line.lstrip("#")), 3)
            parts.append(f"<h{level}>" + html.escape(line.lstrip("# ")) + f"</h{level}>")
        elif line.strip():
            parts.append("<p>" + html.escape(line) + "</p>")
    if in_list: parts.append("</ul>")
    if in_code: parts.append("</code></pre>")
    return ''.join(parts)

DISEASE_CLASSES = [
    ("AKIEC", "日光性角化症／表皮內癌"),
    ("BCC", "基底細胞癌"),
    ("BKL", "良性角化症樣病灶"),
    ("DF", "皮膚纖維瘤"),
    ("NV", "黑色素細胞痣"),
    ("VASC", "血管性病灶"),
    ("MEL", "黑色素瘤"),
]

SITE_CLASSES_ZH = {
    "head": "頭部",
    "torso": "軀幹",
    "upper_extremity": "上肢",
    "lower_extremity": "下肢",
    "hands_feet": "手／足",
}


class Predictor:
    def __init__(self, disease_checkpoint: Path, site_checkpoint: Path, device_name: str) -> None:
        self.disease_checkpoint = disease_checkpoint
        self.site_checkpoint = site_checkpoint
        self.device_name = device_name
        self.model_registry = load_model_registry(MODEL_LIBRARY_DIR)
        self.model_definitions = {item["id"]: item for item in self.model_registry.get("models", [])}
        self._disease_model = None
        self._disease_transform = None
        self._disease_model_id = None
        self._disease_definition = None
        self._site_model = None
        self._site_transform = None
        self._site_classes: list[str] = []
        self._device = None
        self._lock = threading.Lock()

    @property
    def disease_available(self) -> bool:
        return any(item.get("available", False) for item in self.model_definitions.values())

    def models_for_api(self) -> list[dict]:
        models = [
            {
                "id": item["id"],
                "name": item["name"],
                "group": item.get("group", "其他"),
                "architecture": item.get("architecture", ""),
                "image_size": item.get("image_size"),
                "available": item.get("available", False),
                "kind": "real",
                "class_count": len(self.model_registry.get("class_order", DISEASE_CLASSES)),
            }
            for item in self.model_registry.get("models", [])
        ]
        models.append({
            "id": "demo", "name": "展示模式（假資料）", "group": "展示",
            "architecture": "demo", "image_size": None, "available": True, "kind": "demo",
        })
        return models

    @property
    def site_available(self) -> bool:
        return self.site_checkpoint.is_file()

    def _runtime(self):
        import torch

        if self._device is None:
            if self.device_name == "auto":
                self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            else:
                self._device = torch.device(self.device_name)
        return torch, self._device

    def _load_disease(self, model_id: str) -> dict:
        if model_id == "real":
            model_id = self.model_registry.get("default_model", "mixed_convnext")
        definition = self.model_definitions.get(model_id)
        if not definition or not definition.get("available", False):
            raise FileNotFoundError(f"找不到可用疾病模型：{model_id}")
        if self._disease_model is not None and self._disease_model_id == model_id:
            return definition

        torch, device = self._runtime()
        self._disease_model = None
        self._disease_transform = None
        self._disease_definition = None
        self._disease_model_id = None
        gc.collect()
        if device.type == "cuda":
            torch.cuda.empty_cache()

        model, transform = build_model_from_definition(definition, PROJECT_ROOT)
        model.to(device).eval()
        self._disease_model = model
        self._disease_transform = transform
        self._disease_model_id = model_id
        self._disease_definition = definition
        return definition

    def _load_site(self) -> None:
        if self._site_model is not None:
            return
        if not self.site_available:
            raise FileNotFoundError(f"找不到部位模型：{self.site_checkpoint}")

        torch, device = self._runtime()
        from torch import nn
        from torchvision import transforms
        from torchvision.models import convnext_tiny

        checkpoint = torch.load(self.site_checkpoint, map_location="cpu", weights_only=False)
        classes = list(checkpoint["classes"])
        model = convnext_tiny(weights=None)
        model.classifier[2] = nn.Linear(model.classifier[2].in_features, len(classes))
        model.load_state_dict(checkpoint["model"], strict=True)
        model.to(device).eval()
        self._site_model = model
        self._site_classes = classes
        self._site_transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

    @staticmethod
    def _demo_scores(image_bytes: bytes, count: int, salt: bytes) -> list[float]:
        digest = hashlib.sha256(salt + image_bytes).digest()
        values = [digest[index] + 16 for index in range(count)]
        total = float(sum(values))
        return [value / total for value in values]

    @staticmethod
    def _ranked(labels: list[tuple[str, str]], scores: list[float]) -> list[dict]:
        if len(labels) != len(scores):
            raise ValueError("模型輸出類別數與登錄標籤不一致，請檢查模型定義。")
        result = [
            {"code": code, "label": label, "probability": float(probability)}
            for (code, label), probability in zip(labels, scores)
        ]
        return sorted(result, key=lambda item: item["probability"], reverse=True)

    def predict(
        self,
        image_bytes: bytes,
        model_id: str,
        include_site: bool,
        include_heatmap: bool,
        manual_site: str,
        experiment_tag: str,
        image_name: str = "",
    ) -> dict:
        from PIL import Image, ImageOps, UnidentifiedImageError

        started = time.perf_counter()
        try:
            with Image.open(io.BytesIO(image_bytes)) as opened:
                if opened.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("請上傳 JPG、PNG 或 WEBP 影像。")
                if opened.width * opened.height > MAX_IMAGE_PIXELS:
                    raise ValueError("影像超過 6,400 萬像素，請先縮小尺寸。")
                image = ImageOps.exif_transpose(opened).convert("RGB")
                width, height = image.size
        except (UnidentifiedImageError, OSError) as error:
            raise ValueError("無法讀取影像，檔案可能已損毀。") from error
        heatmap = {
            "requested": include_heatmap,
            "available": False,
            "method": "Grad-CAM",
            "target_class_code": "",
            "target_class_label": "",
            "layers": [],
            "overlay_data_url": "",
            "notice": "",
        }

        with self._lock:
            if model_id == "demo":
                disease_scores = self._demo_scores(image_bytes, len(DISEASE_CLASSES), b"disease")
                disease_mode = "展示模式（假資料）"
                site_scores = self._demo_scores(image_bytes, 5, b"site") if include_site else []
                site_labels = list(SITE_CLASSES_ZH)
                if include_heatmap:
                    heatmap["notice"] = "展示模式不會偽造熱力圖；請選擇可用的卷積疾病模型。"
            else:
                torch, device = self._runtime()
                definition = self._load_disease(model_id)
                model_id = definition["id"]
                tensor = self._disease_transform(image).unsqueeze(0).to(device)
                if include_heatmap:
                    try:
                        logits, activation_map, layers, reason = gradcam_prediction(
                            self._disease_model,
                            tensor,
                            definition,
                        )
                        if activation_map is not None:
                            target_index = int(logits.argmax(dim=1)[0].item())
                            target_code, target_label = DISEASE_CLASSES[target_index]
                            heatmap.update({
                                "available": True,
                                "target_class_code": target_code,
                                "target_class_label": target_label,
                                "layers": layers,
                                "overlay_data_url": overlay_data_url(image, activation_map),
                                "notice": "紅黃區域對最高機率類別分數影響較大；Grad-CAM 不是病灶分割，也不是因果或確診證據。",
                            })
                        else:
                            heatmap["notice"] = reason
                    except Exception as error:
                        with torch.inference_mode():
                            logits = self._disease_model(tensor)
                        heatmap["notice"] = f"熱力圖產生失敗，但疾病推論仍完成：{error}"
                else:
                    with torch.inference_mode():
                        logits = self._disease_model(tensor)
                disease_scores = torch.softmax(logits.detach(), dim=1)[0].float().cpu().tolist()
                if not torch.isfinite(logits).all().item():
                    raise ValueError("模型輸出包含非有限值，請改用其他模型並檢查權重。")
                disease_mode = definition["name"]
                site_scores = []
                site_labels = []
                if include_site:
                    self._load_site()
                    with torch.inference_mode():
                        site_tensor = self._site_transform(image).unsqueeze(0).to(device)
                        site_logits = self._site_model(site_tensor)
                        site_scores = torch.softmax(site_logits, dim=1)[0].float().cpu().tolist()
                        if not torch.isfinite(site_logits).all().item():
                            raise ValueError("部位模型輸出包含非有限值，請檢查權重。")
                    site_labels = self._site_classes

        disease = self._ranked(DISEASE_CLASSES, disease_scores)
        site = self._ranked(
            [(code, SITE_CLASSES_ZH.get(code, code)) for code in site_labels],
            site_scores,
        ) if include_site else []

        return {
            "prediction_id": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "experiment_tag": experiment_tag.strip() or "未命名",
            "model_id": model_id,
            "model_label": disease_mode,
            "device": str(self._device or "demo"),
            "image": {"width": width, "height": height, "bytes": len(image_bytes)},
            "image_name": image_name,
            "manual_site": manual_site,
            "disease": disease,
            "site": site,
            "heatmap": heatmap,
            "site_output_notice": "探索性部位輸出；DensePose 模型不是臨床定位器。" if include_site else "",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "medical_notice": "研究用途輸出，不構成醫療診斷。",
        }


class SkinDetectServer(ThreadingHTTPServer):
    def __init__(self, address, handler, predictor: Predictor, training_manager: TrainingManager, environment: str) -> None:
        super().__init__(address, handler)
        self.predictor = predictor
        self.training_manager = training_manager
        self.environment = environment
        self.history: list[dict] = []
        self.history_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server: SkinDetectServer

    def log_message(self, format_string: str, *args) -> None:
        print("[UI] " + format_string % args, flush=True)

    def _json(self, payload: dict | list, status: int = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"/", "/prototype/skin-detect", "/prototype/skin-detect/"} else request_path.lstrip("/")
        target = (STATIC_DIR / relative).resolve()
        if not target.is_relative_to(STATIC_DIR.resolve()) or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
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

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/manual-images/"):
            relative = unquote(path.removeprefix("/manual-images/"))
            target = (MANUAL_IMAGES_DIR / relative).resolve()
            if not target.is_relative_to(MANUAL_IMAGES_DIR.resolve()) or not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            data = target.read_bytes()
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix in {".html", ".md", ".json", ".txt"}:
                content_type += "; charset=utf-8"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        if path in {"/manual", "/manual.md"}:
            if path == "/manual" and (MANUAL_IMAGES_DIR / "index.html").is_file():
                self.send_response(HTTPStatus.FOUND)
                self.send_header("Location", "/manual-images/index.html")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if not MANUAL_PATH.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "Handbook unavailable")
                return
            text = MANUAL_PATH.read_text(encoding="utf-8-sig")
            if path == "/manual.md":
                content = text.encode("utf-8")
                content_type = "text/plain; charset=utf-8"
            else:
                content = ("<!doctype html><html lang='zh-Hant'><meta charset='utf-8'>"
                           "<meta name='viewport' content='width=device-width, initial-scale=1'>"
                           "<title>SkinDetect 使用手冊</title><link rel='stylesheet' href='/styles.css'>"
                           "<body><main class='manual-page'><nav><a href='/prototype/skin-detect'>返回 UI</a>"
                           " · <a href='/manual.md'>查看 Markdown 原檔</a></nav>" + render_manual(text) + "</main></body></html>").encode("utf-8")
                content_type = "text/html; charset=utf-8"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)
            return
        if path == "/api/health":
            self._json({
                "status": "ok",
                "environment": self.server.environment,
                "disease_checkpoint": self.server.predictor.disease_available,
                "site_checkpoint": self.server.predictor.site_available,
            })
            return
        if path == "/api/config":
            self._json({
                "environment": self.server.environment,
                "prototype_switcher": self.server.environment != "production",
                "variants": [
                    {"id": "A", "name": "實驗工作台"},
                    {"id": "B", "name": "單張檢測流程"},
                    {"id": "C", "name": "研究審查台"},
                ],
            })
            return
        if path == "/api/models":
            self._json({
                "models": self.server.predictor.models_for_api(),
                "default_model": self.server.predictor.model_registry.get("default_model", "demo"),
                "site_model": {
                    "id": "densepose_site",
                    "name": "DensePose 五類部位模型",
                    "available": self.server.predictor.site_available,
                },
            })
            return
        if path == "/api/history":
            with self.server.history_lock:
                self._json(list(reversed(self.server.history[-20:])))
            return
        if path == "/api/training/status":
            self._json(self.server.training_manager.status())
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
        self._serve_static(path)

    def do_POST(self) -> None:
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
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 30 * 1024 * 1024:
                raise ValueError("上傳內容必須小於 30 MB。")
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            arguments = prediction_payload(payload, self.server.predictor.model_registry.get("default_model", "demo"))
            result = self.server.predictor.predict(**arguments)
            with self.server.history_lock:
                self.server.history.append({
                    "prediction_id": result["prediction_id"],
                    "created_at": result["created_at"],
                    "experiment_tag": result["experiment_tag"],
                    "model_label": result["model_label"],
                    "model_id": result["model_id"],
                    "image_name": result["image_name"],
                    "top_disease": result["disease"][0],
                    "elapsed_ms": result["elapsed_ms"],
                })
                del self.server.history[:-50]
            self._json(result)
        except Exception as error:
            self._json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SkinDetect UI prototype")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument(
        "--environment",
        choices=("prototype", "production"),
        default=os.environ.get("SKINDETECT_ENV", "prototype"),
    )
    parser.add_argument(
        "--disease-checkpoint",
        type=Path,
        default=PROJECT_ROOT / "多來源混合訓練_第二版" / "results" / "imagenet_seed17" / "best.pt",
    )
    parser.add_argument(
        "--site-checkpoint",
        type=Path,
        default=PROJECT_ROOT / "重要資產" / "DensePose_五類部位Backbone_2026-08-24" / "densepose_true_seed17.pt",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    predictor = Predictor(
        disease_checkpoint=args.disease_checkpoint.resolve(),
        site_checkpoint=args.site_checkpoint.resolve(),
        device_name=args.device,
    )
    training_manager = TrainingManager(PROJECT_ROOT)
    server = SkinDetectServer((args.host, args.port), Handler, predictor, training_manager, args.environment)
    base_url = f"http://{args.host}:{args.port}/prototype/skin-detect"
    print("SkinDetect UI 已啟動", flush=True)
    print(base_url + "?variant=A", flush=True)
    print(base_url + "?variant=B", flush=True)
    print(base_url + "?variant=C", flush=True)
    if not args.no_open:
        threading.Timer(0.8, lambda: webbrowser.open(base_url + "?variant=A")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSkinDetect UI 已停止", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
