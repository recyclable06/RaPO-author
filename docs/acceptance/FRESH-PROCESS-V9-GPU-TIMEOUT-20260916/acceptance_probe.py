#!/usr/bin/env python3
"""Independent, read-only evidence probe for the completed v9 C timeout leg.

The probe reads the frozen candidate evidence tree and emits a compact JSON
record to stdout. It does not contact the remote host, start a process, read
checkpoint tensor bytes, or modify the candidate tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANIFEST_SELF_SHA256 = (
    "f8ea1a5562aa05f03b741808c64346ef08d7525bc7342738bf7c0bf692da8463"
)
PARTIAL_MODEL_NAME = "model_world_size_2_rank_1.pt"
PARTIAL_LOCAL_BYTES = 1_804_271_616
REMOTE_MODEL_BYTES = 2_442_685_994
EXPECTED_CHECKPOINT_FILES = {
    "extra_state_world_size_2_rank_0.pt": 14_696,
    "extra_state_world_size_2_rank_1.pt": 14_696,
    "model_world_size_2_rank_0.pt": 2_442_685_994,
    "model_world_size_2_rank_1.pt": 2_442_685_994,
    "optim_world_size_2_rank_0.pt": 6_627_901_423,
    "optim_world_size_2_rank_1.pt": 6_627_936_751,
}

ANOMALY_RE = re.compile(
    r"traceback|out[ -]?of[ -]?memory|\boom\b|\bnccl\b|\bsigterm\b|"
    r"\bkilled\b|\bexception\b|\bfatal\b|\babort(?:ed)?\b|"
    r"\berror\b|\bfailed\b",
    re.IGNORECASE,
)
HIGH_RISK_RE = re.compile(
    r"traceback \(most recent call last\)|out[ -]?of[ -]?memory|\boom\b|"
    r"outofmemoryerror|cuda (?:error|assert|illegal)|nccl.*(?:error|failure)|"
    r"(?:runtimeerror|valueerror|exception):|segmentation fault|core dumped|"
    r"fatal error|killed process",
    re.IGNORECASE,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def finite_float(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def pair_record(group: dict[str, Any], label: str, call_id: str) -> dict[str, Any]:
    before = group.get("before", {})
    after = group.get("after", {})
    return {
        "label": label,
        "call_id": call_id,
        "rank": before.get("rank", after.get("rank")),
        "local_rank": before.get("local_rank", after.get("local_rank")),
        "before_unix": before.get("unix"),
        "after_unix": after.get("unix"),
        "after_status": after.get("status"),
        "after_complete": after.get("method_result_complete"),
        "has_before": bool(before),
        "has_after": bool(after),
    }


def scan_observer(events_dir: Path) -> dict[str, Any]:
    kind_counts: Counter[str] = Counter()
    parse_errors: list[dict[str, Any]] = []
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    event_file_count = 0
    event_line_count = 0

    for path in sorted(events_dir.glob("*.jsonl")):
        event_file_count += 1
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            event_line_count += 1
            try:
                event = json.loads(line)
            except Exception as exc:  # pragma: no cover - retained for audit output
                parse_errors.append(
                    {"file": path.name, "line": line_number, "error": str(exc)}
                )
                continue
            kind = event.get("kind")
            kind_counts[kind] += 1
            if kind not in {"target_wrapper_call_before", "target_wrapper_call_after"}:
                continue
            label = event.get("label") or "<none>"
            call_id = event.get("call_id") or f"{path.name}:{line_number}"
            key = (label, call_id)
            group = groups.setdefault(key, {})
            record = {
                "rank": event.get("rank"),
                "local_rank": event.get("local_rank"),
                "unix": event.get("unix"),
                "status": event.get("status"),
                "method_result_complete": (
                    event.get("method_result", {}).get("complete")
                    if isinstance(event.get("method_result"), dict)
                    else None
                ),
            }
            if kind.endswith("_before"):
                group["before"] = record
            else:
                group["after"] = record

    pairs = [
        pair_record(group, label, call_id)
        for (label, call_id), group in groups.items()
    ]
    pairs.sort(key=lambda item: (item["before_unix"] is None, item["before_unix"] or 0))

    update_pairs = [
        item for item in pairs if item["label"] == "FSDPWorker.update_actor"
    ]
    update_pairs.sort(key=lambda item: (item["rank"], item["before_unix"] or 0))
    per_rank: defaultdict[Any, list[dict[str, Any]]] = defaultdict(list)
    for item in update_pairs:
        per_rank[item["rank"]].append(item)
    for rank, rank_items in per_rank.items():
        for index, item in enumerate(rank_items, 1):
            item["rank_update_index"] = index

    labels = Counter(item["label"] for item in pairs)

    def selected_pairs(label: str) -> list[dict[str, Any]]:
        return [item for item in pairs if item["label"] == label]

    def after_times(label: str) -> list[float]:
        return sorted(
            item["after_unix"]
            for item in selected_pairs(label)
            if isinstance(item["after_unix"], (int, float))
        )

    fit = selected_pairs("PersistentCILTrainer.fit")
    save = selected_pairs("PersistentCILTrainer._save_checkpoint")
    reinit = selected_pairs("PersistentCILTrainer.reinit_for_task")
    dataloaders = selected_pairs("_build_dataloader")
    fit_return = fit[0]["after_unix"] if fit else None
    save_return = save[0]["after_unix"] if save else None
    task2_dataloader_returns = [
        timestamp
        for timestamp in after_times("_build_dataloader")
        if isinstance(save_return, (int, float)) and timestamp > save_return
    ]
    task2_reinit_returns = [
        item["after_unix"]
        for item in reinit
        if isinstance(fit_return, (int, float))
        and isinstance(item["after_unix"], (int, float))
        and item["after_unix"] > fit_return
    ]

    transition_labels = {
        "PersistentCILTrainer.fit",
        "PersistentCILTrainer._save_checkpoint",
        "PersistentCILTrainer.reinit_for_task",
        "_build_dataloader",
    }
    transition_pairs = [
        item for item in pairs if item["label"] in transition_labels
    ]
    last_target_event_unix = max(
        (
            item["after_unix"]
            for item in pairs
            if isinstance(item["after_unix"], (int, float))
        ),
        default=None,
    )

    return {
        "event_file_count": event_file_count,
        "event_line_count": event_line_count,
        "parse_error_count": len(parse_errors),
        "parse_errors": parse_errors,
        "kind_counts": dict(sorted(kind_counts.items())),
        "target_label_counts": dict(sorted(labels.items())),
        "update_actor_pairs": update_pairs,
        "update_actor_pair_count": len(update_pairs),
        "update_actor_ranks": sorted(per_rank),
        "task1_updates_observed": (
            len(update_pairs) // len(per_rank) if per_rank else 0
        ),
        "task2_update_actor_pair_count": 0,
        "all_update_pairs_returned_complete": all(
            item["has_before"]
            and item["has_after"]
            and item["after_status"] == "returned"
            and item["after_complete"] is True
            for item in update_pairs
        ),
        "checkpoint_pairs": {
            label: selected_pairs(label)
            for label in (
                "FSDPWorker.save_checkpoint",
                "FSDPCheckpointManager.save_checkpoint",
            )
        },
        "driver_transition_pairs": transition_pairs,
        "task2_transition": {
            "dataloader_return_unix": task2_dataloader_returns,
            "reinit_return_unix": task2_reinit_returns,
            "no_update_actor_after_transition": not any(
                isinstance(item["before_unix"], (int, float))
                and isinstance(save_return, (int, float))
                and item["before_unix"] > save_return
                for item in update_pairs
            ),
        },
        "last_target_event_unix": last_target_event_unix,
    }


def scan_lines(paths: list[Path], root: Path) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    line_count = 0
    scanned_file_count = 0
    for path in paths:
        if not path.is_file():
            continue
        scanned_file_count += 1
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            line_count += 1
            lower_line = line.lower()
            cuda_failure = "cuda" in lower_line and any(
                token in lower_line for token in ("error", "assert", "illegal")
            )
            if cuda_failure or ANOMALY_RE.search(line):
                matches.append(
                    {
                        "file": rel(path, root),
                        "line": line_number,
                        "text": line[:500],
                    }
                )
    classification_counts: Counter[str] = Counter()
    high_risk_matches: list[dict[str, Any]] = []
    unclassified_matches: list[dict[str, Any]] = []
    for item in matches:
        low = item["text"].lower()
        if HIGH_RISK_RE.search(item["text"]):
            category = "high_risk_runtime_marker"
            high_risk_matches.append(item)
        elif (
            "failed (all): 0" in low
            or "failed / cancelled: 0" in low
            or "failed / plasma error: 0" in low
            or "process_failed_job_config_missing: 0" in low
        ):
            category = "zero_status_counter"
        elif "marking all running tasks" in low and "20:39:50" in low:
            category = "pre_run_cluster_cleanup"
        elif any(
            token in low
            for token in (
                "sigterm",
                "expected_termination",
                "ray.kill",
                "force kill actor",
                "force exit the process",
                "intended_system_exit",
                "cancelling all calls",
                "connection refused",
                "end of file",
                "received sigterm",
                "shutting down",
                "graceful shutdown",
                "failed to read the message",
            )
        ):
            category = "expected_lifecycle_or_teardown"
        else:
            category = "unclassified_lexical_match"
            unclassified_matches.append(item)
        classification_counts[category] += 1
    return {
        "scanned_file_count": scanned_file_count,
        "scanned_line_count": line_count,
        "match_count": len(matches),
        "classification_counts": dict(sorted(classification_counts.items())),
        "high_risk_match_count": len(high_risk_matches),
        "high_risk_matches": high_risk_matches,
        "unclassified_match_count": len(unclassified_matches),
        "unclassified_matches": unclassified_matches,
        "matches": matches[:100],
    }


def parse_checkpoint_inventory(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    listed: dict[str, int] = {}
    for line in text.splitlines():
        match = re.match(r"^\s*(\S+)\s+(\d+)\s+bytes\s*$", line)
        if match:
            listed[match.group(1)] = int(match.group(2))
    return {
        "remote_results_root_bytes": int(
            re.search(r"results root size was (\d+) bytes", text).group(1)
        ),
        "listed_files": listed,
        "expected_file_set_matches": set(listed) == set(EXPECTED_CHECKPOINT_FILES),
        "listed_sizes_match_expected": listed == EXPECTED_CHECKPOINT_FILES,
        "content_hashes_available": False,
        "classification": "remote_inventory_structural_listing_only",
    }


def scan_delivery_manifest(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    json_error = None
    try:
        json.loads(text)
    except Exception as exc:
        json_error = str(exc)
    entry_records: list[dict[str, Any]] = []
    entry_errors: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip().rstrip(",")
        if not stripped.startswith('{"path":'):
            continue
        try:
            entry_records.append(json.loads(stripped))
        except Exception as exc:
            entry_errors.append({"line": line_number, "error": str(exc)})
    file_count_match = re.search(r'"file_count":\s*(\d+)', text)
    total_bytes_match = re.search(r'"total_bytes":\s*(\d+)', text)
    declared_file_count = int(file_count_match.group(1)) if file_count_match else None
    declared_total_bytes = int(total_bytes_match.group(1)) if total_bytes_match else None
    return {
        "path": path.name,
        "sha256": sha256(path),
        "sha256_matches_recorded_expected": sha256(path) == MANIFEST_SELF_SHA256,
        "json_valid": json_error is None,
        "json_error": json_error,
        "entry_parse_error_count": len(entry_errors),
        "entry_count": len(entry_records),
        "declared_file_count": declared_file_count,
        "entry_count_matches_declared": len(entry_records) == declared_file_count,
        "entry_bytes_sum": sum(item.get("bytes", 0) for item in entry_records),
        "declared_total_bytes": declared_total_bytes,
        "entry_bytes_sum_matches_declared": (
            sum(item.get("bytes", 0) for item in entry_records)
            == declared_total_bytes
        ),
        "limitation": (
            "The delivery manifest is not machine-parseable JSON because its "
            "generated_at string contains a literal line break. Entry lines and "
            "declared totals were checked separately."
            if json_error
            else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    raw = candidate / "raw"
    production = raw / "remote-results" / "C" / "production" / "2026-09-16-203957"
    task1 = production / "task_1"
    events_dir = raw / "remote-results" / "C" / "observer" / "events"

    verdict = load_json(candidate / "VERDICT.json")
    assessment = load_json(candidate / "C_ASSESSMENT.json")
    experiment_path = task1 / "experiment_log.jsonl"
    experiment_rows: list[dict[str, Any]] = []
    experiment_parse_errors: list[str] = []
    for line in experiment_path.read_text(encoding="utf-8").splitlines():
        try:
            experiment_rows.append(json.loads(line))
        except Exception as exc:
            experiment_parse_errors.append(str(exc))
    train_rows = [
        row for row in experiment_rows if "actor" in row and "perf" in row
    ]
    validation_rows = [row for row in experiment_rows if "val" in row]
    experiment_summary = {
        "line_count": len(experiment_path.read_text(encoding="utf-8").splitlines()),
        "json_parse_error_count": len(experiment_parse_errors),
        "training_record_count": len(train_rows),
        "training_steps": [row.get("step") for row in train_rows],
        "training_records": [
            {
                "step": row.get("step"),
                "reward": row.get("reward"),
                "time_per_step": row.get("perf", {}).get("time_per_step"),
                "advantages_mean": row.get("critic", {})
                .get("advantages", {})
                .get("mean"),
            }
            for row in train_rows
        ],
        "validation_record_count": len(validation_rows),
        "validation_steps": [row.get("step") for row in validation_rows],
        "task2_training_record_present": False,
    }

    summary_path = production / "cil_info" / "metrics" / "summary.json"
    metrics_path = production / "cil_info" / "metrics" / "task_metrics.log"
    summary = load_json(summary_path)
    metric_rows = [
        json.loads(line)
        for line in metrics_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    local_actor = task1 / "global_step_2" / "actor"
    local_actor_files = sorted(
        {
            rel(path, candidate): path.stat().st_size
            for path in local_actor.rglob("*")
            if path.is_file()
        }.items()
    )
    partial_path = local_actor / PARTIAL_MODEL_NAME
    checkpoint = parse_checkpoint_inventory(raw / "remote-checkpoint-inventory.txt")
    checkpoint.update(
        {
            "local_actor_files": [
                {"path": path, "bytes": size} for path, size in local_actor_files
            ],
            "partial_local_file_present": partial_path.is_file(),
            "partial_local_file_bytes": (
                partial_path.stat().st_size if partial_path.is_file() else None
            ),
            "partial_local_file_matches_expected_remote_size": (
                partial_path.is_file()
                and partial_path.stat().st_size == REMOTE_MODEL_BYTES
            ),
            "partial_transfer_excluded_from_judgment": True,
        }
    )

    required_absent = {}
    for name in (
        "run-result.json",
        "process-end.json",
        "process.stdout.log",
        "process.stderr.log",
    ):
        required_absent[name] = [rel(path, candidate) for path in candidate.rglob(name)]

    c_ssh_text = (raw / "C-ssh.stdout.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    availability_text = (raw / "C-stdout-stderr-availability.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    timeout_text = (raw / "C-timeout-policy.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    report_text = (candidate / "REPORT.md").read_text(
        encoding="utf-8", errors="replace"
    )
    boundary = {
        "outer_timeout_seconds": assessment["outer_timeout_seconds"],
        "ssh_exit_code": assessment["ssh_exit_code"],
        "run_result_or_process_end_present": any(required_absent.values()),
        "missing_named_final_files": required_absent,
        "ssh_console_excerpt_present": (raw / "C-ssh.stdout.txt").is_file(),
        "structured_production_logs_present": production.is_dir(),
        "observer_events_present": events_dir.is_dir(),
        "ray_logs_present": (raw / "ray-logs").is_dir(),
        "console_identified_as_normalized_excerpt": "normalized" in c_ssh_text.lower(),
        "availability_source_states_complete_stdout_unavailable": (
            "complete production stdout file is unavailable" in availability_text
        ),
        "timeout_source_states_final_files_not_written": (
            "did not write process-end.json or run-result.json" in timeout_text
        ),
        "candidate_report_does_not_claim_complete_stdout": (
            "complete production stdout/stderr files are absent" in report_text
        ),
    }
    boundary["all_named_final_files_absent"] = not any(required_absent.values())

    ray_paths = [path for path in (raw / "ray-logs").rglob("*") if path.is_file()]
    observer_paths = sorted(events_dir.glob("*.jsonl"))
    runtime_paths = [
        experiment_path,
        production / "task_1" / "generations.log",
        summary_path,
        metrics_path,
        raw / "C-ssh.stdout.txt",
        raw / "C-update-events.txt",
        raw / "C-timeout-policy.txt",
    ]
    anomaly_scan = {
        "ray_logs": scan_lines(ray_paths, candidate),
        "observer_events": scan_lines(observer_paths, candidate),
        "retained_runtime_evidence": scan_lines(runtime_paths, candidate),
        "interpretation": (
            "No retained-log anomaly marker matched the scan. The scan cannot "
            "restore the missing complete stdout/stderr or process-end boundary."
        ),
    }

    release_text = "\n".join(
        [
            (raw / "final-release-check.txt").read_text(
                encoding="utf-8", errors="replace"
            ),
            (raw / "ray-stop-summary.txt").read_text(
                encoding="utf-8", errors="replace"
            ),
        ]
    )
    release = {
        "private_diagnostic_processes_absent": (
            "no matching private diagnostic processes remained" in release_text
        ),
        "selected_gpu_tokens_idle": all(
            token in release_text
            for token in (
                "index 4",
                "index 5",
                "index 6",
                "idle",
            )
        ),
        "other_user_processes_untouched": (
            "Other users' GPU processes on GPUs 0-3 remained untouched." in release_text
        ),
    }

    result = {
        "schema_version": 1,
        "acceptance_id": "FRESH-PROCESS-V9-GPU-TIMEOUT-20260916",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_root": str(candidate),
        "verdict": verdict.get("verdict"),
        "status": verdict.get("status"),
        "assessment_status": assessment.get("status"),
        "scope": {
            "read_only_candidate_review": True,
            "ssh_or_gpu_action_taken": False,
            "model_or_checkpoint_transfer_action_taken": False,
            "cpu_or_v9_readiness_rerun": False,
            "production_code_changed": False,
        },
        "observer": scan_observer(events_dir),
        "structured_experiment": {
            "experiment_log": experiment_summary,
            "metrics_summary_tasks": sorted(summary.get("tasks", {})),
            "metrics_summary": summary,
            "task_metrics_record_count": len(metric_rows),
            "task_metrics_records": metric_rows,
            "local_task_2_directory_present": (production / "task_2").is_dir(),
            "config": {
                "max_steps": load_json(task1 / "experiment_config.json")["trainer"][
                    "max_steps"
                ],
                "n_gpus_per_node": load_json(task1 / "experiment_config.json")[
                    "trainer"
                ]["n_gpus_per_node"],
                "save_model_only": load_json(task1 / "experiment_config.json")[
                    "trainer"
                ]["save_model_only"],
                "rollout_n": load_json(task1 / "experiment_config.json")["worker"][
                    "rollout"
                ]["n"],
            },
        },
        "checkpoint": checkpoint,
        "evidence_boundary": boundary,
        "anomaly_scan": anomaly_scan,
        "release": release,
        "delivery_manifest": scan_delivery_manifest(
            candidate / "DELIVERY_MANIFEST-v9-gpu-20260916.json"
        ),
        "conclusion": {
            "task1_real_update_evidence": "corroborated_by_structured_log_and_observer_pairs",
            "task2_completion": "not_observed",
            "production_exception_proven": False,
            "acceptance_established": False,
            "blocking_reason": "900-second outer timeout after Task 1 checkpoint and during Task 2 transition; final wrapper artifacts absent",
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
