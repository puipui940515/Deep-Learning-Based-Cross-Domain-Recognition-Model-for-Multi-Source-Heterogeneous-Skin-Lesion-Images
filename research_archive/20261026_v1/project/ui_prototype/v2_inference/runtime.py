"""延遲載入原 V2；預設封鎖真實模型執行，CPU 驗收不會 import torch。"""
from __future__ import annotations

import importlib.metadata
import csv
import io
import os
import subprocess
import sys
import threading
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

from .contract import ModelContract, read_json, sha256
from .core import MODES, NAMES, MEDICAL_NOTICE, InferenceError, combine_probabilities, ranked_probabilities

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 64_000_000
# 本機 WDDM 的 nvidia-smi 將下列已核對桌面程序也列為 C+G，不能用「任何 PID」當訓練中。
# 僅允許這些具名桌面程序；python.exe、其他運算器與所有未知名稱仍封鎖。
DESKTOP_GPU_PROCESSES = frozenset(name.lower() for name in (
    "ShellHost.exe", "CrossDeviceResume.exe", "explorer.exe", "SearchHost.exe", "StartMenuExperienceHost.exe",
    "msedgewebview2.exe", "PhoneExperienceHost.exe", "TextInputHost.exe", "Blitz.exe", "WidgetBoard.exe",
    "OverwolfBrowser.exe", "ShellExperienceHost.exe", "EdgeGameAssist.exe", "ChatGPT.exe",
    "codex-computer-use-swift.exe", "WindowsTerminal.exe", "ApplicationFrameHost.exe", "SystemSettings.exe",
    "Overwolf.exe", "vgtray.exe", "RazerAppEngine.exe", "Discord.exe"))


def gpu_idle_check():
    """只查 nvidia-smi，不建立 CUDA context；不干擾、不終止別人的程序。"""
    try:
        reply = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=8, check=True)
        other = []
        for row in csv.reader(reply.stdout.splitlines(), skipinitialspace=True):
            if not row: continue
            if len(row) != 2 or not row[0].strip().isdigit():
                raise InferenceError("GPU_STATUS_UNKNOWN", "GPU 程序清單格式不明，已停止。", 503)
            if int(row[0]) != os.getpid() and PureWindowsPath(row[1].strip()).name.lower() not in DESKTOP_GPU_PROCESSES:
                other.append(int(row[0]))
        if other:
            raise InferenceError("GPU_BUSY", "其他程序正在使用 GPU；請等待 B 釋放，不啟動模型。", 503)
    except (OSError, subprocess.SubprocessError) as error:
        raise InferenceError("GPU_STATUS_UNKNOWN", "無法確認 GPU 排程，已停止真實推論。", 503) from error


def open_rgb(data):
    """沿用 Validation 的 RGB 語意：不加 EXIF 旋轉、裁切或測試增強。"""
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise InferenceError("INVALID_IMAGE", "影像須有內容且不超過 20 MB。")
    from PIL import Image, UnidentifiedImageError
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise InferenceError("INVALID_IMAGE", "只接受 JPG、PNG 或 WebP。")
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise InferenceError("INVALID_IMAGE", "影像超過 6,400 萬像素。")
                return image.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise InferenceError("INVALID_IMAGE", "影像損毀或尺寸過大。") from error


