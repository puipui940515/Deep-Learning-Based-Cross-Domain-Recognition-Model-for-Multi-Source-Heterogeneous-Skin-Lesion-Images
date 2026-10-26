"""B 釋放 GPU 後的一次有界驗證：6 張既有 Validation + 兩模式獨立測速。"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .contract import ModelContract, sha256
from .core import SINGLE, ENSEMBLE, CLASS_CODES, combine_probabilities, ranked_probabilities
from .runtime import V2Predictor, gpu_idle_check

ATOL = 0.003  # 固定驗收容差：web batch1 對 C batch32 CUDA AMP，機率絕對差 0.3pp；不事後調整。


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def now(): return datetime.now(timezone.utc).isoformat()


def gpu_snapshot():
    reply = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu,pstate,temperature.gpu", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=8, check=True)
    return reply.stdout.strip()


def approved_validation_images(contract, cases):
    """只讀已知 train/validation Manifest，且只開啟選定的六張 Validation 原圖。"""
    manifest = contract.resolve("資料治理與泛化修復/data/governed_18979_20261018_v1/mixed_manifest.csv")
    if sha256(manifest) != contract.spec["manifest_sha256"]:
        raise RuntimeError("固定 train/validation Manifest 指紋不符")
    wanted = {(case["source"], case["record_id"]):case for case in cases}
    selected = {}
    with manifest.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["split"] not in {"train", "validation"}:
                raise RuntimeError("此發布檔不符合已知排除 Test 的契約")
            key = row["source"], row["record_id"]
            if key in wanted:
                if row["split"] != "validation" or row["image_path"] != wanted[key]["image_path"]:
                    raise RuntimeError("六張參照不屬於正式 Validation 或路徑不同")
                path = contract.resolve(row["image_path"])
                if not path.is_relative_to(contract.resolve("dataSets")) or sha256(path).lower() != row["sha256"].lower():
                    raise RuntimeError("選定 Validation 影像位置或 SHA 不符")
                selected[key] = path
    if set(selected) != set(wanted):
        raise RuntimeError("未找到完整六張 Validation 參照")
    return selected


def consistency(project, output, replay):
    contract = ModelContract(project)
    cases = replay["gpu_validation_cases"]
    images = approved_validation_images(contract, cases)
    predictor = V2Predictor(project, enabled=True)
    rows, passed, maximum, per_image_max = [], True, 0.0, {}
    try:
        for mode in (SINGLE, ENSEMBLE):
            for case in cases:
                key = case["source"], case["record_id"]
                path = images[key]
                result = predictor.predict(path.read_bytes(), mode, path.name)
                actual = {item["code"]: item["probability"] for item in result["disease"]}
                expected = case["seed_probabilities"]["1"] if mode == SINGLE else case["ensemble_probabilities"]
                error = max(abs(actual[code] - expected[i]) for i,code in enumerate(CLASS_CODES))
                # Ensemble 也逐成員核對，防止平均恰好掩蓋錯用某個 Seed。
                member_errors = {seed:max(abs(value - case["seed_probabilities"][seed][i]) for i,value in enumerate(vector))
                                 for seed,vector in result["member_probabilities"].items()}
                expected_top = ranked_probabilities(expected)[0]["code"]
                top_match = result["disease"][0]["code"] == expected_top
                row_passed = error <= ATOL and all(value <= ATOL for value in member_errors.values()) and top_match
                passed = passed and row_passed
                maximum = max(maximum, error, *member_errors.values())
                rows.append(dict(model_id=mode, source=key[0], record_id=key[1], image_sha256=sha256(path),
                                 probability_max_absolute_error=error, member_max_absolute_error=member_errors,
                                 expected_top1=expected_top, actual_top1=result["disease"][0]["code"], top1_matches=top_match,
                                 passed=row_passed))
    finally:
        if predictor.session is not None: predictor.session.close()
    report = dict(status="passed" if passed else "failed", created_at=now(), conditions=dict(web_batch=1, reference_batch=32,
                  image_size=224, cuda_amp=True, classes=list(CLASS_CODES), calibrated=False, tta=False,
                  probability_atol=ATOL, top1_exact_required=True, independent_of_training=True),
                  cases=rows, model_image_pairs=len(rows), max_probability_absolute_error=maximum,
                  reference_sha256=replay["reference_sha256"], contract_sha256=sha256(contract.path), test_read=False)
    write_new(output, report)
    if not passed: raise RuntimeError("真實輸出一致性未通過；已保存失敗，不放寬容差或繼續測速。")


def benchmark_worker(project, mode, case, output):
    gpu_idle_check()
    contract = ModelContract(project)
    image_path = approved_validation_images(contract,[case])[(case["source"],case["record_id"])]
    data = image_path.read_bytes()
    before = gpu_snapshot()
    predictor = V2Predictor(project,enabled=True)
    started = time.perf_counter()
    cold = predictor.predict(data,mode,image_path.name)
    cold_request_ms = (time.perf_counter()-started)*1000
    for _ in range(3): predictor.predict(data,mode,image_path.name)
    samples = [predictor.predict(data,mode,image_path.name)["timing"] for _ in range(10)]
    after = gpu_snapshot()
    torch = predictor.session.torch
    forward = sorted(sample["forward_and_softmax_ms"] for sample in samples)
    total = sorted(sample["total_ms"] for sample in samples)
    report = dict(status="passed",created_at=now(),model_id=mode,pid=os.getpid(),
                  process_isolated=True,contract_sha256=sha256(contract.path),
                  conditions=dict(image_source=case["source"],record_id=case["record_id"],image_sha256=sha256(image_path),
                                  input_size=224,batch=1,warmup_requests=3,measured_requests=10,cuda_amp=True,torch_threads=1,
                                  pretrained_download=False,calibrated=False,tta=False,
                                  cudnn_deterministic=torch.backends.cudnn.deterministic,cudnn_benchmark=torch.backends.cudnn.benchmark,
                                  allow_tf32_matmul=torch.backends.cuda.matmul.allow_tf32,allow_tf32_cudnn=torch.backends.cudnn.allow_tf32,
                                  cuda_version=torch.version.cuda,cudnn_version=torch.backends.cudnn.version(),versions=contract.spec["versions"],
                                  platform=platform.platform()),
                  cold_model_load_ms=cold["timing"]["model_load_ms_this_request"],cold_request_total_ms=cold_request_ms,
                  latency=dict(forward_softmax_median_ms=statistics.median(forward),forward_softmax_p95_ms=forward[-1],
                               end_to_end_median_ms=statistics.median(total),end_to_end_p95_ms=total[-1],samples=samples),
                  vram=dict(peak_allocated_bytes=max(s["vram"]["peak_allocated_bytes"] for s in samples),
                            peak_reserved_bytes=max(s["vram"]["peak_reserved_bytes"] for s in samples)),
                  gpu_before=before,gpu_after=after,test_read=False,
                  notes=["模型 cold load 包含程式匯入、契約/權重 SHA、CPU 建構/載入及 GPU 搬移；不代表清空 OS 磁碟快取。",
                         "forward 包含模型前向、float32 CPU softmax；端到端包含圖片解碼、前處理、搬移、排程檢查與等權計算，不含 HTTP/瀏覽器傳輸。",
                         "10 個樣本的 p95 採 nearest-rank，即本次最大值；少量樣本不代表長期服務 SLA。",
                         "PyTorch allocated/reserved 峰值是程序配置器資料；nvidia-smi 裝置用量包含桌面與其他非計算工作，不混為模型 VRAM。"])
    predictor.session.close()
    write_new(output,report)


def run_child(args, extra, log):
    command = [sys.executable,"-B","-u","-m","v2_inference.gpu_acceptance","--project",str(args.project),
               "--output-dir",str(args.output_dir),"--replay",str(args.replay),"--gpu-released",*extra]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(args.project / "ui_prototype") + os.pathsep + env.get("PYTHONPATH", "")
    if log.exists():
        log = log.with_name(log.stem + f"-attempt-{time.time_ns()}" + log.suffix)
    with log.open("x",encoding="utf-8") as handle:
        result = subprocess.run(command,stdout=handle,stderr=subprocess.STDOUT,timeout=300,env=env)
    if result.returncode: raise RuntimeError(f"GPU 子程序失敗，請讀 {log}；未自動重試。")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--replay",type=Path,required=True)
    parser.add_argument("--gpu-released",action="store_true",help="僅在確認 B 試跑已結束且 GPU 已釋放後使用")
    parser.add_argument("--worker",choices=["consistency",SINGLE,ENSEMBLE])
    args=parser.parse_args()
    if not args.gpu_released: raise SystemExit("需要先確認 B 已釋放 GPU；本程式沒有自動排程或輪詢。")
    contract=ModelContract(args.project)
    replay=json.loads(args.replay.read_text(encoding="utf-8-sig"))
    if replay["status"]!="passed" or replay["stage"]!="stored_score_adapter_replay": raise SystemExit("先沿用通過的 CPU 分數重播紀錄。")
    args.output_dir.mkdir(parents=True,exist_ok=True)
    if args.worker:
        if args.worker=="consistency": consistency(args.project,args.output_dir/"gpu_consistency.json",replay)
        else: benchmark_worker(args.project,args.worker,replay["gpu_validation_cases"][0],args.output_dir/(args.worker+"_benchmark.json"))
        return
    # 完成的收據直接沿用；失敗／指紋不同停止，不自動重跑任何已完成步驟。
    receipts=[("consistency","gpu_consistency.json"),(SINGLE,SINGLE+"_benchmark.json"),(ENSEMBLE,ENSEMBLE+"_benchmark.json")]
    for worker,name in receipts:
        path=args.output_dir/name
        if path.exists():
            existing=json.loads(path.read_text(encoding="utf-8"))
            if existing["status"]!="passed" or existing["contract_sha256"]!=sha256(contract.path): raise RuntimeError("既有收據失敗或契約不同，已停止。")
            continue
        gpu_idle_check()
        run_child(args,["--worker",worker],args.output_dir/(worker+".log"))
    acceptance=args.output_dir/"GPU_ACCEPTANCE.json"
    if not acceptance.exists():
        write_new(acceptance,dict(status="passed",created_at=now(),contract_sha256=sha256(contract.path),
                                  outputs={name:sha256(args.output_dir/name) for _,name in receipts},test_read=False))
    print(f"GPU acceptance completed: {acceptance}")


if __name__=="__main__": main()
