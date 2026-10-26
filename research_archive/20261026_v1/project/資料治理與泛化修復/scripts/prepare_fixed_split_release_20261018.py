"""Versioned extraction, original historical reproduction, and fixed-split SHA-256 governance.

No split algorithm is implemented here. The supplied reproduction script assigns
splits. Existing project helpers provide hashing, label metadata and group audits.
"""
from pathlib import Path, PurePosixPath
from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(r"D:\SkinDetect_base")
TASK = Path(r"[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md")
OUT = TASK / "outputs"
RUNTIME = TASK / "work/split-audit-deps"
sys.path.insert(0, str(RUNTIME))
VERSION = "18979_20261018_v1"
EXTRACT = ROOT / f"dataSets/BCN20000/images/historical_{VERSION}"
HIST = ROOT / f"資料治理與泛化修復/data/historical_{VERSION}"
GOV = ROOT / f"資料治理與泛化修復/data/governed_{VERSION}"
SOURCE_SCRIPT = Path(r"[USER_HOME]\Downloads\reproduce_dataset_split.py")
ZIP = ROOT / "dataSets/BCN20000/BCN_20k_train.zip"
REFERENCE = "e1d994cf3904fc6cf93b0f994d0b1b9b0b2c44888348c734f5a669a648164d7e"
SCRIPT_SHA = "c04cb936cb4171a7091b9856890d4c5b6916dd15fdcc2a1405f6535a30eea321"

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

definition = module("fixed_release_existing_definition", ROOT / "資料治理與泛化修復/scripts/data_definition.py")
mixed = module("fixed_release_existing_mixed", ROOT / "多來源混合訓練_第二版/scripts/build_manifest_v2.py")
read = definition.read_csv
sha = mixed.sha256

def write_json(path, value):
    with path.open("x", encoding="utf-8") as h:
        json.dump(value, h, ensure_ascii=False, indent=2)

def write_csv(path, rows, fields=None):
    fields = fields or list(rows[0])
    with path.open("x", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields, extrasaction="raise")
        w.writeheader()
        w.writerows(rows)

def original_inputs():
    audit = json.loads((OUT / "manifest_input_audit_20261018.json").read_text(encoding="utf-8"))
    result = {}
    for name, info in audit["input_files"].items():
        if name.startswith(("dataSets/HAM10000/", "dataSets/BCN20000/", "dataSets/PAD-UFES-20/", "資料治理與泛化修復/schema/")):
            actual = sha(ROOT / name).lower()
            assert actual == info["sha256"], f"Original input changed: {name}"
            result[name] = actual
    assert sha(SOURCE_SCRIPT).lower() == SCRIPT_SHA, "Reproduction script changed"
    import numpy, sklearn
    assert numpy.__version__ == "1.26.4" and sklearn.__version__ == "1.5.1"
    return result

def identity(rows):
    ordered = sorted(rows, key=lambda r: (r["source"], r["split"], r["image_id"]))
    return hashlib.sha256("\n".join(f"{r['source']}\t{r['image_id']}\t{r['label']}\t{r['split']}" for r in ordered).encode()).hexdigest()

def counts(rows):
    return {s: {p: sum(r["source"] == s and r["split"] == p for r in rows) for p in ["train", "validation", "test"]} for s in ["HAM10000", "BCN20000", "PAD-UFES-20"]}

