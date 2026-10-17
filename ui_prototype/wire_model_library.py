from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "ui_prototype" / "server.py"


def replace_once(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError("找不到預期的模型資產庫接線位置")
    return text.replace(old, new, 1)


def main() -> None:
    text = SERVER.read_text(encoding="utf-8-sig")
    text = replace_once(text, "import base64\nimport hashlib", "import base64\nimport gc\nimport hashlib")
    text = replace_once(
        text,
        "from urllib.parse import unquote, urlparse\n",
        "from urllib.parse import unquote, urlparse\n\nfrom model_runtime import build_model_from_definition, load_model_registry\n",
    )
    text = replace_once(
        text,
        'EXPERIMENT_REGISTRY = EXPERIMENT_LIBRARY_DIR / "registry.json"',
        'EXPERIMENT_REGISTRY = EXPERIMENT_LIBRARY_DIR / "registry.json"\nMODEL_LIBRARY_DIR = PROJECT_ROOT / "模型資產庫"',
    )
    text = replace_once(
        text,
        '''        self._disease_model = None
        self._disease_transform = None
        self._site_model = None''',
        '''        self.model_registry = load_model_registry(MODEL_LIBRARY_DIR)
        self.model_definitions = {item["id"]: item for item in self.model_registry.get("models", [])}
        self._disease_model = None
        self._disease_transform = None
        self._disease_model_id = None
        self._disease_definition = None
        self._site_model = None''',
    )
    text = replace_once(
        text,
        '''    @property
    def disease_available(self) -> bool:
        return self.disease_checkpoint.is_file()

    @property
    def site_available(self) -> bool:''',
        '''    @property
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
            }
            for item in self.model_registry.get("models", [])
        ]
        models.append({
            "id": "demo", "name": "展示模式（假資料）", "group": "展示",
            "architecture": "demo", "image_size": None, "available": True, "kind": "demo",
        })
        return models

    @property
    def site_available(self) -> bool:''',
    )
    old_loader = '''    def _load_disease(self) -> None:
        if self._disease_model is not None:
            return
        if not self.disease_available:
            raise FileNotFoundError(f"找不到疾病模型：{self.disease_checkpoint}")

        torch, device = self._runtime()
        stage2_src = PROJECT_ROOT / "第二階段" / "src"
        sys.path.insert(0, str(stage2_src))
        from stage2.data import build_transform
        from stage2.models import build_model

        checkpoint = torch.load(self.disease_checkpoint, map_location="cpu", weights_only=False)
        model = build_model("convnext_tiny", pretrained=False, num_classes=7)
        model.load_state_dict(checkpoint["model"], strict=True)
        model.to(device).eval()
        self._disease_model = model
        self._disease_transform = build_transform(224, train=False)
'''
    new_loader = '''    def _load_disease(self, model_id: str) -> dict:
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
'''
    text = replace_once(text, old_loader, new_loader)
    text = replace_once(
        text,
        '''                torch, device = self._runtime()
                self._load_disease()
                with torch.inference_mode():''',
        '''                torch, device = self._runtime()
                definition = self._load_disease(model_id)
                model_id = definition["id"]
                with torch.inference_mode():''',
    )
    text = replace_once(
        text,
        '                disease_mode = "多來源 ConvNeXt-Tiny／ImageNet"',
        '                disease_mode = definition["name"]',
    )
    old_api = '''                "models": [
                    {
                        "id": "mixed_convnext",
                        "name": "多來源 ConvNeXt-Tiny",
                        "available": self.server.predictor.disease_available,
                        "kind": "real",
                    },
                    {
                        "id": "demo",
                        "name": "展示模式（假資料）",
                        "available": True,
                        "kind": "demo",
                    },
                ],'''
    new_api = '''                "models": self.server.predictor.models_for_api(),'''
    text = replace_once(text, old_api, new_api)
    SERVER.write_text(text, encoding="utf-8")
    print("模型資產庫接線完成")


if __name__ == "__main__":
    main()
