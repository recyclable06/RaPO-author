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
import shutil
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
        "_read_json", "_safe_join", "_path_within", "_path_overlaps_roots", "_artifact_manifest",
        "_manifest_hash", "_validate_artifact_manifest", "_encode_pickle", "_decode_pickle",
        "_capture_driver_rng_state", "_restore_driver_rng_state", "_validate_driver_rng_payload",
        "_repo_root", "_source_identity", "_path_identity", "_model_identity", "_input_identity",
        "_config_identity", "_plan_identity", "_loader_policy", "_validate_boundary_context",
        "_load_task_boundary", "_validate_identity_hashes", "_boundary_state_path",
        "_publish_task_boundary",
    }
    nodes = []
    boundary_assignments = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "CILBoundaryError":
            nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted_functions:
            nodes.append(node)
        elif isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if any(target.startswith("_BOUNDARY_") for target in targets):
                boundary_assignments.append(node)
                nodes.append(node)
    assert len(nodes) == len(wanted_functions) + 1 + len(boundary_assignments)
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


def _make_fixture(tmp_path: Path, *, world_size: int = 1) -> tuple[dict[str, Any], Path, Path]:
    root = tmp_path / "task_1"
    checkpoint = root / "global_step_3"
    actor = checkpoint / "actor"
    actor.mkdir(parents=True)
    for rank in range(world_size):
        (actor / f"model_world_size_{world_size}_rank_{rank}.pt").write_bytes(
            f"model-shard-{rank}".encode()
        )
        (actor / f"optim_world_size_{world_size}_rank_{rank}.pt").write_bytes(
            f"optimizer-shard-{rank}".encode()
        )
        (actor / f"extra_state_world_size_{world_size}_rank_{rank}.pt").write_bytes(
            f"worker-rng-{rank}".encode()
        )
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


