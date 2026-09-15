#!/usr/bin/env python3
"""Independent, read-only acceptance probe for effective-update attempt-15.

This script intentionally reads the frozen diagnostic tree and the integration
source tree.  It does not import or execute production code, rerun a GPU job,
or rewrite the diagnostic manifest.  It records compact evidence and its own
judgement so the acceptance is independent of the executor's judge.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def compact(value: Any, limit: int = 320) -> Any:
    if isinstance(value, dict):
        return {key: compact(item, limit) for key, item in list(value.items())[:20]}
    if isinstance(value, list):
        if len(value) > 12:
            return {"type": "array", "length": len(value), "head": [compact(x, limit) for x in value[:3]]}
        return [compact(item, limit) for item in value]
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    return value


def path_get(root: Any, path: str, default: Any = None) -> Any:
    cur = root
    if not path:
        return cur
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return default
    return cur


def walk(node: Any, path: str = "") -> Iterable[tuple[str, Any]]:
    yield path, node
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else key
            yield from walk(value, child)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk(value, f"{path}[{index}]")


def schema_summary(node: Any, depth: int = 0, max_depth: int = 4) -> Any:
    if depth > max_depth:
        if isinstance(node, list):
            return {"type": "array", "length": len(node)}
        if isinstance(node, dict):
            return {"type": "object", "keys": list(node)[:30]}
        return type(node).__name__
    if isinstance(node, dict):
        return {key: schema_summary(value, depth + 1, max_depth) for key, value in node.items()}
    if isinstance(node, list):
        return {"type": "array", "length": len(node), "item": schema_summary(node[0], depth + 1, max_depth) if node else None}
    return type(node).__name__


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def first_present(root: Any, paths: Iterable[str]) -> tuple[str | None, Any]:
    for path in paths:
        value = path_get(root, path, None)
        if value is not None:
            return path, value
    return None, None


def walk_bounded(node: Any, path: str = "", depth: int = 0, max_depth: int = 12, max_array_items: int = 24) -> Iterable[tuple[str, Any]]:
    """Walk scalar/object metadata without expanding large evidence arrays."""
    yield path, node
    if depth >= max_depth:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else key
            yield from walk_bounded(value, child, depth + 1, max_depth, max_array_items)
    elif isinstance(node, list) and len(node) <= max_array_items:
        for index, value in enumerate(node):
            yield from walk_bounded(value, f"{path}[{index}]", depth + 1, max_depth, max_array_items)


def collect_interesting(root: Any) -> list[dict[str, Any]]:
    needles = (
        "hook", "ema", "sync", "anchor", "worker", "uuid", "optimizer", "advantage",
        "parameter", "param", "grad", "generation", "generate", "input", "image", "ray",
        "cuda", "error", "source", "model", "environment", "sample", "stale", "changed",
    )
    hits: list[dict[str, Any]] = []
    for path, value in walk_bounded(root):
        key = path.rsplit(".", 1)[-1].split("[", 1)[0].lower()
        if not any(needle in key for needle in needles):
            continue
        if isinstance(value, (dict, list)) and len(value) > 30:
            shown = {"type": "array" if isinstance(value, list) else "object", "length": len(value)}
        else:
            shown = compact(value)
        hits.append({"path": path, "value": shown})
    return hits


def verify_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / "HASHES.json"
    manifest_hash = sha256_file(manifest_path)
    manifest = json_load(manifest_path)
    checks: list[dict[str, Any]] = []
    for rel, expected in sorted(manifest.get("files", {}).items()):
        path = root / rel
        item = {
            "path": rel,
            "exists": path.is_file(),
            "bytes_expected": expected.get("bytes"),
            "bytes_actual": path.stat().st_size if path.is_file() else None,
            "sha256_expected": expected.get("sha256"),
            "sha256_actual": sha256_file(path) if path.is_file() else None,
        }
        item["ok"] = (
            item["exists"]
            and item["bytes_actual"] == item["bytes_expected"]
            and item["sha256_actual"] == item["sha256_expected"]
        )
        checks.append(item)
    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_hash,
        "self_excluded": manifest.get("self_excluded"),
        "declared_file_count": len(checks),
        "all_files_match": all(item["ok"] for item in checks),
        "mismatches": [item for item in checks if not item["ok"]],
    }


def source_inventory(root: Path) -> dict[str, Any]:
    # Source identity is checked from the integration worktree without importing
    # code.  The exact manifest and handoff text remain the authoritative record.
    manifest_path = root / "docs" / "INTEGRATION_HASHES.json"
    manifest = json_load(manifest_path)
    key_files = list(manifest.get("algorithm_files", [])) + list(manifest.get("test_files", []))
    key_checks = []
    for item in key_files:
        path = root / Path(item["path"])
        actual = sha256_file(path) if path.is_file() else None
        expected = item.get("integrated_sha256") or item.get("source_a_sha256")
        key_checks.append({
            "path": item["path"],
            "exists": path.is_file(),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "source_match_recorded": item.get("source_match"),
            "ok": path.is_file() and actual == expected and item.get("source_match") is True,
        })
    files = sorted(path for path in root.rglob("*") if path.is_file() and ".git" not in path.parts)
    return {
        "root": str(root),
        "worktree_file_count_including_untracked_runtime_cache": len(files),
        "integration_manifest_sha256": sha256_file(manifest_path),
        "integration_manifest_sha256_expected": "6514f4dca401ffc805ae57031d1926f742e531ce0fbb981448315538ade8b0b1",
        "integration_manifest_hash_ok": sha256_file(manifest_path) == "6514f4dca401ffc805ae57031d1926f742e531ce0fbb981448315538ade8b0b1",
        "integration_handoff_sha256": sha256_file(root / "docs" / "INTEGRATION_HANDOFF.md") if (root / "docs" / "INTEGRATION_HANDOFF.md").is_file() else None,
        "key_file_count": len(key_checks),
        "key_files_all_match": all(item["ok"] for item in key_checks),
        "key_files": key_checks,
    }


def _snapshot_workers(snapshot: Any) -> dict[int, dict[str, Any]]:
    if not isinstance(snapshot, dict):
        return {}
    result: dict[int, dict[str, Any]] = {}
    for worker in snapshot.get("workers", []):
        if isinstance(worker, dict) and isinstance(worker.get("rank"), int):
            result[worker["rank"]] = worker
    return result


def _record_values(record: Any) -> list[float]:
    if not isinstance(record, dict) or not isinstance(record.get("values"), list):
        return []
    return [float(value) for value in record["values"] if isinstance(value, (int, float))]


def _record_summary_delta(left: Any, right: Any) -> float:
    fields = ("sum", "abs_sum", "sum_squares", "max_abs")
    deltas = []
    for field in fields:
        if isinstance(left, dict) and isinstance(right, dict) and isinstance(left.get(field), (int, float)) and isinstance(right.get(field), (int, float)):
            deltas.append(abs(float(left[field]) - float(right[field])))
    return max(deltas, default=0.0)


def compare_modules(left: Any, left_module: str, right: Any, right_module: str, label: str) -> dict[str, Any]:
    """Compare only recorded samples and summary statistics; never claim full tensors."""
    left_workers = _snapshot_workers(left)
    right_workers = _snapshot_workers(right)
    sample_count = 0
    changed_sample_count = 0
    changed_parameter_count = 0
    max_sample_delta = 0.0
    max_summary_delta = 0.0
    all_finite = True
    record_count = 0
    missing = []
    scopes: set[str] = set()
    for rank in sorted(set(left_workers) | set(right_workers)):
        lmod = left_workers.get(rank, {}).get(left_module, {})
        rmod = right_workers.get(rank, {}).get(right_module, {})
        lrecords = lmod.get("samples", {}) if isinstance(lmod, dict) else {}
        rrecords = rmod.get("samples", {}) if isinstance(rmod, dict) else {}
        keys = sorted(set(lrecords) & set(rrecords))
        missing.extend([f"rank{rank}:{key}" for key in sorted(set(lrecords) ^ set(rrecords))])
        for key in keys:
            record_count += 1
            left_record = lrecords[key]
            right_record = rrecords[key]
            scopes.update(str(item.get("summary_scope")) for item in (left_record, right_record) if isinstance(item, dict) and item.get("summary_scope") is not None)
            lvalues = _record_values(left_record)
            rvalues = _record_values(right_record)
            if len(lvalues) != len(rvalues):
                missing.append(f"rank{rank}:{key}:sample_length")
                continue
            record_changed = False
            for lvalue, rvalue in zip(lvalues, rvalues):
                all_finite = all_finite and math.isfinite(lvalue) and math.isfinite(rvalue)
                delta = abs(lvalue - rvalue)
                sample_count += 1
                max_sample_delta = max(max_sample_delta, delta)
                if delta != 0.0:
                    changed_sample_count += 1
                    record_changed = True
            summary_delta = _record_summary_delta(left_record, right_record)
            max_summary_delta = max(max_summary_delta, summary_delta)
            record_changed = record_changed or summary_delta != 0.0
            changed_parameter_count += int(record_changed)
    return {
        "label": label,
        "record_count": record_count,
        "sample_count": sample_count,
        "changed_sample_count": changed_sample_count,
        "changed_parameter_count": changed_parameter_count,
        "max_abs_sample_delta": max_sample_delta,
        "max_summary_stat_abs_delta": max_summary_delta,
        "all_recorded_values_finite": all_finite,
        "summary_scopes": sorted(scopes),
        "missing_or_mismatched": missing,
        "full_parameter_equality_proven": False,
        "sampled_equal": bool(not missing and changed_sample_count == 0 and max_summary_delta == 0.0),
        "sampled_changed": bool(not missing and changed_sample_count > 0),
    }


def compare_sync_candidate(event: Any, key: str, stage: str) -> dict[str, Any]:
    sample_count = 0
    changed_sample_count = 0
    max_sample_delta = 0.0
    max_summary_delta = 0.0
    missing = []
    scopes: set[str] = set()
    before = event.get("before", {}) if isinstance(event, dict) else {}
    after = event.get("after", {}) if isinstance(event, dict) else {}
    snapshot = before if stage == "before" else after if stage == "after" else None
    candidates = snapshot.get("candidates", {}) if isinstance(snapshot, dict) else {}
    candidate = candidates.get(key, {}) if isinstance(candidates, dict) else {}
    actor = candidate.get("actor") if isinstance(candidate, dict) else None
    vllm = candidate.get("vllm") if isinstance(candidate, dict) else None
    if not isinstance(actor, dict) or not isinstance(vllm, dict):
        missing.append(f"{stage}:{key}")
    else:
        scopes.update(str(item.get("summary_scope")) for item in (actor, vllm) if item.get("summary_scope") is not None)
        actor_values = _record_values(actor)
        vllm_values = _record_values(vllm)
        if len(actor_values) != len(vllm_values):
            missing.append(f"{stage}:{key}:sample_length")
        else:
            for actor_value, vllm_value in zip(actor_values, vllm_values):
                sample_count += 1
                delta = abs(actor_value - vllm_value)
                max_sample_delta = max(max_sample_delta, delta)
                if delta != 0.0:
                    changed_sample_count += 1
            max_summary_delta = _record_summary_delta(actor, vllm)
    return {
        "key": key,
        "sample_count": sample_count,
        "changed_sample_count": changed_sample_count,
        "max_abs_sample_delta": max_sample_delta,
        "max_summary_stat_abs_delta": max_summary_delta,
        "summary_scopes": sorted(scopes),
        "missing_or_mismatched": missing,
        "sampled_equal": bool(not missing and changed_sample_count == 0),
        "sampled_nonzero_difference": bool(not missing and changed_sample_count > 0),
        "summary_stats_equal": bool(not missing and max_summary_delta == 0.0),
        "full_parameter_equality_proven": False,
    }


def compare_event_actor_records(events_left: list[dict[str, Any]], events_right: list[dict[str, Any]], key: str, left_stage: str, right_stage: str, label: str) -> dict[str, Any]:
    sample_count = 0
    changed_sample_count = 0
    max_sample_delta = 0.0
    max_summary_delta = 0.0
    missing = []
    by_rank_left = {item.get("rank"): item.get("event", {}) for item in events_left}
    by_rank_right = {item.get("rank"): item.get("event", {}) for item in events_right}
    for rank in sorted(set(by_rank_left) | set(by_rank_right)):
        left_event = by_rank_left.get(rank, {})
        right_event = by_rank_right.get(rank, {})
        left_candidate = (left_event.get(left_stage, {}).get("candidates", {}) or {}).get(key, {})
        right_candidate = (right_event.get(right_stage, {}).get("candidates", {}) or {}).get(key, {})
        left_record = left_candidate.get("actor") if isinstance(left_candidate, dict) else None
        right_record = right_candidate.get("actor") if isinstance(right_candidate, dict) else None
        if not isinstance(left_record, dict) or not isinstance(right_record, dict):
            missing.append(f"rank{rank}:{key}")
            continue
        left_values = _record_values(left_record)
        right_values = _record_values(right_record)
        if len(left_values) != len(right_values):
            missing.append(f"rank{rank}:{key}:sample_length")
            continue
        for left_value, right_value in zip(left_values, right_values):
            sample_count += 1
            delta = abs(left_value - right_value)
            max_sample_delta = max(max_sample_delta, delta)
            if delta != 0.0:
                changed_sample_count += 1
        max_summary_delta = max(max_summary_delta, _record_summary_delta(left_record, right_record))
    return {
        "label": label,
        "key": key,
        "sample_count": sample_count,
        "changed_sample_count": changed_sample_count,
        "max_abs_sample_delta": max_sample_delta,
        "max_summary_stat_abs_delta": max_summary_delta,
        "missing_or_mismatched": missing,
        "sampled_equal": bool(not missing and changed_sample_count == 0 and max_summary_delta == 0.0),
        "sampled_changed": bool(not missing and changed_sample_count > 0),
        "sampled_nonzero_difference": bool(not missing and changed_sample_count > 0),
        "full_parameter_equality_proven": False,
    }


def _latest_sync_events(snapshot: Any) -> list[dict[str, Any]]:
    events = []
    for rank, worker in sorted(_snapshot_workers(snapshot).items()):
        history = worker.get("sync_history", [])
        if isinstance(history, list) and history:
            events.append({"rank": rank, "event": history[-1], "history_length": len(history)})
    return events


def _phase_summary(fit: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "before_update": "before_actor_update",
        "after_update": "after_actor_update_before_vllm_sync",
        "after_vllm_sync": "after_production_vllm_sync",
        "after_fit": "after_fit_before_new_anchor_copy",
        "after_anchor_copy": "after_actor_to_anchor_copy",
    }
    phases = {}
    for name, phase in expected.items():
        value = fit.get(name, {})
        workers = _snapshot_workers(value)
        phases[name] = {
            "recorded_phase": value.get("phase") if isinstance(value, dict) else None,
            "expected_phase": phase,
            "phase_name_match": isinstance(value, dict) and value.get("phase") == phase,
            "world_size": value.get("world_size") if isinstance(value, dict) else None,
            "workers": [
                {
                    "rank": rank,
                    "hostname": worker.get("hostname"),
                    "cuda_visible_devices": worker.get("cuda_visible_devices"),
                    "manager_loaded": (worker.get("manager_state") or {}).get("loaded"),
                    "sync_history_length": len(worker.get("sync_history", [])) if isinstance(worker.get("sync_history"), list) else None,
                    "event_indices": [event.get("event_index") for event in worker.get("sync_history", [])] if isinstance(worker.get("sync_history"), list) else [],
                }
                for rank, worker in sorted(workers.items())
            ],
        }
    return phases


def _static_source_audit(diagnostic_root: Path, source_root: Path, raw: dict[str, Any]) -> dict[str, Any]:
    probe_path = diagnostic_root / "effective_update_probe.py"
    probe = probe_path.read_text(encoding="utf-8") if probe_path.is_file() else ""
    sync_path = source_root / "verl" / "workers" / "sharding_manager" / "fsdp_vllm.py"
    trainer_path = source_root / "verl" / "trainer" / "ray_trainer.py"
    worker_path = source_root / "verl" / "workers" / "fsdp_workers.py"
    rapo_path = source_root / "examples" / "baselines" / "_rapo_components.py"
    source_text = {
        "sync_manager": sync_path.read_text(encoding="utf-8") if sync_path.is_file() else "",
        "trainer": trainer_path.read_text(encoding="utf-8") if trainer_path.is_file() else "",
        "worker": worker_path.read_text(encoding="utf-8") if worker_path.is_file() else "",
        "rapo": rapo_path.read_text(encoding="utf-8") if rapo_path.is_file() else "",
    }
    checks = {
        "probe_uses_production_persistent_runner": "rapo.PersistentRunner.__ray_actor_class__" in probe,
        "probe_calls_unchanged_trainer_fit": "trainer.fit()" in probe,
        "probe_wraps_original_actor_update": "original_update = group.update_actor" in probe and "output = original_update(batch)" in probe,
        "probe_wraps_original_advantage_hook": "original_hook = trainer._compute_advantage_with_hooks" in probe and "result = original_hook(data" in probe,
        "probe_wraps_original_sync": "original_sync = manager_class._sync_weight_to_vllm" in probe and "result = original_sync(manager_self)" in probe,
        "probe_defers_vllm_observation_until_loaded": "production _sync_weight_to_vllm entered before vLLM wake/load boundary" in probe and "getattr(manager_self, \"loaded\", False)" in probe,
        "probe_has_no_direct_load_weights_call": re.search(r"^\s*[A-Za-z_][\w.]*\.load_weights\(", probe, re.MULTILINE) is None,
        "production_sync_gathers_and_loads_weights": "def _sync_weight_to_vllm" in source_text["sync_manager"] and "model.load_weights" in source_text["sync_manager"],
        "production_wakes_before_sync": "self.inference_engine.wake_up" in source_text["sync_manager"] and "self._sync_weight_to_vllm()" in source_text["sync_manager"],
        "production_actor_update_calls_policy": "def update_actor" in source_text["worker"] and "self.actor.update_policy(data=data)" in source_text["worker"],
        "production_fit_calls_actor_update": "self.actor_rollout_ref_wg.update_actor(batch)" in source_text["trainer"],
        "production_rapo_fit_installs_hook": "ray_trainer_module.compute_advantage = self._compute_advantage_with_hooks" in source_text["rapo"] and "super().fit()" in source_text["rapo"],
        "production_rapo_hook_uses_ema": "self.ema_adv.compute_grpo_advantage(data)" in source_text["rapo"],
    }
    manifest_path = source_root / "docs" / "INTEGRATION_HASHES.json"
    expected_runtime = {
        "source": raw.get("source"),
        "model": raw.get("model"),
        "inputs": raw.get("inputs"),
    }
    constants = {}
    for name in ("SOURCE", "MODEL", "INPUTS"):
        match = re.search(rf"^{name}\s*=\s*[\"']([^\"']+)[\"']", probe, re.MULTILINE)
        constants[name.lower()] = match.group(1) if match else None
    return {
        "diagnostic_probe_sha256": sha256_file(probe_path) if probe_path.is_file() else None,
        "runtime_identity": expected_runtime,
        "probe_constants": constants,
        "runtime_identity_matches_probe_constants": {
            "source": expected_runtime["source"] == constants.get("source"),
            "model": expected_runtime["model"] == constants.get("model"),
            "inputs": expected_runtime["inputs"] == constants.get("inputs"),
        },
        "checks": checks,
        "all_static_chain_checks_pass": all(checks.values()),
        "integration_manifest_sha256": sha256_file(manifest_path) if manifest_path.is_file() else None,
    }


def _run_log_audit(diagnostic_root: Path) -> dict[str, Any]:
    meta = diagnostic_root / "attempt-15" / "meta"
    stdout_path = meta / "run.stdout"
    stderr_path = meta / "run.stderr"
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.is_file() else ""
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.is_file() else ""
    save_lines = [line.strip() for line in stdout.splitlines() if "Saving model to" in line]
    error_pattern = re.compile(r"illegal memory access|CUDA error|out of memory|Traceback|RuntimeError", re.IGNORECASE)
    stderr_errors = [line.strip() for line in stderr.splitlines() if error_pattern.search(line)]
    prior = {}
    for attempt in (9, 11, 13):
        path = diagnostic_root / f"attempt-{attempt}" / "meta" / "run.stderr"
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        prior[str(attempt)] = [line.strip() for line in text.splitlines() if error_pattern.search(line)][:5]
    exit_path = meta / "run.exitcode"
    exit_code = exit_path.read_text(encoding="utf-8", errors="replace").strip() if exit_path.is_file() else None
    return {
        "run_start": (meta / "run-start.txt").read_text(encoding="utf-8", errors="replace").strip() if (meta / "run-start.txt").is_file() else None,
        "run_finish": (meta / "run-finish.txt").read_text(encoding="utf-8", errors="replace").strip() if (meta / "run-finish.txt").is_file() else None,
        "run_exitcode": exit_code,
        "attempt15_stderr_error_like_lines": stderr_errors[:20],
        "attempt15_cuda_error_free": not stderr_errors,
        "prior_cuda_error_samples": prior,
        "checkpoint_save_log_lines": save_lines[:20],
        "checkpoint_save_log_count": len(save_lines),
        "checkpoint_write_observed_in_log": bool(save_lines),
        "runtime_identity_markers": {
            "qwen2_vl_model_loaded": "Qwen2VLForConditionalGeneration" in stdout,
            "image_input_key_seen": "image_key: images" in stdout,
            "generation_batch_four_seen": "current_batch_size=4" in stdout,
            "input_path_seen": "/mnt/conda/zhenglifeng/t/eu-p1-20260908/inputs" in stdout,
        },
    }


def evaluate(raw: dict[str, Any], diagnostic_root: Path, source_root: Path) -> dict[str, Any]:
    fit = raw.get("fit", {}) if isinstance(raw.get("fit"), dict) else {}
    before = fit.get("before_update", {})
    after_update = fit.get("after_update", {})
    after_fit = fit.get("after_fit", {})
    after_copy = fit.get("after_anchor_copy", {})

    initial_actor_anchor = compare_modules(
        raw.get("initial_anchor_copy", {}), "actor", raw.get("initial_anchor_copy", {}), "anchor", "initial actor vs initial anchor"
    )
    actor_sample_delta = compare_modules(before, "actor_trainable", after_update, "actor_trainable", "before update vs after update actor trainable samples")
    old_anchor_stable = compare_modules(before, "anchor", after_update, "anchor", "old anchor before vs after actor update")
    updated_actor_vs_old_anchor = compare_modules(after_update, "actor_trainable", after_update, "anchor", "updated actor vs old anchor")
    new_anchor_match = compare_modules(after_fit, "actor_trainable", after_copy, "anchor", "post-fit actor vs copied new anchor")

    before_events = _latest_sync_events(after_fit)
    initial_events = []
    for rank, worker in sorted(_snapshot_workers(after_fit).items()):
        history = worker.get("sync_history", [])
        if isinstance(history, list) and history:
            initial_events.append({"rank": rank, "event": history[0], "history_length": len(history)})
    selected_keys = []
    for item in before_events:
        selected = item.get("event", {}).get("selected", {})
        if isinstance(selected, dict) and selected.get("actor_key"):
            selected_keys.append(selected.get("actor_key"))
    mapped_key = selected_keys[0] if selected_keys and len(set(selected_keys)) == 1 else None
    stale_checks = [compare_sync_candidate(item.get("event", {}), mapped_key, "before") for item in before_events] if mapped_key else []
    synced_checks = [compare_sync_candidate(item.get("event", {}), mapped_key, "after") for item in before_events] if mapped_key else []
    mapped_actor_update_checks = [
        compare_event_actor_records(initial_events, before_events, mapped_key, "after", "before", "initial synced actor vs post-update actor before sync")
    ] if mapped_key else []

    def aggregate(checks: list[dict[str, Any]], label: str) -> dict[str, Any]:
        return {
            "label": label,
            "worker_count": len(checks),
            "sample_count": sum(item.get("sample_count", 0) for item in checks),
            "changed_sample_count": sum(item.get("changed_sample_count", 0) for item in checks),
            "max_abs_sample_delta": max((item.get("max_abs_sample_delta", 0.0) for item in checks), default=0.0),
            "max_summary_stat_abs_delta": max((item.get("max_summary_stat_abs_delta", 0.0) for item in checks), default=0.0),
            "missing_or_mismatched": [missing for item in checks for missing in item.get("missing_or_mismatched", [])],
            "summary_scopes": sorted({scope for item in checks for scope in item.get("summary_scopes", [])}),
            "sampled_equal": bool(checks and all(item.get("sampled_equal") for item in checks)),
            "sampled_nonzero_difference": bool(checks and all(item.get("sampled_nonzero_difference") for item in checks)),
            "summary_stats_equal": bool(checks and all(item.get("summary_stats_equal") for item in checks)),
            "full_parameter_equality_proven": False,
        }

    stale_vllm = aggregate(stale_checks, "actor vs stale vLLM before production sync")
    synced_vllm = aggregate(synced_checks, "actor vs vLLM after production sync")
    mapped_actor_update = aggregate(mapped_actor_update_checks, "mapped actor initial vs post-update")

    advantages = fit.get("advantages", {}) if isinstance(fit.get("advantages"), dict) else {}
    ema_before = fit.get("ema_state_before", {}) if isinstance(fit.get("ema_state_before"), dict) else {}
    ema_after = fit.get("ema_state", {}) if isinstance(fit.get("ema_state"), dict) else {}
    grad_values = []
    metrics = fit.get("update_metrics", {}) if isinstance(fit.get("update_metrics"), dict) else {}
    for value in metrics.get("actor/grad_norm", []):
        if isinstance(value, (int, float)):
            grad_values.append(float(value))
    log_prob_delta = fit.get("actor_log_prob_delta", {}) if isinstance(fit.get("actor_log_prob_delta"), dict) else {}
    generation = fit.get("post_sync_generation", {}) if isinstance(fit.get("post_sync_generation"), dict) else {}
    config = raw.get("config", {}) if isinstance(raw.get("config"), dict) else {}
    ray_mapping = raw.get("ray_mapping", {}) if isinstance(raw.get("ray_mapping"), dict) else {}
    selected_rows = raw.get("resource_gate", {}).get("selected", []) if isinstance(raw.get("resource_gate"), dict) else []
    worker_devices = [
        {
            "rank": worker.get("rank"),
            "hostname": worker.get("hostname"),
            "cuda_visible_devices": worker.get("cuda_visible_devices"),
            "ray_gpu_ids": (worker.get("worker_device_mapping") or {}).get("ray_gpu_ids"),
            "uuids": (worker.get("worker_device_mapping") or {}).get("torch_properties"),
        }
        for _, worker in sorted(_snapshot_workers(before).items())
    ]

    static_audit = _static_source_audit(diagnostic_root, source_root, raw)
    log_audit = _run_log_audit(diagnostic_root)
    flags = {
        "result_status_pass": raw.get("status") == "pass",
        "run_exitcode_zero": log_audit.get("run_exitcode") == "0",
        "attempt15_cuda_error_free": log_audit.get("attempt15_cuda_error_free") is True,
        "static_production_chain_proven": static_audit.get("all_static_chain_checks_pass") is True,
        "runtime_identity_matches_probe": all(static_audit.get("runtime_identity_matches_probe_constants", {}).values()),
        "world_size_two": before.get("world_size") == 2 and after_update.get("world_size") == 2,
        "worker_phases_correct": all(item.get("phase_name_match") for item in _phase_summary(fit).values()),
        "mapping_expected_physical_4_6": ray_mapping.get("expected_physical_indices") == [4, 6] and ray_mapping.get("mapping_check", {}).get("status") == "pass",
        "workers_expose_physical_4_6": sorted(int(item.get("ray_gpu_ids", [None])[0]) for item in worker_devices if item.get("ray_gpu_ids")) == [4, 6],
        "ctan_hook_once": fit.get("hook_calls") == 1,
        "advantages_finite_and_nonzero": advantages.get("total_count") == 1536 and advantages.get("finite_count") == 1536 and advantages.get("nonzero_count") == 1029,
        "ema_count_0_to_1": ema_before.get("update_count") == 0 and ema_after.get("update_count") == 1,
        "gradients_finite_nonzero": bool(grad_values) and all(math.isfinite(value) and value != 0.0 for value in grad_values),
        "actor_sampled_change": actor_sample_delta.get("sampled_changed") is True and actor_sample_delta.get("changed_parameter_count") == 16,
        "initial_actor_anchor_sampled_match": initial_actor_anchor.get("sampled_equal") is True,
        "old_anchor_sampled_stable": old_anchor_stable.get("sampled_equal") is True,
        "updated_actor_differs_from_old_anchor": updated_actor_vs_old_anchor.get("sampled_changed") is True,
        "new_anchor_sampled_matches_actor": new_anchor_match.get("sampled_equal") is True,
        "mapped_actor_sampled_change": mapped_actor_update.get("sampled_nonzero_difference") is True,
        "stale_vllm_sampled_difference": stale_vllm.get("sampled_nonzero_difference") is True,
        "synced_vllm_sampled_and_summary_equal": synced_vllm.get("sampled_equal") is True and synced_vllm.get("summary_stats_equal") is True,
        "log_prob_finite_nonzero": log_prob_delta.get("finite_count") == log_prob_delta.get("total_count") and log_prob_delta.get("nonzero_count", 0) > 0,
        "post_sync_generation_finite": generation.get("batch_size") == 4 and generation.get("response_tokens") == 384 and generation.get("finite_response_tokens") is True,
        "ray_shutdown": raw.get("ray_shutdown") is True,
        "no_production_source_edit_flag": raw.get("no_production_source_edit") is True,
    }
    return {
        "decision": "PASS_LIMITED_EFFECTIVE_UPDATE_WITH_SCOPE_EXCEPTION" if all(flags.values()) else "INSUFFICIENT_OR_FAIL",
        "flags": flags,
        "phase_summary": _phase_summary(fit),
        "identity": {
            "source": raw.get("source"),
            "model": raw.get("model"),
            "inputs": raw.get("inputs"),
            "config": compact(config),
        },
        "ray_mapping": compact(ray_mapping),
        "selected_gpu_rows": compact(selected_rows),
        "worker_devices": worker_devices,
        "ctan": {
            "hook_calls": fit.get("hook_calls"),
            "advantages": compact(advantages),
            "ema_before": compact(ema_before),
            "ema_after": compact(ema_after),
        },
        "actor": {
            "grad_norms": grad_values,
            "sample_delta": actor_sample_delta,
            "mapped_actor_update": mapped_actor_update,
            "log_prob_delta": compact(log_prob_delta),
        },
        "anchor": {
            "initial_actor_vs_anchor": initial_actor_anchor,
            "old_anchor_stable": old_anchor_stable,
            "updated_actor_vs_old_anchor": updated_actor_vs_old_anchor,
            "new_anchor_matches_updated_actor": new_anchor_match,
        },
        "vllm": {
            "selected_key": mapped_key,
            "stale_before_sync": stale_vllm,
            "after_sync": synced_vllm,
            "event_boundaries": [item.get("event", {}).get("boundary") for item in before_events],
            "loaded_at_wrapper_entry": [item.get("event", {}).get("loaded_at_wrapper_entry") for item in before_events],
        },
        "generation": compact(generation),
        "static_source_audit": static_audit,
        "run_log_audit": log_audit,
        "declared_no_checkpoint_write": raw.get("no_checkpoint_write"),
        "checkpoint_write_scope_pass": log_audit.get("checkpoint_write_observed_in_log") is False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result_path = args.diagnostic_root / "attempt-15" / "meta" / "effective-update-result.json"
    raw = json_load(result_path)
    evidence = {
        "probe": "independent_probe.py",
        "diagnostic_root": str(args.diagnostic_root),
        "result_path": str(result_path),
        "result_bytes": result_path.stat().st_size,
        "result_sha256": sha256_file(result_path),
        "manifest": verify_manifest(args.diagnostic_root),
        "source_inventory": source_inventory(args.source_root),
        "evaluation": evaluate(raw, args.diagnostic_root, args.source_root),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "result_sha256": evidence["result_sha256"],
        "manifest": evidence["manifest"],
        "source_key_file_count": evidence["source_inventory"]["key_file_count"],
        "top_level_keys": list(raw),
        "decision": evidence["evaluation"]["decision"],
        "checkpoint_write_observed_in_log": evidence["evaluation"]["run_log_audit"]["checkpoint_write_observed_in_log"],
        "output": str(args.output),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
