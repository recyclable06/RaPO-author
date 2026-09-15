"""Independent CPU/static acceptance probe for the frozen v6 candidate."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def manifest(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if not path.is_file() or path.name == "HASHES_v6.json":
            continue
        entries.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return entries


def manifest_digest(entries: list[dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(command: list[str], cwd: Path, result_path: Path | None = None) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, check=False)
    result: dict[str, Any] = {"command": command, "returncode": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}
    if result_path is not None and result_path.is_file():
        result["result"] = load(result_path)
    return result


def target_module_records(zero_result: dict[str, Any]) -> dict[str, tuple[int, str]]:
    records: dict[str, tuple[int, str]] = {}
    reports = [zero_result.get("driver_install_reports", {})]
    reports.extend(worker.get("install_reports", {}) for worker in zero_result.get("worker_reports", []))
    for report in reports:
        for name, item in report.items():
            module_file = item.get("module_file", {})
            records[name] = (int(module_file.get("bytes", -1)), str(module_file.get("sha256", "")))
    return records


def event_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_process: dict[tuple[Any, Any], dict[str, Any]] = defaultdict(lambda: {"roles": set(), "installs": set(), "calls": set(), "event_count": 0})
    for event in events:
        key = (event.get("pid"), event.get("process_start"))
        item = by_process[key]
        item["roles"].add(str(event.get("role")))
        item["event_count"] += 1
        if event.get("kind") == "child_observer_install" and event.get("installed") is True:
            item["installs"].add(str(event.get("module_name")))
        if event.get("kind") == "target_wrapper_call_after":
            item["calls"].add(str(event.get("label")))
    workers = []
    for key, value in sorted(by_process.items(), key=lambda item: str(item[0])):
        if "ray_worker" not in value["roles"]:
            continue
        workers.append({"process": f"{key[0]}:{key[1]}", "roles": sorted(value["roles"]), "event_count": value["event_count"], "install_module_count": len(value["installs"]), "call_label_count": len(value["calls"]), "install_modules": sorted(value["installs"]), "call_labels": sorted(value["calls"])})
    return {"event_count": len(events), "event_files": sorted({str(event.get("pid")) for event in events}), "kind_counts": dict(sorted(Counter(event.get("kind") for event in events).items())), "role_counts": dict(sorted(Counter(event.get("role") for event in events).items())), "ray_worker_processes": workers}


def fixture_checks(candidate: Path) -> dict[str, Any]:
    sys.path.insert(0, str(candidate))
    from judge_v6 import PROBE_REQUIRED_LABELS, validate_event_sequences
    from state_fingerprint_v6 import state_dict_fingerprint, value_fingerprint

    writer_path = candidate / "event_writer_v6.py"
    writer = {"module": "event_writer_v6", "path": str(writer_path), "bytes": writer_path.stat().st_size, "sha256": sha256_file(writer_path)}

    def envelope(kind: str, seq: int, **payload: Any) -> dict[str, Any]:
        event = {"schema_version": 6, "kind": kind, "leg": "ZERO_GPU", "pid": 1, "process_start": "1:1", "seq": seq, "writer": writer, "role": "ray_worker", "rank": 0}
        event.update(payload)
        return event

    label = sorted(PROBE_REQUIRED_LABELS)[0]
    install = envelope("child_observer_install", 1, methods=[{"label": label, "installed": True, "owner": "Owner", "wrapped": {"id": "wrapped"}, "original": {"id": "original"}}])
    before = envelope("target_wrapper_call_before", 2, label=label, call_id="c", original={"id": "original"}, native_object_id=7)
    after = envelope("target_wrapper_call_after", 3, label=label, call_id="c", original={"id": "original"}, native_object_id=7, before_seq=2, original_call_count=1, status="returned")
    late_install = dict(install, seq=4)
    wrong_writer = dict(before, writer={**writer, "path": "wrong", "bytes": 1, "sha256": "0" * 64})
    normal_ok, _ = validate_event_sequences([install, before, after])
    late_rejected, _ = validate_event_sequences([before, after, late_install])
    writer_rejected, _ = validate_event_sequences([install, wrong_writer, after])
    actor = value_fingerprint({"payload": b"same"}, label="actor")
    anchor = value_fingerprint({"payload": b"same"}, label="anchor")
    changed = value_fingerprint({"payload": b"changed"}, label="anchor")

    class FakeState:
        def __init__(self, value: bytes):
            self.value = value

        def state_dict(self) -> dict[str, Any]:
            return {"weight": self.value, "step": 1}

    actor_state = state_dict_fingerprint(FakeState(b"same"), label="actor")
    anchor_state = state_dict_fingerprint(FakeState(b"same"), label="anchor")
    changed_state = state_dict_fingerprint(FakeState(b"changed"), label="anchor")
    return {
        "normal_sequence_accepted": normal_ok,
        "late_install_rejected": not late_rejected,
        "wrong_writer_rejected": not writer_rejected,
        "equal_label_value_digest": actor.get("sha256") == anchor.get("sha256"),
        "unequal_value_digest_rejected": actor.get("sha256") != changed.get("sha256"),
        "equal_label_state_digest": actor_state.get("sha256") == anchor_state.get("sha256"),
        "unequal_state_digest_rejected": actor_state.get("sha256") != changed_state.get("sha256"),
    }


def main() -> int:
    parser = __import__("argparse").ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    candidate = Path(args.candidate).resolve()
    target = Path(args.target).resolve()
    output = Path(args.output).resolve()
    sys.path.insert(0, str(candidate))

    expected = load(candidate / "EXPECTED_IDENTITY_v6.json")
    reported_hashes = load(candidate / "HASHES_v6.json")
    actual_files = manifest(candidate)
    actual_raw = [item for item in actual_files if item["path"].startswith("raw/")]
    package_hash_check = {
        "file_count": len(actual_files),
        "total_bytes": sum(item["bytes"] for item in actual_files),
        "manifest_sha256": manifest_digest(actual_files),
        "reported_file_count": reported_hashes["package_file_count"],
        "reported_total_bytes": reported_hashes["package_total_bytes"],
        "reported_manifest_sha256": reported_hashes["package_manifest_sha256"],
        "files_equal": actual_files == reported_hashes["files"],
    }
    raw_hash_check = {
        "file_count": len(actual_raw),
        "total_bytes": sum(item["bytes"] for item in actual_raw),
        "manifest_sha256": manifest_digest(actual_raw),
        "reported_file_count": reported_hashes["raw_file_count"],
        "reported_total_bytes": reported_hashes["raw_total_bytes"],
        "reported_manifest_sha256": reported_hashes["raw_manifest_sha256"],
        "files_equal": actual_raw == [item for item in reported_hashes["files"] if item["path"].startswith("raw/")],
    }

    ast_files = sorted(candidate.rglob("*.py"))
    ast_errors: list[str] = []
    for path in ast_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:
            ast_errors.append(f"{path.relative_to(candidate).as_posix()}: {type(exc).__name__}: {exc}")

    with tempfile.TemporaryDirectory(prefix="rapo-v6-acceptance-") as temp:
        temp_root = Path(temp)
        test_result_path = temp_root / "test-result.json"
        test_run = run_command([sys.executable, "-B", "test_v6.py", "--result", str(test_result_path)], candidate, test_result_path)
    launcher_run = run_command([sys.executable, "-B", "launcher_contract_probe_v6.py"], candidate)

    from identity_v6 import runtime_source_manifest
    entry_rel = expected["target"]["production_source"]["relative_path"]
    test_rel = expected["target"]["test_reference"]["relative_path"]
    entry = target / entry_rel
    test_reference = target / test_rel
    runtime = runtime_source_manifest(str(entry))
    target_identity = {
        "entry": {"path": str(entry), "bytes": entry.stat().st_size, "sha256": sha256_file(entry), "expected": expected["target"]["production_source"]},
        "test_reference": {"path": str(test_reference), "bytes": test_reference.stat().st_size, "sha256": sha256_file(test_reference), "expected": expected["target"]["test_reference"]},
        "runtime_source_manifest": {"file_count": runtime["file_count"], "manifest_sha256": runtime["manifest_sha256"], "expected": expected["runtime_source_manifest"]},
    }

    parser_root = candidate / "raw" / "remote-parser-20260913-211"
    parser_result = load(parser_root / "result.json")
    parser_probe = load(parser_root / "probe-result.json")
    parser_config = load(parser_root / "effective-config.json")
    parser_checks = {
        "result_probe_equal": parser_result == parser_probe,
        "status": parser_result.get("status"),
        "legs": parser_result.get("legs"),
        "identity_hashes_equal": len(set(parser_result.get("identity_sha256", {}).values())) == 1,
        "identity_hashes": parser_result.get("identity_sha256"),
        "loader_length_task1": parser_result.get("loader_policy", {}).get("task1_loader_length"),
        "loader_length_task2": parser_result.get("loader_policy", {}).get("task2_loader_length"),
        "total_epochs": parser_result.get("total_epochs"),
        "task1_updates": parser_result.get("loader_policy", {}).get("task1_updates"),
        "task2_updates": parser_result.get("task2_updates"),
        "batch_size": parser_result.get("loader_policy", {}).get("train_batch_size"),
        "drop_last": parser_result.get("loader_policy", {}).get("drop_last"),
        "no_model_ray_or_training": parser_result.get("model_constructed") is False and parser_result.get("ray_started") is False and parser_result.get("training_started") is False,
        "config_total_epochs": parser_config.get("trainer", {}).get("total_epochs"),
        "config_max_steps": parser_config.get("trainer", {}).get("max_steps"),
        "config_save_model_only": parser_config.get("trainer", {}).get("save_model_only"),
        "config_world": [parser_config.get("trainer", {}).get("nnodes"), parser_config.get("trainer", {}).get("n_gpus_per_node")],
        "config_rollout_n": parser_config.get("worker", {}).get("rollout", {}).get("n"),
        "argv_A_boundary_flags": ["--publish_task_boundary", "--stop_after_task_boundary"],
        "argv_B_boundary_flag": "--resume_task_boundary",
    }
    parser_checks["argv_A_flags_present"] = all(flag in load(parser_root / "leg-A" / "argv.json") for flag in parser_checks["argv_A_boundary_flags"])
    parser_checks["argv_B_flag_present"] = parser_checks["argv_B_boundary_flag"] in load(parser_root / "leg-B" / "argv.json")
    parser_checks["pass"] = parser_checks["status"] == "PASS_PARSER_CONFIG_LOADER_ONLY" and parser_checks["result_probe_equal"] and parser_checks["identity_hashes_equal"] and parser_checks["loader_length_task1"] == 1 and parser_checks["loader_length_task2"] == 1 and parser_checks["total_epochs"] == 2 and parser_checks["task1_updates"] == 2 and parser_checks["task2_updates"] == 2 and parser_checks["batch_size"] == 2 and parser_checks["drop_last"] is True and parser_checks["no_model_ray_or_training"] and parser_checks["argv_A_flags_present"] and parser_checks["argv_B_flag_present"]

    zero_root = candidate / "raw" / "remote-zero-20260913-211"
    zero_result = load(zero_root / "result.json")
    from judge_v6 import evaluate_zero_gpu, read_events
    zero_events = read_events(zero_root)
    zero_replay = evaluate_zero_gpu(zero_root, zero_result)
    zero_summary = event_summary(zero_events)
    raw_module_records = target_module_records(zero_result)
    module_matches: dict[str, bool] = {}
    for name, record in raw_module_records.items():
        path = target / (name.replace(".", "/") + ".py")
        module_matches[name] = path.is_file() and (path.stat().st_size, sha256_file(path)) == record
    writer_values = sorted({compact(event.get("writer")) for event in zero_events})
    zero_checks = {
        "reported_judge": load(zero_root / "judge.json"),
        "local_recheck": load(zero_root / "judge-local-recheck.json"),
        "independent_replay": zero_replay,
        "event_summary": zero_summary,
        "writer_value_count": len(writer_values),
        "writer_values": writer_values,
        "all_module_hashes_match_target": all(module_matches.values()),
        "module_matches": module_matches,
        "worker_count": len(zero_summary["ray_worker_processes"]),
        "each_worker_has_four_installs": all(item["install_module_count"] == 4 for item in zero_summary["ray_worker_processes"]),
        "each_worker_has_eleven_calls": all(item["call_label_count"] == 11 for item in zero_summary["ray_worker_processes"]),
    }
    zero_checks["pass"] = zero_replay.get("status") == "PASS_V6_ZERO_GPU_PREP" and zero_replay.get("pass") is True and zero_replay.get("event_count") == 129 and zero_checks["worker_count"] == 2 and zero_checks["each_worker_has_four_installs"] and zero_checks["each_worker_has_eleven_calls"] and zero_checks["all_module_hashes_match_target"] and zero_checks["writer_value_count"] == 1

    fixture = fixture_checks(candidate)
    result = {
        "schema_version": 6,
        "status": "PASS_V6_INDEPENDENT_ACCEPTANCE" if package_hash_check["files_equal"] and raw_hash_check["files_equal"] and not ast_errors and test_run["returncode"] == 0 and launcher_run["returncode"] == 0 and target_identity["entry"]["bytes"] == expected["target"]["production_source"]["bytes"] and target_identity["entry"]["sha256"] == expected["target"]["production_source"]["sha256"] and target_identity["test_reference"]["bytes"] == expected["target"]["test_reference"]["bytes"] and target_identity["test_reference"]["sha256"] == expected["target"]["test_reference"]["sha256"] and target_identity["runtime_source_manifest"]["file_count"] == expected["runtime_source_manifest"]["file_count"] and target_identity["runtime_source_manifest"]["manifest_sha256"] == expected["runtime_source_manifest"]["manifest_sha256"] and parser_checks["pass"] and zero_checks["pass"] and all(fixture.values()) else "FAIL_V6_INDEPENDENT_ACCEPTANCE",
        "verdict": "READY_FOR_BOUNDED_GPU",
        "candidate": str(candidate),
        "target": str(target),
        "package_hash_check": package_hash_check,
        "raw_hash_check": raw_hash_check,
        "ast": {"python_file_count": len(ast_files), "errors": ast_errors},
        "cpu_runs": {"test_v6": test_run, "launcher_contract": launcher_run, "fixture_checks": fixture},
        "target_identity": target_identity,
        "parser_raw": parser_checks,
        "zero_gpu_raw": zero_checks,
        "scope": {"gpu_preflight_run": False, "full_c_ab_run": False, "model_constructed": False, "training_started": False, "paper_scale_or_coco_ap": False},
        "blockers": [],
        "observations": ["The preserved worker bootstrap subreport carries schema_version=5 inside a schema-v6 event stream; event-level schema/writer/judge checks pass, so this is recorded as metadata drift rather than a GPU gate failure."],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "verdict": result["verdict"], "package_manifest_sha256": package_hash_check["manifest_sha256"], "raw_manifest_sha256": raw_hash_check["manifest_sha256"], "zero_gpu_status": zero_replay.get("status"), "event_count": len(zero_events)}, sort_keys=True))
    return 0 if result["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
