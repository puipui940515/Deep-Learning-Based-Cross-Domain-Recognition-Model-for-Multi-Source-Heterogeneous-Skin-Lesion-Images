import json, sys
from datetime import datetime, timezone
from pathlib import Path
import torch
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from stage3.models import build_v10_model, count_parameters
def main():
    config = json.loads((ROOT/"config/stage3.json").read_text(encoding="utf-8")); spec = config["versions"]["v10"]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_v10_model(config["num_classes"], spec["fusion_hidden_dim"], spec["fusion_dropout"], spec["gradient_checkpointing"]).to(device)
    image = torch.randn(spec["batch_size"], 3, spec["image_size"], spec["image_size"], device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["base_learning_rate"])
    report = {"checked_at_utc":datetime.now(timezone.utc).isoformat(), "purpose":"non_experimental_memory_smoke_test",
              "uses_v9_weights":False, "test_split_used":False, "device":str(device),
              "device_name":torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU",
              "image_size":spec["image_size"], "batch_size":spec["batch_size"],
              "gradient_checkpointing":spec["gradient_checkpointing"], "parameters":count_parameters(model)}
    try:
        if device.type == "cuda": torch.cuda.reset_peak_memory_stats()
        model.train(); optimizer.zero_grad(set_to_none=True); logits = model((image, image, image, image)); logits.sum().backward(); optimizer.step()
        report.update(passed=tuple(logits.shape)==(spec["batch_size"], config["num_classes"]), output_shape=list(logits.shape))
        if device.type == "cuda":
            report["peak_cuda_memory_bytes"] = torch.cuda.max_memory_allocated(); report["peak_cuda_memory_gib"] = round(torch.cuda.max_memory_allocated()/1024**3, 3)
            report["peak_cuda_reserved_bytes"] = torch.cuda.max_memory_reserved(); report["peak_cuda_reserved_gib"] = round(torch.cuda.max_memory_reserved()/1024**3, 3)
            report["optimizer_step_tested"] = True
    except torch.cuda.OutOfMemoryError as error: report.update(passed=False, error=f"CUDA OOM: {error}")
    output=ROOT/"results/memory_smoke_test.json"; output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2)); raise SystemExit(0 if report["passed"] else 1)
if __name__ == "__main__": main()
