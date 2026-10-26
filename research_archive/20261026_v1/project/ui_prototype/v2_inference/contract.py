"""唯讀核對原基線與程式指紋；不讀 Manifest 成員、不反序列化模型。"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from .core import CLASS_CODES, InferenceError


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def function_sha(path, function, validation_branch=False):
    tree = ast.parse(Path(path).read_text(encoding="utf-8-sig"))
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == function)
    if validation_branch:
        node = next(item for item in node.body if isinstance(item, ast.If) and ast.unparse(item.test) == "not train")
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


class ModelContract:
    def __init__(self, project, path=None):
        self.project = Path(project).resolve()
        self.path = Path(path) if path else Path(__file__).with_name("models_v1.json")
        self.spec = read_json(self.path)
        if tuple(self.spec["class_order"]) != CLASS_CODES:
            raise InferenceError("CONTRACT_MISMATCH", "模型契約的七類順序錯誤。", 503)

    def resolve(self, relative):
        path = (self.project / relative).resolve()
        if not path.is_relative_to(self.project):
            raise InferenceError("CONTRACT_MISMATCH", "模型契約路徑超出專案。", 503)
        return path

    def validate(self, seeds, weights=False):
        """weights=False 只讀小型 metadata；weights=True 才讀指定 best.pt bytes 作 SHA。"""
        try:
            cfg = read_json(self.resolve(self.spec["config"]["path"]))
            if sha256(self.resolve(self.spec["config"]["path"])) != self.spec["config"]["sha256"]:
                raise ValueError("原基線配置指紋不同")
            training = cfg["training"]
            if (tuple(cfg["class_names"]), training["model"], training["initialization"], training["image_size"],
                    training["normalization"], training["transform"]) != (CLASS_CODES, "convnextv2_tiny", "imagenet", 224, "imagenet_mean_std", "regularized_native"):
                raise ValueError("架構、七類或前處理不同")
            for source in self.spec["source_contracts"]:
                path = self.resolve(source["path"])
                observed = function_sha(path, source["function"], source.get("validation_branch", False))
                if observed != source["ast_sha256"]:
                    raise ValueError(f"正式前處理／builder 有改變：{source['path']}:{source['function']}")
            for seed in seeds:
                member = self.spec["members"][str(seed)]
                for field in ("run_inputs", "result"):
                    if sha256(self.resolve(member[field]["path"])) != member[field]["sha256"]:
                        raise ValueError(f"Seed {seed} {field} 指紋不同")
                run = read_json(self.resolve(member["run_inputs"]["path"]))["contract"]
                result = read_json(self.resolve(member["result"]["path"]))
                if (run["seed"], run["run_id"], run["architecture"], run["initialization"], tuple(run["data"]["class_names"]),
                        run["data"]["manifest_sha256"], result["status"], result["test_used"], result["best"]["epoch"]) != (
                        seed, member["run_id"], "convnextv2_tiny_7_class", "imagenet", CLASS_CODES,
                        self.spec["manifest_sha256"], "completed", False, member["best_epoch"]):
                    raise ValueError(f"Seed {seed} 身分與正式最佳輪不同")
                if run["training"] != training:
                    raise ValueError("run_inputs 與原配置不符")
                checkpoint = self.resolve(member["checkpoint"]["path"])
                if not checkpoint.is_file() or checkpoint.stat().st_size != member["checkpoint"]["size_bytes"]:
                    raise ValueError(f"Seed {seed} best.pt 不存在或尺寸不同")
                if weights and sha256(checkpoint) != member["checkpoint"]["sha256"]:
                    raise ValueError(f"Seed {seed} best.pt SHA256 不符")
            return cfg
        except (OSError, KeyError, ValueError, StopIteration, TypeError) as error:
            raise InferenceError("CONTRACT_MISMATCH", f"原 V2 契約檢查失敗：{error}", 503) from error