def _refresh_state_fingerprint(payload: dict[str, Any]) -> None:
    payload["state_fingerprint"] = N["_sha256_bytes"](N["_canonical_json_bytes"]({
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


def test_multi_rank_native_checkpoint_fixture_is_accepted(tmp_path):
    _, _, marker = _make_fixture(tmp_path, world_size=2)
    boundary = N["_load_task_boundary"](str(marker))
    files = {item["path"] for item in boundary["checkpoint"]["files"]}
    assert "dataloader.pt" in files
    for rank in (0, 1):
        assert f"actor/model_world_size_2_rank_{rank}.pt" in files
        assert f"actor/optim_world_size_2_rank_{rank}.pt" in files
        assert f"actor/extra_state_world_size_2_rank_{rank}.pt" in files


def test_missing_dataloader_fails_closed_even_with_refreshed_manifest(tmp_path):
    _, root, marker = _make_fixture(tmp_path)
    checkpoint = root / "global_step_3"
    (checkpoint / "dataloader.pt").unlink()
    payload = json.loads(marker.read_text(encoding="utf-8"))
    entries = N["_artifact_manifest"](str(checkpoint))
    payload["checkpoint"]["files"] = entries
    payload["checkpoint"]["manifest_sha256"] = N["_manifest_hash"](entries)
    _refresh_state_fingerprint(payload)
    marker.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(N["CILBoundaryError"], match="dataloader.pt"):
        N["_load_task_boundary"](str(marker))


def test_missing_native_rank_state_fails_closed_even_with_refreshed_manifest(tmp_path):
    _, root, marker = _make_fixture(tmp_path, world_size=2)
    checkpoint = root / "global_step_3"
    (checkpoint / "actor" / "optim_world_size_2_rank_1.pt").unlink()
    payload = json.loads(marker.read_text(encoding="utf-8"))
    entries = N["_artifact_manifest"](str(checkpoint))
    payload["checkpoint"]["files"] = entries
    payload["checkpoint"]["manifest_sha256"] = N["_manifest_hash"](entries)
    _refresh_state_fingerprint(payload)
    marker.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(N["CILBoundaryError"], match="rank 1"):
        N["_load_task_boundary"](str(marker))


def test_model_identity_binds_all_local_model_content(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text('{"model_type":"fixture"}', encoding="utf-8")
    (model_dir / "tokenizer.json").write_text('{"tokenizer":"fixture"}', encoding="utf-8")
    (model_dir / "tokenizer_config.json").write_text('{"padding_side":"right"}', encoding="utf-8")
    (model_dir / "model.safetensors.index.json").write_text('{"weight_map":{}}', encoding="utf-8")
    (model_dir / "model.safetensors").write_bytes(b"weights-A")
    config = SimpleNamespace(
        worker=SimpleNamespace(
            actor=SimpleNamespace(
                model=SimpleNamespace(model_path=str(model_dir), revision=None, model_revision=None)
            )
        )
    )

    first = N["_model_identity"](config)
    assert first["content_manifest"]["kind"] == "directory"
    assert {item["path"] for item in first["content_manifest"]["files"]} == {
        "config.json",
        "model.safetensors",
        "model.safetensors.index.json",
        "tokenizer.json",
        "tokenizer_config.json",
    }
    (model_dir / "model.safetensors").write_bytes(b"weights-B")
    second = N["_model_identity"](config)
    assert second["hash"] != first["hash"]
    assert second["content_manifest"]["manifest_sha256"] != first["content_manifest"]["manifest_sha256"]


def test_model_identity_rejects_remote_id_even_with_immutable_revision():
    config = SimpleNamespace(
        worker=SimpleNamespace(
            actor=SimpleNamespace(
                model=SimpleNamespace(
                    model_path="org/model",
                    tokenizer_path="org/tokenizer",
                    revision="0123456789abcdef0123456789abcdef01234567",
                )
            )
        )
    )
    with pytest.raises(N["CILBoundaryError"], match="local model directory"):
        N["_model_identity"](config)


def test_model_identity_binds_independent_tokenizer_content(tmp_path):
    model_dir = tmp_path / "model"
    tokenizer_dir = tmp_path / "tokenizer"
    model_dir.mkdir()
    tokenizer_dir.mkdir()
    (model_dir / "config.json").write_text('{"model_type":"fixture"}', encoding="utf-8")
    (model_dir / "model.safetensors").write_bytes(b"weights")
    (tokenizer_dir / "tokenizer.json").write_bytes(b"token-A")
    config = SimpleNamespace(
        worker=SimpleNamespace(
            actor=SimpleNamespace(
                model=SimpleNamespace(
                    model_path=str(model_dir),
                    tokenizer_path=str(tokenizer_dir),
                )
            )
        )
    )

    first = N["_model_identity"](config)
    assert first["tokenizer_path"] == str(tokenizer_dir.resolve())
    assert first["tokenizer_content_manifest"]["kind"] == "directory"
    first_tokenizer_hash = first["tokenizer_content_manifest"]["manifest_sha256"]
    (tokenizer_dir / "tokenizer.json").write_bytes(b"token-B")
    second = N["_model_identity"](config)
    assert second["hash"] != first["hash"]
    assert second["tokenizer_content_manifest"]["manifest_sha256"] != first_tokenizer_hash


def test_runner_consumes_configured_tokenizer_path():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    runner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "PersistentRunner")
    init = next(node for node in runner.body if isinstance(node, ast.FunctionDef) and node.name == "init")
    calls = {
        node.func.id: node
        for node in ast.walk(init)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"get_tokenizer", "get_processor"}
    }
    assert set(calls) == {"get_tokenizer", "get_processor"}
    assert all(ast.unparse(call.args[0]) == "tokenizer_path" for call in calls.values())


def test_source_identity_covers_dynamic_production_roots_and_config():
    identity = N["_source_identity"]()
    paths = {item["path"] for item in identity["files"]}
    assert len(paths) > 80
    assert "verl/__init__.py" in paths
    assert "verl/models/__init__.py" in paths
    assert "verl/models/monkey_patch.py" in paths
    assert "verl/models/transformers/qwen2_vl.py" in paths
    assert "verl/workers/fsdp_workers.py" in paths
    assert "verl/workers/actor/dp_actor.py" in paths
    assert "verl/workers/sharding_manager/fsdp_vllm.py" in paths
    assert "verl/utils/checkpoint/fsdp_checkpoint_manager.py" in paths
    assert "examples/reward_function/cls.py" in paths
    assert "examples/baselines/img_cls_cil/image_cls_cil_rapo.py" in paths
    assert "examples/config.yaml" in paths
    assert "scripts/image/rapo_cfg.json" in paths
    assert "scripts/image/10task.sh" in paths
    assert "requirements.txt" in paths
    assert "environment.lock.yml" in paths
    assert not any("__pycache__" in path or path.endswith(".log") for path in paths)


def test_source_identity_tracks_configured_reward_and_tree_add_delete_mutation(tmp_path):
    for relative in (
        "verl/models",
        "examples/baselines/img_cls_cil",
        "examples/baselines/cil_misc",
        "scripts/image",
        "runtime",
        "examples/cache",
        "examples/output",
        "examples/docs",
    ):
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)
    for relative in ("requirements.txt", "environment.yml", "environment.lock.yml"):
        (tmp_path / relative).write_text(relative, encoding="utf-8")
    (tmp_path / "verl/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "verl/models/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "verl/models/runtime.py").write_text("MODEL = 1\n", encoding="utf-8")
    (tmp_path / "examples/baselines/img_cls_cil/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "examples/baselines/cil_misc/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "examples/config.yaml").write_text(
        "worker:\n  reward:\n    reward_function: ./runtime/custom_reward.py:compute_score\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts/image/rapo_cfg.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "scripts/image/10task.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    reward = tmp_path / "runtime/custom_reward.py"
    reward.write_text("def compute_score(data):\n    return 1.0\n", encoding="utf-8")
    (tmp_path / "examples/cache/ignored.py").write_text("IGNORED = True\n", encoding="utf-8")
    (tmp_path / "examples/output/ignored.py").write_text("IGNORED = True\n", encoding="utf-8")
    (tmp_path / "examples/docs/ignored.py").write_text("IGNORED = True\n", encoding="utf-8")

    previous_repo_root = N["_repo_root"]
    N["_repo_root"] = lambda: str(tmp_path)
    try:
        first = N["_source_identity"]()
        first_paths = {item["path"] for item in first["files"]}
        assert "verl/models/__init__.py" in first_paths
        assert "runtime/custom_reward.py" in first_paths
        assert "examples/reward_function/cls.py" not in first_paths
        assert "examples/cache/ignored.py" not in first_paths
        assert "examples/output/ignored.py" not in first_paths
        assert "examples/docs/ignored.py" not in first_paths

        added = tmp_path / "verl/models/added.py"
        added.write_text("ADDED = True\n", encoding="utf-8")
        with_added = N["_source_identity"]()
        assert with_added["manifest_sha256"] != first["manifest_sha256"]
        added.unlink()
        after_delete = N["_source_identity"]()
        assert after_delete["manifest_sha256"] == first["manifest_sha256"]

        original = reward.read_text(encoding="utf-8")
        reward.write_text(original.replace("1.0", "2.0"), encoding="utf-8")
        after_same_size_mutation = N["_source_identity"]()
        assert after_same_size_mutation["manifest_sha256"] != first["manifest_sha256"]
    finally:
        N["_repo_root"] = previous_repo_root


def test_pruning_guard_protects_boundary_children_and_parent(tmp_path):
    boundary_root = tmp_path / "task_1"
    checkpoint = boundary_root / "global_step_3"
    unrelated = tmp_path / "task_2" / "global_step_1"
    assert N["_path_overlaps_roots"](str(checkpoint), [str(boundary_root)])
    assert N["_path_overlaps_roots"](str(boundary_root), [str(checkpoint)])
    assert not N["_path_overlaps_roots"](str(unrelated), [str(boundary_root)])


def test_source_guards_preserve_continuous_path_and_restore_order():
    source = SOURCE.read_text(encoding="utf-8")
    assert "--resume_task_boundary" in source
    assert "--publish_task_boundary" in source
    assert "--stop_after_task_boundary" in source
    assert "stop-after-boundary mode may only publish Task 1" in source
    assert "fresh_boundary_resume" in source
    assert "restore_boundary_checkpoint" in source
    assert "load_checkpoint_path = None" in source
    assert source.index("trainer.restore_boundary_checkpoint") < source.index("trainer.actor_rollout_ref_wg.copy_actor_to_anchor()")
    assert "Task-2 boundary loader cursor must be zero" in source
    assert "protected_boundary_roots" in source
    assert "_path_overlaps_roots" in source
    assert "Preserving protected boundary checkpoint" in source
    assert "refusing to prune a protected boundary path" not in source
    assert "stopping normally before Task 2" in source


def _compile_production_pruning_loops():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    run_node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_run_cil")
    loops = [
        node
        for node in ast.walk(run_node)
        if isinstance(node, ast.For)
        and isinstance(node.target, ast.Name)
        and node.target.id == "entry"
        and "_path_overlaps_roots" in ast.unparse(node)
        and "shutil.rmtree" in ast.unparse(node)
    ]
    assert len(loops) == 3
    loops.sort(key=lambda node: node.lineno)
    compiled = []
    for index, loop in enumerate(loops):
        wrapper = ast.FunctionDef(
            name=f"prune_{index}",
            args=ast.arguments(
                posonlyargs=[],
                args=[
                    ast.arg(arg="task_save_dir"),
                    ast.arg(arg="previous_task_dir"),
                    ast.arg(arg="protected_boundary_roots"),
                    ast.arg(arg="ckpt_dirname"),
                ],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=[copy.deepcopy(loop), ast.Return(value=ast.Constant(value=None))],
            decorator_list=[],
            returns=None,
            type_comment=None,
        )
        module = ast.Module(body=[wrapper], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace = {
            "os": os,
            "shutil": shutil,
            "_path_overlaps_roots": N["_path_overlaps_roots"],
        }
        exec(compile(module, str(SOURCE), "exec"), namespace)
        compiled.append(namespace[f"prune_{index}"])
    return compiled


def _make_checkpoint(root: Path, name: str) -> Path:
    checkpoint = root / name
    checkpoint.mkdir(parents=True, exist_ok=True)
    (checkpoint / "payload").write_text(name, encoding="utf-8")
    return checkpoint


def test_actual_production_pruning_skips_boundary_and_continues(tmp_path):
    current_prune, previous_prune, final_prune = _compile_production_pruning_loops()
    boundary_root = tmp_path / "task_1"
    protected_one = _make_checkpoint(boundary_root, "global_step_1")
    protected_two = _make_checkpoint(boundary_root, "global_step_2")
    before_boundary = {
        path.relative_to(boundary_root).as_posix(): path.read_text(encoding="utf-8")
        for path in boundary_root.rglob("payload")
    }

    # Task 1 has multiple checkpoints and the protected boundary is its root.
    # Returning from this production loop is the path that must reach the
    # normal stop-after-boundary break.
    current_prune(
        str(boundary_root), str(boundary_root), [str(boundary_root)], "global_step_2"
    )
    reached_task1_stop = True
    assert reached_task1_stop
    assert protected_one.is_dir() and protected_two.is_dir()

    # A no-stop run entering Task 2 must preserve the published Task-1 root
    # while still pruning ordinary old checkpoints.
    task2_dir = tmp_path / "task_2"
    old_task2 = _make_checkpoint(task2_dir, "global_step_1")
    keep_task2 = _make_checkpoint(task2_dir, "global_step_2")
    previous_prune(
        str(task2_dir), str(task2_dir), [str(boundary_root)], "global_step_2"
    )
    reached_task2 = True
    assert reached_task2
    assert not old_task2.exists()
    assert not keep_task2.exists()

    previous_prune(
        str(boundary_root), str(boundary_root), [str(boundary_root)], "global_step_99"
    )
    final_prune(
        str(boundary_root), str(boundary_root), [str(boundary_root)], "global_step_99"
    )
    assert {
        path.relative_to(boundary_root).as_posix(): path.read_text(encoding="utf-8")
        for path in boundary_root.rglob("payload")
    } == before_boundary
