"""CPU protocol checks for CAND-RESUME-CIL-001.

The fixture is deliberately made from small real files, then passed through
the production boundary publisher and validator.  It verifies the storage
protocol only; it is not a substitute for native model restoration or a GPU
two-process run.
"""

from __future__ import annotations

import argparse
import ast
import base64
import copy
import hashlib
import json
import os
import pickle
import random
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import torch


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "examples/baselines/img_cls_cil/image_cls_cil_rapo.py"


def _load_production_protocol() -> dict[str, Any]:
    """Execute the unmodified pure protocol nodes from production source."""
    tree = ast.parse(SOURCE.read_bytes(), filename=str(SOURCE))
    wanted_functions = {
        "_canonical_json_bytes", "_sha256_bytes", "_sha256_file", "_atomic_write_json",
        "_read_json", "_safe_join", "_path_within", "_artifact_manifest",
        "_manifest_hash", "_validate_artifact_manifest", "_encode_pickle", "_decode_pickle",
        "_capture_driver_rng_state", "_restore_driver_rng_state", "_validate_driver_rng_payload",
        "_repo_root", "_source_identity", "_path_identity", "_model_identity", "_input_identity",
        "_config_identity", "_plan_identity", "_loader_policy", "_validate_boundary_context",
        "_load_task_boundary", "_validate_identity_hashes", "_boundary_state_path",
        "_publish_task_boundary",
    }
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "CILBoundaryError":
            nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted_functions:
            nodes.append(node)
        elif isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if any(target.startswith("_BOUNDARY_") for target in targets):
                nodes.append(node)
    assert len(nodes) == len(wanted_functions) + 1 + 4
    namespace: dict[str, Any] = {
        "__file__": str(SOURCE),
        "Any": Any,
        "Optional": Any,
        "PPOConfig": Any,
        "argparse": argparse,
        "base64": base64,
        "copy": copy,
        "hashlib": hashlib,
        "json": json,
        "os": os,
        "pickle": pickle,
        "random": random,
        "tempfile": tempfile,
        "Path": Path,
        "np": np,
        "torch": torch,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


N = _load_production_protocol()


def _hash(value: Any) -> str:
    return N["_sha256_bytes"](N["_canonical_json_bytes"](value))


def _wrapped(payload: Any) -> dict[str, Any]:
    return {"payload": payload, "hash": _hash(payload)}


def _fixture_context() -> dict[str, Any]:
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
    source = {"files": [], "manifest_sha256": N["_manifest_hash"]([])}
    model = {
        "path": "fixture-model",
        "metadata": [{"path": "config.json", "bytes": 1, "sha256": "fixture"}],
        "anchor_provenance": "reconstructed_from_task1_actor",
    }
    model["hash"] = _hash(model)
    input_identity = {
        "train": {"kind": "file", "path": "fixture-train", "bytes": 1, "sha256": "fixture"},
        "val": {"kind": "file", "path": "fixture-val", "bytes": 1, "sha256": "fixture"},
    }
    input_identity["hash"] = _hash(input_identity)
    config_payload = {"ppo": {"fixture": True}, "cil": {"prompt_seen_labels": True}}
    return {
        "plan": _wrapped(plan_payload),
        "config": _wrapped(config_payload),
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


def _make_fixture(tmp_path: Path) -> tuple[dict[str, Any], Path, Path]:
    root = tmp_path / "task_1"
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
    context = _fixture_context()
    marker = N["_publish_task_boundary"](
        boundary_root=str(root),
        checkpoint_path=str(checkpoint),
        tracker_path=str(tracker),
        global_step=3,
        ema_payload={"ema_mean": 1.0, "ema_std": 2.0, "update_count": 4},
        driver_rng_payload=N["_capture_driver_rng_state"](),
        vllm_rng_payloads=[{
            "rank": 0,
            "torch_random_states": [1, 2, 3],
            "gen_random_states": [4, 5, 6],
        }],
        context=context,
    )
    return context, root, Path(marker)


def test_valid_boundary_fixture_is_production_serialized_and_validated(tmp_path):
    _, root, marker = _make_fixture(tmp_path)
    boundary = N["_load_task_boundary"](str(marker))
    assert boundary["status"] == "complete"
    assert boundary["completed_task"] == 1
    assert boundary["next_task"] == 2
    assert boundary["global_step"] == 3
    assert boundary["checkpoint"]["save_model_only"] is False
    assert boundary["loader_policy"]["cursor"] == 0
    assert boundary["loader_policy"]["current_classes"] == ["c", "d"]
    assert boundary["_boundary_root"] == str(root.resolve())
    assert (root / "boundary_state" / "driver_rng.json").is_file()
    assert (root / "boundary_state" / "vllm_rng_rank_0.json").is_file()


@pytest.mark.parametrize("mutation", ["delete", "append"])
def test_missing_or_corrupt_checkpoint_fails_closed(tmp_path, mutation):
    _, _, marker = _make_fixture(tmp_path)
    checkpoint_file = marker.parent / "global_step_3" / "actor" / "model_world_size_1_rank_0.pt"
    if mutation == "delete":
        checkpoint_file.unlink()
    else:
        checkpoint_file.write_bytes(checkpoint_file.read_bytes() + b"corrupt")
    with pytest.raises(N["CILBoundaryError"]):
        N["_load_task_boundary"](str(marker))


def test_marker_semantic_mismatch_fails_closed(tmp_path):
    _, _, marker = _make_fixture(tmp_path)
    payload = json.loads(marker.read_text(encoding="utf-8"))
    payload["loader_policy"]["cursor"] = 1
    marker.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(N["CILBoundaryError"]):
        N["_load_task_boundary"](str(marker))


def test_model_only_marker_fails_closed(tmp_path):
    _, _, marker = _make_fixture(tmp_path)
    payload = json.loads(marker.read_text(encoding="utf-8"))
    payload["checkpoint"]["save_model_only"] = True
    marker.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(N["CILBoundaryError"]):
        N["_load_task_boundary"](str(marker))


def test_source_guards_preserve_continuous_path_and_restore_order():
    source = SOURCE.read_text(encoding="utf-8")
    assert "--resume_task_boundary" in source
    assert "--publish_task_boundary" in source
    assert "fresh_boundary_resume" in source
    assert "restore_boundary_checkpoint" in source
    assert "load_checkpoint_path = None" in source
    assert source.index("trainer.restore_boundary_checkpoint") < source.index("trainer.actor_rollout_ref_wg.copy_actor_to_anchor()")
    assert "Task-2 boundary loader cursor must be zero" in source
    assert "refusing to prune the read-only source boundary root" in source
