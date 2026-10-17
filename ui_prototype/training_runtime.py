from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


TRAINING_FOLDER_NAME = "UI訓練任務"
TRAIN_SCRIPT_RELATIVE = Path("資料治理與泛化修復/scripts/train_regularized.py")
GATE_RELATIVE = Path("資料治理與泛化修復/reports/pipeline_gate.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_int(payload: dict, name: str, default: int, minimum: int, maximum: int) -> int:
    value = payload.get(name, default)
    if isinstance(value, bool):
        raise ValueError(f"{name} 必須是整數。")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} 必須是整數。") from error
    if isinstance(value, float) and value != parsed:
        raise ValueError(f"{name} 必須是整數，不能有小數。")
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} 必須介於 {minimum} 到 {maximum}。")
    return parsed


def _as_float(payload: dict, name: str, default: float, minimum: float, maximum: float) -> float:
    value = payload.get(name, default)
    if isinstance(value, bool):
        raise ValueError(f"{name} 必須是數值。")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} 必須是數值。") from error
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} 必須介於 {minimum} 到 {maximum}。")
    return parsed


def validate_parameters(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("訓練設定必須是 JSON 物件。")
    mode = str(payload.get("mode", "smoke"))
    if mode not in {"smoke", "formal"}:
        raise ValueError("mode 只能是 smoke 或 formal。")
    return {
        "mode": mode,
        "epochs": _as_int(payload, "epochs", 1 if mode == "smoke" else 12, 1, 100),
        "seed": _as_int(payload, "seed", 17, 0, 2_147_483_647),
        "batch_size": _as_int(payload, "batch_size", 16, 1, 64),
        "learning_rate": _as_float(payload, "learning_rate", 0.0001, 0.000001, 0.01),
        "weight_decay": _as_float(payload, "weight_decay", 0.05, 0.0, 0.5),
        "label_smoothing": _as_float(payload, "label_smoothing", 0.1, 0.0, 0.4),
        "mixup_alpha": _as_float(payload, "mixup_alpha", 0.2, 0.0, 1.0),
        "early_stopping_patience": _as_int(payload, "early_stopping_patience", 4, 1, 20),
    }


def build_command(project_root: Path, parameters: dict, output_root: Path) -> list[str]:
    command = [
        sys.executable,
        str(project_root / TRAIN_SCRIPT_RELATIVE),
        "--seed", str(parameters["seed"]),
        "--epochs", str(parameters["epochs"]),
        "--batch-size", str(parameters["batch_size"]),
        "--learning-rate", str(parameters["learning_rate"]),
        "--weight-decay", str(parameters["weight_decay"]),
        "--label-smoothing", str(parameters["label_smoothing"]),
        "--mixup-alpha", str(parameters["mixup_alpha"]),
        "--early-stopping-patience", str(parameters["early_stopping_patience"]),
        "--output-root", str(output_root),
    ]
    if parameters["mode"] == "smoke":
        command.extend(["--max-train-samples", "280", "--max-val-samples-per-source", "70"])
    return command


class TrainingManager:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.jobs_root = self.project_root / TRAINING_FOLDER_NAME
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.train_script = self.project_root / TRAIN_SCRIPT_RELATIVE
        self.gate_path = self.project_root / GATE_RELATIVE
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._log_handle = None
        self._job: dict | None = None

    def capabilities(self) -> dict:
        gate = {}
        if self.gate_path.is_file():
            try:
                gate = json.loads(self.gate_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                gate = {}
        return {
            "available": self.train_script.is_file() and bool(gate.get("passed")),
            "pipeline": "來源→重複洩漏→過擬合→設備與構圖差異",
            "model": "ConvNeXt-Tiny（ImageNet 初始化）",
            "dataset": "清理後 HAM10000＋BCN20000＋PAD-UFES-20",
            "clean_rows": gate.get("clean_rows"),
            "gate_passed": bool(gate.get("passed")),
            "defaults": validate_parameters({"mode": "formal"}),
            "limits": {
                "epochs": [1, 100], "batch_size": [1, 64],
                "learning_rate": [0.000001, 0.01], "weight_decay": [0.0, 0.5],
                "label_smoothing": [0.0, 0.4], "mixup_alpha": [0.0, 1.0],
                "early_stopping_patience": [1, 20],
            },
        }

    def _metadata_path(self, job: dict) -> Path:
        return self.jobs_root / job["job_id"] / "job.json"

    def _write_job(self, job: dict) -> None:
        target = self._metadata_path(job)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)

    def _tail_log(self, job: dict, line_limit: int = 80) -> list[str]:
        path = self.jobs_root / job["job_id"] / "stdout.log"
        if not path.is_file():
            return []
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 128 * 1024))
            text = handle.read().decode("utf-8", errors="replace")
        text = text.replace("\r", "\n")
        return [line for line in text.splitlines() if line.strip()][-line_limit:]

    def _public_job(self, job: dict | None) -> dict | None:
        if not job:
            return None
        public = dict(job)
        lines = self._tail_log(job)
        public["log_lines"] = lines
        epoch_matches = []
        for line in lines:
            epoch_matches.extend(re.findall(r"Epoch\s+(\d+)\s*/\s*(\d+)", line, flags=re.IGNORECASE))
        if epoch_matches:
            current, total = map(int, epoch_matches[-1])
            public["progress"] = {
                "epoch": current, "total_epochs": total,
                "percent": round(100 * max(0, current - 1) / max(total, 1), 1),
            }
        else:
            public["progress"] = {"epoch": 0, "total_epochs": job["parameters"]["epochs"], "percent": 0.0}
        if job["status"] == "completed":
            public["progress"]["percent"] = 100.0
        return public

    def _refresh_locked(self) -> None:
        if self._process is None or self._job is None:
            return
        code = self._process.poll()
        if code is None:
            return
        if self._job["status"] not in {"stopped", "failed", "completed"}:
            self._job["status"] = "completed" if code == 0 else "failed"
            self._job["exit_code"] = code
            self._job["finished_at"] = utc_now()
            self._write_job(self._job)

    def status(self) -> dict:
        with self._lock:
            self._refresh_locked()
            current = self._public_job(self._job)
        history = []
        for path in sorted(self.jobs_root.glob("*/job.json"), reverse=True)[:12]:
            try:
                item = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
            history.append(self._public_job(item))
        return {"capabilities": self.capabilities(), "current": current, "history": history}

    def start(self, payload: dict) -> dict:
        parameters = validate_parameters(payload)
        capabilities = self.capabilities()
        if not capabilities["available"]:
            raise RuntimeError("資料治理閘門未通過或訓練腳本不存在。")
        with self._lock:
            self._refresh_locked()
            if self._process is not None and self._process.poll() is None:
                raise RuntimeError("已有訓練任務執行中；請等待完成或先停止。")
            job_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
            job_dir = self.jobs_root / job_id
            output_root = job_dir / "outputs"
            job_dir.mkdir(parents=True, exist_ok=False)
            command = build_command(self.project_root, parameters, output_root)
            job = {
                "job_id": job_id, "status": "starting", "created_at": utc_now(),
                "started_at": None, "finished_at": None, "exit_code": None,
                "parameters": parameters,
                "output_directory": output_root.relative_to(self.project_root).as_posix(),
                "result_file": (output_root / f"regularized_seed{parameters['seed']}" / "result.json").relative_to(self.project_root).as_posix(),
            }
            self._write_job(job)
            log_path = job_dir / "stdout.log"
            self._log_handle = log_path.open("a", encoding="utf-8", buffering=1)
            environment = os.environ.copy()
            environment["PYTHONUTF8"] = "1"
            environment["PYTHONIOENCODING"] = "utf-8"
            try:
                self._process = subprocess.Popen(
                    command, cwd=str(self.project_root), stdout=self._log_handle,
                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=environment,
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                )
            except Exception:
                self._log_handle.close()
                self._log_handle = None
                job["status"] = "failed"
                job["finished_at"] = utc_now()
                self._write_job(job)
                raise
            job["status"] = "running"
            job["started_at"] = utc_now()
            job["pid"] = self._process.pid
            self._job = job
            self._write_job(job)
            threading.Thread(target=self._watch, args=(self._process, job_id), daemon=True).start()
            return self._public_job(job)

    def _watch(self, process: subprocess.Popen, job_id: str) -> None:
        code = process.wait()
        with self._lock:
            if self._job and self._job["job_id"] == job_id:
                if self._job["status"] != "stopped":
                    self._job["status"] = "completed" if code == 0 else "failed"
                self._job["exit_code"] = code
                self._job["finished_at"] = utc_now()
                self._write_job(self._job)
            if self._log_handle:
                self._log_handle.close()
                self._log_handle = None

    def stop(self) -> dict:
        with self._lock:
            self._refresh_locked()
            if self._process is None or self._job is None or self._process.poll() is not None:
                raise RuntimeError("目前沒有執行中的訓練任務。")
            self._job["status"] = "stopping"
            self._write_job(self._job)
            process = self._process
            job_id = self._job["job_id"]
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        with self._lock:
            if self._job and self._job["job_id"] == job_id:
                self._job["status"] = "stopped"
                self._job["exit_code"] = process.returncode
                self._job["finished_at"] = utc_now()
                self._write_job(self._job)
                return self._public_job(self._job)
        raise RuntimeError("訓練任務狀態已改變。")