class TorchSession:
    """只有明確開啟執行的請求才會建立；完整使用既有正式 builder/Validation transform。"""
    def __init__(self, contract, device="cuda"):
        self.contract, self.device_name = contract, device
        self.models, self.mode = {}, None
        self.load_ms, self.torch, self.device = None, None, None

    def prepare(self, mode):
        if self.mode == mode:
            return 0.0
        started = time.perf_counter()
        seeds = MODES[mode]
        if self.device_name == "cuda":
            gpu_idle_check()
        cfg = self.contract.validate(seeds, weights=True)
        for package, version in self.contract.spec["versions"].items():
            if importlib.metadata.version(package) != version:
                raise InferenceError("ENVIRONMENT_MISMATCH", f"{package} 版本不同於正式 run_inputs。", 503)
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        import torch
        self.torch = torch
        if self.device_name == "cuda" and not torch.cuda.is_available():
            raise InferenceError("CUDA_UNAVAILABLE", "CUDA 不可用，不自動改用 CPU。", 503)
        self.device = torch.device(self.device_name)
        torch.set_num_threads(1)
        scripts = self.contract.resolve("資料治理與泛化修復/scripts")
        for directory in (self.contract.resolve("第二階段/src"), scripts):
            if str(directory) not in sys.path:
                sys.path.insert(0, str(directory))
        from model_profiles import construct_model
        from train_regularized import build_transform
        from stage2.engine import seed_everything
        self.close()
        self.transform = build_transform(224, False)
        try:
            for seed in seeds:
                seed_everything(seed)  # 沿用 C 參照的 cuDNN deterministic=True、benchmark=False。
                member = self.contract.spec["members"][str(seed)]
                checkpoint = torch.load(self.contract.resolve(member["checkpoint"]["path"]), map_location="cpu", weights_only=True)
                if (checkpoint["seed"], checkpoint["epoch"], checkpoint["run_id"], checkpoint["architecture"],
                        checkpoint["initialization"], checkpoint["test_used"], checkpoint["data_provenance"]["manifest_sha256"],
                        tuple(checkpoint["data_provenance"]["class_names"])) != (
                        seed, member["best_epoch"], member["run_id"], "convnextv2_tiny_7_class", "imagenet", False,
                        self.contract.spec["manifest_sha256"], tuple(self.contract.spec["class_order"])):
                    raise InferenceError("CHECKPOINT_MISMATCH", "Checkpoint 的 Seed／最佳輪／架構／資料不符。", 503)
                model = construct_model(cfg, restore=True)
                model.load_state_dict(checkpoint["model"], strict=True)
                self.models[seed] = model.to(self.device).eval()
                del checkpoint
            self.synchronize()
            self.mode = mode
            self.load_ms = (time.perf_counter() - started) * 1000
            return self.load_ms
        except Exception:
            self.close()
            raise

    def synchronize(self):
        if self.torch is not None and self.device_name == "cuda":
            self.torch.cuda.synchronize(self.device)

    def score(self, image):
        torch = self.torch
        if self.device_name == "cuda":
            gpu_idle_check()
            torch.cuda.reset_peak_memory_stats(self.device)
        self.synchronize()
        started = time.perf_counter()
        tensor = self.transform(image).unsqueeze(0).to(self.device)
        self.synchronize()
        preprocessing_ms = (time.perf_counter() - started) * 1000
        forward_start = time.perf_counter()
        scores = {}
        with torch.inference_mode():
            for seed, model in self.models.items():
                with torch.amp.autocast(device_type=self.device.type, enabled=self.device.type == "cuda"):
                    logits = model(tensor)
                # C 紀錄同樣先 float32 CPU logits，再 softmax；不在 fp16 上做機率正規化。
                logits_cpu = logits.detach().float().cpu()
                if not torch.isfinite(logits_cpu).all().item() or tuple(logits_cpu.shape) != (1, 7):
                    raise InferenceError("INVALID_SCORES", "模型 logits 形狀或數值錯誤。", 500)
                scores[seed] = logits_cpu.softmax(-1)[0].tolist()
        self.synchronize()
        memory = None
        if self.device_name == "cuda":
            memory = dict(allocated_bytes=torch.cuda.memory_allocated(self.device),
                          reserved_bytes=torch.cuda.memory_reserved(self.device),
                          peak_allocated_bytes=torch.cuda.max_memory_allocated(self.device),
                          peak_reserved_bytes=torch.cuda.max_memory_reserved(self.device))
        return scores, dict(preprocessing_and_transfer_ms=preprocessing_ms,
                            forward_and_softmax_ms=(time.perf_counter() - forward_start) * 1000,
                            vram=memory)

    def close(self):
        self.models.clear()
        self.mode = None
        if self.torch is not None and self.device_name == "cuda":
            self.torch.cuda.empty_cache()


