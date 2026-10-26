"""本機展示與 V2 API；預設不啟動真實模型，沒有訓練控制路由。"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from v2_inference.core import MODES, InferenceError
from v2_inference.runtime import MAX_IMAGE_BYTES, V2Predictor

MAX_BODY = 29 * 1024 * 1024


def parse_request(payload):
    if not isinstance(payload, dict):
        raise InferenceError("INVALID_REQUEST", "請求內容必須是 JSON 物件。")
    mode = payload.get("model_id")
    if not isinstance(mode, str) or mode not in MODES:
        raise InferenceError("UNKNOWN_MODEL", "請選擇原 Seed1 或原三 Seed 等權 Ensemble。")
    name = payload.get("image_name", "")
    if not isinstance(name, str) or len(name) > 200:
        raise InferenceError("INVALID_REQUEST", "影像名稱須為 200 字內文字。")
    value = payload.get("image_data_url")
    if not isinstance(value, str) or "," not in value:
        raise InferenceError("INVALID_IMAGE", "缺少影像。")
    header, encoded = value.split(",", 1)
    if header not in {"[EMBEDDED_IMAGE_OMITTED] "[EMBEDDED_IMAGE_OMITTED] "[EMBEDDED_IMAGE_OMITTED]
        raise InferenceError("INVALID_IMAGE", "只接受 JPG、PNG 或 WebP。")
    if len(encoded) > ((MAX_IMAGE_BYTES + 2) // 3) * 4:
        raise InferenceError("INVALID_IMAGE", "影像超過 20 MB。", 413)
    try:
        data = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise InferenceError("INVALID_IMAGE", "影像編碼無效。") from error
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise InferenceError("INVALID_IMAGE", "影像須有內容且不超過 20 MB。", 413)
    return data, mode, name


class EnsembleServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, frontend, predictor):
        self.frontend, self.predictor = Path(frontend).resolve(), predictor
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def reply(self, status, value):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in {"/api/v2/models", "/api/v2/health"}:
            self.reply(200, self.server.predictor.catalog())
            return
        if path.startswith("/api/"):
            self.reply(404, {"error": "此服務沒有這個 API。", "code": "NOT_FOUND"})
            return
        relative = "index.html" if path == "/" else unquote(path).lstrip("/")
        try:
            target = (self.server.frontend / relative).resolve()
            if not target.is_relative_to(self.server.frontend) or not target.is_file() or target.suffix not in {".html", ".css", ".js", ".svg", ".png", ".webp", ".jpg"}:
                self.reply(404, {"error": "找不到檔案。", "code": "NOT_FOUND"})
                return
            data = target.read_bytes()
        except (OSError, ValueError):
            self.reply(404, {"error": "找不到檔案。", "code": "NOT_FOUND"})
            return
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if urlsplit(self.path).path != "/api/v2/predict":
            self.reply(404, {"error": "沒有訓練或其他寫入路由。", "code": "NOT_FOUND"})
            return
        origin = self.headers.get("Origin")
        if origin is not None and origin != "http://" + self.headers.get("Host", ""):
            self.reply(403, {"error": "只接受同源的本機網站請求。", "code": "ORIGIN_REJECTED"})
            return
        try:
            if self.headers.get_content_type() != "application/json":
                raise InferenceError("INVALID_REQUEST", "請使用 application/json。", 415)
            if self.headers.get("Transfer-Encoding"):
                raise InferenceError("INVALID_REQUEST", "不接受分塊請求。")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as error:
                raise InferenceError("INVALID_REQUEST", "Content-Length 無效。") from error
            if not 0 < length <= MAX_BODY:
                raise InferenceError("INVALID_REQUEST", "請求過大或沒有內容。", 413)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise InferenceError("INVALID_REQUEST", "請求未完整傳送。")
            try:
                payload = json.loads(raw)
            except (ValueError, UnicodeError) as error:
                raise InferenceError("INVALID_REQUEST", "JSON 內容無效。") from error
            result = self.server.predictor.predict(*parse_request(payload))
            self.reply(200, result)
        except InferenceError as error:
            if error.status == 500:
                traceback.print_exc()
            self.reply(error.status, {"error": str(error), "code": error.code, "is_mock": False})
        except Exception:
            traceback.print_exc()
            self.reply(500, {"error": "服務執行失敗，沒有回傳 mock 結果。", "code": "SERVER_FAILURE", "is_mock": False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument("--enable-models", action="store_true", help="僅在確認 B 已釋放 GPU 後使用；否則維持關閉。")
    args = parser.parse_args()
    predictor = V2Predictor(args.project, enabled=args.enable_models, device=args.device)
    server = EnsembleServer(("127.0.0.1", args.port), args.project / "ui_prototype/static/showcase_v1", predictor)
    print(f"SkinDetect V2 frontend: http://127.0.0.1:{args.port}/index.html", flush=True)
    print(f"Real model execution: {'ENABLED - verify B released GPU' if args.enable_models else 'DISABLED - CPU preview only'}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if predictor.session is not None:
            predictor.session.close()


if __name__ == "__main__":
    main()
