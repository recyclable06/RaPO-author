from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def compact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: compact(item) for key, item in value.items() if key not in {"state", "writer"}}
    if isinstance(value, list):
        return [compact(item) for item in value]
    return value


def scan_events(directory: Path) -> dict[str, Any]:
    files = sorted(directory.glob("*.jsonl"))
    kind_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    phase_counts: Counter[str] = Counter()
    records = 0
    target_events: list[dict[str, Any]] = []
    installed_targets: set[str] = set()
    for path in files:
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                record = json.loads(raw)
                records += 1
                kind = str(record.get("kind", ""))
                kind_counts[kind] += 1
                if kind in {"target_wrapper_call_before", "target_wrapper_call_after"}:
                    label = str(record.get("label", ""))
                    target_counts[label] += 1
                    phase_counts[f"{label}:{record.get('phase', kind.rsplit('_', 1)[-1])}"] += 1
                    target_events.append(
                        {
                            "file": path.name,
                            "kind": kind,
                            "label": label,
                            "phase": record.get("phase"),
                            "pid": record.get("pid"),
                            "rank": record.get("rank", record.get("local_rank")),
                            "unix": record.get("unix"),
                            "call_id": record.get("call_id"),
                            "role": record.get("role"),
                        }
                    )
                elif kind == "child_observer_install":
                    for method in record.get("methods", []):
                        label = method.get("label")
                        if label:
                            installed_targets.add(str(label))
    target_events.sort(key=lambda item: (item.get("unix") or 0, item.get("pid") or 0, item.get("kind", "")))
    return {
        "file_count": len(files),
        "record_count": records,
        "kind_counts": dict(sorted(kind_counts.items())),
        "target_call_counts": dict(sorted(target_counts.items())),
        "target_phase_counts": dict(sorted(phase_counts.items())),
        "installed_target_labels": sorted(installed_targets),
        "target_events": target_events,
    }


def selected_lines(text: str, patterns: list[str], limit: int = 40) -> list[dict[str, Any]]:
    regexes = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    result: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if any(regex.search(line) for regex in regexes):
            result.append({"line": line_no, "text": line[:500]})
            if len(result) >= limit:
                break
    return result


def source_excerpt(path: Path, start: int, end: int) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [{"line": number, "text": lines[number - 1]} for number in range(start, min(end, len(lines)) + 1)]


def verify_manifest(shared: Path) -> dict[str, Any]:
    path = shared / "DELIVERY_MANIFEST-SHARED-EVIDENCE.json"
    manifest = read_json(path)
    entries = manifest.get("files", [])
    by_path = {entry["path"]: entry for entry in entries}
    actual_paths = {
        file.relative_to(shared).as_posix()
        for file in shared.rglob("*")
        if file.is_file() and file != path
    }
    missing = sorted(set(by_path) - actual_paths)
    extra = sorted(actual_paths - set(by_path))
    mismatches: list[dict[str, Any]] = []
    total_bytes = 0
    for relative, entry in sorted(by_path.items()):
        file = shared / Path(relative)
        if not file.is_file():
            continue
        actual_bytes = file.stat().st_size
        total_bytes += actual_bytes
        if actual_bytes != entry.get("bytes") or sha256_file(file) != entry.get("sha256"):
            mismatches.append(
                {
                    "path": relative,
                    "expected_bytes": entry.get("bytes"),
                    "actual_bytes": actual_bytes,
                    "expected_sha256": entry.get("sha256"),
                    "actual_sha256": sha256_file(file),
                }
            )
    return {
        "path": str(path),
        "self_sha256": sha256_file(path),
        "declared_file_count": manifest.get("file_count"),
        "declared_total_bytes": manifest.get("total_bytes"),
        "actual_entry_count": len(entries),
        "actual_total_bytes": total_bytes,
        "missing": missing,
        "extra": extra,
        "mismatches": mismatches,
        "ok": not missing and not extra and not mismatches and len(entries) == manifest.get("file_count") and total_bytes == manifest.get("total_bytes"),
    }


