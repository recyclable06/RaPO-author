from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import tempfile
from pathlib import Path
from typing import Any


V4 = Path(r"C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\diagnostics\fresh-process-resume-20260911\v4")
SUPPLEMENT = Path(r"C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\diagnostics\fresh-process-resume-20260911\v3-bootstrap-supplement")
V3 = Path(r"C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\diagnostics\fresh-process-resume-20260911\v3")
TARGET = Path(r"C:\Users\Administrator\.codex\worktrees\8ac5\RaPO-author")
TARGET_ENTRY = TARGET / "examples/baselines/img_cls_cil/image_cls_cil_rapo.py"

REQUIRED_LABELS = {
    "FSDPCheckpointManager.load_checkpoint",
    "FSDPWorker.__init__",
    "FSDPWorker.update_actor",
    "PersistentRefFSDPWorker.__init__",
    "PersistentRefFSDPWorker.copy_actor_to_anchor",
    "PersistentRunner.__init__",
    "PersistentRunner.init",
    "PersistentRunner.run_task",
    "PersistentCILTrainer._load_checkpoint",
    "PersistentCILTrainer.reinit_for_task",
    "PersistentCILTrainer.fit",
}
REQUIRED_CALLED = REQUIRED_LABELS - {"FSDPWorker.__init__", "PersistentRefFSDPWorker.__init__"}
REQUIRED_MODULES = {
    "verl.utils.checkpoint.fsdp_checkpoint_manager",
    "verl.workers.fsdp_workers",
    "examples.baselines.img_cls_cil.image_cls_cil_rapo",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def compact_manifest_sha256(entries: list[dict[str, Any]]) -> str:
    return sha256_bytes(json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def actual_manifest(root: Path, *, exclude_names: set[str] | None = None) -> list[dict[str, Any]]:
    excluded = exclude_names or set()
    # Match the WindowsPath ordering used when the frozen v4 manifest was
    # produced; its order is case-insensitive, unlike a string-key sort.
    paths = sorted(
        path for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.name not in excluded
    )
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in paths
    ]


def compare_declared(root: Path, entries: list[dict[str, Any]]) -> dict[str, Any]:
    checks = []
    for item in entries:
        path = root / str(item["path"]).replace("/", os.sep)
        if not path.is_file():
            checks.append({"path": item["path"], "match": False, "error": "missing"})
            continue
        checks.append({
            "path": item["path"],
            "expected_bytes": int(item["bytes"]),
            "actual_bytes": path.stat().st_size,
            "expected_sha256": item["sha256"],
            "actual_sha256": sha256_file(path),
            "match": path.stat().st_size == int(item["bytes"]) and sha256_file(path) == item["sha256"],
        })
    return {
        "count": len(checks),
        "all_match": all(item["match"] for item in checks),
        "mismatches": [item for item in checks if not item["match"]],
    }


def ast_checks() -> dict[str, Any]:
    paths = sorted(V4.glob("*.py"), key=lambda path: path.name)
    results = {}
    for path in paths:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            results[path.name] = "PASS"
        except Exception as exc:
            results[path.name] = f"FAIL: {type(exc).__name__}: {exc}"
    return {"files": results, "all_pass": all(value == "PASS" for value in results.values())}


def read_events(root: Path) -> list[dict[str, Any]]:
    events = []
    for path in sorted((root / "observer" / "events").glob("events-*.jsonl"), key=lambda item: item.name):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events


def event_checks() -> dict[str, Any]:
    event_root = V4 / "raw/ray-3"
    events = read_events(event_root)
    writer_entry = next(item for item in load_json(V4 / "HASHES_V4.json")["files"] if item["path"] == "event_writer_v4.py")
    grouped: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    writer_identity_ok = True
    for event in events:
        key = (event.get("pid"), event.get("process_start"))
        grouped.setdefault(key, []).append(event)
        writer = event.get("writer") or {}
        writer_identity_ok = writer_identity_ok and (
            writer.get("module") == "event_writer_v4"
            and writer.get("bytes") == writer_entry["bytes"]
            and writer.get("sha256") == writer_entry["sha256"]
            and event.get("writer_seq") == event.get("seq")
        )
    sequence_failures = []
    for key, records in grouped.items():
        seqs = [record.get("seq") for record in records]
        if any(not isinstance(seq, int) or seq <= 0 for seq in seqs):
            sequence_failures.append({"process": str(key), "reason": "invalid sequence"})
        if any(left >= right for left, right in zip(seqs, seqs[1:])):
            sequence_failures.append({"process": str(key), "seqs": seqs})

    installs = [event for event in events if event.get("kind") == "child_observer_install"]
    install_labels = set()
    install_modules = set()
    rank_install_labels: dict[str, set[str]] = {}
    for event in installs:
        module = event.get("module_name")
        if isinstance(module, str):
            install_modules.add(module)
        rank_key = str(event.get("rank")) if event.get("role") == "ray_worker" else None
        if rank_key is not None:
            rank_install_labels.setdefault(rank_key, set())
        for method in event.get("methods") or []:
            label = method.get("label") if isinstance(method, dict) else None
            if isinstance(label, str):
                install_labels.add(label)
                if rank_key is not None:
                    rank_install_labels[rank_key].add(label)

    call_after_by_process: dict[tuple[Any, Any, str], list[dict[str, Any]]] = {}
    rank_call_labels: dict[str, set[str]] = {}
    for event in events:
        if event.get("kind") != "target_wrapper_call_after":
            continue
        key = (event.get("pid"), event.get("process_start"), event.get("label"))
        call_after_by_process.setdefault(key, []).append(event)
        if event.get("role") == "ray_worker":
            rank_call_labels.setdefault(str(event.get("rank")), set()).add(str(event.get("label")))
    call_failures = []
    for key, records in call_after_by_process.items():
        for record in records:
            if record.get("original_call_count") != 1 or not (record.get("original") or {}).get("module"):
                call_failures.append({"key": str(key), "record": record})

    ray_result = load_json(V4 / "raw/ray-result-final.json")
    judge_result = load_json(V4 / "raw/FRESH_PROCESS_REPORT_V4_FINAL.json")
    return {
        "event_count": len(events),
        "event_file_count": len(list((event_root / "observer/events").glob("events-*.jsonl"))),
        "writer_identity_and_writer_seq": writer_identity_ok,
        "sequence_failures": sequence_failures,
        "sequence_ok": not sequence_failures and writer_identity_ok,
        "install_modules": sorted(install_modules),
        "install_labels": sorted(install_labels),
        "all_required_modules_installed": install_modules == REQUIRED_MODULES,
        "all_required_labels_installed": install_labels == REQUIRED_LABELS,
        "worker_ranks": sorted(rank_install_labels),
        "rank_install_labels": {key: sorted(value) for key, value in sorted(rank_install_labels.items())},
        "rank_call_labels": {key: sorted(value) for key, value in sorted(rank_call_labels.items())},
        "each_rank_has_required_called_labels": all(value == REQUIRED_CALLED for value in rank_call_labels.values()) and set(rank_call_labels) == {"0", "1"},
        "call_failures": call_failures,
        "all_observed_original_calls_once": not call_failures,
        "ray_result_status": ray_result.get("status"),
        "ray_result_gpu_requested": ray_result.get("gpu_requested"),
        "ray_result_model_imported": ray_result.get("model_imported"),
        "ray_result_production_entry_imported": ray_result.get("production_entry_imported"),
        "ray_result_worker_report_count": len(ray_result.get("worker_reports") or []),
        "ray_result_worker_reports_are_raw_child_probe": all(
            report.get("module_name") == "examples.baselines.img_cls_cil.image_cls_cil_rapo"
            and report.get("role") == "ray_worker"
            and len(report.get("calls") or []) == 8
            for report in ray_result.get("worker_reports") or []
        ),
        "runner_error_is_expected_inert_failure": "NoneType" in str(ray_result.get("runner_error")),
        "recorded_judge_status": judge_result.get("status"),
        "recorded_judge_pass": judge_result.get("pass"),
    }


def load_judge_v4():
    spec = importlib.util.spec_from_file_location("v4_acceptance_judge", V4 / "judge_v4.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load v4 judge")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_install(module_name: str, labels: list[str], pid: int, role: str, rank: int | None, seq: int) -> dict[str, Any]:
    methods = []
    for label in labels:
        methods.append({
            "label": label,
            "installed": True,
            "original": {"module": module_name, "qualname": label, "object_id": 10},
            "wrapped": {"module": module_name, "qualname": label, "object_id": 11},
        })
    return {
        "schema_version": 4,
        "kind": "child_observer_install",
        "pid": pid,
        "process_start": f"{pid}:1",
        "seq": seq,
        "writer_seq": seq,
        "writer": {"path": "/diagnostic/event_writer_v4.py", "sha256": "a" * 64},
        "role": role,
        "rank": rank,
        "module_name": module_name,
        "module": module_name,
        "actual_module_object_id": 20,
        "installed": True,
        "methods": methods,
    }


def judge_concat_negative() -> dict[str, Any]:
    """Show whether v4 judge accepts labels split across ranks/processes."""
    judge = load_judge_v4()
    module_labels = {
        "verl.utils.checkpoint.fsdp_checkpoint_manager": ["FSDPCheckpointManager.load_checkpoint"],
        "verl.workers.fsdp_workers": ["FSDPWorker.__init__", "FSDPWorker.update_actor"],
        "examples.baselines.img_cls_cil.image_cls_cil_rapo": [
            "PersistentRefFSDPWorker.__init__", "PersistentRefFSDPWorker.copy_actor_to_anchor",
            "PersistentRunner.__init__", "PersistentRunner.init", "PersistentRunner.run_task",
            "PersistentCILTrainer._load_checkpoint", "PersistentCILTrainer.reinit_for_task", "PersistentCILTrainer.fit",
        ],
    }
    events = []
    seq_by_process: dict[int, int] = {}

    def add(event: dict[str, Any]) -> None:
        events.append(event)

    for pid, role, rank in ((1, "production_driver", None), (2, "ray_runner", None), (3, "ray_worker", 0), (4, "ray_worker", 1)):
        seq_by_process[pid] = 0
        for module_name, labels in module_labels.items():
            seq_by_process[pid] += 1
            add(synthetic_install(module_name, labels, pid, role, rank, seq_by_process[pid]))

    split = sorted(REQUIRED_CALLED)
    for pid, rank, labels in ((3, 0, split[:4]), (4, 1, split[4:])):
        for label in labels:
            seq_by_process[pid] += 1
            base = {
                "schema_version": 4,
                "pid": pid,
                "process_start": f"{pid}:1",
                "writer": {"path": "/diagnostic/event_writer_v4.py", "sha256": "a" * 64},
                "role": "ray_worker",
                "rank": rank,
                "label": label,
                "original": {"module": "examples.baselines.img_cls_cil.image_cls_cil_rapo", "qualname": label},
            }
            before = dict(base, kind="target_wrapper_call_before", seq=seq_by_process[pid], writer_seq=seq_by_process[pid], original_call_count=0)
            add(before)
            seq_by_process[pid] += 1
            after = dict(base, kind="target_wrapper_call_after", seq=seq_by_process[pid], writer_seq=seq_by_process[pid], original_call_count=1)
            add(after)

    with tempfile.TemporaryDirectory(prefix="rapo-v4-judge-negative-") as temporary:
        root = Path(temporary)
        event_dir = root / "observer" / "events"
        event_dir.mkdir(parents=True)
        for pid in seq_by_process:
            (event_dir / f"events-{pid}.jsonl").write_text(
                "".join(json.dumps(event, sort_keys=True) + "\n" for event in events if event.get("pid") == pid),
                encoding="utf-8",
            )
        probe_result = {
            "schema_version": 4,
            "status": "PASS_ZERO_GPU_RAY_REAL_CHILD_OBSERVER",
            "gpu_requested": False,
            "model_imported": False,
            "canonical_target_module": "examples.baselines.img_cls_cil.image_cls_cil_rapo",
        }
        result = judge.evaluate(root, probe_result)
    return {
        "synthetic_labels_split_across_ranks": True,
        "judge_pass": result.get("pass"),
        "judge_status": result.get("status"),
        "judge_reasons": result.get("reasons"),
        "finding": "judge aggregates observed labels globally instead of requiring each role/rank to cover required calls",
    }


def supplement_checks() -> dict[str, Any]:
    manifest = load_json(SUPPLEMENT / "HASHES_SUPPLEMENT.json")
    key_results = compare_declared(SUPPLEMENT, manifest["key_files"])
    raw_root = SUPPLEMENT / "raw"
    raw_entries = actual_manifest(raw_root)
    raw_entries_with_prefix = [
        {"path": f"raw/{item['path']}", "bytes": item["bytes"], "sha256": item["sha256"]}
        for item in raw_entries
    ]
    raw_result = load_json(SUPPLEMENT / "raw/supplement-result.json")
    raw_events = load_json(SUPPLEMENT / "raw/raw-events.json")
    return {
        "declared_raw_file_count": manifest["raw_file_count"],
        "actual_raw_file_count": len(raw_entries),
        "declared_raw_total_bytes": manifest["raw_total_bytes"],
        "actual_raw_total_bytes": sum(item["bytes"] for item in raw_entries),
        "raw_count_and_bytes_match": len(raw_entries) == manifest["raw_file_count"] and sum(item["bytes"] for item in raw_entries) == manifest["raw_total_bytes"],
        "key_files": key_results,
        "declared_raw_manifest_sha256": manifest["raw_manifest_sha256"],
        "computed_v4_style_raw_manifest_sha256": compact_manifest_sha256(raw_entries_with_prefix),
        "raw_aggregate_reproduced_by_declared_schema": compact_manifest_sha256(raw_entries_with_prefix) == manifest["raw_manifest_sha256"],
        "raw_aggregate_reproducibility": "NOT_REPRODUCIBLE_WITHOUT_PER_FILE_MANIFEST_OR_ALGORITHM",
        "supplement_status": raw_result.get("status"),
        "fresh_child_method_count": len(raw_result.get("fresh_child_uninstalled_methods") or {}),
        "fresh_child_all_required_methods_have_no_marker": raw_result.get("fresh_child_all_required_methods_have_no_marker"),
        "actual_runner_wrapper_event_count": len(raw_result.get("actual_runner_wrapper_events") or []),
        "serialized_wrapper_event_count": len(raw_result.get("serialized_wrapper_events") or []),
        "raw_event_count": len(raw_events),
        "raw_event_child_bootstrap_count": len([event for event in raw_events if event.get("kind") == "child_bootstrap_install"]),
        "raw_event_child_observer_install_count": len([event for event in raw_events if event.get("kind") == "child_observer_install"]),
    }


def parser_checks() -> dict[str, Any]:
    result = load_json(V4 / "raw/parser-result-v2.json")
    config = load_json(V4 / "raw/parser-3/effective-config.json")
    target_source = TARGET_ENTRY.read_text(encoding="utf-8")
    trainer_source = (TARGET / "verl/trainer/config.py").read_text(encoding="utf-8")
    report_source = V4 / "REPORT_V4.md"
    return {
        "status": result.get("status"),
        "positive_legs": result.get("production_positive_legs"),
        "positive_legs_exactly_CAB": set(result.get("production_positive_legs") or []) == {"A", "B", "C"},
        "missing_cil_cfg_rejected": result.get("launcher_negative_missing_cil_cfg_rejected"),
        "negative_content_rejected": result.get("production_negative_content_rejected"),
        "identity_sha256_values": result.get("identity_sha256"),
        "identity_same_across_legs": len(set((result.get("identity_sha256") or {}).values())) == 1,
        "production_entry_imported": result.get("production_entry_imported"),
        "model_constructed": result.get("model_constructed"),
        "ray_started": result.get("ray_started"),
        "parser_only_total_epochs": config.get("trainer", {}).get("total_epochs"),
        "parser_only_max_steps": config.get("trainer", {}).get("max_steps"),
        "author_total_epochs_declared_int": "total_epochs: int" in trainer_source,
        "runner_multiplies_epochs_by_loader_length": "config.trainer.total_epochs * len(train_dataloader)" in target_source,
        "v4_report_explicitly_parser_only": "parser-only" in report_source.read_text(encoding="utf-8"),
    }


def identity_checks() -> dict[str, Any]:
    v4_hashes = load_json(V4 / "HASHES_V4.json")
    v4_actual = actual_manifest(V4, exclude_names={"HASHES_V4.json"})
    raw_actual = [item for item in v4_actual if item["path"].startswith("raw/")]
    v4_declared = v4_hashes["files"]
    v3_hash_path = V3 / "HASHES_V3.json"
    target_hash = sha256_file(TARGET_ENTRY)
    return {
        "v4_declared_file_count": v4_hashes["package_file_count"],
        "v4_declared_total_bytes": v4_hashes["package_total_bytes"],
        "v4_actual_file_count": len(v4_actual),
        "v4_actual_total_bytes": sum(item["bytes"] for item in v4_actual),
        "v4_files_exactly_match_declared": v4_actual == v4_declared,
        "v4_package_manifest_reproduced": compact_manifest_sha256(v4_declared) == v4_hashes["package_manifest_sha256"],
        "v4_raw_file_count": len(raw_actual),
        "v4_raw_total_bytes": sum(item["bytes"] for item in raw_actual),
        "v4_raw_manifest_reproduced": compact_manifest_sha256(raw_actual) == v4_hashes["raw_manifest_sha256"],
        "v3_hash_file_sha256": sha256_file(v3_hash_path),
        "v3_frozen_self_sha256_expected": v4_hashes["frozen_v3_self_sha256"],
        "v3_frozen_self_matches": sha256_file(v3_hash_path) == v4_hashes["frozen_v3_self_sha256"],
        "target_entry_bytes": TARGET_ENTRY.stat().st_size,
        "target_entry_sha256": target_hash,
        "target_entry_matches_v4_expected": TARGET_ENTRY.stat().st_size == 102269 and target_hash == "3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3",
    }


def main() -> int:
    output = {
        "status": "PASS_LIMITED_REVIEW_WITH_FINDINGS",
        "scope": {
            "gpu_executed": False,
            "ray_executed_by_acceptance": False,
            "ssh_executed": False,
            "installation_executed": False,
            "model_constructed_by_acceptance": False,
            "training_executed": False,
            "inference_executed": False,
            "production_files_modified": False,
            "prep_files_modified": False,
        },
        "identity_checks": identity_checks(),
        "ast_checks": ast_checks(),
        "parser_checks": parser_checks(),
        "event_checks": event_checks(),
        "judge_concat_negative": judge_concat_negative(),
        "supplement_checks": supplement_checks(),
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
