from __future__ import annotations

import ast
import difflib
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


CANDIDATE = Path(r"C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\acceptance\FRESH-PROCESS-A-OBSERVER-RUNTIME-CANDIDATE-20260919")
V9 = Path(r"C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\diagnostics\fresh-process-resume-20260911\v9")
OLD_ACCEPTANCE = Path(r"C:\Users\Administrator\Desktop\RaPO-author\docs\acceptance\FRESH-PROCESS-A-OBSERVER-DELTA-20260919")
OUT = Path(r"C:\Users\Administrator\Desktop\RaPO-author\docs\acceptance\FRESH-PROCESS-A-OBSERVER-RUNTIME-20260919")
MANIFEST_NAME = "RUNTIME_CANDIDATE_MANIFEST.json"
HASHES_NAME = "HASHES_RUNTIME.json"
CANDIDATE_OBSERVER_SHA = "e9c2f17115c44348d1e9e056ee8b3b0b691d2f4ce40e3af0f5ca483f4cd53bd1"
CANDIDATE_EVENT_WRITER_SHA = "e9fc45c8a605dd9451a7f90c533c4c1ed6b1d800a35822a659a7c68fa911df61"
CANDIDATE_MANIFEST_SHA = "e3417329860bbfb4dd43298b4d760e24caff60e39a3f93539d02b5071de7e338"
V9_HASHES_SHA = "45f79cbf83d004b6fd05c4e1ef61fe2f5b296dba1771aae24e45e570b890ee39"
PRODUCTION_SOURCE_SHA = "3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3"
RAY_VERSION = "2.46.0"
FORBIDDEN_LABELS = {
    "PersistentRunner.init",
    "PersistentRunner.restore_boundary_driver_rng",
    "PersistentCILTrainer.__init__",
    "PersistentCILTrainer._load_checkpoint",
    "PersistentCILTrainer.restore_boundary_checkpoint",
    "PersistentCILTrainer.reinit_for_task",
    "PersistentCILTrainer.fit",
    "PersistentCILTrainer._save_checkpoint",
    "_build_dataloader",
    "FSDPCheckpointManager.save_checkpoint",
    "FSDPWorker.save_checkpoint",
    "PersistentRefFSDPWorker.capture_boundary_vllm_rng",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def file_record(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(CANDIDATE).as_posix() if path.is_relative_to(CANDIDATE) else str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def verify_hashes_runtime() -> dict[str, Any]:
    payload = read_json(CANDIDATE / HASHES_NAME)
    expected = {item["path"]: item for item in payload.get("files", [])}
    actual = {
        path.relative_to(CANDIDATE).as_posix(): path
        for path in CANDIDATE.rglob("*")
        if path.is_file() and path.name != HASHES_NAME
    }
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    mismatches = []
    for relative, item in sorted(expected.items()):
        path = actual.get(relative)
        if path is None:
            continue
        actual_bytes = path.stat().st_size
        actual_sha = sha256_file(path)
        if actual_bytes != int(item.get("bytes", -1)) or actual_sha != item.get("sha256"):
            mismatches.append({"path": relative, "expected": item, "actual": {"bytes": actual_bytes, "sha256": actual_sha}})
    extra_categories = Counter(
        "pycache" if relative.startswith("__pycache__/") else "ray-temp" if "/ray-temp/" in relative else "other"
        for relative in extra
    )
    return {
        "declared_file_count": payload.get("file_count"),
        "declared_total_bytes": payload.get("total_bytes"),
        "entry_count": len(expected),
        "entry_total_bytes": sum(int(item.get("bytes", 0)) for item in expected.values()),
        "actual_nonself_file_count": len(actual),
        "actual_nonself_total_bytes": sum(path.stat().st_size for path in actual.values()),
        "missing": missing,
        "extra_count": len(extra),
        "extra_total_bytes": sum(actual[relative].stat().st_size for relative in extra),
        "extra_categories": dict(extra_categories),
        "mismatches": mismatches,
        "hashes_runtime_sha256": sha256_file(CANDIDATE / HASHES_NAME),
        "ok": not missing and not mismatches and len(expected) == int(payload.get("file_count", -1)) and sum(int(item.get("bytes", 0)) for item in expected.values()) == int(payload.get("total_bytes", -1)),
    }


def verify_candidate_manifest() -> dict[str, Any]:
    path = CANDIDATE / MANIFEST_NAME
    payload = read_json(path)
    expected = {item["path"]: item for item in payload.get("files", [])}
    missing = []
    mismatches = []
    escapes = []
    for relative, item in sorted(expected.items()):
        file_path = (CANDIDATE / relative).resolve()
        if file_path.parent != CANDIDATE.resolve():
            escapes.append(relative)
            continue
        if not file_path.is_file():
            missing.append(relative)
            continue
        actual = {"bytes": file_path.stat().st_size, "sha256": sha256_file(file_path)}
        if actual["bytes"] != int(item.get("bytes", -1)) or actual["sha256"] != item.get("sha256"):
            mismatches.append({"path": relative, "expected": item, "actual": actual})
    local_deps, missing_local_deps = import_closure(expected)
    runtime = payload.get("runtime", {})
    v9_hashes = V9 / "HASHES_v9.json"
    return {
        "manifest_sha256": sha256_file(path),
        "self_excluded": payload.get("self_excluded"),
        "declared_file_count": len(expected),
        "missing": missing,
        "escapes": escapes,
        "mismatches": mismatches,
        "local_import_closure": local_deps,
        "missing_local_imports": missing_local_deps,
        "production_source": payload.get("production_source"),
        "frozen_v9": payload.get("frozen_v9"),
        "runtime": runtime,
        "v9_hashes_local_sha256": sha256_file(v9_hashes) if v9_hashes.is_file() else None,
        "v9_hashes_matches_declared": v9_hashes.is_file() and sha256_file(v9_hashes) == payload.get("frozen_v9", {}).get("hashes_sha256"),
        "ok": payload.get("self_excluded") is True and not missing and not escapes and not mismatches and not missing_local_deps,
    }


def import_closure(expected: dict[str, Any]) -> tuple[dict[str, list[str]], list[str]]:
    names = {Path(relative).stem for relative in expected if relative.endswith(".py")}
    closure: dict[str, list[str]] = {}
    missing: list[str] = []
    for relative in sorted(expected):
        if not relative.endswith(".py"):
            continue
        path = CANDIDATE / relative
        tree = ast.parse(read_text(path), filename=str(path))
        local = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                local.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                local.add(node.module.split(".")[0])
        local_deps = sorted(dep for dep in local if dep in names and dep != path.stem)
        closure[relative] = local_deps
        for dep in local_deps:
            target = CANDIDATE / (dep + ".py")
            if not target.is_file():
                missing.append(f"{relative}->{dep}.py")
    return closure, sorted(set(missing))


def diff_summary() -> dict[str, Any]:
    v9_payload = read_json(V9 / "HASHES_v9.json")
    v9_entries = {item["path"]: item for item in v9_payload.get("files", [])}
    candidate_payload = read_json(CANDIDATE / HASHES_NAME)
    groups: dict[str, list[str]] = {"identical": [], "trailing_blank_only": [], "semantic_changed": [], "added_to_candidate": []}
    details: dict[str, Any] = {}
    for item in candidate_payload.get("files", []):
        relative = item["path"]
        if not relative.endswith(".py") or relative.startswith("raw/"):
            continue
        candidate_path = CANDIDATE / relative
        v9_path = V9 / relative
        if not v9_path.is_file():
            groups["added_to_candidate"].append(relative)
            continue
        candidate_bytes = candidate_path.read_bytes()
        v9_bytes = v9_path.read_bytes()
        if candidate_bytes == v9_bytes:
            groups["identical"].append(relative)
            continue
        candidate_lines = read_text(candidate_path).replace("\r\n", "\n").splitlines()
        v9_lines = read_text(v9_path).replace("\r\n", "\n").splitlines()
        normalized_equal = "\n".join(candidate_lines).rstrip() == "\n".join(v9_lines).rstrip()
        groups["trailing_blank_only" if normalized_equal else "semantic_changed"].append(relative)
        diff = list(difflib.unified_diff(v9_lines, candidate_lines, n=1))
        details[relative] = {"candidate_bytes": len(candidate_bytes), "v9_bytes": len(v9_bytes), "normalized_equal": normalized_equal, "diff_lines": len(diff), "diff_head": diff[:24]}
    return {"groups": groups, "details": details, "v9_hashes_sha256": sha256_file(V9 / "HASHES_v9.json"), "v9_entry_count": len(v9_entries)}


def read_events() -> tuple[list[dict[str, Any]], list[str], list[str]]:
    event_root = CANDIDATE / "raw" / "zero-gpu-real-ray-aob2" / "observer" / "events"
    records: list[dict[str, Any]] = []
    invalid: list[str] = []
    files = sorted(path.name for path in event_root.glob("events-*.jsonl"))
    for path in sorted(event_root.glob("events-*.jsonl")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                invalid.append(f"{path.name}:{line_no}:{exc}")
                continue
            record["_event_file"] = path.name
            record["_event_line"] = line_no
            records.append(record)
    return records, files, invalid


def event_summary() -> dict[str, Any]:
    records, files, invalid = read_events()
    result = read_json(CANDIDATE / "raw" / "zero-gpu-real-ray-aob2" / "result.json")
    bootstraps = [record for record in records if record.get("kind") == "child_bootstrap_install"]
    before = [record for record in records if record.get("kind") == "target_wrapper_call_before" and record.get("label") == "PersistentRunner.run_task"]
    after = [record for record in records if record.get("kind") == "target_wrapper_call_after" and record.get("label") == "PersistentRunner.run_task"]
    runner_events = [record for record in records if record.get("label") == "PersistentRunner.run_task"]
    runner_pid = before[0].get("pid") if before else None
    runner_start = before[0].get("process_start") if before else None
    runner_bootstraps = [record for record in bootstraps if record.get("pid") == runner_pid and record.get("process_start") == runner_start]
    worker_report = result.get("worker_report") or {}
    probe_pid = worker_report.get("pid")
    probe_bootstraps = [record for record in bootstraps if record.get("pid") == probe_pid and record.get("role") == "ray_worker"]
    forbidden = [record for record in records if record.get("kind") in {"target_wrapper_call_before", "target_wrapper_call_after"} and record.get("label") in FORBIDDEN_LABELS]
    constructor = [record for record in records if record.get("kind") in {"target_wrapper_call_before", "target_wrapper_call_after"} and record.get("label") == "PersistentRunner.__init__"]
    target_writer_ok = all(record.get("writer", {}).get("sha256") == CANDIDATE_EVENT_WRITER_SHA for record in runner_events)
    same_call = bool(before and after and before[0].get("call_id") == after[0].get("call_id") and before[0].get("pid") == after[0].get("pid") and before[0].get("process_start") == after[0].get("process_start"))
    exact_inert_error = bool(after and after[0].get("error") == "AttributeError: 'NoneType' object has no attribute '_task_id'")
    all_candidate_bootstrap = all(record.get("observer", {}).get("sha256") == CANDIDATE_OBSERVER_SHA and record.get("runtime_manifest", {}).get("sha256") == CANDIDATE_MANIFEST_SHA for record in bootstraps)
    runner_identity = {
        "pid": runner_pid,
        "process_start": runner_start,
        "target_event_roles": sorted({record.get("role") for record in runner_events}),
        "event_files": sorted({record.get("_event_file") for record in runner_events}),
        "matching_bootstrap_count": len(runner_bootstraps),
        "matching_bootstrap_roles": sorted({record.get("role") for record in runner_bootstraps}),
        "matching_bootstrap_stages": sorted({record.get("stage") for record in runner_bootstraps}),
        "candidate_observer_and_manifest": all(record.get("observer", {}).get("sha256") == CANDIDATE_OBSERVER_SHA and record.get("runtime_manifest", {}).get("sha256") == CANDIDATE_MANIFEST_SHA for record in runner_bootstraps),
    }
    return {
        "record_count": len(records),
        "event_file_count": len(files),
        "event_files": files,
        "invalid_json_lines": invalid,
        "kind_counts": dict(Counter(record.get("kind") for record in records)),
        "role_counts": dict(Counter(record.get("role") for record in records)),
        "bootstrap_count": len(bootstraps),
        "all_bootstraps_candidate_identity": all_candidate_bootstrap,
        "runner_identity": runner_identity,
        "probe_actor": {"pid": probe_pid, "bootstrap_count": len(probe_bootstraps), "is_distinct_from_runner": probe_pid != runner_pid, "role_stages": sorted({f"{record.get('role')}:{record.get('stage')}" for record in probe_bootstraps})},
        "run_task_before_count": len(before),
        "run_task_after_count": len(after),
        "run_task_same_call_pid_start": same_call,
        "run_task_exact_inert_error": exact_inert_error,
        "run_task_before_after": [{"kind": record.get("kind"), "pid": record.get("pid"), "process_start": record.get("process_start"), "role": record.get("role"), "call_id": record.get("call_id"), "error": record.get("error")} for record in before + after],
        "target_event_writer_identity": target_writer_ok,
        "forbidden_call_count": len(forbidden),
        "forbidden_labels": sorted({record.get("label") for record in forbidden}),
        "persistent_runner_constructor_event_count": len(constructor),
        "remote_wrapper_install_count": sum(record.get("kind") == "ray_remote_wrapper_install" for record in records),
        "driver_remote_wrapper_install_count": sum(record.get("kind") == "ray_remote_wrapper_install" and record.get("pid") == 3910612 for record in records),
        "raw_result_claims": {
            "status": result.get("status"),
            "ray_version": result.get("ray_version"),
            "gpu_requested": result.get("gpu_requested"),
            "num_cpus_requested": result.get("num_cpus_requested"),
            "non_target_results": result.get("non_target_results"),
            "release": result.get("release"),
            "required_conditions": result.get("required_conditions"),
        },
        "independent_conditions": {
            "record_and_file_counts_match_result": len(records) == result.get("event_count") and len(files) == len(result.get("event_files", [])) and files == result.get("event_files", []),
            "real_ray_version": result.get("ray_version") == RAY_VERSION,
            "zero_gpu": result.get("gpu_requested") is False,
            "candidate_identity_all_bootstraps": all_candidate_bootstrap,
            "production_runner_actor_bound_by_same_pid_start": bool(runner_bootstraps),
            "probe_actor_not_used_as_runner": probe_pid != runner_pid,
            "run_task_pair": len(before) == 1 and len(after) == 1 and same_call,
            "exact_inert_error": exact_inert_error,
            "forbidden_calls_zero": not forbidden,
            "non_target_values": result.get("non_target_results") == {"decorated_class": 8, "direct_class_options": 5, "direct_function": 10, "inherited_method": 15, "remote_exception_types": ["AssertionError", "AttributeError"]},
            "release_claims": result.get("release") == {"error": None, "ray_shutdown_called": True, "runner_killed": True},
        },
    }


def static_wiring() -> dict[str, Any]:
    run_v9 = read_text(CANDIDATE / "run_v9.py")
    runtime_entry = read_text(CANDIDATE / "runtime_entry_v6.py")
    bootstrap = read_text(CANDIDATE / "child_bootstrap_v6.py")
    launcher = read_text(CANDIDATE / "zero_gpu_real_ray_launcher.py")
    probe = read_text(CANDIDATE / "zero_gpu_real_ray_probe.py")
    manifest = read_json(CANDIDATE / MANIFEST_NAME)
    candidate_has_config = [(name, (CANDIDATE / name).is_file()) for name in ("PPO_CONFIG_TEMPLATE_v9.json", "EXPECTED_IDENTITY_v9.json")]
    v9_has_config = [(name, (V9 / name).is_file()) for name in ("PPO_CONFIG_TEMPLATE_v9.json", "EXPECTED_IDENTITY_v9.json")]
    return {
        "run_v9": {
            "candidate_root_in_path_list": "paths = [str(HERE.resolve()), str(source_root.resolve())]" in run_v9,
            "inherited_v9_appended_after_candidate": "paths.append(str(Path(inherited_v9).resolve()))" in run_v9,
            "runtime_root_bound": 'env["RAPO_DIAG_RUNTIME_ROOT"] = str(HERE.resolve())' in run_v9,
            "runtime_manifest_referenced": "RAPO_DIAG_RUNTIME_MANIFEST" in run_v9 or MANIFEST_NAME in run_v9,
            "manifest_verified_before_subprocess": "verify(" in run_v9 or "verify_manifest" in run_v9,
            "subprocess_launch_present": "subprocess.Popen" in run_v9,
        },
        "runtime_entry": {
            "candidate_observer_dir_reinserted_first": "sys.path.insert(0, str(observer_dir))" in runtime_entry,
            "production_source_inserted_after_candidate": "sys.path.insert(0, str(root))" in runtime_entry,
            "runtime_root_defaulted": 'RAPO_DIAG_RUNTIME_ROOT", str(observer_dir)' in runtime_entry,
        },
        "bootstrap": {
            "records_manifest": "RAPO_DIAG_RUNTIME_MANIFEST" in bootstrap,
            "verifies_manifest_contents": "verify" in bootstrap or "expected" in bootstrap,
        },
        "zero_gpu_probe_launcher": {
            "verifies_manifest": "def verify(" in launcher and "RUNTIME_CANDIDATE_MANIFEST.json" in launcher,
            "sets_manifest_env": 'RAPO_DIAG_RUNTIME_MANIFEST' in launcher,
            "zero_gpu_env": '"CUDA_VISIBLE_DEVICES": ""' in launcher,
        },
        "zero_gpu_probe": {
            "verifies_manifest": "def verify_manifest(" in probe,
            "sets_manifest_env": '"RAPO_DIAG_RUNTIME_MANIFEST"' in probe,
        },
        "config_resolution": {
            "candidate_has_ppo_or_expected": any(value for _, value in candidate_has_config),
            "candidate_config_files": candidate_has_config,
            "frozen_v9_config_files": v9_has_config,
            "manifest_path_priority": manifest.get("path_priority"),
        },
        "runtime_manifest_claim": manifest.get("runtime"),
        "candidate_manifest_hash": sha256_file(CANDIDATE / MANIFEST_NAME),
    }


def old_reference_comparison() -> dict[str, Any]:
    old = read_json(OLD_ACCEPTANCE / "raw" / "local-validation.json")
    verdict = read_json(OLD_ACCEPTANCE / "VERDICT.json")
    return {
        "old_real_ray_probe": old.get("real_ray_probe"),
        "old_delta_dispatch_ready": verdict.get("delta_dispatch_ready"),
        "old_overall": verdict.get("overall"),
        "new_raw_real_ray_status": read_json(CANDIDATE / "raw" / "zero-gpu-real-ray-aob2" / "result.json").get("status"),
        "new_raw_ray_version": read_json(CANDIDATE / "raw" / "zero-gpu-real-ray-aob2" / "result.json").get("ray_version"),
        "new_manifest_sha": sha256_file(CANDIDATE / MANIFEST_NAME),
        "new_observer_sha": CANDIDATE_OBSERVER_SHA,
    }


def main() -> None:
    result = {
        "schema": "fresh-process-a-observer-runtime-independent-incremental-review-v1",
        "reviewed_at": "2026-09-19",
        "scope": {"read_only": True, "new_ssh": False, "gpu": False, "model": False, "training": False, "install": False, "cpu_budget": "necessary local checks only"},
        "candidate": {"root": str(CANDIDATE), "manifest_sha256": sha256_file(CANDIDATE / MANIFEST_NAME), "observer_sha256": CANDIDATE_OBSERVER_SHA, "production_source_sha256_declared": PRODUCTION_SOURCE_SHA, "frozen_v9_hashes_sha256_declared": V9_HASHES_SHA},
        "delivery_hashes": verify_hashes_runtime(),
        "candidate_manifest": verify_candidate_manifest(),
        "source_diffs": diff_summary(),
        "events": event_summary(),
        "static_wiring": static_wiring(),
        "old_reference_comparison": old_reference_comparison(),
        "verdict": {
            "overall": "NOT_READY_FOR_BOUNDED_A_ONLY",
            "real_ray_zero_gpu_dispatch": "INDEPENDENTLY_CORROBORATED",
            "a_actual_postpublication_driver_rng": "NOT_RUN_AND_REQUIRED",
            "production_launcher_manifest_guard": "MISSING_IN_RUN_V9",
            "two_gpu_runtime_wiring": "NOT_ESTABLISHED_BY_ZERO_GPU_MANIFEST",
            "minimal_actions": [
                "Add a fail-closed candidate-manifest/content verification in the production run_v9 path before subprocess execution, and set RAPO_DIAG_RUNTIME_MANIFEST there.",
                "Use frozen v9 PPO_CONFIG_TEMPLATE_v9.json and EXPECTED_IDENTITY_v9.json explicitly from the frozen v9 root; never search candidate or fall back to an old observer.",
                "Run the new candidate-bound A-only two-step sequence on two GPUs and derive actual post-publication driver_rng_expected from the new observer after-event.",
            ],
        },
    }
    output = OUT / "raw" / "independent_review.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"overall": result["verdict"]["overall"], "manifest_ok": result["candidate_manifest"]["ok"], "hashes_ok": result["delivery_hashes"]["ok"], "events": result["events"]["record_count"], "runner_pair": result["events"]["independent_conditions"]["run_task_pair"], "production_launcher_manifest_guard": result["static_wiring"]["run_v9"]["manifest_verified_before_subprocess"]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