def verify_index(shared: Path) -> dict[str, Any]:
    path = shared / "EVIDENCE_INDEX.json"
    index = read_json(path)
    entries = index.get("entries", [])
    return {
        "path": str(path),
        "self_sha256": sha256_file(path),
        "copied_file_count": index.get("copied_file_count"),
        "copied_total_bytes": index.get("copied_total_bytes"),
        "entry_count": len(entries),
        "entry_total_bytes": sum(int(entry.get("bytes", 0)) for entry in entries),
        "max_file_bytes": max((int(entry.get("bytes", 0)) for entry in entries), default=0),
        "tensor_or_weight_files_copied": index.get("tensor_or_weight_files_copied"),
        "ok": len(entries) == index.get("copied_file_count") and sum(int(entry.get("bytes", 0)) for entry in entries) == index.get("copied_total_bytes"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shared", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--diagnostic-root", type=Path, required=True)
    args = parser.parse_args()

    shared = args.shared.resolve()
    evidence = shared / "evidence"
    diagnostic = args.diagnostic_root.resolve()
    prod = args.source_root / "examples" / "baselines" / "img_cls_cil" / "image_cls_cil_rapo.py"
    checkpoint = args.source_root / "verl" / "utils" / "checkpoint" / "fsdp_checkpoint_manager.py"
    run_v9 = diagnostic / "v9" / "run_v9.py"

    a_root = evidence / "A-root"
    b_root = evidence / "B-root"
    a_boundary = evidence / "A-boundary"
    b_stdout = (b_root / "process.stdout.log").read_text(encoding="utf-8", errors="replace")
    b_stderr = (b_root / "process.stderr.log").read_text(encoding="utf-8", errors="replace")
    b_timeline = (evidence / "B-supervisor" / "timeline.log").read_text(encoding="utf-8", errors="replace")

    b_end = read_json(b_root / "process-end.json")
    b_result = read_json(b_root / "run-result.json")
    b_comparison = read_json(b_root / "boundary_manifest_comparison.json")
    a_expected = read_json(a_root / "boundary-expected.json")
    marker = read_json(a_boundary / "task1-complete.json")

    a_events = scan_events(evidence / "A-observer-events")
    b_events = scan_events(evidence / "B-observer-events")

    b_anchor_events = [
        event for event in b_events["target_events"] if event["label"] == "PersistentRefFSDPWorker.init_anchor"
    ]
    b_absent_labels = [
        "PersistentRunner.run_task",
        "PersistentCILTrainer._load_checkpoint",
        "PersistentCILTrainer.restore_boundary_checkpoint",
        "FSDPCheckpointManager.load_checkpoint",
        "PersistentCILTrainer.fit",
    ]
    b_absent_actual_calls = {
        label: b_events["target_call_counts"].get(label, 0) for label in b_absent_labels
    }

    ray_samples: dict[str, list[dict[str, Any]]] = {}
    for name in ("raylet.out", "dashboard.log", "dashboard_agent.log", "gcs_server.err"):
        path = evidence / "ray-logs" / name
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            ray_samples[name] = selected_lines(text, [r"SIGTERM", r"graceful", r"shutdown", r"keepalive"], limit=12)

    result = {
        "schema": "fresh-process-r2-shared-independent-review-v1",
        "reviewed_at": "2026-09-19T00:00:00+08:00",
        "scope": {
            "shared_evidence": str(shared),
            "delivery_manifest_sha256": sha256_file(shared / "DELIVERY_MANIFEST-SHARED-EVIDENCE.json"),
            "evidence_index_sha256": sha256_file(shared / "EVIDENCE_INDEX.json"),
            "read_only": True,
            "production_modified": False,
            "experiment_rerun": False,
        },
        "integrity": {
            "delivery_manifest": verify_manifest(shared),
            "evidence_index": verify_index(shared),
        },
        "A": {
            "marker": {
                "path": "evidence/A-boundary/task1-complete.json",
                "sha256": sha256_file(a_boundary / "task1-complete.json"),
                "status": marker.get("status"),
                "completed_task": marker.get("completed_task"),
                "next_task": marker.get("next_task"),
                "global_step": marker.get("global_step"),
                "state_fingerprint": marker.get("state_fingerprint"),
                "checkpoint_manifest_sha256": marker.get("checkpoint", {}).get("manifest_sha256"),
                "ema_sha256": marker.get("ema", {}).get("sha256"),
                "driver_rng_sha256": marker.get("rng", {}).get("driver", {}).get("sha256"),
                "vllm_rng_sha256": [item.get("sha256") for item in marker.get("rng", {}).get("vllm", [])],
            },
            "boundary_expected": {
                "path": "evidence/A-root/boundary-expected.json",
                "sha256": sha256_file(a_root / "boundary-expected.json"),
                "complete": a_expected.get("complete"),
                "errors": a_expected.get("errors", []),
                "driver_present": a_expected.get("driver") is not None,
                "native_ranks": sorted(a_expected.get("native_by_rank", {}).keys()),
                "vllm_ranks": sorted(a_expected.get("vllm_by_rank", {}).keys()),
            },
            "observer": {
                "file_count": a_events["file_count"],
                "record_count": a_events["record_count"],
                "target_call_counts": a_events["target_call_counts"],
                "run_task_actual_call_count": a_events["target_call_counts"].get("PersistentRunner.run_task", 0),
                "driver_rng_expected_records": sum(
                    1 for event in a_events["target_events"] if event["label"] == "driver_rng_expected"
                ),
            },
            "finding": "marker_linked_artifacts_present_but_post_publication_driver_observer_proof_incomplete",
        },
        "B": {
            "process_end": b_end,
            "run_result_derived_fields": {
                "exit_code": b_result.get("exit_code"),
                "model_constructed": b_result.get("model_constructed"),
                "training_started": b_result.get("training_started"),
                "boundary_unchanged": b_result.get("boundary_unchanged"),
            },
            "boundary_manifest": {
                "equal": b_comparison.get("equal"),
                "before_sha256": b_comparison.get("before_sha256"),
                "after_sha256": b_comparison.get("after_sha256"),
            },
            "observer": {
                "file_count": b_events["file_count"],
                "record_count": b_events["record_count"],
                "target_call_counts": b_events["target_call_counts"],
                "anchor_init_events": b_anchor_events,
                "actual_call_counts_for_restore_or_fit": b_absent_actual_calls,
            },
            "stdout_stage_lines": selected_lines(
                b_stdout,
                [
                    r"after HuggingFace model init",
                    r"after FSDP module init",
                    r"after vLLM init",
                    r"Workers initialised \(persistent\)",
                    r"Resuming",
                    r"Task.?2",
                    r"run_task",
                    r"fit\(",
                ],
                limit=80,
            ),
            "stderr_signal_lines": selected_lines(
                b_stderr,
                [r"SIGTERM", r"SIGABRT", r"Traceback", r"RuntimeError", r"CUDA", r"OOM", r"NCCL", r"fatal", r"abort"],
                limit=80,
            ),
            "supervisor_timeline_lines": [
                {"line": line_no, "text": line}
                for line_no, line in enumerate(b_timeline.splitlines(), 1)
                if any(
                    token in line
                    for token in (
                        "leg_deadline_reached",
                        "child_already_exited",
                        "launcher_grace_expired",
                        "no_safe_sigkill_target",
                        "launcher_still_active",
                        "supervisor_end",
                    )
                )
            ],
            "ray_shutdown_samples": ray_samples,
            "finding": "model_fsdp_vllm_and_persistent_workers_initialized_then_both_ranks_entered_anchor_init_without_after; task2_restore_and_fit_not_observed; internal_abort_cause_unresolved",
        },
        "source_order": {
            "production_file": {"path": str(prod), "sha256": sha256_file(prod)},
            "checkpoint_file": {"path": str(checkpoint), "sha256": sha256_file(checkpoint)},
            "run_v9_file": {"path": str(run_v9), "sha256": sha256_file(run_v9)},
            "production_excerpts": {
                "anchor_method": source_excerpt(prod, 984, 1014),
                "anchor_dispatch": source_excerpt(prod, 1599, 1601),
                "main_order": source_excerpt(prod, 1789, 1796),
                "run_task_checkpoint_restore": source_excerpt(prod, 1379, 1448),
                "run_task_dispatch": source_excerpt(prod, 1854, 1867),
            },
            "checkpoint_load_excerpt": source_excerpt(checkpoint, 61, 75),
            "derived_flag_excerpt": source_excerpt(run_v9, 230, 232),
        },
        "minimum_next_evidence": [
            "不要把 B 的 run_v9 model_constructed=false/training_started=false 当作未构造模型或未开始训练的独立事实；它们由 returncode == 0 派生。",
            "如需给 B 的 SIGABRT 归因，只请求源端 Ray worker PID 1161595(rank0) 与 1162100(rank1) 对应的 stdout/stderr 原件；当前 shared inventory 未记录这些文件名，因此不能凭空填路径。",
            "A 先补齐实际 PersistentRunner.run_task 调用及 post-publication driver RNG 观测；仅 marker 文件与 manifest-linked subordinate artifacts 不能关闭 A boundary finding。",
            "Host 211 cleanup 仍为 UNCONFIRMED；本复核未改变该状态。",
        ],
        "overall_verdict": "PARTIAL_EVIDENCE_SUPPLEMENT",
    }
    print(json.dumps(compact(result), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
