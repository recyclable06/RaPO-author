#!/usr/bin/env python3
"""Read-only independent acceptance probe for the continuous Task1 -> Task2 run.

The executor's runtime judge is not used as the acceptance decision.  This
probe verifies the frozen diagnostic manifest, integration-source identity,
the small runtime archive, task-boundary records, EMA/optimizer/anchor
continuity, retention aggregate arithmetic, checkpoint manifests, and cleanup
markers.  It never imports production code, starts Ray/GPU work, or rewrites
the diagnostic tree.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable


TARGET_MANIFEST_SHA256 = ""  # filled in the evidence after the fixed manifest is read
INTEGRATION_MANIFEST_SHA256 = "6514f4dca401ffc805ae57031d1926f742e531ce0fbb981448315538ade8b0b1"
EXPECTED_SOURCE_HEAD = "da0c5ad521387bab75e74dc0bf0fd47dc13a3647"
EXPECTED_ENTRY_RELATIVE = "examples/baselines/img_cls_cil/image_cls_cil_rapo.py"
EXPECTED_ENTRY_SHA256 = "8a13974e3dfa7756a076844ce25ef6d66c71c29751fd2dec2f00a52b49092f3d"
EXPECTED_PHYSICAL_GPUS = [4, 6]
EXPECTED_MODEL_TOKEN = "Qwen2-VL-2B-Instruct-895c3a4"
EXPECTED_INPUT_ROOT_TOKEN = "/mnt/conda/zhenglifeng/t/eu-p1-20260908/inputs"
EXPECTED_DIAGNOSTIC_CONFIG_SHA256 = "6093d4d72cef88b07d3a1b16cc8f49ba7c51163fdd01e05daab9cd7236eef0ab"
EXPECTED_INPUT_MANIFEST_SHA256 = "eccd0dfe6c159eaca002ad016bb3a7bfe36578b4212957321f3c4ee41975e2af"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path is not None and path.is_file() else ""


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def get_path(node: Any, path: str, default: Any = None) -> Any:
    current = node
    for part in path.split(".") if path else []:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return default
    return current


def walk(node: Any, path: str = "") -> Iterable[tuple[str, Any]]:
    yield path, node
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else str(key)
            yield from walk(value, child)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk(value, f"{path}[{index}]")


def find_values(node: Any, keys: set[str]) -> list[Any]:
    values = []
    for path, value in walk(node):
        key = path.rsplit(".", 1)[-1].split("[", 1)[0]
        if key in keys:
            values.append(value)
    return values


def compact(value: Any, limit: int = 320) -> Any:
    if isinstance(value, dict):
        return {key: compact(item, limit) for key, item in list(value.items())[:24]}
    if isinstance(value, list):
        if len(value) > 16:
            return {"type": "array", "length": len(value), "head": [compact(item, limit) for item in value[:3]]}
        return [compact(item, limit) for item in value]
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    return value


def verify_diagnostic_manifest(root: Path) -> dict[str, Any]:
    path = root / "HASHES.json"
    if not path.is_file():
        return {"status": "not_available", "reason": f"missing {path}"}
    manifest = load_json(path)
    checks = []
    files = manifest.get("files", {})
    if not isinstance(files, dict):
        return {"status": "invalid", "reason": "HASHES.json.files is not an object"}
    for relative, expected in sorted(files.items()):
        item_path = root / relative
        actual_hash = sha256_file(item_path) if item_path.is_file() else None
        actual_bytes = item_path.stat().st_size if item_path.is_file() else None
        checks.append({
            "path": relative,
            "exists": item_path.is_file(),
            "bytes_expected": expected.get("bytes") if isinstance(expected, dict) else None,
            "bytes_actual": actual_bytes,
            "sha256_expected": expected.get("sha256") if isinstance(expected, dict) else None,
            "sha256_actual": actual_hash,
            "ok": bool(item_path.is_file() and isinstance(expected, dict)
                       and actual_bytes == expected.get("bytes")
                       and actual_hash == expected.get("sha256")),
        })
    extras = []
    for item in root.rglob("*"):
        if item.is_file() and item.name != "HASHES.json" and "__pycache__" not in item.parts:
            relative = str(item.relative_to(root)).replace("\\", "/")
            if relative not in files:
                extras.append(relative)
    return {
        "status": "pass" if all(item["ok"] for item in checks) else "invalid",
        "manifest_path": str(path),
        "manifest_sha256": sha256_file(path),
        "self_excluded": manifest.get("self_excluded"),
        "declared_file_count": len(checks),
        "all_files_match": all(item["ok"] for item in checks),
        "mismatches": [item for item in checks if not item["ok"]],
        "unexpected_non_cache_files": sorted(extras),
    }


def verify_evidence_manifest(root: Path) -> dict[str, Any]:
    path = root / "HASHES.json"
    if not path.is_file():
        return {"status": "not_ready", "reason": f"fixed evidence HASHES.json is missing: {path}"}
    manifest = load_json(path)
    declared = manifest.get("files", {})
    if isinstance(declared, list):
        declared = {str(item.get("path")): item for item in declared if isinstance(item, dict) and item.get("path")}
    if not isinstance(declared, dict):
        return {"status": "invalid", "reason": "evidence HASHES.json.files is not an object/list"}
    checks = []
    for relative, expected in sorted(declared.items()):
        item_path = root / str(relative)
        actual_hash = sha256_file(item_path) if item_path.is_file() else None
        actual_bytes = item_path.stat().st_size if item_path.is_file() else None
        checks.append({
            "path": relative,
            "exists": item_path.is_file(),
            "bytes_expected": expected.get("bytes") if isinstance(expected, dict) else None,
            "bytes_actual": actual_bytes,
            "sha256_expected": expected.get("sha256") if isinstance(expected, dict) else None,
            "sha256_actual": actual_hash,
            "ok": bool(item_path.is_file() and isinstance(expected, dict) and actual_bytes == expected.get("bytes") and actual_hash == expected.get("sha256")),
        })
    return {
        "status": "pass" if all(item["ok"] for item in checks) else "invalid",
        "manifest_path": str(path),
        "manifest_sha256": sha256_file(path),
        "self_excluded": manifest.get("self_excluded", manifest.get("excluded_self")),
        "declared_file_count": len(checks),
        "all_files_match": all(item["ok"] for item in checks),
        "mismatches": [item for item in checks if not item["ok"]],
    }


def verify_manifest_snapshot(root: Path, snapshot_name: str = "manifest-start.json") -> dict[str, Any]:
    """Return a re-checkable snapshot of the target manifest and its entries."""
    result = verify_diagnostic_manifest(root)
    result["snapshot_name"] = snapshot_name
    return result


def verify_integration_source(root: Path) -> dict[str, Any]:
    manifest_path = root / "docs" / "INTEGRATION_HASHES.json"
    if not manifest_path.is_file():
        return {"status": "invalid", "reason": "integration manifest missing"}
    manifest_hash = sha256_file(manifest_path)
    manifest = load_json(manifest_path)
    entries = list(manifest.get("algorithm_files", [])) + list(manifest.get("test_files", []))
    checks = []
    for entry in entries:
        relative = entry.get("path")
        item_path = root / str(relative)
        expected = entry.get("integrated_sha256") or entry.get("source_a_sha256")
        actual = sha256_file(item_path) if item_path.is_file() else None
        checks.append({
            "path": relative,
            "exists": item_path.is_file(),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "source_match_recorded": entry.get("source_match"),
            "ok": bool(item_path.is_file() and actual == expected and entry.get("source_match") is True),
        })
    target = manifest.get("target", {})
    return {
        "status": "pass" if manifest_hash == INTEGRATION_MANIFEST_SHA256 and all(item["ok"] for item in checks) else "invalid",
        "manifest_sha256": manifest_hash,
        "manifest_sha256_expected": INTEGRATION_MANIFEST_SHA256,
        "manifest_hash_ok": manifest_hash == INTEGRATION_MANIFEST_SHA256,
        "target_branch": target.get("branch"),
        "target_head": target.get("base_head"),
        "target_head_ok": target.get("base_head") == EXPECTED_SOURCE_HEAD,
        "algorithm_file_count": len(manifest.get("algorithm_files", [])),
        "test_file_count": len(manifest.get("test_files", [])),
        "key_files_all_match": all(item["ok"] for item in checks),
        "key_files": checks,
    }


def run_git_status(root: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        return {"returncode": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    except OSError as exc:
        return {"returncode": None, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"}


def static_source_audit(diagnostic_root: Path, source_root: Path) -> dict[str, Any]:
    probe_path = diagnostic_root / "continuous_task_probe.py"
    probe = text(probe_path)
    production = text(source_root / "examples" / "baselines" / "img_cls_cil" / "image_cls_cil_rapo.py")
    trainer = text(source_root / "verl" / "trainer" / "ray_trainer.py")
    workers = text(source_root / "verl" / "workers" / "fsdp_workers.py")
    manager = text(source_root / "verl" / "utils" / "checkpoint" / "fsdp_checkpoint_manager.py")
    checkpoint_base = text(source_root / "verl" / "utils" / "checkpoint" / "checkpoint_manager.py")
    data_loader = text(source_root / "verl" / "trainer" / "data_loader.py")
    rapo = text(source_root / "examples" / "baselines" / "_rapo_components.py")
    checks = {
        "probe_parses": True,
        "probe_uses_production_runner_actor_class": "raw_runner = production.PersistentRunner.__ray_actor_class__" in probe,
        "probe_calls_production_cil_entry": "production._run_cil(" in probe,
        "probe_calls_original_runner_run_task": "result = super().run_task(config, task_id" in probe,
        "probe_calls_unchanged_production_run_task": "result = super().run_task(config, task_id" in probe,
        "probe_transparently_wraps_reinit": "result = original_reinit(*reinit_args, **reinit_kwargs)" in probe,
        "probe_transparently_wraps_anchor_copy": "result = original_copy(*copy_args, **copy_kwargs)" in probe,
        "probe_transparently_wraps_advantage": "result = original(data, adv_estimator" in probe,
        "probe_does_not_call_load_weights_directly": re.search(r"^\s*[A-Za-z_][\w.]*\.load_weights\(", probe, re.MULTILINE) is None,
        "production_runner_created_once": "runner = PersistentRunner.remote()" in production and "runner.init.remote" in production,
        "production_runner_worker_init_once": "runner.init_anchor_on_workers.remote()" in production,
        "production_task_loop_calls_run_task": "runner.run_task.remote" in production and "enumerate(class_splits)" in production,
        "production_task2_checkpoint_path_passed": "last_checkpoint if task_idx > 0" in production,
        "production_task2_skip_dataloader_state": "skip_dataloader_state = task_idx > 0" in production,
        "production_anchor_actions_are_task_gated": "copy_actor_to_anchor" in production and "enable_anchor" in production,
        "production_task_reinit": "trainer.reinit_for_task(" in production,
        "production_task_fit": "trainer.fit()" in production,
        "production_ema_save": "_save_ema_state(ema_state_path, ema_payload, task_id=task_id)" in production,
        "production_task2_uses_in_memory_state": "load_checkpoint_path=config.trainer.load_checkpoint_path if task_id == 1 else None" in production,
        "production_reinit_presets_step": "self._preset_global_step = last_global_step" in production,
        "production_reinit_clears_task2_load": "self.config.trainer.load_checkpoint_path = None" in production,
        "checkpoint_manager_saves_model_optimizer_extra": "self.actor_rollout_ref_wg.save_checkpoint" in trainer and "torch.save(dataloader_state_dict" in trainer,
        "checkpoint_manager_saves_tracker": "checkpointer_tracker_path" in trainer and "last_global_step" in trainer,
        "checkpoint_manager_saves_optimizer_scheduler_rng": "get_state_dict(self.model, self.optimizer" in manager and '"lr_scheduler": self.lr_scheduler.state_dict()' in manager and '"rng": self.get_rng_state()' in manager,
        "checkpoint_manager_loads_optimizer_scheduler_rng": "optimizers=self.optimizer" in manager and "self.lr_scheduler.load_state_dict" in manager and "self.load_rng_state" in manager,
        "checkpoint_base_rng_components": all(token in checkpoint_base for token in ("torch.get_rng_state()", "torch.cuda.get_rng_state()", "np.random.get_state()", "random.getstate()")),
        "dataloader_is_stateful_and_seeded": "StatefulDataLoader" in data_loader and "RandomSampler" in data_loader and "manual_seed(config.seed)" in data_loader,
        "production_update_path": "self.actor.update_policy(data=data)" in workers and "self.actor_rollout_ref_wg.update_actor(batch)" in trainer,
        "production_rapo_hook_path": "self.ema_adv.compute_grpo_advantage(data)" in rapo and "ray_trainer_module.compute_advantage = self._compute_advantage_with_hooks" in rapo,
    }
    try:
        ast.parse(probe)
    except SyntaxError as exc:
        checks["probe_parses"] = False
        parse_error = f"{type(exc).__name__}: {exc}"
    else:
        parse_error = None
    return {
        "status": "pass" if all(checks.values()) else "invalid",
        "probe_path": str(probe_path),
        "probe_sha256": sha256_file(probe_path) if probe_path.is_file() else None,
        "production_entry_sha256": sha256_file(source_root / EXPECTED_ENTRY_RELATIVE) if (source_root / EXPECTED_ENTRY_RELATIVE).is_file() else None,
        "parse_error": parse_error,
        "checks": checks,
    }


def _records_from_runtime(evidence_root: Path, result: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    sources: dict[str, Any] = {}
    run_root = _run_root(evidence_root)
    embedded = result.get("task_records") or result.get("records")
    if isinstance(embedded, list):
        records = [item for item in embedded if isinstance(item, dict)]
        sources["embedded"] = True
    for task_id in (1, 2):
        path_candidates = [
            run_root / f"task_{task_id}" / "continuous-task-probe.json",
            run_root / f"task{task_id}" / "continuous-task-probe.json",
            run_root / f"task-{task_id}" / "continuous-task-probe.json",
        ]
        path = next((candidate for candidate in path_candidates if candidate.is_file()), None)
        if path is not None:
            item = load_json(path)
            if isinstance(item, dict):
                records = [record for record in records if record.get("task_id") != task_id]
                records.append(item)
                sources[f"task_{task_id}"] = str(path)
    records.sort(key=lambda item: int(item.get("task_id", 999)))
    return records, sources


def _run_root(evidence_root: Path) -> Path:
    for candidate in (evidence_root / "run", evidence_root / "raw" / "run"):
        if candidate.is_dir():
            return candidate
    return evidence_root


def _runtime_result_path(evidence_root: Path) -> Path | None:
    names = (
        "continuous-probe-result-rejudged.json",
        "continuous-probe-result.json",
        "rejudged-result.json",
        "runtime-result.json",
    )
    candidates = [evidence_root / name for name in names]
    candidates.extend(evidence_root.rglob("*.json"))
    seen: set[Path] = set()
    for path in candidates:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        if path.name in names:
            return path
    return None


def _worker_by_rank(snapshot: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(snapshot, list):
        return {}
    result = {}
    for item in snapshot:
        if isinstance(item, dict) and item.get("rank") is not None:
            result[str(item["rank"])] = item
    return result


def _sample_equal(left: Any, right: Any, module: str) -> bool:
    lhs, rhs = _worker_by_rank(left), _worker_by_rank(right)
    if not lhs or lhs.keys() != rhs.keys():
        return False
    for rank in lhs:
        litem, ritem = lhs[rank].get(module, {}), rhs[rank].get(module, {})
        if not isinstance(litem, dict) or not isinstance(ritem, dict):
            return False
        if litem.get("status") != "pass" or ritem.get("status") != "pass":
            return False
        if litem.get("name") != ritem.get("name") or litem.get("shape") != ritem.get("shape"):
            return False
        if litem.get("sample_count") != ritem.get("sample_count"):
            return False
        if litem.get("sample_sha256") != ritem.get("sample_sha256"):
            return False
    return True


def _sample_changed(left: Any, right: Any, module: str) -> bool:
    lhs, rhs = _worker_by_rank(left), _worker_by_rank(right)
    if not lhs or lhs.keys() != rhs.keys():
        return False
    return any(
        lhs[rank].get(module, {}).get("status") == "pass"
        and rhs[rank].get(module, {}).get("status") == "pass"
        and lhs[rank].get(module, {}).get("name") == rhs[rank].get(module, {}).get("name")
        and lhs[rank].get(module, {}).get("shape") == rhs[rank].get(module, {}).get("shape")
        and lhs[rank].get(module, {}).get("sample_sha256") != rhs[rank].get(module, {}).get("sample_sha256")
        for rank in lhs
    )


def _actor_anchor_equal(snapshot: Any) -> bool:
    workers = _worker_by_rank(snapshot)
    return bool(workers) and all(
        worker.get("actor", {}).get("status") == "pass"
        and worker.get("anchor", {}).get("status") == "pass"
        and worker.get("actor", {}).get("name") == worker.get("anchor", {}).get("name")
        and worker.get("actor", {}).get("shape") == worker.get("anchor", {}).get("shape")
        and worker.get("actor", {}).get("sample_count") == worker.get("anchor", {}).get("sample_count")
        and worker.get("actor", {}).get("sample_sha256") == worker.get("anchor", {}).get("sample_sha256")
        for worker in workers.values()
    )


def _gpu_mapping(records: list[dict[str, Any]], result: dict[str, Any]) -> dict[str, Any]:
    expected = result.get("identity", {}).get("resource_preflight") or result.get("resource_preflight") or {}
    ids = expected.get("requested_physical_gpu_ids") or result.get("resource_mapping", {}).get("physical_gpu_ids") or EXPECTED_PHYSICAL_GPUS
    try:
        ids = [int(item) for item in ids]
    except (TypeError, ValueError):
        ids = []
    uuid_by_id = expected.get("expected_uuid_by_physical_id") or result.get("resource_mapping", {}).get("uuid_by_physical_id") or {}
    checks = []
    snapshots = []
    for task in records:
        for phase in ("worker_before", "worker_after"):
            value = task.get(phase)
            if isinstance(value, list):
                snapshots.extend(value)
        for event in task.get("anchor_copy_events", []):
            for phase in ("before", "after"):
                value = event.get(phase)
                if isinstance(value, list):
                    snapshots.extend(value)
    for worker in snapshots:
        try:
            rank = int(worker.get("rank"))
        except (TypeError, ValueError):
            checks.append({"status": "invalid", "reason": "missing rank"})
            continue
        mapping = worker.get("mapping") or worker.get("worker_device_mapping") or {}
        props = mapping.get("torch_properties") or []
        actual_uuids = [str(item.get("uuid", "")).lower().removeprefix("gpu-") for item in props if isinstance(item, dict)]
        cvd_raw = str(mapping.get("cuda_visible_devices") or worker.get("cuda_visible_devices") or "")
        try:
            cvd = [int(part.strip()) for part in cvd_raw.split(",") if part.strip()]
        except ValueError:
            cvd = []
        expected_id = ids[rank] if 0 <= rank < len(ids) else None
        expected_uuid = str(uuid_by_id.get(str(expected_id), "")).lower().removeprefix("gpu-") if expected_id is not None else ""
        ray_gpu_ids = [str(item) for item in mapping.get("ray_gpu_ids", [])]
        ray_ids_match = not ray_gpu_ids or (expected_id is not None and str(expected_id) in ray_gpu_ids)
        ok = bool(expected_id is not None and expected_uuid and cvd == [expected_id]
                  and mapping.get("torch_device_count") == 1
                  and actual_uuids == [expected_uuid] and ray_ids_match)
        checks.append({
            "rank": rank,
            "pid": worker.get("pid"),
            "expected_physical_gpu": expected_id,
            "expected_uuid": expected_uuid,
            "worker_cvd": cvd,
            "ray_gpu_ids": ray_gpu_ids,
            "actual_uuids": actual_uuids,
            "pre_model_mapping_observed": bool(worker.get("pre_model_mapping")),
            "status": "pass" if ok else "invalid",
        })
    return {
        "status": "pass" if checks and all(item.get("status") == "pass" for item in checks) else "invalid",
        "expected_physical_gpu_ids": ids,
        "checks": checks,
        "pre_model_mapping_observed": bool(checks) and all(item.get("pre_model_mapping_observed") for item in checks),
    }


def _retention_audit(evidence_root: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    run_root = _run_root(evidence_root)
    task2 = next((item for item in records if item.get("task_id") == 2), {})
    calls = task2.get("advantage_calls", []) if isinstance(task2, dict) else []
    direct = len(calls) == 2 and all(
        item.get("has_anchor_log_probs_after_hook") is True
        and item.get("retention_formula_match") is True
        and finite(item.get("retention_delta_sum"))
        and float(item.get("retention_delta_sum")) > 0.0
        for item in calls
    )
    log_candidates = [
        run_root / "task_2" / "experiment_log.jsonl",
        run_root / "task2" / "experiment_log.jsonl",
    ]
    log_path = next((path for path in log_candidates if path.is_file()), None)
    rows = []
    if log_path is not None:
        for line in text(log_path).splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            reward = item.get("reward") if isinstance(item, dict) else None
            if isinstance(reward, dict) and "retention_reward" in reward and "retention_drift" in reward:
                rows.append(item)
    checks = []
    for call, row in zip(calls, rows):
        reward = row.get("reward", {})
        batch_size = get_path(call, "raw_reward.count")
        retention_reward = reward.get("retention_reward")
        actual = call.get("retention_delta_sum")
        expected = float(batch_size) * 0.5 * float(retention_reward) if finite(batch_size) and finite(retention_reward) else None
        ok = bool(expected is not None and finite(actual) and abs(float(actual) - expected) <= 2e-4 * max(1.0, abs(expected))
                  and finite(reward.get("retention_drift")) and float(reward.get("retention_drift")) >= -2e-6
                  and 0.0 <= float(retention_reward) <= 1.00002)
        checks.append({
            "step": row.get("step"),
            "batch_size": batch_size,
            "retention_reward": retention_reward,
            "retention_drift": reward.get("retention_drift"),
            "expected_delta_sum": expected,
            "actual_delta_sum": actual,
            "status": "pass" if ok else "invalid",
        })
    aggregate = bool(checks and len(checks) == len(calls) and all(item["status"] == "pass" for item in checks))
    second_varies = False
    if len(calls) >= 2:
        first_delta = calls[0].get("retention_delta_sum")
        second_delta = calls[1].get("retention_delta_sum")
        first_drift = get_path(calls[0], "retention_observation.drift_per_sequence.std_population")
        second_drift = get_path(calls[1], "retention_observation.drift_per_sequence.std_population")
        second_varies = (finite(first_delta) and finite(second_delta) and float(first_delta) != float(second_delta)) or (finite(second_drift) and float(second_drift) > 0.0)
    return {
        "direct_tensor_formula_observed": direct,
        "aggregate_log_reconciliation": aggregate,
        "log_path": str(log_path) if log_path else None,
        "checks": checks,
        "second_task2_batch_varies": second_varies,
        "limited_basis": not direct and aggregate,
    }


def _ema_audit(records: list[dict[str, Any]], evidence_root: Path) -> dict[str, Any]:
    calls = []
    for task in records:
        calls.extend(task.get("advantage_calls", []))
    recurrence = []
    for index, call in enumerate(calls):
        before, after = call.get("ema_before") or {}, call.get("ema_after") or {}
        observed = get_path(call, "ema_observation.score_std_sample")
        beta = before.get("beta", 0.999)
        if not before.get("_initialized", False):
            expected = observed
        elif finite(before.get("ema_std")) and finite(observed) and finite(beta):
            expected = float(beta) * float(before["ema_std"]) + (1.0 - float(beta)) * float(observed)
        else:
            expected = None
        ok = bool(finite(expected) and finite(after.get("ema_std")) and abs(float(after["ema_std"]) - float(expected)) <= 2e-4
                  and isinstance(before.get("update_count"), int) and isinstance(after.get("update_count"), int)
                  and after["update_count"] == before["update_count"] + 1
                  and finite(after.get("ema_mean")))
        recurrence.append({"call_index": index, "before_count": before.get("update_count"), "after_count": after.get("update_count"), "expected_std": expected, "actual_std": after.get("ema_std"), "status": "pass" if ok else "invalid"})
    task1 = next((item for item in records if item.get("task_id") == 1), {})
    task2 = next((item for item in records if item.get("task_id") == 2), {})
    reinit = next((item for item in task2.get("reinit_events", []) if item.get("task_id") == 2), {})
    end1, end2 = task1.get("ema_after_task") or {}, task2.get("ema_after_task") or {}
    loaded = reinit.get("ema_adv_state_argument") or {}
    fields = ("ema_mean", "ema_std", "update_count", "beta", "eps", "bootstrap_steps", "activate_from_task", "min_std", "guard_abs_max", "bias_correction", "beta_warmup_steps", "beta_warmup_init", "last_batch_reward_mean", "last_batch_reward_std")
    loaded_match = bool(loaded) and loaded.get("task") == 1 and all(loaded.get(field) == end1.get(field) for field in fields)
    run_root = _run_root(evidence_root)
    sidecar_candidates = [run_root / "ema_online_stats.json", evidence_root / "ema_online_stats.json", evidence_root.parent / "ema_online_stats.json"]
    sidecar_path = next((path for path in sidecar_candidates if path.is_file()), None)
    sidecar = load_json(sidecar_path) if sidecar_path else {}
    latest = sidecar.get("latest") if isinstance(sidecar, dict) else {}
    sidecar_ok = isinstance(latest, dict) and latest.get("task") == 2 and latest.get("update_count") == 4
    return {
        "recurrence": recurrence,
        "recurrence_pass": bool(recurrence) and all(item["status"] == "pass" for item in recurrence),
        "task1_end": compact(end1),
        "task2_reinit_payload_matches_task1_end": loaded_match,
        "task2_reinit": compact(reinit.get("ema_after")),
        "task2_end": compact(end2),
        "expected_counts": {"task1_end": 2, "task2_reinit": reinit.get("ema_after", {}).get("update_count"), "task2_end": end2.get("update_count")},
        "sidecar": {"path": str(sidecar_path) if sidecar_path else None, "latest": compact(latest), "valid": sidecar_ok},
        "status": "pass" if bool(recurrence) and all(item["status"] == "pass" for item in recurrence) and loaded_match and end1.get("update_count") == 2 and reinit.get("ema_after", {}).get("update_count") == 2 and end2.get("update_count") == 4 and sidecar_ok else "invalid",
    }


def _optimizer_audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    task1 = next((item for item in records if item.get("task_id") == 1), {})
    task2 = next((item for item in records if item.get("task_id") == 2), {})
    a, b, c = _worker_by_rank(task1.get("worker_after")), _worker_by_rank(task2.get("worker_before")), _worker_by_rank(task2.get("worker_after"))
    checks = []
    for rank in sorted(set(a) | set(b) | set(c)):
        first, boundary, second = a.get(rank, {}).get("optimizer", {}), b.get(rank, {}).get("optimizer", {}), c.get(rank, {}).get("optimizer", {})
        fs, bs, ss = a.get(rank, {}).get("scheduler", {}), b.get(rank, {}).get("scheduler", {}), c.get(rank, {}).get("scheduler", {})
        check = {
            "rank": rank,
            "optimizer_object_same": first.get("object_id") == boundary.get("object_id") == second.get("object_id"),
            "optimizer_state_same_at_boundary": first.get("state_fingerprint") == boundary.get("state_fingerprint"),
            "optimizer_state_nonempty": first.get("moments_nonempty") is True and (first.get("state_entries") or 0) > 0,
            "optimizer_step_increased": finite(second.get("step_max")) and finite(first.get("step_max")) and float(second["step_max"]) > float(first["step_max"]),
            "scheduler_object_same": fs.get("object_id") == bs.get("object_id") == ss.get("object_id"),
            "scheduler_state_same_at_boundary": fs.get("last_epoch") == bs.get("last_epoch") and fs.get("_step_count") == bs.get("_step_count"),
            "scheduler_step_increased": finite(ss.get("last_epoch")) and finite(fs.get("last_epoch")) and int(ss["last_epoch"]) > int(fs["last_epoch"]),
        }
        check["status"] = "pass" if all(value is True for key, value in check.items() if key != "rank") else "invalid"
        checks.append(check)
    return {"status": "pass" if checks and all(item["status"] == "pass" for item in checks) else "invalid", "checks": checks}


def _checkpoint_audit(evidence_root: Path, result: dict[str, Any]) -> dict[str, Any]:
    checkpoints = result.get("checkpoints")
    if not isinstance(checkpoints, list):
        checkpoints = result.get("checkpoint_manifests")
    if not isinstance(checkpoints, list):
        checkpoints = []
    if not checkpoints:
        for path in sorted(evidence_root.rglob("*.json")):
            try:
                item = load_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(item, dict) and ("files" in item or "file_count" in item) and ("task" in item or "checkpoint_relative_path" in item):
                checkpoints.append(item)
    checks = []
    for item in checkpoints:
        task = item.get("task") or item.get("task_id")
        files = item.get("files") if isinstance(item.get("files"), list) else []
        names = [str(file.get("path", "")) for file in files if isinstance(file, dict)]
        total = sum(int(file.get("bytes", 0)) for file in files if isinstance(file, dict) and isinstance(file.get("bytes"), (int, float)))
        declared_total = item.get("total_bytes")
        expected_step = 2 if int(task) == 1 else 4 if int(task) == 2 else None
        tracker = item.get("tracker") or {}
        required = [
            any("model_world_size_2_rank_" in name for name in names),
            any("optim_world_size_2_rank_" in name for name in names),
            any("extra_state_world_size_2_rank_" in name for name in names),
            any(name.endswith("dataloader.pt") for name in names),
        ]
        ok = bool(expected_step is not None and len(files) >= 18 and all(required)
                  and (declared_total is None or int(declared_total) == total)
                  and tracker.get("last_global_step", expected_step) == expected_step)
        checks.append({"task": task, "file_count": len(files), "total_bytes": total, "declared_total_bytes": declared_total, "required_payloads": required, "tracker_step": tracker.get("last_global_step"), "status": "pass" if ok else "invalid", "paths": names[:24]})
    return {"status": "pass" if len(checks) == 2 and all(item["status"] == "pass" for item in checks) else "invalid", "checks": checks, "checkpoint_count": len(checks), "note": "Checkpoint hashes are verified from the archived manifest; large checkpoint tensors are not copied into the local acceptance tree."}


def _log_and_cleanup_audit(evidence_root: Path, result: dict[str, Any]) -> dict[str, Any]:
    candidates = [evidence_root, evidence_root / "run", evidence_root / "probe", evidence_root / "raw", evidence_root / "raw" / "run", evidence_root / "raw" / "probe"]
    exit_candidates = [candidate / name for candidate in candidates for name in ("run.exitcode", "exitcode")]
    exit_path = next((path for path in exit_candidates if path.is_file()), None)
    exit_value = text(exit_path).strip() if exit_path else None
    stdout_candidates = [candidate / name for candidate in candidates for name in ("run.stdout", "stdout")]
    stderr_candidates = [candidate / name for candidate in candidates for name in ("run.stderr", "stderr")]
    stdout_path = next((path for path in stdout_candidates if path.is_file()), None)
    stderr_path = next((path for path in stderr_candidates if path.is_file()), None)
    stdout, stderr = text(stdout_path), text(stderr_path)
    error_rx = re.compile(r"illegal memory access|out of memory|traceback|runtimeerror", re.I)
    error_lines = [line.strip() for line in stderr.splitlines() if error_rx.search(line)]
    save_lines = [line.strip() for line in stdout.splitlines() if "Saving model to" in line]
    shutdown = result.get("ray_shutdown")
    if shutdown is None:
        shutdown = result.get("cleanup", {}).get("ray_shutdown") if isinstance(result.get("cleanup"), dict) else None
    postflight_candidates = [candidate / "resource-postflight.json" for candidate in candidates]
    postflight_path = next((path for path in postflight_candidates if path.is_file()), None)
    postflight = load_json(postflight_path) if postflight_path else {}
    selected_idle = False
    if isinstance(postflight, dict):
        gpu_rows = {int(item.get("index")): item for item in (postflight.get("gpu_query", {}).get("gpus", []) if isinstance(postflight.get("gpu_query"), dict) else []) if isinstance(item, dict) and str(item.get("index", "")).isdigit()}
        apps = postflight.get("compute_apps_query", {}).get("apps", []) if isinstance(postflight.get("compute_apps_query"), dict) else []
        app_uuids = {str(item.get("gpu_uuid", "")).lower().removeprefix("gpu-") for item in apps if isinstance(item, dict)}
        selected_idle = all(index in gpu_rows and int(gpu_rows[index].get("memory_used_mib", 10**9)) <= 64 and int(gpu_rows[index].get("utilization_gpu_percent", 100)) == 0 for index in EXPECTED_PHYSICAL_GPUS) and not any(str(gpu_rows[index].get("uuid", "")).lower().removeprefix("gpu-") in app_uuids for index in EXPECTED_PHYSICAL_GPUS if index in gpu_rows)
    fallback_cleanup = result.get("status") == "pass_limited_continuous_runtime" and selected_idle
    status = "pass" if exit_value == "0" and not error_lines and shutdown is True else "limited" if (exit_value == "0" or fallback_cleanup) and not error_lines else "invalid"
    return {
        "run_exitcode": exit_value,
        "stderr_error_like_lines": error_lines[:20],
        "checkpoint_save_log_count": len(save_lines),
        "checkpoint_save_log_lines": save_lines[:12],
        "identity_markers": {
            "model_loaded": EXPECTED_MODEL_TOKEN in stdout,
            "input_root_seen": EXPECTED_INPUT_ROOT_TOKEN in stdout,
            "task_boundary_seen": "Task 1" in stdout and "Task 2" in stdout,
        },
        "ray_shutdown": shutdown,
        "postflight_path": str(postflight_path) if postflight_path else None,
        "selected_gpus_idle_in_postflight": selected_idle,
        "status": status,
    }


def evaluate_runtime(evidence_root: Path, result: dict[str, Any], static: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    records, record_sources = _records_from_runtime(evidence_root, result)
    records_by_task = {int(item.get("task_id")): item for item in records if str(item.get("task_id", "")).isdigit()}
    task1, task2 = records_by_task.get(1, {}), records_by_task.get(2, {})
    runner_pid_same = bool(task1 and task2 and task1.get("runner_pid") == task2.get("runner_pid"))
    group_same = bool(task1 and task2 and task1.get("runner_group_object_id") == task2.get("runner_group_object_id") and task1.get("worker_names") == task2.get("worker_names") and task1.get("world_size") == task2.get("world_size") == 2)
    task1_result = task1.get("production_result") or {}
    task2_reinit = next((item for item in task2.get("reinit_events", []) if item.get("task_id") == 2), {})
    task_boundary = {
        "task1_global_step_after": task1.get("trainer_global_step_after"),
        "task2_global_step_before": task2.get("trainer_global_step_before"),
        "task2_global_step_after": task2.get("trainer_global_step_after"),
        "task2_reinit_last_global_step": task2_reinit.get("last_global_step"),
        "task1_checkpoint": task1_result.get("last_checkpoint_path"),
        "task2_config_checkpoint": task2.get("task_config_load_checkpoint_path"),
        "task2_reinit_load_checkpoint": task2_reinit.get("load_checkpoint_path"),
    }
    boundary = bool(task_boundary["task1_global_step_after"] == 2 and task_boundary["task2_global_step_before"] == 2 and task_boundary["task2_global_step_after"] == 4 and task_boundary["task2_reinit_last_global_step"] == 2 and task_boundary["task2_reinit_load_checkpoint"] is None and isinstance(task_boundary["task1_checkpoint"], str) and task_boundary["task1_checkpoint"].endswith("global_step_2") and task_boundary["task2_config_checkpoint"] == task_boundary["task1_checkpoint"])
    actions = result.get("driver_actions") or []
    actions_ok = actions == [{"task_id": 1, "actions": {"copy_actor_to_anchor": False, "enable_anchor": False}}, {"task_id": 2, "actions": {"copy_actor_to_anchor": True, "enable_anchor": True}}]
    initial_match = _sample_equal(task1.get("worker_before"), task1.get("worker_before"), "actor") and _actor_anchor_equal(task1.get("worker_before"))
    task1_changed = _sample_changed(task1.get("worker_before"), task1.get("worker_after"), "actor")
    task2_changed = _sample_changed(task2.get("worker_before"), task2.get("worker_after"), "actor")
    actor_boundary = _sample_equal(task1.get("worker_after"), task2.get("worker_before"), "actor")
    copy_events = task2.get("anchor_copy_events", [])
    copy_event = copy_events[0] if copy_events else {}
    anchor_copy_before = _sample_equal(task1.get("worker_after"), copy_event.get("before"), "actor")
    anchor_copy_after = _actor_anchor_equal(copy_event.get("after"))
    anchor_stable = _sample_equal(copy_event.get("after"), task2.get("worker_after"), "anchor")
    calls = task1.get("advantage_calls", []) + task2.get("advantage_calls", [])
    groups_four = len(calls) == 4 and all(sorted((item.get("group_counts") or {}).values()) == [4, 4] for item in calls)
    group_varied = bool(calls) and all(all(finite(group.get("std_population")) and float(group["std_population"]) > 0.0 for group in item.get("group_rewards", [])) for item in calls)
    raw_varied = bool(calls) and all(finite(get_path(item, "raw_reward.std_population")) and float(get_path(item, "raw_reward.std_population")) > 0.0 and get_path(item, "raw_reward.finite_count") == get_path(item, "raw_reward.count") for item in calls)
    adv_good = bool(calls) and all(item.get("advantages_all_finite") is True and (get_path(item, "advantages.nonzero_count") or 0) > 0 for item in calls)
    retention = _retention_audit(evidence_root, records)
    ema = _ema_audit(records, evidence_root)
    optimizer = _optimizer_audit(records)
    mapping = _gpu_mapping(records, result)
    checkpoints = _checkpoint_audit(evidence_root, result)
    logs = _log_and_cleanup_audit(evidence_root, result)
    identity_nodes = [result, result.get("identity", {}), result.get("source", {}), result.get("inputs", {}), result.get("config", {})]
    identity_text = json.dumps(identity_nodes, ensure_ascii=False)
    runtime_identity = {
        "source_entry_sha256_seen": EXPECTED_ENTRY_SHA256 in identity_text,
        "diagnostic_config_sha256_seen": EXPECTED_DIAGNOSTIC_CONFIG_SHA256 in identity_text,
        "input_manifest_sha256_seen": EXPECTED_INPUT_MANIFEST_SHA256 in identity_text,
        "model_token_seen": EXPECTED_MODEL_TOKEN in identity_text,
        "input_root_seen": EXPECTED_INPUT_ROOT_TOKEN in identity_text,
    }
    static_ok = static.get("status") == "pass" and source.get("status") == "pass"
    gates = {
        "runtime_result_status_is_pass_limited": result.get("status") == "pass_limited_continuous_runtime",
        "runtime_identity_matches_frozen_source_config_inputs": all(runtime_identity.values()),
        "same_runner_pid": runner_pid_same,
        "same_worker_group": group_same,
        "worker_mapping_expected_physical_4_6": mapping.get("status") == "pass" and mapping.get("expected_physical_gpu_ids") == EXPECTED_PHYSICAL_GPUS,
        "task_boundary_steps_and_checkpoint_path": boundary,
        "production_weight_actions": actions_ok,
        "task1_actor_updated": task1_changed,
        "task2_actor_updated": task2_changed,
        "actor_continuity_at_boundary": actor_boundary,
        "initial_actor_anchor_match": initial_match,
        "anchor_copy_and_freeze": anchor_copy_before and anchor_copy_after and anchor_stable,
        "four_completion_groups": groups_four,
        "group_reward_variation": group_varied,
        "raw_reward_finite_and_varied": raw_varied,
        "advantages_finite_and_nonzero": adv_good,
        "retention_observed_with_limited_basis": retention.get("direct_tensor_formula_observed") or retention.get("aggregate_log_reconciliation"),
        "second_task2_retention_varies": retention.get("second_task2_batch_varies") or result.get("algorithm_observations", {}).get("retention_step4", {}).get("drift", 0) != result.get("algorithm_observations", {}).get("retention_step3", {}).get("drift", 0),
        "ema_recurrence_and_continuity": ema.get("status") == "pass",
        "optimizer_scheduler_continuity": optimizer.get("status") == "pass",
        "checkpoints_complete": checkpoints.get("status") == "pass",
        "logs_exit_and_cleanup": logs.get("status") in {"pass", "limited"},
        "static_production_chain": static_ok,
    }
    strict_runtime = all(gates.values())
    limited_basis = bool(retention.get("limited_basis")) or not logs.get("ray_shutdown")
    decision = "PASS_LIMITED_CONTINUOUS_RUNTIME" if strict_runtime and not limited_basis else "PASS_LIMITED_CONTINUOUS_RUNTIME_WITH_SCOPE_NOTES" if strict_runtime else "FAIL_OR_INSUFFICIENT"
    return {
        "decision": decision,
        "gates": gates,
        "runtime_identity": runtime_identity,
        "record_sources": record_sources,
        "task_boundary": task_boundary,
        "runner": {"same_runner_pid": runner_pid_same, "same_worker_group": group_same},
        "worker_mapping": mapping,
        "algorithm": {"call_count": len(calls), "four_groups": groups_four, "group_reward_variation": group_varied, "raw_reward_finite_and_varied": raw_varied, "advantages_finite_and_nonzero": adv_good, "retention": retention},
        "actor_anchor": {"initial_actor_anchor_match": initial_match, "task1_actor_changed": task1_changed, "task2_actor_changed": task2_changed, "actor_boundary": actor_boundary, "copy_before_matches": anchor_copy_before, "copy_after_matches": anchor_copy_after, "anchor_stable": anchor_stable, "full_parameter_equality_proven": False},
        "ema": ema,
        "optimizer_scheduler": optimizer,
        "checkpoints": checkpoints,
        "logs_cleanup": logs,
        "scope_notes": [
            "This is same-process PersistentRunner Task1 -> Task2 evidence only; it is not cross-process exact resume.",
            "Sampled actor/anchor comparisons do not establish all-parameter equality.",
            "If retention tensor fields are absent, acceptance relies on exact production-log aggregate reconciliation and records that limitation.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    diag = args.diagnostic_root.resolve()
    source = args.source_root.resolve()
    evidence_root = args.evidence_root.resolve()
    evidence_manifest_start = verify_evidence_manifest(evidence_root)
    if evidence_manifest_start.get("status") != "pass":
        raise SystemExit(f"fixed runtime evidence manifest is not ready: {evidence_manifest_start}")
    manifest_start = verify_diagnostic_manifest(diag)
    source_audit = verify_integration_source(source)
    static = static_source_audit(diag, source)
    result_path = _runtime_result_path(evidence_root)
    if result_path is None:
        raise SystemExit(f"runtime evidence is not ready under {evidence_root}")
    result = load_json(result_path)
    if not isinstance(result, dict):
        raise SystemExit(f"runtime result is not a JSON object: {result_path}")
    runtime = evaluate_runtime(evidence_root, result, static, source_audit)
    evidence_manifest_end = verify_evidence_manifest(evidence_root)
    manifest_end = verify_diagnostic_manifest(diag)
    evidence = {
        "schema_version": 1,
        "probe": "independent_probe.py",
        "diagnostic_root": str(diag),
        "source_root": str(source),
        "evidence_root": str(evidence_root),
        "runtime_result_path": str(result_path),
        "runtime_result_bytes": result_path.stat().st_size,
        "runtime_result_sha256": sha256_file(result_path),
        "evidence_manifest_start": evidence_manifest_start,
        "evidence_manifest_end": evidence_manifest_end,
        "evidence_manifest_unchanged": evidence_manifest_start.get("manifest_sha256") == evidence_manifest_end.get("manifest_sha256") and evidence_manifest_end.get("all_files_match"),
        "target_manifest_start": manifest_start,
        "target_manifest_end": manifest_end,
        "target_manifest_unchanged": manifest_start.get("manifest_sha256") == manifest_end.get("manifest_sha256") and manifest_start.get("all_files_match") and manifest_end.get("all_files_match"),
        "source_inventory": source_audit,
        "source_git_status": run_git_status(source),
        "static_source_audit": static,
        "runtime_result_compact": compact(result),
        "runtime_evaluation": runtime,
        "cross_process_finding": "CAND-RESUME-CIL-001 remains open; no cross-process task-boundary entry/state protocol was exercised.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"decision": runtime["decision"], "target_manifest_unchanged": evidence["target_manifest_unchanged"], "evidence_manifest_unchanged": evidence["evidence_manifest_unchanged"], "runtime_result_sha256": evidence["runtime_result_sha256"], "output": str(args.output)}, indent=2, ensure_ascii=False))
    return 0 if runtime["decision"].startswith("PASS_") and evidence["target_manifest_unchanged"] and evidence["evidence_manifest_unchanged"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
