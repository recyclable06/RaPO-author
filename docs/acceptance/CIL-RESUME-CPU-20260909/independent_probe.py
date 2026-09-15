#!/usr/bin/env python3
"""Independent static/CPU acceptance probe for CAND-RESUME-CIL-001.

This probe reads the frozen remediation worktree, executes only the pure
boundary serializer/validator nodes extracted from the production source on
small real files, and reports static protocol coverage.  It does not import
the training entry point, start Ray, create a model, use a GPU, or modify the
target worktree.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import os
import pickle
import random
import tempfile
from pathlib import Path
from typing import Any, Optional


EXPECTED_TARGET_MANIFEST_SHA256 = "1dfbdc9efcdb853be12e5ab0ded6ffb0f6c4aabc23e811eca836c5de0b58e740"
EXPECTED_INTEGRATION_MANIFEST_SHA256 = "6514f4dca401ffc805ae57031d1926f742e531ce0fbb981448315538ade8b0b1"
EXPECTED_BASE_HEAD = "da0c5ad521387bab75e74dc0bf0fd47dc13a3647"
EXPECTED_IMAGE_SOURCE_SHA256 = "23cbb3c01f69704eb304c2b9c884d8165a9783a913422d6e679e63bb42d71928"
EXPECTED_TEST_SHA256 = "a8b17b247eac0526108fbd7388af9b98946752bb8214d24229f00121bd200896"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_hash_manifest(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    entries = manifest.get("files", [])
    if isinstance(entries, dict):
        entries = [{"path": key, **value} for key, value in entries.items()]
    checks = []
    for item in entries:
        relative = str(item["path"])
        path = root / relative
        actual_hash = sha256_file(path) if path.is_file() else None
        actual_bytes = path.stat().st_size if path.is_file() else None
        checks.append({
            "path": relative,
            "expected_bytes": item.get("bytes"),
            "actual_bytes": actual_bytes,
            "expected_sha256": item.get("sha256"),
            "actual_sha256": actual_hash,
            "ok": path.is_file() and actual_bytes == item.get("bytes") and actual_hash == item.get("sha256"),
        })
    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "declared_file_count": len(checks),
        "all_files_match": all(item["ok"] for item in checks),
        "checks": checks,
    }


def extract_protocol_nodes(source: Path) -> dict[str, Any]:
    tree = ast.parse(source.read_bytes(), filename=str(source))
    wanted = {
        "_canonical_json_bytes", "_sha256_bytes", "_sha256_file", "_atomic_write_json",
        "_read_json", "_safe_join", "_path_within", "_artifact_manifest", "_manifest_hash",
        "_validate_artifact_manifest", "_encode_pickle", "_decode_pickle",
        "_capture_driver_rng_state", "_restore_driver_rng_state", "_validate_driver_rng_payload",
        "_validate_identity_hashes", "_load_task_boundary", "_publish_task_boundary",
    }
    nodes: list[ast.AST] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "CILBoundaryError":
            nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted:
            nodes.append(node)
        elif isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if any(target.startswith("_BOUNDARY_") for target in targets):
                nodes.append(node)

    namespace: dict[str, Any] = {
        "__file__": str(source),
        "Any": Any,
        "Optional": Optional,
        "PPOConfig": Any,
        "argparse": argparse,
        "base64": base64,
        "hashlib": hashlib,
        "json": json,
        "os": os,
        "pickle": pickle,
        "random": random,
        "tempfile": tempfile,
        "Path": Path,
    }
    import numpy as np
    import torch

    namespace["np"] = np
    namespace["torch"] = torch
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    return namespace


def fixture_context(protocol: dict[str, Any]) -> dict[str, Any]:
    plan_payload = {
        "class_order_ids": [0, 1, 2, 3],
        "class_order_names": ["a", "b", "c", "d"],
        "class_splits": [[0, 1], [2, 3]],
        "class_split_names": [["a", "b"], ["c", "d"]],
        "total_tasks": 2,
        "base_classes": 2,
        "incremental_classes": 2,
        "completed_task": 1,
        "next_task": 2,
        "completed_task_classes": ["a", "b"],
        "next_task_classes": ["c", "d"],
        "next_task_seen_classes": ["a", "b", "c", "d"],
        "prompt_seen_labels": True,
    }
    wrapped = lambda payload: {"payload": payload, "hash": protocol["_sha256_bytes"](protocol["_canonical_json_bytes"](payload))}
    source = {"files": [], "manifest_sha256": protocol["_manifest_hash"]([])}
    model = {
        "path": "fixture-model",
        "metadata": [{"path": "config.json", "bytes": 1, "sha256": "fixture"}],
        "anchor_provenance": "reconstructed_from_task1_actor",
    }
    model["hash"] = protocol["_sha256_bytes"](protocol["_canonical_json_bytes"](model))
    input_identity = {
        "train": {"kind": "file", "path": "fixture-train", "bytes": 1, "sha256": "fixture"},
        "val": {"kind": "file", "path": "fixture-val", "bytes": 1, "sha256": "fixture"},
    }
    input_identity["hash"] = protocol["_sha256_bytes"](protocol["_canonical_json_bytes"](input_identity))
    return {
        "plan": wrapped(plan_payload),
        "config": wrapped({"ppo": {"fixture": True}, "cil": {"prompt_seen_labels": True}}),
        "source": source,
        "model": model,
        "input": input_identity,
        "loader_policy": {
            "kind": "new_task_dataloader",
            "task_id": 2,
            "cursor": 0,
            "sampler": "RandomSampler",
            "seed": 7,
            "shuffle": True,
            "drop_last": True,
            "batch_size": 2,
            "current_classes": ["c", "d"],
            "seen_classes": ["a", "b", "c", "d"],
            "prompt_classes": ["a", "b", "c", "d"],
        },
    }


def make_fixture(protocol: dict[str, Any], tmp: Path) -> tuple[Path, Path]:
    root = tmp / "task_1"
    checkpoint = root / "global_step_3"
    actor = checkpoint / "actor"
    actor.mkdir(parents=True)
    (actor / "model_world_size_1_rank_0.pt").write_bytes(b"model-shard")
    (actor / "optim_world_size_1_rank_0.pt").write_bytes(b"optimizer-shard")
    (actor / "extra_state_world_size_1_rank_0.pt").write_bytes(b"worker-rng")
    (checkpoint / "dataloader.pt").write_bytes(b"task1-cursor")
    tracker = root / "checkpoint_tracker.json"
    tracker.write_text(json.dumps({
        "best_global_step": 3,
        "best_val_reward_score": 0.5,
        "last_global_step": 3,
        "last_actor_path": str(actor.resolve()),
    }), encoding="utf-8")
    import numpy as np
    import torch

    context = fixture_context(protocol)
    marker = protocol["_publish_task_boundary"](
        boundary_root=str(root),
        checkpoint_path=str(checkpoint),
        tracker_path=str(tracker),
        global_step=3,
        ema_payload={"ema_mean": 1.0, "ema_std": 2.0, "update_count": 4},
        driver_rng_payload=protocol["_capture_driver_rng_state"](),
        vllm_rng_payloads=[{"rank": 0, "torch_random_states": [1, 2, 3], "gen_random_states": [4, 5, 6]}],
        context=context,
    )
    # Keep imports live in this small CPU fixture and make the environment
    # identity explicit in the output rather than relying on test claims.
    _ = np, torch
    return root, Path(marker)


def refresh_state_fingerprint(protocol: dict[str, Any], payload: dict[str, Any]) -> None:
    payload["state_fingerprint"] = protocol["_sha256_bytes"](protocol["_canonical_json_bytes"]({
        "plan": payload["plan"]["hash"],
        "config": payload["config"]["hash"],
        "source": payload["source"]["manifest_sha256"],
        "model": payload["model"]["hash"],
        "input": payload["input"]["hash"],
        "loader_policy": payload["loader_policy"],
        "checkpoint": payload["checkpoint"]["manifest_sha256"],
        "ema": payload["ema"]["sha256"],
        "driver": payload["rng"]["driver"]["sha256"],
        "vllm": payload["rng"]["vllm"],
    }))


def run_protocol_checks(protocol: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="cil-resume-independent-") as temp:
        tmp = Path(temp)
        root, marker = make_fixture(protocol, tmp)
        valid = protocol["_load_task_boundary"](str(marker))
        checks["valid_production_serialized_fixture"] = {
            "pass": valid["status"] == "complete" and valid["next_task"] == 2 and valid["loader_policy"]["cursor"] == 0,
            "marker": str(marker),
        }

        missing = json.loads(marker.read_text(encoding="utf-8"))
        (root / "global_step_3" / "actor" / "model_world_size_1_rank_0.pt").unlink()
        try:
            protocol["_load_task_boundary"](str(marker))
        except Exception as exc:
            checks["missing_checkpoint_fails_closed"] = {"pass": type(exc).__name__ == "CILBoundaryError", "error": str(exc)}
        else:
            checks["missing_checkpoint_fails_closed"] = {"pass": False, "error": "accepted missing checkpoint"}

        # Rebuild a clean fixture, then remove dataloader.pt and rewrite the
        # marker manifest as a publisher would if it did not enforce the
        # required native dataloader artifact.  The current validator accepts
        # this, which is recorded as a specification gap rather than hidden.
        with tempfile.TemporaryDirectory(prefix="cil-resume-no-dataloader-") as temp_no_loader:
            root2, marker2 = make_fixture(protocol, Path(temp_no_loader))
            checkpoint2 = root2 / "global_step_3"
            (checkpoint2 / "dataloader.pt").unlink()
            payload = json.loads(marker2.read_text(encoding="utf-8"))
            entries = protocol["_artifact_manifest"](str(checkpoint2))
            payload["checkpoint"]["files"] = entries
            payload["checkpoint"]["manifest_sha256"] = protocol["_manifest_hash"](entries)
            refresh_state_fingerprint(protocol, payload)
            marker2.write_text(json.dumps(payload), encoding="utf-8")
            try:
                protocol["_load_task_boundary"](str(marker2))
            except Exception as exc:
                checks["missing_dataloader_rejected"] = {"pass": True, "error": str(exc)}
            else:
                checks["missing_dataloader_rejected"] = {
                    "pass": False,
                    "error": "validator accepted a manifest without dataloader.pt",
                }

    return checks


def static_audit(source: Path, helper_source: Path, test_source: Path) -> dict[str, Any]:
    text = source.read_text(encoding="utf-8")
    helper_text = helper_source.read_text(encoding="utf-8")
    test_text = test_source.read_text(encoding="utf-8")
    ast.parse(text, filename=str(source))
    test_tree = ast.parse(test_text)
    test_nodes = [node for node in ast.walk(test_tree) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
    tests = [node.name for node in test_nodes]
    parametrized_cases = len(tests)
    for node in test_nodes:
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "parametrize"
                and len(decorator.args) >= 2
                and isinstance(decorator.args[1], (ast.List, ast.Tuple))
            ):
                parametrized_cases += max(0, len(decorator.args[1].elts) - 1)

    def has_direct_return_or_break(nodes: list[ast.stmt]) -> bool:
        for node in nodes:
            if isinstance(node, (ast.Return, ast.Break)):
                return True
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if has_direct_return_or_break([child for child in ast.iter_child_nodes(node) if isinstance(child, ast.stmt)]):
                return True
        return False

    run_cil = next(node for node in ast.walk(ast.parse(text)) if isinstance(node, ast.FunctionDef) and node.name == "_run_cil")
    task_loop = next(node for node in ast.walk(run_cil) if isinstance(node, ast.For) and isinstance(node.target, ast.Tuple))
    loop_start = text.index("for task_idx, task_class_ids in enumerate(class_splits[start_task_idx:], start=start_task_idx):")
    loop_end = text.index("# ── Clean up", loop_start)
    publish_call = text.index("publish_task_boundary=(known_args.publish_task_boundary and task_id == 1)", loop_start, loop_end)
    loop_tail = text[publish_call:loop_end]
    boundary_source_files = []
    for line in text.splitlines():
        if '"' in line and line.strip().startswith('"') and line.strip().endswith('",'):
            value = line.strip().strip('",')
            if value.startswith(("examples/", "verl/")):
                boundary_source_files.append(value)
    return {
        "production_ast_parses": True,
        "cli_flags": "--resume_task_boundary" in text and "--publish_task_boundary" in text,
        "explicit_fresh_branch": "fresh_boundary_resume" in text and "restore_boundary_checkpoint" in text,
        "continuous_load_path_none": "load_checkpoint_path=config.trainer.load_checkpoint_path if task_id == 1 else None" in text,
        "fresh_loader_cursor_zero": "Task-2 boundary loader cursor must be zero" in text and '"cursor": 0' in text,
        "restore_before_anchor_copy": text.index("trainer.restore_boundary_checkpoint(checkpoint_path") < text.index("trainer.actor_rollout_ref_wg.copy_actor_to_anchor()"),
        "marker_atomic_last": "_atomic_write_json(marker_path, marker, refuse_replace=True)" in text,
        "post_validation_before_publish": text.index("if extra_val_splits:") < text.index("if publish_task_boundary:", text.index("def run_task")),
        "driver_rng_before_task_loader": text.index("restore_boundary_driver_rng.remote") < text.index("for task_idx, task_class_ids"),
        "native_continual_loader_skip_helper": "skip dataloader state to avoid sample-replay" in helper_text,
        "new_task_test_function_count": len(tests),
        "new_task_parametrized_case_count": parametrized_cases,
        "new_test_names": sorted(tests),
        "publish_stops_after_task1": has_direct_return_or_break(task_loop.body),
        "published_boundary_pruning_guard": "published_boundary_root" in text or "boundary_root_to_preserve" in text,
        "dataloader_required_by_boundary_validator": "dataloader.pt" in text[text.index("def _load_task_boundary"):text.index("def _validate_identity_hashes")],
        "source_identity_file_count": len(boundary_source_files),
        "source_identity_files": boundary_source_files,
        "model_identity_has_revision_or_selected_metadata": "revision" in text[text.index("def _model_identity"):text.index("def _input_identity")],
        "model_identity_binds_full_weight_manifest": "_path_identity" in text[text.index("def _model_identity"):text.index("def _input_identity")],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-ref", type=Path, required=True)
    parser.add_argument("--integration-ref", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=False)
    args = parser.parse_args()

    target = args.root.resolve()
    source = target / "examples/baselines/img_cls_cil/image_cls_cil_rapo.py"
    test_source = target / "tests/author_fixes/test_cil_resume.py"
    manifest_path = target / "docs/remediation/CAND-RESUME-CIL-001/HASHES.json"
    integration_manifest = args.integration_ref.resolve() / "docs/INTEGRATION_HASHES.json"
    helper_source = target / "examples/baselines/img_cls_cil/image_cls_cil.py"

    target_manifest = verify_hash_manifest(target, manifest_path)
    integration_manifest_sha = sha256_file(integration_manifest)
    protocol = extract_protocol_nodes(source)
    protocol_checks = run_protocol_checks(protocol)
    static = static_audit(source, helper_source, test_source)

    target_source_hash = sha256_file(source)
    test_hash = sha256_file(test_source)
    blocking_findings = []
    if not static["publish_stops_after_task1"]:
        blocking_findings.append({
            "id": "CIL-CPU-001",
            "severity": "P1-gate",
            "file": str(source),
            "lines": "1648-1714",
            "finding": "--publish_task_boundary publishes Task 1 but the production task loop has no stop/return boundary; the same process proceeds to Task 2.",
        })
    if not static["published_boundary_pruning_guard"]:
        blocking_findings.append({
            "id": "CIL-CPU-002",
            "severity": "P1-gate",
            "file": str(source),
            "lines": "1795-1823,1846-1856",
            "finding": "pruning protects the source boundary only when resume_boundary is non-null; the publishing process has resume_boundary=None, so default latest/none pruning can remove the published Task-1 checkpoint after continuing.",
        })
    if not protocol_checks["missing_dataloader_rejected"]["pass"]:
        blocking_findings.append({
            "id": "CIL-CPU-003",
            "severity": "spec-gap",
            "file": str(source),
            "lines": "563-585,678-728",
            "finding": "the boundary manifest validator accepts a complete manifest without dataloader.pt; the frozen specification requires the native full checkpoint artifact set, including dataloader state.",
        })
    if not static["model_identity_binds_full_weight_manifest"]:
        blocking_findings.append({
            "id": "CIL-CPU-004",
            "severity": "spec-gap",
            "file": str(source),
            "lines": "319-339",
            "finding": "model identity binds the absolute path plus selected metadata or an optional revision, but does not require an immutable revision or a full model-weight/content manifest; a changed weight file at the same path can retain the boundary identity.",
        })
    if static["source_identity_file_count"] < 7:
        blocking_findings.append({
            "id": "CIL-CPU-005",
            "severity": "spec-gap",
            "file": str(source),
            "lines": "82-89,270-283",
            "finding": "the boundary source identity is limited to six selected files and is not an equivalent complete production-source identity for the native restore, optimizer/RNG and loader implementation it claims to bind.",
        })

    result = {
        "schema_version": 1,
        "probe": "independent_probe.py",
        "target_root": str(target),
        "source_ref": str(args.source_ref.resolve()),
        "integration_ref": str(args.integration_ref.resolve()),
        "identities": {
            "target_hashes_sha256": target_manifest["manifest_sha256"],
            "target_hashes_expected": EXPECTED_TARGET_MANIFEST_SHA256,
            "target_hashes_self_matches_expected": target_manifest["manifest_sha256"] == EXPECTED_TARGET_MANIFEST_SHA256,
            "target_files_match": target_manifest["all_files_match"],
            "target_source_sha256": target_source_hash,
            "target_source_expected": EXPECTED_IMAGE_SOURCE_SHA256,
            "target_test_sha256": test_hash,
            "target_test_expected": EXPECTED_TEST_SHA256,
            "integration_manifest_sha256": integration_manifest_sha,
            "integration_manifest_expected": EXPECTED_INTEGRATION_MANIFEST_SHA256,
            "base_head_expected": EXPECTED_BASE_HEAD,
        },
        "static_audit": static,
        "protocol_checks": protocol_checks,
        "blocking_findings": blocking_findings,
        "verdict": "FAIL_NOT_READY_FOR_GPU" if blocking_findings else "PASS_READY_FOR_GPU",
        "fresh_process_resume": "not_accepted",
        "gpu_handoff": {
            "required_after_remediation": [
                "Two OS processes: Task 1 publisher exits after marker publication, then Task 2 fresh process starts.",
                "Verify published boundary remains intact under default checkpoint policy and old boundary root is read-only.",
                "Verify native actor/optimizer/scheduler/worker RNG restore, driver/vLLM RNG restore, anchor reconstruction and Task-2 loader cursor=0 on real world-size-2 GPU workers.",
                "Verify Task-2 first real update and bounded trajectory-close metrics; do not call this bitwise state equality.",
            ],
            "not_run": True,
        },
    }
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["verdict"] == "PASS_READY_FOR_GPU" else 2


if __name__ == "__main__":
    raise SystemExit(main())
