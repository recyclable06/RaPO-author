#!/usr/bin/env python3
"""Read-only independent probe for the v9 R2 C/A/B evidence package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


R2_MANIFEST_SHA256 = "7bc2d84c752ccd87982cb53ba8055dff0e25e5d23244541ba54067e0ee549244"
C_HASH_MANIFEST_SHA256 = "72dbe33d171cc2f9d1c6243d76aa75d7836395bbc6d4462c40db829c487fe7cd"
A_MARKER_SHA256 = "c7b8c132de4346bba8c570d429bdcbef603c0bbeea6bfd8803fea84175d4f795"
PRODUCTION_SOURCE_SHA256 = "3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3"
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


def experiment_summary(path: Path) -> dict[str, Any]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    training = [row for row in rows if "actor" in row and "critic" in row]
    validation = [row for row in rows if "val" in row]
    return {
        "path": path.name,
        "line_count": len(rows),
        "training_record_count": len(training),
        "training_steps": [row.get("step") for row in training],
        "training_records": [
            {
                "step": row.get("step"),
                "reward": row.get("reward"),
                "advantage_mean": row.get("critic", {}).get("advantages", {}).get("mean"),
                "retention_drift": row.get("reward", {}).get("retention_drift"),
                "retention_reward": row.get("reward", {}).get("retention_reward"),
            }
            for row in training
        ],
        "validation_record_count": len(validation),
        "validation_steps": [row.get("step") for row in validation],
    }


def high_risk_matches(paths: list[Path], root: Path) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if HIGH_RISK_RE.search(line):
                matches.append({"file": rel(path, root), "line": line_number, "text": line[:500]})
    return matches


def hash_manifest(path: Path) -> dict[str, Any]:
    rows = []
    bad = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split("\t")
        if len(parts) != 3 or not parts[1].isdigit() or not re.fullmatch(r"[0-9a-f]{64}", parts[2]):
            bad.append({"line": line_number, "text": line})
            continue
        rows.append({"path": parts[0], "bytes": int(parts[1]), "sha256": parts[2]})
    return {
        "path": path.name,
        "sha256": sha256(path),
        "sha256_matches_recorded": sha256(path) == C_HASH_MANIFEST_SHA256,
        "entry_count": len(rows),
        "bad_line_count": len(bad),
        "unique_path_count": len({row["path"] for row in rows}),
        "total_bytes": sum(row["bytes"] for row in rows),
        "declared_total_bytes": 36_314_240_992,
        "sha256_field_count": sum(len(row["sha256"]) == 64 for row in rows),
        "entries": rows,
    }


def source_review(source_root: Path, diagnostic_root: Path, identity: dict[str, Any]) -> dict[str, Any]:
    production = source_root / "examples" / "baselines" / "img_cls_cil" / "image_cls_cil_rapo.py"
    observer = diagnostic_root / "child_observer_v6.py"
    derivation = diagnostic_root / "boundary_evidence_v6.py"
    production_lines = production.read_text(encoding="utf-8").splitlines()
    observer_lines = observer.read_text(encoding="utf-8").splitlines()
    derivation_lines = derivation.read_text(encoding="utf-8").splitlines()

    def selected(lines: list[str], needles: tuple[str, ...]) -> list[dict[str, Any]]:
        return [
            {"line": index, "text": line}
            for index, line in enumerate(lines, 1)
            if any(needle in line for needle in needles)
        ]

    return {
        "production_file": str(production),
        "production_sha256": sha256(production),
        "production_sha256_matches_identity": sha256(production) == identity["source"]["production_entry_sha256"],
        "publication_lines": selected(
            production_lines,
            ("def _publish_task_boundary", "_atomic_write_json(os.path.join(boundary_root, driver_rel", "driver_rng_payload=_capture_driver_rng_state()", "if publish_task_boundary:", "worker_rng = trainer.actor_rollout_ref_wg.capture_boundary_vllm_rng()"),
        ),
        "observer_file": str(observer),
        "observer_sha256": sha256(observer),
        "observer_trigger_lines": selected(
            observer_lines,
            ("if label == \"PersistentRunner.run_task\"", "driver_rng_expected", "RAPO_DIAG_LEG", "ray.init", "runtime_env[\"env_vars\"]"),
        ),
        "derivation_file": str(derivation),
        "derivation_sha256": sha256(derivation),
        "derivation_lines": selected(
            derivation_lines,
            ("def _driver_record", "field=\"driver_rng_expected\"", "expected[\"driver\"] is None", "A actual post-publication driver RNG capture is missing"),
        ),
        "classification": "diagnostic_observation_or_collection_gap; production_publication_defect_not_proven",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--closeout", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--diagnostic", type=Path, required=True)
    args = parser.parse_args()

    candidate = args.candidate.resolve()
    raw = candidate / "raw"
    c = raw / "C-production"
    a = raw / "A-valid"
    identity = load_json(candidate / "FROZEN_V9_IDENTITY.json")
    verdict = load_json(candidate / "VERDICT.json")
    assessment = load_json(candidate / "C_ASSESSMENT.json")
    r2_manifest_path = candidate / "DELIVERY_MANIFEST-R2.json"
    r2_manifest = load_json(r2_manifest_path)
    r2_entries = r2_manifest["entries"]

    c_end = load_json(c / "process-end.json")
    c_result = load_json(c / "run-result.json")
    c_task1 = experiment_summary(c / "task_1" / "experiment_log.jsonl")
    c_task2 = experiment_summary(c / "task_2" / "experiment_log.jsonl")
    c_metrics = load_json(c / "cil_info" / "summary.json")
    c_hashes = hash_manifest(raw / "C-supervisor" / "checkpoint-hashes-C.tsv")
    c_files = (raw / "C-supervisor" / "checkpoint-hashes-C.tsv.files").read_text(encoding="utf-8").splitlines()
    c_hashes["files_listing_line_count"] = len(c_files)
    c_hashes["files_listing_total_bytes"] = sum(int(line.split(" ", 1)[0]) for line in c_files if line.split(" ", 1)[0].isdigit())
    c_hashes["observer_event_file_count"] = len(list((raw / "C-observer").rglob("*.jsonl")))
    c_hashes["production_stdout_bytes"] = (c / "process.stdout.log").stat().st_size
    c_hashes["production_stderr_bytes"] = (c / "process.stderr.log").stat().st_size

    a_end = load_json(a / "process-end.json")
    a_result = load_json(a / "run-result.json")
    a_marker_path = a / "task_1" / "task1-complete.json"
    a_marker = load_json(a_marker_path)
    a_boundary = load_json(a / "boundary-expected.json")
    a_task1 = experiment_summary(a / "task_1" / "experiment_log.jsonl")
    boundary_state_names = [
        "boundary_state/driver_rng.json",
        "boundary_state/vllm_rng_rank_0.json",
        "boundary_state/vllm_rng_rank_1.json",
    ]

    a_invalid_result = load_json(raw / "A-invalid" / "run-result.json")
    b_summary_path = raw / "B-timeout-observations.txt"
    b_summary = b_summary_path.read_text(encoding="utf-8")
    closeout = load_json(args.closeout / "VERDICT.json")
    closeout_identity = load_json(args.closeout / "FROZEN_CLOSEOUT_IDENTITY.json")

    c_anomaly_paths = [c / "process.stdout.log", c / "process.stderr.log"]
    a_anomaly_paths = [a / "process.stdout.log", a / "process.stderr.log"]

    result = {
        "schema_version": 1,
        "acceptance_id": "FRESH-PROCESS-V9-R2-20260917",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_root": str(candidate),
        "closeout_root": str(args.closeout.resolve()),
        "verdict": verdict,
        "assessment": assessment,
        "scope": {
            "read_only": True,
            "ssh_gpu_model_install_or_rerun": False,
            "production_or_candidate_modified": False,
            "remote_cleanup_confirmed": False,
        },
        "delivery_manifest": {
            "path": r2_manifest_path.name,
            "sha256": sha256(r2_manifest_path),
            "sha256_matches_recorded": sha256(r2_manifest_path) == R2_MANIFEST_SHA256,
            "entry_count": len(r2_entries),
            "declared_entry_count": r2_manifest.get("entry_count"),
            "entry_count_matches": len(r2_entries) == r2_manifest.get("entry_count"),
            "total_bytes": sum(entry["bytes"] for entry in r2_entries),
            "declared_total_bytes": r2_manifest.get("total_bytes"),
            "total_bytes_matches": sum(entry["bytes"] for entry in r2_entries) == r2_manifest.get("total_bytes"),
            "self_excluded": r2_manifest.get("self_excluded"),
        },
        "C": {
            "classification": "PASS_CONTINUOUS_PRODUCTION_C_ONLY",
            "process_end": {key: c_end.get(key) for key in ("exit_code", "pid", "process_start_ns", "unix")},
            "run_result": {key: c_result.get(key) for key in ("status", "exit_code", "model_constructed", "training_started", "stdout_bytes", "stderr_bytes")},
            "task1": c_task1,
            "task2": c_task2,
            "metrics_summary": c_metrics,
            "checkpoint_hash_manifest": c_hashes,
            "high_risk_log_matches": high_risk_matches(c_anomaly_paths, candidate),
            "raw_observer_events_present": c_hashes["observer_event_file_count"] > 0,
            "reusable_scope": [
                "continuous C Task 1/Task 2 update counts and metrics",
                "C launcher/child exit-0 and complete stdout/stderr/process boundary",
                "remote checkpoint file-size and per-file SHA256 inventory",
                "C frozen identity and production-path evidence"
            ],
            "not_reusable_scope": [
                "fresh-process exact resume",
                "A full boundary proof or B restore proof",
                "local byte rehash of the remote checkpoint files"
            ],
        },
        "A_valid": {
            "classification": "PASS_TASK1_MARKER_BUT_BOUNDARY_INCOMPLETE",
            "process_end": {key: a_end.get(key) for key in ("exit_code", "pid", "process_start_ns", "unix")},
            "run_result": {key: a_result.get(key) for key in ("status", "exit_code", "a_published_and_stopped", "boundary_expected_complete", "model_constructed", "training_started")},
            "marker": {
                "local_sha256": sha256(a_marker_path),
                "local_bytes": a_marker_path.stat().st_size,
                "matches_recorded_sha256": sha256(a_marker_path) == A_MARKER_SHA256,
                "status": a_marker.get("status"),
                "global_step": a_marker.get("global_step"),
                "completed_task": a_marker.get("completed_task"),
                "next_task": a_marker.get("next_task"),
                "state_fingerprint": a_marker.get("state_fingerprint"),
                "rng_references": a_marker.get("rng"),
            },
            "task1": a_task1,
            "boundary_expected": {
                "complete": a_boundary.get("complete"),
                "driver": a_boundary.get("driver"),
                "native_ranks": sorted(a_boundary.get("native_by_rank", {})),
                "vllm_ranks": sorted(a_boundary.get("vllm_by_rank", {})),
                "checkpoint_global_steps": a_boundary.get("checkpoint_global_steps"),
                "errors": a_boundary.get("errors"),
            },
            "raw_observer_event_file_count": len(list((a / "observer" / "events").glob("*.jsonl"))),
            "boundary_state_files_present": {name: (a / name).is_file() for name in boundary_state_names},
            "high_risk_log_matches": high_risk_matches(a_anomaly_paths, candidate),
            "reusable_scope": [
                "A-valid Task 1 production execution and 2 update records",
                "marker bytes/hash/global_step/status and stop-before-Task-2 result",
                "Task 1 checkpoint manifest carried inside the marker"
            ],
            "not_reusable_scope": [
                "full exact boundary evidence",
                "independent proof of the marker-referenced driver/vLLM boundary files",
                "fresh-process exact resume acceptance"
            ],
        },
        "A_invalid": {
            "classification": "NON_TRAINING_GPU_PREFLIGHT_BLOCK",
            "result": {key: a_invalid_result.get(key) for key in ("status", "leg", "model_constructed", "training_started", "error")},
            "scientific_effect": "none",
        },
        "B_valid": {
            "classification": "RESTORE_STAGE_TIMEOUT_INCOMPLETE",
            "candidate_raw_files": [rel(path, candidate) for path in sorted((raw / "B-valid").rglob("*")) if path.is_file()],
            "summary_source": {
                "path": rel(b_summary_path, candidate),
                "sha256": sha256(b_summary_path),
                "is_summary_not_raw": True,
                "textual_markers": {
                    "no_task2_experiment_log_at_last_check": "no Task 2 experiment_log.jsonl" in b_summary,
                    "d_state_observed": "folio_wait_bit_common / D (disk sleep)" in b_summary,
                    "high_rchar_observed": "rchar=45391631405" in b_summary,
                    "sigterm_child_only": "SIGTERM was sent only to PID 1153372" in b_summary,
                    "launcher_not_signaled": "The launcher was not signaled" in b_summary,
                    "ray_pipe_orphan_observation": "private Ray workers retained the child output pipes" in b_summary,
                    "ssh_stream_reset": "SSH launch session then reset" in b_summary,
                },
            },
            "facts_vs_inference": {
                "observed_or_recorded": [
                    "validated child identity and checkpoint-restore-stage position in the retained observation summary",
                    "zero Task 2 update evidence at the last successful remote check",
                    "child-only SIGTERM was recorded after identity revalidation",
                    "launcher finalization and exit classification were not obtained"
                ],
                "not_established": [
                    "I/O as the root cause",
                    "a production code defect as the root cause",
                    "B process exit code and final stdout/stderr",
                    "final Ray/launcher/child/GPU release state"
                ],
            },
            "reusable_scope": ["negative evidence that B did not establish Task 2 progress or exact resume"],
            "not_reusable_scope": ["Task 2 result", "restore pass", "exit status", "final cleanup/release claim"],
        },
        "closeout": {
            "verdict": closeout,
            "identity": closeout_identity,
            "raw_stdout_bytes": (args.closeout / "raw" / "211-readonly.stdout.txt").stat().st_size,
            "raw_stderr": (args.closeout / "raw" / "211-readonly.stderr.txt").read_text(encoding="utf-8", errors="replace"),
            "remote_cleanup_state": "UNCONFIRMED_HOST_UNREACHABLE",
        },
        "source_review": source_review(args.source.resolve(), args.diagnostic.resolve(), identity),
        "overall": {
            "fresh_process_exact_resume": False,
            "paper_faithful_reproduction": False,
            "B_only_rerun_sufficient_for_acceptance": False,
            "minimum_recovery_path": [
                "Keep C continuous-production evidence and its full checkpoint hash inventory reusable.",
                "First repair/isolate the diagnostic A driver-RNG observation path and collect raw A events plus all marker-referenced boundary_state files; do not fabricate RNG.",
                "Only after A full boundary evidence is complete, rerun B as a fresh process with complete raw stdout/stderr/process-end/run-result and observer/Ray evidence.",
                "Keep the original reward/advantage/retention tolerances unchanged and verify B Task 2 updates plus boundary comparison."
            ],
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