def extract():
    original_inputs()
    assert not EXTRACT.exists(), f"Refusing existing extraction destination: {EXTRACT}"
    metadata = read(ROOT / "dataSets/BCN20000/bcn_20k_train.csv")
    needed = {Path(r["bcn_filename"]).stem for r in metadata if r["diagnosis"] in mixed.BCN_MAP}
    assert len(needed) == 11982
    before = ZIP.stat()
    print("Checking original BCN ZIP fingerprint", flush=True)
    zip_before = sha(ZIP)
    extracted = []
    with zipfile.ZipFile(ZIP) as archive:
        selected = [i for i in archive.infolist() if not i.is_dir() and Path(i.filename).stem in needed and Path(i.filename).suffix.lower() in {".jpg", ".jpeg", ".png"}]
        assert len(selected) == len({Path(i.filename).stem for i in selected}) == len(needed)
        for i in selected:
            member = PurePosixPath(i.filename.replace("\\", "/"))
            assert not member.is_absolute() and ".." not in member.parts and ":" not in str(member)
            target = EXTRACT.joinpath(*member.parts).resolve()
            assert target.is_relative_to(EXTRACT.resolve())
        assert shutil.disk_usage(ROOT).free > sum(i.file_size for i in selected) + 1024**3
        EXTRACT.mkdir(parents=True, exist_ok=False)
        for number, info in enumerate(sorted(selected, key=lambda i: i.filename), 1):
            target = EXTRACT.joinpath(*PurePosixPath(info.filename).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            digest, size = hashlib.sha256(), 0
            with archive.open(info) as src, target.open("xb") as dst:
                for block in iter(lambda: src.read(1024 * 1024), b""):
                    dst.write(block)
                    digest.update(block)
                    size += len(block)
            assert size == info.file_size
            extracted.append({"image_id": target.stem, "zip_member": info.filename, "image_path": target.relative_to(ROOT).as_posix(), "bytes": size, "sha256": digest.hexdigest().upper(), "zip_crc32": f"{info.CRC:08X}", "mtime_ns": target.stat().st_mtime_ns})
            if number % 2000 == 0 or number == len(selected):
                print(f"BCN extraction and CRC read: {number}/{len(selected)}", flush=True)
    assert ZIP.stat().st_size == before.st_size and ZIP.stat().st_mtime_ns == before.st_mtime_ns
    print("Confirming original ZIP unchanged", flush=True)
    assert sha(ZIP) == zip_before
    write_csv(EXTRACT / "extraction_inventory.csv", extracted)
    write_json(EXTRACT / "extraction_summary.json", {"images": len(extracted), "bytes": sum(r["bytes"] for r in extracted), "original_zip": str(ZIP), "original_zip_sha256_before_and_after": zip_before, "source_zip_unchanged": True, "all_selected_members_streamed_to_eof_and_crc_checked": True, "unselected_SCC_images_left_in_zip": 431, "existing_files_overwritten": False})

def reproduce():
    inputs = original_inputs()
    assert (EXTRACT / "extraction_summary.json").is_file()
    assert not HIST.exists(), f"Refusing existing history output: {HIST}"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(RUNTIME) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    command = [sys.executable, str(SOURCE_SCRIPT), "--ham", str(ROOT / "dataSets/HAM10000"), "--ham-metadata", str(ROOT / "dataSets/HAM10000/HAM10000_metadata.csv"), "--bcn", str(EXTRACT), "--bcn-metadata", str(ROOT / "dataSets/BCN20000/bcn_20k_train.csv"), "--pad", str(ROOT / "dataSets/PAD-UFES-20"), "--pad-metadata", str(ROOT / "dataSets/PAD-UFES-20/metadata.csv"), "--output", str(HIST)]
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True)
    print(result.stdout, flush=True)
    if result.stderr:
        print(result.stderr, flush=True)
    assert result.returncode == 0, "Historical reproduction failed; no governance step permitted"
    rows = read(HIST / "train.csv") + read(HIST / "validation.csv") + read(HIST / "test.csv")
    assert identity(rows) == REFERENCE
    assert Counter(r["split"] for r in rows) == Counter({"train": 18979, "validation": 3621, "test": 1503})
    assert not mixed.audit_group_leakage(rows)
    with (HIST / "reproduce_dataset_split.py").open("xb") as h:
        h.write(SOURCE_SCRIPT.read_bytes())
    with (HIST / "execution_log.txt").open("x", encoding="utf-8") as h:
        h.write(result.stdout + result.stderr)
    write_json(HIST / "provenance.json", {"command": command, "cwd": str(ROOT), "date": "2026-10-18", "source_script_sha256": SCRIPT_SHA, "input_hashes": inputs, "reference_identity_sha256": REFERENCE, "training_started": False, "policy": "Immutable historical IDs, labels and split assignments; known duplicates/conflicts preserved for reproduction only.", "output_hashes": {f.name: sha(f).lower() for f in HIST.iterdir() if f.is_file()}})