class V2Predictor:
    def __init__(self, project, enabled=False, device="cuda", session_factory=TorchSession):
        self.contract = ModelContract(project)
        self.enabled, self.device, self.session_factory = enabled, device, session_factory
        self.session = None
        self.lock = threading.Lock()

    def catalog(self):
        receipt = self.contract.project / "ui_prototype/validation/ensemble_20261021_v1/GPU_ACCEPTANCE.json"
        gpu_validated = False
        if receipt.is_file():
            try:
                accepted = read_json(receipt)
                gpu_validated = accepted["status"] == "passed" and accepted["contract_sha256"] == sha256(self.contract.path)
                for name, expected in accepted["outputs"].items():
                    if Path(name).name != name or sha256(receipt.parent / name) != expected:
                        gpu_validated = False
            except (OSError, KeyError, ValueError, TypeError):
                gpu_validated = False
        try:
            self.contract.validate((1, 2, 3), weights=False)
            artifacts_ok, reason = True, None
        except InferenceError as error:
            artifacts_ok, reason = False, str(error)
        if not self.enabled:
            reason = ("GPU 驗證已通過；服務目前為預覽模式，真實推論未開啟。" if gpu_validated else
                      "真實模型執行尚未開啟；等待 B 釋放 GPU 並完成 GPU 驗證。") + ("" if artifacts_ok else " " + str(reason))
        return dict(api_version="v2-ensemble-v1", execution_enabled=self.enabled, artifacts_metadata_ok=artifacts_ok,
                    pending_gpu_validation=not gpu_validated, class_order=list(self.contract.spec["class_order"]),
                    preprocessing=self.contract.spec["preprocessing"], medical_notice=MEDICAL_NOTICE,
                    models=[dict(id=mode, name=NAMES[mode], seeds=list(seeds), weights=[1 / len(seeds)] * len(seeds),
                                 available=self.enabled and artifacts_ok, reason=reason) for mode, seeds in MODES.items()])

    def predict(self, data, mode, image_name=""):
        if not isinstance(mode, str) or mode not in MODES:
            raise InferenceError("UNKNOWN_MODEL", "不支援的模型版本。")
        if not self.enabled:
            raise InferenceError("EXECUTION_DISABLED", "真實推論尚未開啟；請等待 B 釋放 GPU，勿將 mock 當作模型結果。", 503)
        if not isinstance(image_name, str) or len(image_name) > 200:
            raise InferenceError("INVALID_REQUEST", "影像名稱必須為 200 字內文字。")
        if not self.lock.acquire(blocking=False):
            raise InferenceError("INFERENCE_BUSY", "另一張影像正在推論，請稍後再試。", 503)
        try:
            started = time.perf_counter()
            image = open_rgb(data)
            decode_ms = (time.perf_counter() - started) * 1000
            if self.session is None:
                self.session = self.session_factory(self.contract, self.device)
            load_ms = self.session.prepare(mode)
            scores, timing = self.session.score(image)
            output = combine_probabilities(mode, scores)
            elapsed_ms = (time.perf_counter() - started) * 1000
            return dict(api_version="v2-ensemble-v1", is_mock=False, model_id=mode, model_label=NAMES[mode],
                        created_at=datetime.now(timezone.utc).isoformat(), device=self.device, calibrated=False,
                        checkpoint_version=self.contract.spec["version"], class_order=list(self.contract.spec["class_order"]),
                        members=[dict(seed=seed, weight=1 / len(MODES[mode]), best_epoch=self.contract.spec["members"][str(seed)]["best_epoch"],
                                      checkpoint_sha256=self.contract.spec["members"][str(seed)]["checkpoint"]["sha256"]) for seed in MODES[mode]],
                        image_name=image_name, image=dict(width=image.width, height=image.height, bytes=len(data)),
                        disease=ranked_probabilities(output), member_probabilities={str(seed):list(vector) for seed,vector in scores.items()},
                        heatmap=dict(available=False, requested=False, method="Grad-CAM", overlay_data_url="", notice="本輪未串接 Grad-CAM。"),
                        medical_notice=MEDICAL_NOTICE, elapsed_ms=elapsed_ms,
                        timing=dict(decode_ms=decode_ms, model_load_ms_this_request=load_ms, total_ms=elapsed_ms, **timing))
        except InferenceError:
            raise
        except Exception as error:
            # 模型失敗後清空 cache，下一次不沿用半載入／不明狀態。
            if self.session is not None:
                self.session.close()
            raise InferenceError("MODEL_FAILURE", "模型執行失敗；已停止本次推論，請檢查本機日誌。", 500) from error
        finally:
            self.lock.release()