def load_source_records():
    extracted = {r["image_id"]: r for r in read(EXTRACT / "extraction_inventory.csv")}
    result = {}
    for source, file, idkey, diagkey in [("HAM10000", "HAM10000_metadata.csv", "image_id", "dx"), ("BCN20000", "bcn_20k_train.csv", "bcn_filename", "diagnosis"), ("PAD-UFES-20", "metadata.csv", "img_id", "diagnostic")]:
        folder = ROOT / "dataSets" / source
        index = {f.stem: f for f in folder.rglob("*") if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png"}}
        for meta in read(folder / file):
            ident = Path(meta[idkey]).stem
            raw = meta[diagkey]
            mapping = definition.DISEASE_MAP.get((source, raw.upper()))
            assert mapping is not None or raw.upper() == "SCC", f"Unmapped label: {source}/{ident}/{raw}"
            code = definition.CLASS_INFO[mapping[0]][0] if mapping else "SCC"
            if source == "BCN20000" and ident not in extracted:
                location = f"dataSets/BCN20000/BCN_20k_train.zip::bcn_20k_train/{Path(meta[idkey]).name}"
            else:
                location = index[ident].relative_to(ROOT).as_posix()
            key = f"{source}::{ident}"
            assert key not in result
            result[key] = {"source": source, "image_id": ident, "group_id": meta["patient_id"] if source == "PAD-UFES-20" else meta["lesion_id"], "canonical": code, "mapping": mapping, "raw_diagnosis": raw, "meta": meta, "location": location}
            assert result[key]["group_id"].strip(), f"Missing reliable grouping ID: {key}"
    assert len(result) == 24726
    return result

def group_checks(rows):
    group, lesion, patient = defaultdict(set), defaultdict(set), defaultdict(set)
    for r in rows:
        source = r["source"]
        group[(source, r["group_id"])].add(r["split"])
        if r["patient_id"]:
            patient[(source, r["patient_id"])].add(r["split"])
        key = (source, r["patient_id"], r["lesion_id"]) if source == "PAD-UFES-20" else (source, r["lesion_id"])
        lesion[key].add(r["split"])
    return {"split_group_cross_split": sum(len(v)>1 for v in group.values()), "available_patient_id_cross_split": sum(len(v)>1 for v in patient.values()), "scoped_lesion_key_cross_split": sum(len(v)>1 for v in lesion.values())}

def derive():
    original_inputs()
    assert not GOV.exists(), f"Refusing existing governed output: {GOV}"
    historical = read(HIST / "train.csv") + read(HIST / "validation.csv") + read(HIST / "test.csv")
    assert identity(historical) == REFERENCE, "Historical identity mismatch"
    assert Counter(r["split"] for r in historical) == Counter({"train":18979,"validation":3621,"test":1503})
    source_records = load_source_records()
    cache = {r["image_id"]: r for r in read(EXTRACT / "extraction_inventory.csv")}
    hash_members = defaultdict(list)
    file_hashes = {}
    print("Auditing all labeled-source image bytes, including excluded SCC", flush=True)
    with zipfile.ZipFile(ZIP) as archive:
        for number, (key, rec) in enumerate(source_records.items(), 1):
            if "::" in rec["location"]:
                _, member = rec["location"].split("::", 1)
                digest = hashlib.sha256()
                with archive.open(member) as h:
                    for block in iter(lambda: h.read(1024*1024), b""):
                        digest.update(block)
                value = digest.hexdigest().upper()
            elif rec["source"] == "BCN20000":
                f = ROOT / rec["location"]
                cached = cache[rec["image_id"]]
                assert f.stat().st_size == int(cached["bytes"]) and f.stat().st_mtime_ns == int(cached["mtime_ns"])
                value = sha(f)
                assert value == cached["sha256"], f"Extracted content changed: {key}"
            else:
                value = sha(ROOT / rec["location"])
            file_hashes[key] = value
            hash_members[value].append(key)
            if number % 4000 == 0 or number == len(source_records):
                print(f"Source byte-hash audit: {number}/{len(source_records)}", flush=True)
    reasons = defaultdict(set)
    duplicates = []
    for key, rec in source_records.items():
        if rec["mapping"] is None:
            reasons[key].add("outside_approved_7class_mapping")
    for digest, keys in sorted(hash_members.items()):
        if len(keys) < 2:
            continue
        labels = {source_records[k]["canonical"] for k in keys}
        duplicates.append({"sha256": digest, "record_ids": keys, "labels": sorted(labels), "cross_source": len({source_records[k]["source"] for k in keys})>1})
        if len(labels) > 1:
            for key in keys:
                reasons[key].add("exact_duplicate_diagnosis_conflict_pending_review")
        else:
            keep = min(keys, key=lambda k:(source_records[k]["image_id"], source_records[k]["source"]))
            for key in keys:
                if key != keep:
                    reasons[key].add("same_label_exact_duplicate_noncanonical")
    approved = {r["record_id"]: set(r["reasons"].split(";")) for r in read(OUT / "approved_exclusions_20261018.csv")}
    assert dict(reasons) == approved, "Content or rule result differs from approved exclusions; stop for review"
    historical_ids = {f"{r['source']}::{r['image_id']}": r for r in historical}
    assert len(historical_ids) == len(historical) == 24103
    enriched = []
    fingerprints = []
    for number, row in enumerate(historical):
        key = f"{row['source']}::{row['image_id']}"
        rec = source_records[key]
        assert Path(row["image_path"]).resolve() == (ROOT / rec["location"]).resolve()
        assert str(rec["mapping"][0]) == row["label"] and rec["canonical"] == row["label_name"]
        base = {**row, "row_id":str(number), "diagnosis_original":rec["raw_diagnosis"], "image_path":rec["location"], "license":"CC BY-NC 4.0" if row["source"]=="HAM10000" else "CC BY 4.0", "split_origin":f"historical_{VERSION};identity={REFERENCE};no_reassignment"}
        value = definition.unify_row(base, rec["meta"])
        value["diagnosis_original"] = rec["raw_diagnosis"]
        value["patient_id"] = rec["meta"].get("patient_id", "")
        value["lesion_id"] = rec["meta"]["lesion_id"]
        value["lesion_record_key"] = json.dumps([row["source"], value["patient_id"], value["lesion_id"]] if row["source"]=="PAD-UFES-20" else [row["source"],value["lesion_id"]], ensure_ascii=False, separators=(",", ":"))
        value["original_metadata_json"] = json.dumps(rec["meta"], ensure_ascii=False, sort_keys=True)
        value["original_site_value"] = rec["meta"].get("localization", rec["meta"].get("anatom_site_general", rec["meta"].get("region", "")))
        value["sha256"] = file_hashes[key]
        value["historical_identity_sha256"] = REFERENCE
        value["historical_split"] = row["split"]
        value["data_role"] = "sealed_test" if row["split"]=="test" else "fit" if row["split"]=="train" else "model_selection"
        value["training_eligible"] = "false" if row["split"]=="test" or key in reasons else "true"
        value["leakage_status"] = "excluded_fixed_split_sha256_audit" if key in reasons else "passed_fixed_split_sha256_group_audit_20261018"
        value["exclusion_reason"] = ";".join(sorted(reasons.get(key, set())))
        enriched.append(value)
        fingerprints.append({"record_id":key,"image_path":rec["location"],"sha256":file_hashes[key],"bytes":(ROOT/rec["location"]).stat().st_size})
    kept = [r for r in enriched if r["record_id"] not in reasons]
    assert Counter(r["split"] for r in kept) == Counter({"train":18919,"validation":3611,"test":1502})
    before_groups, after_groups = group_checks(enriched), group_checks(kept)
    assert not any(before_groups.values()) and not any(after_groups.values()), "Patient or scoped lesion leakage; do not reassign splits"
    for group in json.loads((OUT/"approved_exclusion_summary_20261018.json").read_text(encoding="utf-8"))["cross_group_link_constraints"]:
        splits = {historical_ids[k]["split"] for k in historical_ids if any(source_records[k]["source"]==g[0] and source_records[k]["group_id"]==g[2] for g in group["linked_source_groups"])}
        assert len(splits) <= 1, "Known connected groups cross fixed splits; stop"
    kept_hashes = defaultdict(list)
    historical_hashes = defaultdict(list)
    for r in enriched:
        historical_hashes[r["sha256"]].append(r)
    for r in kept:
        kept_hashes[r["sha256"]].append(r)
    cross_before = [h for h,rs in historical_hashes.items() if len({r["split"] for r in rs})>1]
    cross_after = [h for h,rs in kept_hashes.items() if len({r["split"] for r in rs})>1]
    assert not cross_before and not cross_after, "Exact image content crosses splits; stop"
    assert all(len(rs)==1 for rs in kept_hashes.values()), "Duplicate content remains after approved rules"
    assert all(r["split"] == historical_ids[r["record_id"]]["split"] for r in kept)
    contract = json.loads((ROOT/"資料治理與泛化修復/schema/data_contract_v1.json").read_text(encoding="utf-8"))
    fit_rows = [r for r in kept if r["split"] != "test"]
    for r in fit_rows:
        assert set(contract["required_training_columns"]) <= set(r)
        assert r["split"] in contract["split_values"] and r["training_eligible"]=="true"
    definition_audit = definition.audit(fit_rows, [])
    assert definition_audit["passed"], "Existing metadata definition audit failed"
    samples=[]
    from PIL import Image
    for source in ["HAM10000", "BCN20000", "PAD-UFES-20"]:
        candidates=sorted([r for r in kept if r["source"]==source], key=lambda r:r["image_id"])
        for r in [candidates[0],candidates[len(candidates)//2],candidates[-1]]:
            with Image.open(ROOT/r["image_path"]) as image:
                image.load()
                image.convert("RGB")
                samples.append({"record_id":r["record_id"],"size":image.size,"readable":True})
    assert len(samples)==9
    original_inputs()
    extraction_summary=json.loads((EXTRACT/"extraction_summary.json").read_text(encoding="utf-8"))
    assert sha(ZIP)==extraction_summary["original_zip_sha256_before_and_after"]
    GOV.mkdir(parents=True, exist_ok=False)
    write_csv(GOV/"mixed_manifest.csv", fit_rows)
    write_csv(GOV/"test.csv", [r for r in kept if r["split"]=="test"])
    exclusions=[]
    for key, rs in sorted(reasons.items()):
        rec=source_records[key]
        exclusions.append({"record_id":key,"source":rec["source"],"image_id":rec["image_id"],"patient_id":rec["meta"].get("patient_id",""),"lesion_id":rec["meta"]["lesion_id"],"group_id":rec["group_id"],"diagnosis_original":rec["raw_diagnosis"],"diagnosis_canonical_code":rec["canonical"],"historical_split":historical_ids[key]["split"] if key in historical_ids else "not_in_historical_seven_class_manifest","source_location":rec["location"],"sha256":file_hashes[key],"exclusion_reason":";".join(sorted(rs)),"original_metadata_json":json.dumps(rec["meta"],ensure_ascii=False,sort_keys=True)})
    write_csv(GOV/"exclusions.csv", exclusions)
    write_csv(GOV/"image_sha256.csv", fingerprints)
    write_json(GOV/"duplicate_audit.json", {"input_source_images_hashed":len(source_records),"exact_duplicate_groups":duplicates,"all_source_label_conflict_groups":sum(len(g["labels"])>1 for g in duplicates),"historical_exact_cross_split_groups":len(cross_before),"governed_exact_cross_split_groups":len(cross_after),"governed_duplicate_content_groups":0,"near_duplicate_or_pixel_hash_audit_performed":False})
    write_json(GOV/"data_definition_audit.json", definition_audit)
    report={"release_id":f"governed_{VERSION}","date":"2026-10-18","data_preparation_completed":True,"historical_manifest_directory":str(HIST),"governed_manifest_directory":str(GOV),"historical_identity_sha256":REFERENCE,"historical_reference_verified":True,"before_counts":counts(enriched),"after_counts":counts(kept),"after_totals":dict(Counter(r["split"] for r in kept)),"historical_rows_excluded":sum(r["record_id"] in reasons for r in enriched),"all_source_rows_excluded_including_SCC":len(exclusions),"exclusion_reason_counts_overlapping":dict(Counter(reason for rs in reasons.values() for reason in rs)),"before_group_checks":before_groups,"after_group_checks":after_groups,"split_assignments_preserved":True,"exact_duplicate_content_cross_split":0,"same_content_remaining_after_dedup":0,"available_patient_and_scoped_lesion_isolation_passed":True,"PAD_split_group":"patient_id","PAD_lesion_record_key":["patient_id","lesion_id"],"PAD_cross_patient_standalone_lesion_id_reuse_extra_exclusions":0,"test_excluded_from_training_manifest":True,"lightweight_image_samples":samples,"all_manifest_image_paths_exist":all((ROOT/r["image_path"]).is_file() for r in kept),"original_metadata_and_mapping_hashes_unchanged":True,"original_ZIP_unchanged":True,"source_reproduction_script_unchanged":True,"models_training_code_and_hyperparameters_modified":False,"training_started":False,"runtime":{"python":sys.executable,"dependency_directory":str(RUNTIME)},"limitations":["Byte-exact SHA-256 duplication and provided group identifiers audited; perceptual/decoded-pixel near-duplicates not audited.","HAM and BCN lack patient identifiers; their isolation is lesion-level, not verified patient-level.","Image decoding was sampled (9 images), not a full-image decode audit.","Raw HAM localization preserved in original_site_value/original_metadata_json; no new anatomical mapping inferred. Existing normalized HAM anatomical site remains unknown when absent in its expected input schema.","Training settings and gates are unchanged; a training entry must explicitly select this version. The accurate leakage status is not the old pipeline's release approval."],"input_hashes":original_inputs(),"provenance_code_sha256":sha(Path(__file__)).lower()}
    write_json(GOV/"summary.json",report)
    write_json(GOV/"file_hashes.json",{f.name:sha(f).lower() for f in GOV.iterdir() if f.is_file()})
    print(json.dumps({k:report[k] for k in ["after_counts","after_totals","historical_rows_excluded","after_group_checks","split_assignments_preserved","exact_duplicate_content_cross_split"]},ensure_ascii=False,indent=2),flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--stage",choices=["extract","historical","governed","all"],required=True)
    args=p.parse_args()
    if args.stage in {"extract","all"}:extract()
    if args.stage in {"historical","all"}:reproduce()
    if args.stage in {"governed","all"}:derive()

if __name__=="__main__":
    main()
