"""image_cls_cil_rapo.py
===============================================================================
Class-incremental image classification with RaPO and persistent workers.

Runtime choices:

1. **No Ray restart between tasks** – Worker processes (FSDP + vLLM) are
   spawned once and reused across all CIL tasks, eliminating the ~2-3 min
   per-task overhead of process creation + NCCL init + model loading.

2. **In-memory weight copy instead of HF merge** – From task 2 onward the
   actor FSDP weights are copied into the frozen **anchor** module (previous
   task). The KL **reference** stays the original pretrained weights.

3. **Optimizer state carry-over** – Between tasks the actor's optimizer state
   (AdamW momentum, variance, step counter) is kept in memory, matching the
   original code where ``FSDPCheckpointManager.load_checkpoint()`` restores
   the full optimizer state from the previous task's checkpoint.

CIL evaluation (last_acc, avg_acc, forgetting_rate, per-task decomposition,
extra_val_splits with overall_seen, sample-level metrics) is implemented in
``image_cls_cil.py`` and reused here.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import pickle
import random
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import ray
import torch
from omegaconf import OmegaConf

# ── Base CIL module and RaPO components ─────────────────────────────────────
# We import heavily from the existing modules to avoid duplicating code.
import examples.baselines.img_cls_cil.image_cls_cil as base
from examples.baselines._rapo_components import (
    AnchorRefConfig,
    RetentionRewardConfig,
    EMAAdvConfig,
    EMAAdvNormalizer,
    RayPPOContinualRaPOTrainer,
    _ema_stats_file_from_task_dir,
    _load_ema_state,
    _save_ema_state,
    _load_cil_cfg,
    _build_cil_cfg,
)

from verl.protocol import DataProto
from verl.single_controller.base.decorator import Dispatch, register
from verl.single_controller.ray import RayWorkerGroup
from verl.trainer.config import PPOConfig
from verl.trainer.ray_trainer import ResourcePoolManager, Role
from verl.utils.fsdp_utils import load_fsdp_model, offload_fsdp_model
from verl.utils.tokenizer import get_processor, get_tokenizer
from verl.workers.fsdp_workers import FSDPWorker
from verl.workers.reward import AutoRewardManager

# ── Worker-base MRO proxy (lets PersistentRefFSDPWorker subclass FSDPWorker) ──
from examples.baselines.cil_misc.fsdp_worker_ext import _FSDPWorkerColocBase


# =========================================================================
# Task-1 completion boundary protocol
# =========================================================================

_BOUNDARY_SCHEMA_VERSION = 1
_BOUNDARY_MARKER_NAME = "task1-complete.json"
_BOUNDARY_STATE_DIR = "boundary_state"
_BOUNDARY_SOURCE_ROOTS = (
    # These roots are the production Python implementation that controls the
    # CIL loader, trainer, native checkpoint manager, workers, actor, reward,
    # and sharding/RNG paths.  Only .py files are included; caches and logs are
    # deliberately outside the identity contract.
    "examples/baselines/cil_misc",
    "examples/baselines/img_cls_cil",
    "verl/single_controller",
    "verl/trainer",
    "verl/utils",
    "verl/workers",
)
_BOUNDARY_SOURCE_FILES = (
    # Production entry/config files outside the roots above.
    "examples/baselines/_rapo_components.py",
    "examples/config.yaml",
    "scripts/image/rapo_cfg.json",
    "verl/protocol.py",
)


class CILBoundaryError(ValueError):
    """Raised when a Task-1 completion boundary is not safely resumable."""


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: str, payload: Any, *, refuse_replace: bool = False) -> str:
    """Write a JSON artifact durably enough for a completion marker protocol."""
    path = os.path.abspath(path)
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    if refuse_replace and os.path.exists(path):
        raise CILBoundaryError(f"refusing to replace existing boundary marker: {path}")

    fd, tmp_path = tempfile.mkstemp(prefix=f".{os.path.basename(path)}.", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        try:
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            dir_fd = os.open(parent, flags)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except (AttributeError, OSError):
            # Windows does not expose a directory fsync. The file replace is
            # still atomic on the supported local filesystems.
            pass
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return path


def _read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _safe_join(root: str, relative_path: str) -> str:
    if not isinstance(relative_path, str) or not relative_path or os.path.isabs(relative_path):
        raise CILBoundaryError(f"boundary path must be relative: {relative_path!r}")
    candidate = os.path.realpath(os.path.join(root, relative_path))
    root_real = os.path.realpath(root)
    if os.path.commonpath([candidate, root_real]) != root_real:
        raise CILBoundaryError(f"boundary path escapes root: {relative_path!r}")
    return candidate


def _path_within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([os.path.realpath(path), os.path.realpath(root)]) == os.path.realpath(root)
    except ValueError:
        return False


def _path_overlaps_roots(path: str, roots: Iterable[str]) -> bool:
    """Return whether a candidate path is an ancestor/descendant of a root."""
    return any(_path_within(path, root) or _path_within(root, path) for root in roots)


def _artifact_manifest(root: str) -> list[dict[str, Any]]:
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        raise CILBoundaryError(f"artifact root is not a directory: {root}")
    entries: list[dict[str, Any]] = []
    for current, dirs, files in os.walk(root):
        dirs.sort()
        files.sort()
        for name in files:
            path = os.path.join(current, name)
            if os.path.islink(path):
                raise CILBoundaryError(f"symlink is not a valid boundary artifact: {path}")
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            entries.append({
                "path": relative,
                "bytes": os.path.getsize(path),
                "sha256": _sha256_file(path),
            })
    return entries


def _manifest_hash(entries: list[dict[str, Any]]) -> str:
    return _sha256_bytes(_canonical_json_bytes(entries))


def _validate_artifact_manifest(root: str, entries: Any, *, label: str) -> str:
    if not isinstance(entries, list) or not entries:
        raise CILBoundaryError(f"{label} manifest is empty or malformed")
    expected = []
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
            raise CILBoundaryError(f"{label} manifest item is malformed: {item!r}")
        path = _safe_join(root, item["path"])
        if not os.path.isfile(path):
            raise CILBoundaryError(f"{label} artifact missing: {item['path']}")
        actual_bytes = os.path.getsize(path)
        actual_hash = _sha256_file(path)
        if actual_bytes != item["bytes"] or actual_hash != item["sha256"]:
            raise CILBoundaryError(
                f"{label} artifact hash mismatch: {item['path']} "
                f"expected {item['bytes']}/{item['sha256']}, got {actual_bytes}/{actual_hash}"
            )
        expected.append({"path": item["path"], "bytes": item["bytes"], "sha256": item["sha256"]})
    actual = _artifact_manifest(root)
    if actual != expected:
        raise CILBoundaryError(f"{label} manifest does not cover the complete artifact root")

    if label == "checkpoint":
        relative_paths = {item["path"] for item in expected}
        if "dataloader.pt" not in relative_paths:
            raise CILBoundaryError("full boundary checkpoint is missing dataloader.pt")

        required_roles = {"model", "optim", "extra"}
        shard_roles: dict[tuple[int, int], set[str]] = {}
        prefixes = (
            ("model", "model_world_size_"),
            ("optim", "optim_world_size_"),
            ("extra", "extra_state_world_size_"),
        )
        for relative in sorted(relative_paths):
            if not relative.startswith("actor/"):
                continue
            filename = relative[len("actor/"):]
            if "/" in filename or not filename.endswith(".pt"):
                continue
            for role, prefix in prefixes:
                if not filename.startswith(prefix):
                    continue
                token = filename[len(prefix):-3]
                if "_rank_" not in token:
                    continue
                world_text, rank_text = token.split("_rank_", 1)
                if world_text.isdigit() and rank_text.isdigit():
                    key = (int(world_text), int(rank_text))
                    shard_roles.setdefault(key, set()).add(role)
                break

        if not shard_roles:
            raise CILBoundaryError("full boundary checkpoint has no native actor rank shards")
        world_sizes = {world_size for world_size, _ in shard_roles}
        if len(world_sizes) != 1:
            raise CILBoundaryError("full boundary checkpoint mixes native world sizes")
        world_size = next(iter(world_sizes))
        if world_size <= 0:
            raise CILBoundaryError("full boundary checkpoint has an invalid world size")
        expected_ranks = set(range(world_size))
        actual_ranks = {rank for _, rank in shard_roles}
        if actual_ranks != expected_ranks:
            raise CILBoundaryError(
                "full boundary checkpoint does not contain every native rank "
                f"for world_size={world_size}"
            )
        for rank in sorted(expected_ranks):
            if shard_roles[(world_size, rank)] != required_roles:
                missing = sorted(required_roles - shard_roles[(world_size, rank)])
                raise CILBoundaryError(
                    f"full boundary checkpoint rank {rank} is missing native state: {missing}"
                )
    return _manifest_hash(expected)


def _encode_pickle(value: Any) -> str:
    return base64.b64encode(pickle.dumps(value, protocol=4)).decode("ascii")


def _decode_pickle(value: str) -> Any:
    try:
        return pickle.loads(base64.b64decode(value.encode("ascii")))
    except Exception as exc:
        raise CILBoundaryError(f"invalid encoded RNG state: {exc}") from exc


def _capture_driver_rng_state() -> dict[str, str]:
    return {
        "torch_cpu": _encode_pickle(torch.get_rng_state().cpu().tolist()),
        "numpy": _encode_pickle(np.random.get_state()),
        "python": _encode_pickle(random.getstate()),
    }


def _restore_driver_rng_state(payload: dict[str, str]) -> None:
    required = {"torch_cpu", "numpy", "python"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise CILBoundaryError("driver RNG artifact must contain torch_cpu, numpy and python states")
    try:
        torch_state = torch.tensor(_decode_pickle(payload["torch_cpu"]), dtype=torch.uint8)
        torch.set_rng_state(torch_state)
        np.random.set_state(_decode_pickle(payload["numpy"]))
        random.setstate(_decode_pickle(payload["python"]))
    except CILBoundaryError:
        raise
    except Exception as exc:
        raise CILBoundaryError(f"failed to restore driver RNG state: {exc}") from exc


def _validate_driver_rng_payload(payload: Any) -> None:
    required = {"torch_cpu", "numpy", "python"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise CILBoundaryError("driver RNG artifact must contain torch_cpu, numpy and python states")
    # Decode without mutating the current process. The actual restore happens
    # in the persistent runner immediately before Task-2 loader creation.
    for key in required:
        if not isinstance(payload[key], str):
            raise CILBoundaryError(f"driver RNG field {key} is not encoded text")
        _decode_pickle(payload[key])


def _repo_root() -> str:
    return str(Path(__file__).resolve().parents[3])


def _source_identity() -> dict[str, Any]:
    root = _repo_root()
    relative_paths = set(_BOUNDARY_SOURCE_FILES)
    for source_root in _BOUNDARY_SOURCE_ROOTS:
        source_root_path = os.path.join(root, source_root.replace("/", os.sep))
        if not os.path.isdir(source_root_path):
            raise CILBoundaryError(f"source identity root is missing: {source_root}")
        for current, dirs, names in os.walk(source_root_path):
            dirs[:] = sorted(name for name in dirs if name != "__pycache__" and not name.startswith("."))
            for name in sorted(names):
                if name.endswith(".py") and not name.startswith("."):
                    path = os.path.join(current, name)
                    relative_paths.add(os.path.relpath(path, root).replace(os.sep, "/"))

    files: list[dict[str, Any]] = []
    for relative in sorted(relative_paths):
        path = os.path.join(root, relative.replace("/", os.sep))
        if not os.path.isfile(path):
            raise CILBoundaryError(f"source identity file is missing: {relative}")
        files.append({
            "path": relative,
            "bytes": os.path.getsize(path),
            "sha256": _sha256_file(path),
        })
    return {"files": files, "manifest_sha256": _manifest_hash(files)}


def _path_identity(path_like: Optional[str], *, label: str, include_contents: bool = True) -> dict[str, Any]:
    if not path_like:
        raise CILBoundaryError(f"{label} path is empty")
    path = os.path.abspath(os.path.expanduser(str(path_like)))
    if os.path.isfile(path):
        return {
            "kind": "file",
            "path": path,
            "bytes": os.path.getsize(path),
            "sha256": _sha256_file(path),
        }
    if not os.path.isdir(path):
        raise CILBoundaryError(f"{label} path does not exist: {path}")
    files: list[dict[str, Any]] = []
    for current, dirs, names in os.walk(path):
        dirs.sort()
        names.sort()
        for name in names:
            item_path = os.path.join(current, name)
            if os.path.islink(item_path):
                raise CILBoundaryError(f"{label} contains a symlink: {item_path}")
            relative = os.path.relpath(item_path, path).replace(os.sep, "/")
            item: dict[str, Any] = {"path": relative, "bytes": os.path.getsize(item_path)}
            if include_contents:
                item["sha256"] = _sha256_file(item_path)
            files.append(item)
    return {
        "kind": "directory",
        "path": path,
        "files": files,
        "manifest_sha256": _manifest_hash(files),
    }


def _model_identity(config: PPOConfig) -> dict[str, Any]:
    model_cfg = config.worker.actor.model
    model_path = str(model_cfg.model_path)
    revision = getattr(model_cfg, "revision", None) or getattr(model_cfg, "model_revision", None)
    identity: dict[str, Any] = {"path": os.path.abspath(os.path.expanduser(model_path))}
    if os.path.exists(identity["path"]):
        content_manifest = _path_identity(identity["path"], label="model", include_contents=True)
        if content_manifest.get("kind") == "directory" and not content_manifest.get("files"):
            raise CILBoundaryError("model identity cannot bind an empty local model directory")
        identity["content_manifest"] = content_manifest
    else:
        # A remote model reference is accepted only when pinned to a commit-like
        # immutable revision.  A branch/tag or path string alone cannot prove
        # that the weights, index, config and tokenizer are unchanged.
        revision_text = str(revision or "")
        hex_digits = set("0123456789abcdefABCDEF")
        if len(revision_text) != 40 or any(char not in hex_digits for char in revision_text):
            raise CILBoundaryError(
                "model identity needs a local content manifest or a 40-hex immutable revision"
            )
        identity["revision"] = revision_text
    identity["anchor_provenance"] = "reconstructed_from_task1_actor"
    identity["hash"] = _sha256_bytes(_canonical_json_bytes(identity))
    return identity


def _input_identity(config: PPOConfig) -> dict[str, Any]:
    data = config.data
    result = {
        "train": _path_identity(data.train_files, label="train input"),
        "val": _path_identity(data.val_files, label="validation input"),
    }
    for name in ("image_dir", "format_prompt", "categories_path"):
        value = getattr(data, name, None)
        if value:
            result[name] = _path_identity(value, label=name)
    result["hash"] = _sha256_bytes(_canonical_json_bytes(result))
    return result


def _config_identity(config: PPOConfig, cil_config: Optional[dict[str, Any]]) -> dict[str, Any]:
    if hasattr(config, "to_dict"):
        ppo = copy.deepcopy(config.to_dict())
    else:
        ppo = copy.deepcopy(config)
    trainer = ppo.get("trainer", {}) if isinstance(ppo, dict) else {}
    if isinstance(trainer, dict):
        trainer["save_checkpoint_path"] = "<task-output-root>"
        trainer["load_checkpoint_path"] = None
        trainer["find_last_checkpoint"] = False
    cil = copy.deepcopy(cil_config or {})
    if isinstance(cil, dict):
        cil_group = cil.get("cil")
        if isinstance(cil_group, dict):
            # The boundary plan is authoritative; it is bound separately.
            for key in ("class_order", "class_order_seed", "base_classes", "incremental_classes"):
                cil_group.pop(key, None)
    payload = {"ppo": ppo, "cil": cil}
    return {"payload": payload, "hash": _sha256_bytes(_canonical_json_bytes(payload))}


def _plan_identity(
    class_names: list[str],
    class_order: list[int],
    class_splits: list[list[int]],
    *,
    base_classes: int,
    incremental_classes: int,
    prompt_seen_labels: bool,
) -> dict[str, Any]:
    split_names = [[class_names[i] for i in split] for split in class_splits]
    seen_ids = list(class_splits[0])
    next_ids = list(class_splits[1])
    payload = {
        "class_order_ids": [int(x) for x in class_order],
        "class_order_names": [class_names[i] for i in class_order],
        "class_splits": [[int(x) for x in split] for split in class_splits],
        "class_split_names": split_names,
        "total_tasks": len(class_splits),
        "base_classes": int(base_classes),
        "incremental_classes": int(incremental_classes),
        "completed_task": 1,
        "next_task": 2,
        "completed_task_classes": split_names[0],
        "next_task_classes": split_names[1],
        "next_task_seen_classes": [class_names[i] for i in seen_ids + next_ids],
        "prompt_seen_labels": bool(prompt_seen_labels),
    }
    return {"payload": payload, "hash": _sha256_bytes(_canonical_json_bytes(payload))}


def _loader_policy(config: PPOConfig, plan: dict[str, Any]) -> dict[str, Any]:
    data = config.data
    batch_size = data.mini_rollout_batch_size or data.rollout_batch_size
    plan_payload = plan["payload"]
    prompt_classes = (
        plan_payload["next_task_seen_classes"]
        if plan_payload["prompt_seen_labels"]
        else plan_payload["next_task_classes"]
    )
    return {
        "kind": "new_task_dataloader",
        "task_id": 2,
        "cursor": 0,
        "sampler": "RandomSampler" if data.shuffle else "SequentialSampler",
        "seed": int(data.seed),
        "shuffle": bool(data.shuffle),
        "drop_last": True,
        "batch_size": int(batch_size),
        "current_classes": list(plan_payload["next_task_classes"]),
        "seen_classes": list(plan_payload["next_task_seen_classes"]),
        "prompt_classes": prompt_classes,
    }


def _build_boundary_context(
    config: PPOConfig,
    cil_config: Optional[dict[str, Any]],
    class_names: list[str],
    class_order: list[int],
    class_splits: list[list[int]],
    known_args: argparse.Namespace,
) -> dict[str, Any]:
    plan = _plan_identity(
        class_names,
        class_order,
        class_splits,
        base_classes=len(class_splits[0]),
        incremental_classes=len(class_splits[1]),
        prompt_seen_labels=bool(known_args.prompt_seen_labels),
    )
    context = {
        "plan": plan,
        "config": _config_identity(config, cil_config),
        "source": _source_identity(),
        "model": _model_identity(config),
        "input": _input_identity(config),
    }
    context["loader_policy"] = _loader_policy(config, plan)
    context["state_fingerprint"] = _sha256_bytes(_canonical_json_bytes({
        "plan": plan["hash"],
        "config": context["config"]["hash"],
        "source": context["source"]["manifest_sha256"],
        "model": context["model"]["hash"],
        "input": context["input"]["hash"],
        "loader_policy": context["loader_policy"],
    }))
    return context


def _validate_boundary_context(
    boundary: dict[str, Any],
    *,
    config: PPOConfig,
    cil_config: Optional[dict[str, Any]],
    class_names: list[str],
    known_args: argparse.Namespace,
) -> None:
    plan = boundary["plan"]
    payload = plan.get("payload")
    if not isinstance(payload, dict):
        raise CILBoundaryError("boundary plan payload is missing")
    if payload.get("completed_task") != 1 or payload.get("next_task") != 2:
        raise CILBoundaryError("boundary only supports completed_task=1 and next_task=2")
    class_order_ids = payload.get("class_order_ids")
    if not isinstance(class_order_ids, list) or any(
        not isinstance(i, int) or i < 0 or i >= len(class_names) for i in class_order_ids
    ):
        raise CILBoundaryError("boundary class order contains an invalid class id")
    if len(set(class_order_ids)) != len(class_names):
        raise CILBoundaryError("boundary class order is not a complete permutation")
    if payload.get("class_order_names") != [class_names[i] for i in class_order_ids]:
        raise CILBoundaryError("boundary class order does not match current input classes")
    class_splits = payload.get("class_splits")
    if not isinstance(class_splits, list) or not class_splits:
        raise CILBoundaryError("boundary class_splits is missing")
    for split in class_splits:
        if not isinstance(split, list):
            raise CILBoundaryError("boundary class split is malformed")
        if any(not isinstance(i, int) or i < 0 or i >= len(class_names) for i in split):
            raise CILBoundaryError("boundary class split contains an invalid class id")
    if payload.get("class_split_names") != [[class_names[i] for i in split] for split in class_splits]:
        raise CILBoundaryError("boundary class split names do not match current input classes")
    if known_args.base_classes is not None and int(known_args.base_classes) != payload["base_classes"]:
        raise CILBoundaryError("boundary base_classes differs from the requested plan")
    if known_args.incremental_classes is not None and int(known_args.incremental_classes) != payload["incremental_classes"]:
        raise CILBoundaryError("boundary incremental_classes differs from the requested plan")
    if bool(known_args.prompt_seen_labels) != bool(payload.get("prompt_seen_labels")):
        raise CILBoundaryError("boundary prompt_seen_labels differs from the requested plan")
    if known_args.class_order:
        requested_order = base._parse_class_order_arg(known_args.class_order, len(class_names))
        if requested_order != payload["class_order_ids"]:
            raise CILBoundaryError("boundary class order differs from the requested class_order")
    elif known_args.class_order_seed is not None:
        requested_order = base._build_class_order(len(class_names), None, known_args.class_order_seed)
        if requested_order != payload["class_order_ids"]:
            raise CILBoundaryError("boundary class order differs from the requested class_order_seed")

    expected_context = _build_boundary_context(
        config,
        cil_config,
        class_names,
        payload["class_order_ids"],
        payload["class_splits"],
        known_args,
    )
    for field in ("config", "source", "model", "input"):
        actual_hash = boundary[field].get("hash") or boundary[field].get("manifest_sha256")
        expected_hash = expected_context[field].get("hash") or expected_context[field].get("manifest_sha256")
        if actual_hash != expected_hash:
            raise CILBoundaryError(f"boundary {field} identity mismatch")
    if boundary.get("loader_policy") != expected_context["loader_policy"]:
        raise CILBoundaryError("boundary loader policy differs from the requested Task-2 recipe")


def _load_task_boundary(path: str) -> dict[str, Any]:
    """Load and fail-closed validate all on-disk boundary artifacts."""
    marker_path = os.path.abspath(path)
    if os.path.basename(marker_path) != _BOUNDARY_MARKER_NAME:
        raise CILBoundaryError(f"resume path must be {_BOUNDARY_MARKER_NAME}")
    boundary_root = os.path.dirname(marker_path)
    if not os.path.isfile(marker_path):
        raise CILBoundaryError(f"boundary marker is missing: {marker_path}")
    boundary = _read_json(marker_path)
    if not isinstance(boundary, dict):
        raise CILBoundaryError("boundary marker must contain a JSON object")
    if boundary.get("schema_version") != _BOUNDARY_SCHEMA_VERSION:
        raise CILBoundaryError("unsupported boundary schema version")
    if boundary.get("status") != "complete":
        raise CILBoundaryError("boundary marker is not complete")
    if boundary.get("completed_task") != 1 or boundary.get("next_task") != 2:
        raise CILBoundaryError("boundary marker is not a Task-1→Task-2 boundary")
    loader_policy = boundary.get("loader_policy")
    plan_field = boundary.get("plan")
    plan_payload = plan_field.get("payload", {}) if isinstance(plan_field, dict) else {}
    if not isinstance(plan_payload, dict):
        raise CILBoundaryError("boundary plan payload is missing")
    if not isinstance(loader_policy, dict):
        raise CILBoundaryError("boundary loader policy is missing")
    if loader_policy.get("kind") != "new_task_dataloader" or loader_policy.get("task_id") != 2:
        raise CILBoundaryError("boundary loader policy is not a fresh Task-2 loader")
    if loader_policy.get("cursor") != 0:
        raise CILBoundaryError("Task-2 boundary loader cursor must be zero")
    if loader_policy.get("current_classes") != plan_payload.get("next_task_classes"):
        raise CILBoundaryError("Task-2 current classes do not match the boundary plan")
    if loader_policy.get("seen_classes") != plan_payload.get("next_task_seen_classes"):
        raise CILBoundaryError("Task-2 seen classes do not match the boundary plan")

    checkpoint = boundary.get("checkpoint")
    if not isinstance(checkpoint, dict) or checkpoint.get("save_model_only") is not False:
        raise CILBoundaryError("boundary checkpoint must be a full save_model_only=false checkpoint")
    checkpoint_rel = checkpoint.get("relative_path")
    checkpoint_root = _safe_join(boundary_root, checkpoint_rel)
    if not os.path.isdir(checkpoint_root):
        raise CILBoundaryError(f"boundary checkpoint directory is missing: {checkpoint_rel}")
    step = checkpoint_root.rstrip(os.sep).split(os.sep)[-1]
    if step != f"global_step_{boundary.get('global_step')}":
        raise CILBoundaryError("boundary checkpoint directory and global_step disagree")
    manifest_hash = _validate_artifact_manifest(checkpoint_root, checkpoint.get("files"), label="checkpoint")
    if manifest_hash != checkpoint.get("manifest_sha256"):
        raise CILBoundaryError("checkpoint manifest hash mismatch")
    if "dataloader.pt" not in {item["path"] for item in checkpoint["files"]}:
        raise CILBoundaryError("full boundary checkpoint is missing dataloader.pt")
    if not any(
        f["path"].startswith("actor/") and "optim_world_size_" in f["path"]
        for f in checkpoint["files"]
    ):
        raise CILBoundaryError("full boundary checkpoint has no optimizer state")
    if not any(
        f["path"].startswith("actor/") and "extra_state_world_size_" in f["path"]
        for f in checkpoint["files"]
    ):
        raise CILBoundaryError("full boundary checkpoint has no worker RNG state")

    tracker = boundary.get("tracker")
    if not isinstance(tracker, dict):
        raise CILBoundaryError("boundary tracker metadata is missing")
    tracker_path = _safe_join(boundary_root, tracker.get("relative_path"))
    if not os.path.isfile(tracker_path):
        raise CILBoundaryError("boundary checkpoint tracker is missing")
    if _sha256_file(tracker_path) != tracker.get("sha256"):
        raise CILBoundaryError("boundary checkpoint tracker hash mismatch")
    tracker_payload = _read_json(tracker_path)
    if tracker_payload.get("last_global_step") != boundary.get("global_step"):
        raise CILBoundaryError("tracker and boundary global_step disagree")
    tracker_actor = os.path.realpath(str(tracker_payload.get("last_actor_path", "")))
    if tracker_actor != os.path.realpath(os.path.join(checkpoint_root, "actor")):
        raise CILBoundaryError("tracker last_actor_path is not the boundary actor")

    ema = boundary.get("ema")
    if not isinstance(ema, dict):
        raise CILBoundaryError("boundary EMA artifact metadata is missing")
    ema_path = _safe_join(boundary_root, ema.get("relative_path"))
    if not os.path.isfile(ema_path) or _sha256_file(ema_path) != ema.get("sha256"):
        raise CILBoundaryError("boundary EMA artifact is missing or corrupt")
    ema_payload = _read_json(ema_path)
    if not isinstance(ema_payload, dict) or not isinstance(ema_payload.get("ema_mean"), (int, float)):
        raise CILBoundaryError("boundary EMA payload is malformed")
    if type(ema_payload.get("update_count")) is not int or ema_payload["update_count"] <= 0:
        raise CILBoundaryError("boundary EMA update_count is not a positive integer")
    if ema.get("update_count") != ema_payload["update_count"]:
        raise CILBoundaryError("boundary EMA update_count mismatch")

    rng = boundary.get("rng")
    if not isinstance(rng, dict):
        raise CILBoundaryError("boundary RNG metadata is missing")
    driver = rng.get("driver")
    if not isinstance(driver, dict):
        raise CILBoundaryError("driver RNG metadata is missing")
    driver_path = _safe_join(boundary_root, driver.get("relative_path"))
    if not os.path.isfile(driver_path) or _sha256_file(driver_path) != driver.get("sha256"):
        raise CILBoundaryError("driver RNG artifact is missing or corrupt")
    _validate_driver_rng_payload(_read_json(driver_path))
    vllm = rng.get("vllm")
    if not isinstance(vllm, list) or not vllm:
        raise CILBoundaryError("per-rank vLLM RNG metadata is missing")
    for item in vllm:
        if not isinstance(item, dict):
            raise CILBoundaryError("malformed per-rank vLLM RNG metadata")
        vllm_path = _safe_join(boundary_root, item.get("relative_path"))
        if not os.path.isfile(vllm_path) or _sha256_file(vllm_path) != item.get("sha256"):
            raise CILBoundaryError(f"vLLM RNG artifact is missing or corrupt: {item.get('relative_path')}")
        payload = _read_json(vllm_path)
        if not isinstance(payload, dict) or set(payload) != {"rank", "torch_random_states", "gen_random_states"}:
            raise CILBoundaryError("malformed per-rank vLLM RNG payload")

    _validate_identity_hashes(boundary)
    expected_state_fingerprint = _sha256_bytes(_canonical_json_bytes({
        "plan": boundary["plan"]["hash"],
        "config": boundary["config"]["hash"],
        "source": boundary["source"]["manifest_sha256"],
        "model": boundary["model"]["hash"],
        "input": boundary["input"]["hash"],
        "loader_policy": boundary["loader_policy"],
        "checkpoint": boundary["checkpoint"]["manifest_sha256"],
        "ema": boundary["ema"]["sha256"],
        "driver": boundary["rng"]["driver"]["sha256"],
        "vllm": boundary["rng"]["vllm"],
    }))
    if boundary.get("state_fingerprint") != expected_state_fingerprint:
        raise CILBoundaryError("boundary state fingerprint is invalid")
    boundary["_marker_path"] = marker_path
    boundary["_boundary_root"] = boundary_root
    boundary["_checkpoint_path"] = checkpoint_root
    boundary["_ema_path"] = ema_path
    boundary["_driver_path"] = driver_path
    return boundary


def _validate_identity_hashes(boundary: dict[str, Any]) -> None:
    for field, hash_key in (("plan", "hash"), ("config", "hash"), ("model", "hash"), ("input", "hash")):
        value = boundary.get(field)
        if not isinstance(value, dict) or hash_key not in value:
            raise CILBoundaryError(f"boundary {field} identity hash is missing")
        payload = value.get("payload") if field in {"plan", "config"} else {
            key: item for key, item in value.items() if key not in {"hash"}
        }
        if _sha256_bytes(_canonical_json_bytes(payload)) != value[hash_key]:
            raise CILBoundaryError(f"boundary {field} identity hash is invalid")


def _boundary_state_path(boundary_root: str, name: str) -> str:
    return os.path.join(boundary_root, _BOUNDARY_STATE_DIR, name)


def _publish_task_boundary(
    *,
    boundary_root: str,
    checkpoint_path: str,
    tracker_path: str,
    global_step: int,
    ema_payload: dict[str, Any],
    driver_rng_payload: dict[str, str],
    vllm_rng_payloads: list[dict[str, Any]],
    context: dict[str, Any],
) -> str:
    """Publish a complete Task-1 boundary, with the marker written last."""
    boundary_root = os.path.abspath(boundary_root)
    checkpoint_path = os.path.abspath(checkpoint_path)
    tracker_path = os.path.abspath(tracker_path)
    if not _path_within(checkpoint_path, boundary_root) or not os.path.isdir(checkpoint_path):
        raise CILBoundaryError("boundary checkpoint must be an existing child of the Task-1 root")
    if not os.path.basename(checkpoint_path).startswith("global_step_"):
        raise CILBoundaryError("boundary checkpoint must end in global_step_N")
    if not _path_within(tracker_path, boundary_root) or not os.path.isfile(tracker_path):
        raise CILBoundaryError("boundary tracker must be an existing child of the Task-1 root")
    if not isinstance(global_step, int) or global_step <= 0:
        raise CILBoundaryError("boundary global_step must be a positive integer")
    if not isinstance(ema_payload, dict) or type(ema_payload.get("update_count")) is not int:
        raise CILBoundaryError("boundary EMA payload must contain an integer update_count")
    if ema_payload["update_count"] <= 0:
        raise CILBoundaryError("boundary EMA update_count must be positive")
    if not isinstance(vllm_rng_payloads, list) or not vllm_rng_payloads:
        raise CILBoundaryError("boundary publication needs one vLLM RNG payload per rank")
    if context.get("plan", {}).get("payload", {}).get("next_task") != 2:
        raise CILBoundaryError("boundary publication is limited to Task 1→Task 2")

    tracker_payload = _read_json(tracker_path)
    if tracker_payload.get("last_global_step") != global_step:
        raise CILBoundaryError("tracker last_global_step does not match boundary global_step")
    if os.path.realpath(str(tracker_payload.get("last_actor_path", ""))) != os.path.realpath(
        os.path.join(checkpoint_path, "actor")
    ):
        raise CILBoundaryError("tracker last_actor_path does not point to the boundary actor")

    checkpoint_files = _artifact_manifest(checkpoint_path)
    if not any(
        item["path"].startswith("actor/") and "optim_world_size_" in item["path"]
        for item in checkpoint_files
    ):
        raise CILBoundaryError("boundary publication requires optimizer state")
    if not any(
        item["path"].startswith("actor/") and "extra_state_world_size_" in item["path"]
        for item in checkpoint_files
    ):
        raise CILBoundaryError("boundary publication requires worker RNG state")
    _validate_artifact_manifest(checkpoint_path, checkpoint_files, label="checkpoint")

    state_dir = os.path.join(boundary_root, _BOUNDARY_STATE_DIR)
    os.makedirs(state_dir, exist_ok=True)
    ema_rel = f"{_BOUNDARY_STATE_DIR}/ema_task1.json"
    driver_rel = f"{_BOUNDARY_STATE_DIR}/driver_rng.json"
    _atomic_write_json(os.path.join(boundary_root, ema_rel), ema_payload)
    _atomic_write_json(os.path.join(boundary_root, driver_rel), driver_rng_payload)

    vllm_records: list[dict[str, Any]] = []
    for payload in sorted(vllm_rng_payloads, key=lambda item: int(item.get("rank", -1))):
        if set(payload) != {"rank", "torch_random_states", "gen_random_states"}:
            raise CILBoundaryError("malformed vLLM RNG payload at publication")
        rank = int(payload["rank"])
        rel = f"{_BOUNDARY_STATE_DIR}/vllm_rng_rank_{rank}.json"
        _atomic_write_json(os.path.join(boundary_root, rel), payload)
        vllm_records.append({
            "rank": rank,
            "relative_path": rel,
            "sha256": _sha256_file(os.path.join(boundary_root, rel)),
        })

    checkpoint_rel = os.path.relpath(checkpoint_path, boundary_root).replace(os.sep, "/")
    tracker_rel = os.path.relpath(tracker_path, boundary_root).replace(os.sep, "/")
    marker: dict[str, Any] = {
        "schema_version": _BOUNDARY_SCHEMA_VERSION,
        "status": "complete",
        "completed_task": 1,
        "next_task": 2,
        "global_step": global_step,
        "checkpoint": {
            "relative_path": checkpoint_rel,
            "save_model_only": False,
            "files": checkpoint_files,
            "manifest_sha256": _manifest_hash(checkpoint_files),
        },
        "tracker": {
            "relative_path": tracker_rel,
            "sha256": _sha256_file(tracker_path),
        },
        "ema": {
            "relative_path": ema_rel,
            "sha256": _sha256_file(os.path.join(boundary_root, ema_rel)),
            "update_count": ema_payload["update_count"],
        },
        "plan": context["plan"],
        "config": context["config"],
        "source": context["source"],
        "model": context["model"],
        "input": context["input"],
        "loader_policy": context["loader_policy"],
        "rng": {
            "driver": {
                "relative_path": driver_rel,
                "sha256": _sha256_file(os.path.join(boundary_root, driver_rel)),
            },
            "vllm": vllm_records,
        },
    }
    marker["state_fingerprint"] = _sha256_bytes(_canonical_json_bytes({
        "plan": marker["plan"]["hash"],
        "config": marker["config"]["hash"],
        "source": marker["source"]["manifest_sha256"],
        "model": marker["model"]["hash"],
        "input": marker["input"]["hash"],
        "loader_policy": marker["loader_policy"],
        "checkpoint": marker["checkpoint"]["manifest_sha256"],
        "ema": marker["ema"]["sha256"],
        "driver": marker["rng"]["driver"]["sha256"],
        "vllm": marker["rng"]["vllm"],
    }))
    marker_path = os.path.join(boundary_root, _BOUNDARY_MARKER_NAME)
    _atomic_write_json(marker_path, marker, refuse_replace=True)
    return marker_path


# =========================================================================
# PersistentRefFSDPWorker – FSDPWorker with in-memory weight copy across models
# =========================================================================

class PersistentRefFSDPWorker(_FSDPWorkerColocBase, FSDPWorker):
    """FSDPWorker that supports in-memory weight copy across FSDP models.

    Adds methods for:
    - Copying actor weights → anchor (previous-task, from task 2 onward)
    - Initialising and running the frozen anchor model

    Uses ``_FSDPWorkerColocBase`` as the first parent so that verl's colocated
    worker construction still works (see ``fsdp_worker_ext``).
    """

    def __init__(self, config, role):
        super().__init__(config, role)
        # RaPO always builds a frozen anchor (the previous-task policy) whenever
        # a reference model exists. init_anchor() loads the anchor module from
        # model_path (the original weights at init time); the actual previous-
        # task weights are copied in-memory before each task from
        # activate_from_task onward.
        if self._has_ref:
            self._has_anchor: bool = True
            t_path = getattr(config.actor.model, "anchor_model_path", None)
            if not t_path or not str(t_path).strip():
                config.actor.model.anchor_model_path = config.actor.model.model_path
        else:
            self._has_anchor = False

    # ------------------------------------------------------------------
    # Anchor init
    # ------------------------------------------------------------------

    @register(dispatch_mode=Dispatch.ONE_TO_ALL)
    def init_anchor(self) -> None:
        if not self._has_anchor:
            return

        anchor_model_path: str = getattr(
            self.config.actor.model, "anchor_model_path", ""
        )
        existing_ref = self.ref_fsdp_module
        original_path: str = self.config.actor.model.model_path
        try:
            self.config.actor.model.model_path = anchor_model_path
            self._build_model_optimizer(
                model_config=self.config.actor.model,
                fsdp_config=self.config.ref.fsdp,
                optim_config=None,
                padding_free=self.config.ref.padding_free,
                role="ref",
            )
        finally:
            self.config.actor.model.model_path = original_path

        self.anchor_fsdp_module = self.ref_fsdp_module
        self.ref_fsdp_module = existing_ref

        from verl.workers.actor.dp_actor import DataParallelPPOActor

        self.anchor_policy = DataParallelPPOActor(
            config=self.config.ref,
            actor_module=self.anchor_fsdp_module,
        )

    # ------------------------------------------------------------------
    # Anchor log-probs
    # ------------------------------------------------------------------

    @register(dispatch_mode=Dispatch.DP_COMPUTE_PROTO)
    def compute_anchor_log_probs(self, data: DataProto) -> DataProto:
        # The frozen anchor (previous-task model) is mandatory for the retention
        # reward.  A missing anchor means init_anchor() did not run or the
        # per-task actor->anchor weight copy failed; fail loudly rather than
        # silently substituting the ref model.
        if not self._has_anchor:
            raise RuntimeError(
                "compute_anchor_log_probs() called without an initialised anchor "
                "model. Ensure init_anchor() ran after init_workers() and that the "
                "anchor weights were copied for this task."
            )

        assert hasattr(self, "anchor_fsdp_module")

        self._process_multi_modal_inputs(data)
        data = data.to(torch.cuda.current_device())

        if self._use_ref_param_offload:
            load_fsdp_model(self.anchor_fsdp_module)

        data.meta_info["temperature"] = self.config.rollout.temperature
        with self.ulysses_sharding_manager:
            data = self.ulysses_sharding_manager.preprocess_data(data)
            output = self.anchor_policy.compute_log_prob(data=data)
            output = DataProto.from_dict(tensors={"anchor_log_probs": output})
            output = self.ulysses_sharding_manager.postprocess_data(output)

        if self.world_size > 1:
            self.anchor_fsdp_module._handle.reshard(True)

        if self._use_ref_param_offload:
            offload_fsdp_model(self.anchor_fsdp_module)

        output = output.to("cpu")
        return output

    # ------------------------------------------------------------------
    # In-memory FSDP weight copy: actor → anchor
    # ------------------------------------------------------------------

    @register(dispatch_mode=Dispatch.ONE_TO_ALL)
    def copy_actor_to_anchor(self) -> None:
        """Copy actor FSDP flat-param weights to the anchor FSDP module."""
        if not getattr(self, "_has_anchor", False) or not hasattr(self, "anchor_fsdp_module"):
            raise RuntimeError("copy_actor_to_anchor called without an initialised anchor module")

        if self._use_param_offload:
            load_fsdp_model(self.fsdp_module)
        if self._use_ref_param_offload:
            load_fsdp_model(self.anchor_fsdp_module)

        with torch.no_grad():
            for p_a, p_t in zip(
                self.fsdp_module.parameters(),
                self.anchor_fsdp_module.parameters(),
            ):
                p_t.data.copy_(p_a.data.to(p_t.dtype))

        import torch.distributed as dist
        dist.barrier()

        if self._use_param_offload:
            offload_fsdp_model(self.fsdp_module)
        if self._use_ref_param_offload:
            offload_fsdp_model(self.anchor_fsdp_module)

    # ------------------------------------------------------------------
    # Boundary-only vLLM RNG capture/restore
    # ------------------------------------------------------------------

    @register(dispatch_mode=Dispatch.ONE_TO_ALL)
    def capture_boundary_vllm_rng(self) -> dict[str, Any]:
        """Return the per-rank RNG streams owned by the rollout manager.

        The generic checkpoint manager intentionally does not know about this
        image worker's vLLM sharding manager. Keep this small API local to the
        image CIL worker so video/detection and shared checkpoint code remain
        unchanged.
        """
        manager = getattr(self, "rollout_sharding_manager", None)
        if manager is None or not hasattr(manager, "gen_random_states"):
            raise RuntimeError("vLLM RNG manager is not initialised")
        if getattr(manager, "loaded", False):
            raise RuntimeError("capture_boundary_vllm_rng requires vLLM to be offloaded")
        return {
            "rank": int(self.rank),
            "torch_random_states": manager.torch_random_states.detach().cpu().tolist(),
            "gen_random_states": manager.gen_random_states.detach().cpu().tolist(),
        }

    @register(dispatch_mode=Dispatch.DP_COMPUTE)
    def restore_boundary_vllm_rng(self, payload: dict[str, Any]) -> None:
        """Restore a previously captured per-rank rollout RNG stream."""
        manager = getattr(self, "rollout_sharding_manager", None)
        if manager is None or not hasattr(manager, "gen_random_states"):
            raise RuntimeError("vLLM RNG manager is not initialised")
        if getattr(manager, "loaded", False):
            raise RuntimeError("restore_boundary_vllm_rng requires vLLM to be offloaded")
        if not isinstance(payload, dict):
            raise ValueError("vLLM RNG payload must be a mapping")
        if int(payload.get("rank", -1)) != int(self.rank):
            raise ValueError("vLLM RNG payload rank does not match worker rank")
        try:
            torch_state = torch.tensor(payload["torch_random_states"], dtype=torch.uint8, device="cuda")
            gen_state = torch.tensor(payload["gen_random_states"], dtype=torch.uint8, device="cuda")
            manager.torch_random_states = torch_state
            manager.gen_random_states = gen_state
        except Exception as exc:
            raise ValueError(f"invalid vLLM RNG payload: {exc}") from exc

# =========================================================================
# PersistentCILTrainer – reusable trainer across tasks
# =========================================================================

class PersistentCILTrainer(RayPPOContinualRaPOTrainer):
    """Trainer that can re-run fit() multiple times on the same worker group.

    Supports:
    - Swapping train/val dataloaders between tasks
    - Resetting global_step to pick up from last checkpoint step
    - Setting max_steps for each task
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # When set, _load_checkpoint will use this instead of loading from disk.
        self._preset_global_step: Optional[int] = None
        self._boundary_restored = False

    def _load_checkpoint(self) -> None:
        """Override to support in-memory weight persistence.

        For task 1, behaves normally (loads from disk if path set).
        For task 2+, weights are already in memory so we only set global_step.
        """
        if self._preset_global_step is not None:
            self.global_step = self._preset_global_step
            print(f"[CIL] Set global_step={self.global_step} (weights already in memory)")
            return
        # Task 1: normal checkpoint loading
        super()._load_checkpoint()

    def reinit_for_task(
        self,
        train_dataloader,
        val_dataloader,
        *,
        task_id: int,
        per_task_steps: int,
        last_global_step: int,
        save_checkpoint_path: str,
        load_checkpoint_path: Optional[str],
        ema_adv_state: Optional[dict] = None,
        enable_anchor: bool = False,
        fresh_boundary_resume: bool = False,
    ) -> None:
        """Re-initialise task-dependent state for a new CIL task."""
        self.train_dataloader = train_dataloader
        self.val_dataloader = val_dataloader
        self._task_id = task_id

        # Update config paths
        self.config.trainer.save_checkpoint_path = save_checkpoint_path
        self.config.trainer.find_last_checkpoint = False

        # The normal continuous path deliberately keeps task 2+ in memory.
        # Fresh boundary resume is the explicit exception: its native restore
        # is performed by restore_boundary_checkpoint() before the anchor copy.
        self._boundary_restored = False
        if fresh_boundary_resume:
            if task_id != 2 or not load_checkpoint_path:
                raise CILBoundaryError("fresh boundary resume requires Task 2 and a native checkpoint path")
            self.config.trainer.load_checkpoint_path = load_checkpoint_path
            self._preset_global_step = None
        elif task_id == 1:
            self.config.trainer.load_checkpoint_path = load_checkpoint_path
            self._preset_global_step = None
        else:
            self.config.trainer.load_checkpoint_path = None
            self._preset_global_step = last_global_step

        # Step management
        new_max_steps = per_task_steps + last_global_step
        self.config.trainer.max_steps = new_max_steps
        self.training_steps = new_max_steps

        # Output dir for snapshots
        self.output_dir = save_checkpoint_path

        # Update EMA state
        if self.ema_adv is not None:
            self.ema_adv = EMAAdvNormalizer(
                self.ema_adv_config,
                initial_state=ema_adv_state,
                task_id=task_id,
            )

        # In persistent mode, auxiliary anchor availability is determined by the
        # enable_anchor flag (derived from ref_cfg + task_id) rather than
        # config paths (which are never modified by hooks in persistent mode).
        self._anchor_available = enable_anchor

        # Clear pending retention metrics from previous task to prevent
        # stale metrics leaking into the next task's first log entry.
        self._pending_retention_metrics = {}

        # Reset best score tracking (must match RayPPOTrainer.__init__ defaults)
        self.val_reward_score = 0.0
        self.best_val_reward_score = -1.0
        self.best_global_step = None

    def restore_boundary_checkpoint(self, checkpoint_path: str, expected_global_step: int) -> None:
        """Restore native state once, then let fit() use a controlled preset.

        This keeps the generic trainer untouched while making the order
        explicit: disk actor/optimizer/scheduler/worker RNG restore first,
        anchor reconstruction second, Task-2 rollout third.
        """
        if self._task_id != 2:
            raise CILBoundaryError("native boundary restore is only valid for Task 2")
        if self._preset_global_step is not None or self._boundary_restored:
            raise CILBoundaryError("boundary checkpoint restore was already attempted")
        if not checkpoint_path or self.config.trainer.load_checkpoint_path != checkpoint_path:
            raise CILBoundaryError("boundary checkpoint path was not explicitly installed")
        super()._load_checkpoint()
        if self.global_step != int(expected_global_step):
            raise CILBoundaryError(
                f"native checkpoint restored global_step={self.global_step}, expected {expected_global_step}"
            )
        self.config.trainer.load_checkpoint_path = None
        self._preset_global_step = int(expected_global_step)
        self._boundary_restored = True


# =========================================================================
# Runner – persistent Ray actor that holds workers across all tasks
# =========================================================================

@ray.remote(num_cpus=1)
class PersistentRunner:
    """Ray actor that initialises workers once and executes multiple tasks."""

    def __init__(self):
        self._trainer: Optional[PersistentCILTrainer] = None
        self._tokenizer = None
        self._processor = None
        self._reward_fn = None
        self._val_reward_fn = None

    def init(self, config: PPOConfig) -> None:
        """Initialise workers, tokenizer, processor, reward fns (once)."""
        self._tokenizer = get_tokenizer(
            config.worker.actor.model.model_path,
            override_chat_template=config.data.override_chat_template,
            trust_remote_code=config.worker.actor.model.trust_remote_code,
            use_fast=True,
        )
        self._processor = get_processor(
            config.worker.actor.model.model_path,
            override_chat_template=config.data.override_chat_template,
            trust_remote_code=config.worker.actor.model.trust_remote_code,
            use_fast=True,
        )

        role_worker_mapping = {
            Role.ActorRolloutRef: ray.remote(PersistentRefFSDPWorker),
            Role.Critic: ray.remote(FSDPWorker),
        }
        global_pool_id = "global_pool"
        resource_pool_spec = {
            global_pool_id: [config.trainer.n_gpus_per_node] * config.trainer.nnodes
        }
        mapping = {
            Role.ActorRolloutRef: global_pool_id,
            Role.Critic: global_pool_id,
        }
        resource_pool_manager = ResourcePoolManager(
            resource_pool_spec=resource_pool_spec, mapping=mapping
        )

        remote_reward_manager = ray.remote(AutoRewardManager).options(
            num_cpus=config.worker.reward.num_cpus
        )
        self._reward_fn = remote_reward_manager.remote(config.worker.reward, self._tokenizer)
        self._val_reward_fn = remote_reward_manager.remote(config.worker.reward, self._tokenizer)

        # Build dummy dataloaders for trainer construction (will be replaced per task)
        dummy_train = base._build_dataloader(
            config.data, self._tokenizer, self._processor,
            allowed_classes=None, is_train=True,
        )
        dummy_val = base._build_dataloader(
            config.data, self._tokenizer, self._processor,
            allowed_classes=None, is_train=False,
        )

        ema_adv_config = EMAAdvConfig.from_env()
        retention_cfg = RetentionRewardConfig.from_env()

        self._trainer = PersistentCILTrainer(
            config=config,
            tokenizer=self._tokenizer,
            processor=self._processor,
            train_dataloader=dummy_train,
            val_dataloader=dummy_val,
            role_worker_mapping=role_worker_mapping,
            resource_pool_manager=resource_pool_manager,
            ray_worker_group_cls=RayWorkerGroup,
            reward_fn=self._reward_fn,
            val_reward_fn=self._val_reward_fn,
            ema_adv_config=ema_adv_config,
            ema_adv_state=None,
            retention_cfg=retention_cfg,
            task_id=1,
        )
        self._trainer.init_workers()
        print("[CIL] Workers initialised (persistent).")

    def restore_boundary_driver_rng(self, driver_rng_path: str) -> None:
        """Restore driver RNG before constructing the fresh Task-2 loader."""
        payload = _read_json(driver_rng_path)
        _restore_driver_rng_state(payload)
        print(f"[CIL] Restored boundary driver RNG from {driver_rng_path}")

    def run_task(
        self,
        config: PPOConfig,
        task_id: int,
        val_progress: bool,
        val_write_predictions: bool,
        val_output_dir: Optional[str],
        allowed_classes: Optional[Iterable[str]] = None,
        allowed_class_order: Optional[list[str]] = None,
        extra_val_splits: Optional[list[dict[str, Any]]] = None,
        prompt_label_list: Optional[list[str]] = None,
        copy_actor_to_anchor: bool = False,
        enable_anchor: bool = False,
        fresh_boundary_resume: bool = False,
        boundary: Optional[dict[str, Any]] = None,
        boundary_context: Optional[dict[str, Any]] = None,
        publish_task_boundary: bool = False,
    ) -> dict[str, Any]:
        """Run a single CIL task using the persistent workers."""
        trainer = self._trainer
        tokenizer = self._tokenizer
        processor = self._processor
        trainer._task_id = task_id

        # ── Optimizer state carries over between tasks ──────────────────
        # In the original code, FSDPCheckpointManager.load_checkpoint()
        # restores the previous task's full optimizer state (AdamW momentum,
        # variance, step counter) from the checkpoint.  Persistent workers
        # already keep this state in memory, so we do NOT reset it.

        if fresh_boundary_resume:
            if boundary is None:
                raise CILBoundaryError("fresh boundary resume needs validated boundary metadata")
            if not copy_actor_to_anchor or not enable_anchor:
                raise CILBoundaryError("fresh boundary resume requires the Task-2 previous-task anchor")
            # The runner is a new process. Restore driver/vLLM streams and
            # native actor state before any Task-2 rollout or anchor copy.
            _restore_driver_rng_state(_read_json(boundary["_driver_path"]))

        # ── Build task-specific dataloaders ─────────────────────────────
        train_dataloader = base._build_dataloader(
            config.data, tokenizer, processor, allowed_classes,
            is_train=True, label_list_override=prompt_label_list,
            allowed_class_order=allowed_class_order,
        )
        val_dataloader = base._build_dataloader(
            config.data, tokenizer, processor, allowed_classes,
            is_train=False, label_list_override=prompt_label_list,
            allowed_class_order=allowed_class_order,
        )

        # ── Compute per-task steps ──────────────────────────────────────
        per_task_steps = config.trainer.max_steps
        if config.trainer.total_epochs is not None:
            try:
                per_task_steps = config.trainer.total_epochs * len(train_dataloader)
            except Exception:
                pass

        last_global_step = 0
        if config.trainer.load_checkpoint_path:
            try:
                last_global_step = int(
                    os.path.basename(config.trainer.load_checkpoint_path).split("global_step_")[-1]
                )
            except Exception:
                pass

        # ── EMA state ───────────────────────────────────────────────────
        ema_state_path = _ema_stats_file_from_task_dir(config.trainer.save_checkpoint_path)
        ema_initial_state = (
            _read_json(boundary["_ema_path"])
            if fresh_boundary_resume and boundary is not None
            else _load_ema_state(ema_state_path)
        )

        # ── Reinitialise trainer for this task ──────────────────────────
        if fresh_boundary_resume:
            checkpoint_path = boundary["_checkpoint_path"]
            trainer.reinit_for_task(
                train_dataloader=train_dataloader,
                val_dataloader=val_dataloader,
                task_id=task_id,
                per_task_steps=per_task_steps,
                last_global_step=last_global_step,
                save_checkpoint_path=config.trainer.save_checkpoint_path,
                load_checkpoint_path=checkpoint_path,
                ema_adv_state=ema_initial_state,
                enable_anchor=enable_anchor,
                fresh_boundary_resume=True,
            )
            trainer.restore_boundary_checkpoint(checkpoint_path, int(boundary["global_step"]))
            vllm_payloads = []
            for item in boundary["rng"]["vllm"]:
                payload = _read_json(_safe_join(boundary["_boundary_root"], item["relative_path"]))
                vllm_payloads.append(payload)
            payload_by_rank = {int(item["rank"]): item for item in vllm_payloads}
            trainer.actor_rollout_ref_wg.restore_boundary_vllm_rng(
                [payload_by_rank[rank] for rank in sorted(payload_by_rank)]
            )
        else:
            trainer.reinit_for_task(
                train_dataloader=train_dataloader,
                val_dataloader=val_dataloader,
                task_id=task_id,
                per_task_steps=per_task_steps,
                last_global_step=last_global_step,
                save_checkpoint_path=config.trainer.save_checkpoint_path,
                load_checkpoint_path=config.trainer.load_checkpoint_path if task_id == 1 else None,
                ema_adv_state=ema_initial_state,
                enable_anchor=enable_anchor,
            )

        if copy_actor_to_anchor:
            if fresh_boundary_resume and not trainer._boundary_restored:
                raise CILBoundaryError("anchor copy was requested before native boundary restore")
            print(f"[CIL] task {task_id}: copying actor → anchor")
            trainer.actor_rollout_ref_wg.copy_actor_to_anchor()
        if fresh_boundary_resume:
            _atomic_write_json(
                os.path.join(config.trainer.save_checkpoint_path, "boundary_restore_event.json"),
                {
                    "completed_task": 1,
                    "next_task": 2,
                    "checkpoint_path": boundary["_checkpoint_path"],
                    "global_step": int(boundary["global_step"]),
                    "current_classes": list(boundary["loader_policy"]["current_classes"]),
                    "seen_classes": list(boundary["loader_policy"]["seen_classes"]),
                    "loader_cursor": 0,
                    "task1_dataloader_loaded": False,
                    "native_restore_before_anchor_copy": True,
                    "anchor_provenance": "reconstructed_from_task1_actor",
                    "state_fingerprint": boundary["state_fingerprint"],
                },
            )
        trainer.val_progress = val_progress
        trainer.val_write_predictions = val_write_predictions
        trainer.val_output_dir = val_output_dir

        if hasattr(trainer, "output_dir") and trainer.output_dir:
            base._snapshot_training_config(trainer.output_dir, config)

        # ── Train ───────────────────────────────────────────────────────
        trainer.fit()

        # ── Save EMA state ──────────────────────────────────────────────
        if trainer.ema_adv is not None:
            ema_payload = trainer.ema_adv.state_dict()
            _save_ema_state(ema_state_path, ema_payload, task_id=task_id)
            print(f"[EMA-ADV] Saved EMA online state to: {ema_state_path}")

        # ── Post-training evaluation (extra_val_splits) ─────────────────
        extra_eval_results = {}
        if extra_val_splits:
            split_map = {split["name"]: split for split in extra_val_splits}
            overall_split = split_map.get("overall_seen")

            if overall_split is not None:
                overall_val_loader = base._build_dataloader(
                    config.data, tokenizer, processor,
                    allowed_classes=overall_split.get("allowed_classes", []),
                    is_train=False,
                    allowed_class_order=overall_split.get("class_order"),
                )
                trainer.val_dataloader = overall_val_loader
                trainer.val_progress = False
                trainer.val_write_predictions = False
                trainer.collect_sample_level = True
                overall_metrics = trainer._validate()
                trainer.collect_sample_level = False

                sample_acc = [float(x) for x in overall_metrics.pop("_sample_accuracy_scores", [])]
                sample_labels = [str(x) for x in overall_metrics.pop("_sample_labels_norm", [])]
                if len(sample_acc) != len(sample_labels):
                    raise RuntimeError("Sample-level validation trace length mismatch.")

                extra_eval_results["overall_seen"] = overall_metrics

                for split in extra_val_splits:
                    split_name = split["name"]
                    if split_name == "overall_seen":
                        continue
                    split_allowed = {
                        base._normalize_label_name(str(x))
                        for x in split.get("allowed_classes", [])
                    }
                    hit_acc = [
                        a for a, lbl in zip(sample_acc, sample_labels)
                        if lbl in split_allowed
                    ]
                    split_acc = float(np.mean(hit_acc)) if hit_acc else 0.0
                    extra_eval_results[split_name] = {
                        "val/cls_accuracy": split_acc,
                        "val/accuracy_reward": split_acc,
                    }

        boundary_marker_path = None
        if publish_task_boundary:
            if task_id != 1 or boundary_context is None:
                raise CILBoundaryError("only Task 1 may publish the frozen boundary in this scope")
            if config.trainer.save_model_only:
                raise CILBoundaryError("task boundary publication requires save_model_only=false")
            # fit() may have saved before extra validation; refresh the same
            # final global-step directory after every post-training validation.
            trainer._save_checkpoint()
            if trainer.ema_adv is None:
                raise CILBoundaryError("task boundary publication requires enabled EMA state")
            final_ema_payload = trainer.ema_adv.state_dict()
            _save_ema_state(ema_state_path, final_ema_payload, task_id=task_id)
            tracker_for_boundary = os.path.join(
                config.trainer.save_checkpoint_path, "checkpoint_tracker.json"
            )
            tracker_payload = _read_json(tracker_for_boundary)
            step = tracker_payload.get("last_global_step")
            checkpoint_for_boundary = os.path.join(
                config.trainer.save_checkpoint_path, f"global_step_{step}"
            )
            worker_rng = trainer.actor_rollout_ref_wg.capture_boundary_vllm_rng()
            boundary_marker_path = _publish_task_boundary(
                boundary_root=config.trainer.save_checkpoint_path,
                checkpoint_path=checkpoint_for_boundary,
                tracker_path=tracker_for_boundary,
                global_step=int(step),
                ema_payload=final_ema_payload,
                driver_rng_payload=_capture_driver_rng_state(),
                vllm_rng_payloads=worker_rng,
                context=boundary_context,
            )
            print(f"[CIL] Published Task-1 completion boundary: {boundary_marker_path}")

        # ── Checkpoint path ─────────────────────────────────────────────
        tracker_path = os.path.join(
            config.trainer.save_checkpoint_path, "checkpoint_tracker.json"
        )
        last_checkpoint = None
        if os.path.exists(tracker_path):
            with open(tracker_path, encoding="utf-8") as f:
                tracker_info = json.load(f)
            step = tracker_info.get("last_global_step")
            if step is not None:
                last_checkpoint = os.path.join(
                    config.trainer.save_checkpoint_path, f"global_step_{step}"
                )

        return {
            "extra_eval_results": extra_eval_results,
            "last_checkpoint_path": last_checkpoint,
            "boundary_marker_path": boundary_marker_path,
        }

    def init_anchor_on_workers(self) -> None:
        """Trigger anchor model init on all FSDP workers."""
        self._trainer.actor_rollout_ref_wg.init_anchor()


# =========================================================================
# Resolve ref/anchor weight-copy actions per task
# =========================================================================

def _resolve_weight_actions(
    ref_cfg: AnchorRefConfig,
    task_id: int,
) -> dict[str, bool]:
    """Anchor/ref actions for this task.

    Before ``activate_from_task`` the retention anchor is unused. From that
    task onward the actor's previous-task weights are copied into the anchor.
    The KL reference always stays the original pretrained base.
    """
    if task_id < ref_cfg.activate_from_task:
        return {
            "copy_actor_to_anchor": False,
            "enable_anchor": False,
        }
    return {
        "copy_actor_to_anchor": True,
        "enable_anchor": True,
    }


# =========================================================================
# Main CIL loop (persistent workers, no ray restart)
# =========================================================================

def _run_cil(
    ppo_config: PPOConfig,
    known_args: argparse.Namespace,
    ref_cfg: AnchorRefConfig,
    cil_config: Optional[dict] = None,
) -> None:
    """Class-incremental learning with persistent workers."""
    import shutil

    resume_boundary: Optional[dict[str, Any]] = None
    if known_args.resume_task_boundary:
        if known_args.publish_task_boundary:
            raise CILBoundaryError("a fresh resume run cannot also publish a Task-1 boundary")
        resume_boundary = _load_task_boundary(known_args.resume_task_boundary)
    if known_args.stop_after_task_boundary and not known_args.publish_task_boundary:
        raise CILBoundaryError("--stop_after_task_boundary requires --publish_task_boundary")
    if known_args.publish_task_boundary and known_args.save_task_ckpt == "none":
        raise CILBoundaryError("save_task_ckpt=none cannot publish a resumable boundary")

    current_time = time.strftime("%Y-%m-%d-%H%M%S")
    save_dir = known_args.save_dir
    if save_dir is None:
        raise ValueError("Error: --save_dir is required for class-incremental learning.")
    save_dir = f"{save_dir}/{current_time}"
    if resume_boundary and _path_within(save_dir, resume_boundary["_boundary_root"]):
        raise CILBoundaryError(
            "fresh resume output root must be separate from the read-only Task-1 boundary root"
        )

    os.makedirs(save_dir, exist_ok=True)
    cil_info_dir = os.path.join(save_dir, "cil_info")
    metrics_dir = os.path.join(cil_info_dir, "metrics")
    os.makedirs(metrics_dir, exist_ok=True)
    base._snapshot_launch_script(cil_info_dir, explicit_script_path=known_args.launch_script)
    base._snapshot_repro_files(cil_info_dir, ppo_config)

    if cil_config is not None:
        with open(os.path.join(cil_info_dir, "cil_cfg.json"), "w", encoding="utf-8") as f:
            json.dump(cil_config, f, indent=2, ensure_ascii=False)
        print(f"[CIL] Saved CIL config to {os.path.join(cil_info_dir, 'cil_cfg.json')}")

    # ── Class order & task splits ───────────────────────────────────────
    class_names = base._list_class_names_from_dir(ppo_config.data.train_files)
    total_classes = len(class_names)
    if resume_boundary is not None:
        boundary_plan = resume_boundary["plan"]["payload"]
        total_tasks = int(boundary_plan["total_tasks"])
        base_classes = int(boundary_plan["base_classes"])
        incremental_classes = int(boundary_plan["incremental_classes"])
        class_order = [int(x) for x in boundary_plan["class_order_ids"]]
        class_splits = [[int(x) for x in split] for split in boundary_plan["class_splits"]]
        _validate_boundary_context(
            resume_boundary,
            config=ppo_config,
            cil_config=cil_config,
            class_names=class_names,
            known_args=known_args,
        )
        ppo_config.trainer.load_checkpoint_path = resume_boundary["_checkpoint_path"]
        ppo_config.trainer.find_last_checkpoint = False
    else:
        total_tasks, base_classes, incremental_classes = base._resolve_task_plan(
            total_classes, known_args.base_classes, known_args.incremental_classes
        )
        class_order = base._build_class_order(total_classes, known_args.class_order, known_args.class_order_seed)
        class_splits = base._chunk_classes(class_order, base_classes, incremental_classes, total_tasks)
    class_order_names = [class_names[i] for i in class_order]

    boundary_context = None
    if known_args.publish_task_boundary:
        boundary_context = _build_boundary_context(
            ppo_config,
            cil_config,
            class_names,
            class_order,
            class_splits,
            known_args,
        )

    with open(os.path.join(cil_info_dir, "class_order.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "class_order_seed": known_args.class_order_seed,
                "final_class_order_ids": class_order,
                "final_class_order_names": class_order_names,
            },
            f, indent=2,
        )

    all_labels_path = os.path.join(cil_info_dir, "all_labels.json")
    with open(all_labels_path, "w", encoding="utf-8") as f:
        json.dump(class_order_names, f, ensure_ascii=True)

    # Precompute per-task sample counts
    task_samples_info: list[dict[str, Any]] = []
    for idx in range(len(class_splits)):
        ids = class_splits[idx]
        ordered_class_names = [class_names[i] for i in ids]
        allowed_norm = {base._normalize_label_name(name) for name in ordered_class_names}
        train_samples = base._count_class_samples(ppo_config.data.train_files, allowed_norm)
        val_samples = base._count_class_samples(ppo_config.data.val_files, allowed_norm)
        task_samples_info.append({
            "task": idx + 1,
            "classes": ordered_class_names,
            "train_samples": train_samples,
            "val_samples": val_samples,
        })

    with open(os.path.join(cil_info_dir, "task_samples.json"), "w", encoding="utf-8") as f:
        json.dump(task_samples_info, f, indent=2)

    # ── CIL metrics tracking ───────────────────────────────────────────
    overall_last_acc_history: list[float] = []
    summary: dict[str, Any] = {
        "class_order_seed": known_args.class_order_seed,
        "final_class_order_ids": class_order,
        "final_class_order_names": class_order_names,
        "total_tasks": total_tasks,
        "base_classes": base_classes,
        "incremental_classes": incremental_classes,
        "tasks": {},
    }

    last_checkpoint: Optional[str] = ppo_config.trainer.load_checkpoint_path
    previous_task_dir: Optional[str] = None
    start_task_idx = 1 if resume_boundary is not None else 0
    seen_class_ids: list[int] = list(class_splits[0]) if resume_boundary is not None else []
    task_acc_matrix: list[list[float]] = []
    protected_boundary_roots: list[str] = []
    if resume_boundary is not None:
        protected_boundary_roots.append(resume_boundary["_boundary_root"])
    published_boundary_root: Optional[str] = None
    stopped_after_boundary = False

    # ── Wandb ──────────────────────────────────────────────────────────
    wandb_available = False
    if os.environ.get("WANDB_DISABLED", "false").lower() not in {"true", "1", "yes"}:
        try:
            import wandb
            shared_run_id = wandb.util.generate_id()
            shared_run_name = f"{ppo_config.trainer.experiment_name}-cil-{time.strftime('%Y%m%d-%H%M%S')}"
            os.environ["WANDB_RUN_ID"] = shared_run_id
            os.environ.setdefault("WANDB_RESUME", "allow")
            os.environ.setdefault("WANDB_RUN_NAME", shared_run_name)
            os.environ.setdefault("WANDB_INIT_TIMEOUT", "120")
            wandb_available = True
        except Exception as exc:
            print(f"Warning: failed to prepare wandb env: {exc}")

    # ── Ensure Ray is running ──────────────────────────────────────────
    base._ensure_ray()

    # ── Create persistent runner and initialise workers ONCE ───────────
    runner = PersistentRunner.remote()
    ray.get(runner.init.remote(ppo_config))

    # Initialise the frozen anchor model on all workers. A failure here is fatal:
    # the retention reward requires anchor log-probs from task 2 onward.
    ray.get(runner.init_anchor_on_workers.remote())
    if resume_boundary is not None:
        # This happens after worker construction but before the first fresh
        # Task-2 dataloader is built. Native/vLLM streams are restored after
        # the native actor checkpoint load inside run_task().
        ray.get(runner.restore_boundary_driver_rng.remote(resume_boundary["_driver_path"]))

    if resume_boundary is None:
        print(f"[CIL] Starting {total_tasks} CIL tasks with persistent workers.")
    else:
        print(
            f"[CIL] Resuming from Task-1 boundary at global_step={resume_boundary['global_step']}; "
            "starting a new Task-2 loader at cursor=0."
        )

    # ── Task loop ──────────────────────────────────────────────────────
    for task_idx, task_class_ids in enumerate(class_splits[start_task_idx:], start=start_task_idx):
        task_id = task_idx + 1
        seen_class_ids.extend(task_class_ids)
        ordered_task_class_names = [class_names[i] for i in task_class_ids]
        prompt_label_list = None
        if known_args.prompt_seen_labels:
            prompt_label_list = [class_names[i] for i in seen_class_ids]
        task_allowed_class_order = prompt_label_list or ordered_task_class_names
        fresh_boundary_resume = bool(resume_boundary is not None and task_id == 2)
        if fresh_boundary_resume:
            task_allowed_class_order = list(resume_boundary["loader_policy"]["prompt_classes"])
            prompt_label_list = (
                list(resume_boundary["loader_policy"]["seen_classes"])
                if resume_boundary["plan"]["payload"]["prompt_seen_labels"]
                else None
            )

        task_config = copy.deepcopy(ppo_config)
        task_save_dir = os.path.join(save_dir, f"task_{task_id}")
        os.makedirs(task_save_dir, exist_ok=True)
        task_config.trainer.save_checkpoint_path = task_save_dir
        task_config.trainer.find_last_checkpoint = False
        task_config.trainer.skip_dataloader_state = task_idx > 0
        task_config.trainer.load_checkpoint_path = (
            last_checkpoint if task_idx > 0
            else ppo_config.trainer.load_checkpoint_path
        )

        # Build evaluation plan (identical to original)
        seen_class_names = [class_names[i] for i in seen_class_ids]
        eval_plan = []
        for eval_idx, eval_class_ids in enumerate(class_splits[: task_idx + 1]):
            ordered_eval_classes = [class_names[i] for i in eval_class_ids]
            eval_plan.append({
                "name": f"task{eval_idx + 1}",
                "allowed_classes": ordered_eval_classes,
                "class_order": seen_class_names,
            })
        eval_plan.append({
            "name": "overall_seen",
            "allowed_classes": seen_class_names,
            "class_order": seen_class_names,
        })

        # Determine weight copy actions
        weight_actions = _resolve_weight_actions(ref_cfg, task_id)

        # Run the task
        result = ray.get(
            runner.run_task.remote(
                config=task_config,
                task_id=task_id,
                val_progress=not known_args.no_val_progress,
                val_write_predictions=known_args.val_write_predictions,
                val_output_dir=known_args.val_output_dir,
                allowed_classes=ordered_task_class_names,
                allowed_class_order=task_allowed_class_order,
                extra_val_splits=eval_plan,
                prompt_label_list=prompt_label_list,
                copy_actor_to_anchor=weight_actions["copy_actor_to_anchor"],
                enable_anchor=weight_actions["enable_anchor"],
                fresh_boundary_resume=fresh_boundary_resume,
                boundary=resume_boundary if fresh_boundary_resume else None,
                boundary_context=boundary_context,
                publish_task_boundary=(known_args.publish_task_boundary and task_id == 1),
            )
        )

        extra_eval_results = result.get("extra_eval_results", {}) if isinstance(result, dict) else {}
        last_checkpoint = result.get("last_checkpoint_path") if isinstance(result, dict) else None
        boundary_marker_path = result.get("boundary_marker_path") if isinstance(result, dict) else None
        if boundary_marker_path:
            published_boundary_root = os.path.dirname(os.path.abspath(boundary_marker_path))
            protected_boundary_roots.append(published_boundary_root)
            if known_args.stop_after_task_boundary and task_id != 1:
                raise CILBoundaryError("stop-after-boundary mode may only publish Task 1")
        elif known_args.stop_after_task_boundary and task_id == 1:
            raise CILBoundaryError("stop-after-boundary mode returned without a published boundary marker")

        # ── CIL metrics (identical to original) ────────────────────────
        single_acc = extra_eval_results.get(f"task{task_id}", {}).get(
            "val/cls_accuracy",
            extra_eval_results.get(f"task{task_id}", {}).get("val/accuracy_reward", 0.0),
        )
        overall_last_acc = extra_eval_results.get("overall_seen", {}).get(
            "val/cls_accuracy",
            extra_eval_results.get("overall_seen", {}).get("val/accuracy_reward", 0.0),
        )
        overall_last_acc_history.append(overall_last_acc)
        cumulative_avg = sum(overall_last_acc_history) / len(overall_last_acc_history)

        per_task_acc_raw = {
            f"task{j}": extra_eval_results.get(f"task{j}", {}).get(
                "val/cls_accuracy",
                extra_eval_results.get(f"task{j}", {}).get("val/accuracy_reward", 0.0),
            )
            for j in range(1, task_id + 1)
        }
        per_task_acc_pct = {k: round(v * 100, 4) for k, v in per_task_acc_raw.items()}

        current_row = [per_task_acc_raw[f"task{j}"] for j in range(1, task_id + 1)]
        task_acc_matrix.append(current_row)

        fr: Optional[float] = None
        if task_id >= 2:
            np_acctable = np.zeros([task_id, task_id], dtype=np.float32)
            for idxx, line in enumerate(task_acc_matrix):
                idxy = len(line)
                np_acctable[idxx, :idxy] = np.array(line, dtype=np.float32)
            np_acctable = np_acctable.T
            fr = float(np.mean((np.max(np_acctable, axis=1) - np_acctable[:, task_id - 1])[: task_id - 1]))

        def _pct(v: Optional[float]) -> Optional[float]:
            return round(v * 100, 4) if v is not None else None

        summary["tasks"][f"task{task_id}"] = {
            "last_acc": _pct(overall_last_acc),
            "average_acc": _pct(cumulative_avg),
            "last_acc_details": per_task_acc_pct,
            "forgetting_rate": _pct(fr),
        }

        current_samples = task_samples_info[task_idx]
        train_samples = current_samples["train_samples"]
        val_samples = current_samples["val_samples"]

        with open(os.path.join(metrics_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        task_log_path = os.path.join(metrics_dir, "task_metrics.log")
        with open(task_log_path, "a", encoding="utf-8") as f:
            f.write(
                json.dumps({
                    "task": task_id,
                    "last_acc": _pct(overall_last_acc),
                    "average_acc": _pct(cumulative_avg),
                    "last_acc_details": per_task_acc_pct,
                    "forgetting_rate": _pct(fr),
                })
                + "\n"
            )

        decomp_parts = [f"T{j}:{per_task_acc_pct[f'task{j}']:.2f}%" for j in range(1, task_id + 1)]
        extra_metrics_str = ""
        if fr is not None:
            extra_metrics_str += f" | FR: {_pct(fr):.2f}%"
        log_msg = (
            f"[Task {task_id} Finished] "
            + f"Last acc: {_pct(overall_last_acc):.2f}% | Average acc: {_pct(cumulative_avg):.2f}%"
            + f" | Decomp: {' '.join(decomp_parts)}"
            + extra_metrics_str
        )
        print(log_msg)

        # ── Checkpoint pruning (identical to original) ──────────────────
        if known_args.save_task_ckpt in ("latest", "none") and last_checkpoint:
            try:
                ckpt_dirname = os.path.basename(last_checkpoint.rstrip(os.sep))
                for entry in os.listdir(task_save_dir):
                    full_path = os.path.join(task_save_dir, entry)
                    if not os.path.isdir(full_path):
                        continue
                    if entry.startswith("global_step_") and entry != ckpt_dirname:
                        if _path_overlaps_roots(full_path, protected_boundary_roots):
                            raise CILBoundaryError("refusing to prune a protected boundary path")
                        shutil.rmtree(full_path)
            except CILBoundaryError:
                raise
            except Exception as exc:
                print(f"Warning: failed to prune old checkpoints in {task_save_dir}: {exc}")

        if known_args.save_task_ckpt in ("latest", "none") and previous_task_dir and previous_task_dir != task_save_dir:
            try:
                for entry in os.listdir(previous_task_dir):
                    full_path = os.path.join(previous_task_dir, entry)
                    if os.path.isdir(full_path) and entry.startswith("global_step_"):
                        if _path_overlaps_roots(full_path, protected_boundary_roots):
                            raise CILBoundaryError("refusing to prune a protected boundary path")
                        shutil.rmtree(full_path)
            except CILBoundaryError:
                raise
            except Exception as exc:
                print(f"Warning: failed to prune checkpoints in previous task dir {previous_task_dir}: {exc}")

        previous_task_dir = task_save_dir

        if wandb_available:
            try:
                import wandb
                if wandb.run is not None:
                    wandb_payload: dict[str, Any] = {
                        "cil/task": task_id,
                        "cil/single_acc": _pct(single_acc),
                        "cil/overall_last_acc": _pct(overall_last_acc),
                        "cil/cumulative_average_acc": _pct(cumulative_avg),
                        "cil/train_samples": train_samples,
                        "cil/val_samples": val_samples,
                    }
                    if fr is not None:
                        wandb_payload["cil/forgetting_rate"] = _pct(fr)
                    wandb.log(wandb_payload)
            except Exception as exc:
                print(f"Warning: wandb log failed at task {task_id}: {exc}")

        if known_args.stop_after_task_boundary and task_id == 1:
            stopped_after_boundary = True
            print(
                "[CIL] Task-1 completion boundary published and validated; "
                "stopping normally before Task 2."
            )
            break

    if known_args.save_task_ckpt == "none" and previous_task_dir:
        try:
            for entry in os.listdir(previous_task_dir):
                full_path = os.path.join(previous_task_dir, entry)
                if os.path.isdir(full_path) and entry.startswith("global_step_"):
                    if _path_overlaps_roots(full_path, protected_boundary_roots):
                        raise CILBoundaryError("refusing to prune a protected boundary path")
                    shutil.rmtree(full_path)
        except CILBoundaryError:
            raise
        except Exception as exc:
            print(f"Warning: failed to prune final task checkpoints in {previous_task_dir}: {exc}")

    # ── Clean up ───────────────────────────────────────────────────────
    ray.kill(runner)
    if stopped_after_boundary:
        print("[CIL] Exited normally after publishing the Task-1 boundary; Task 2 was not run.")
    else:
        print(f"[CIL] All {total_tasks} tasks completed.")


# =========================================================================
# Argument parsing (--cil_cfg provides defaults; CLI args override)
# =========================================================================

def _parse_args() -> "tuple[argparse.Namespace, list[str]]":
    # ── Phase 1: extract --cil_cfg path (before full parse) ───────────────
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--cil_cfg", type=str, default=None)
    pre_args, _ = pre_parser.parse_known_args()

    cfg_defaults: dict[str, Any] = {}
    if pre_args.cil_cfg is not None:
        cfg_defaults = _load_cil_cfg(pre_args.cil_cfg)
        print(f"[CIL-CFG] Loaded defaults from {pre_args.cil_cfg}")

    # ── Phase 2: full parser (cfg values become defaults, CLI overrides) ──
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--cil_cfg", type=str, default=None,
        help="Path to cil_cfg.json. Values serve as defaults; CLI args override.",
    )

    # ── standard CIL args ─────────────────────────────────────────────
    parser.add_argument("--val_write_predictions", action="store_true")
    parser.add_argument("--val_output_dir", default=None)
    parser.add_argument("--no_val_progress", action="store_true")
    parser.add_argument("--class_order_seed", type=int, default=None)
    parser.add_argument("--class_order", type=str, default=None)
    parser.add_argument("--save_task_ckpt", type=str, default="latest", choices=["none", "latest", "all"])
    parser.add_argument("--save_dir", type=str, default=None)
    parser.add_argument("--base_classes", type=int, default=None)
    parser.add_argument("--incremental_classes", type=int, default=None)
    parser.add_argument("--launch_script", type=str, default=None)
    parser.add_argument("--prompt_seen_labels", action="store_true")
    parser.add_argument(
        "--resume_task_boundary",
        type=str,
        default=None,
        help="Explicit task1-complete.json for a fresh-process Task-2 resume.",
    )
    parser.add_argument(
        "--publish_task_boundary",
        action="store_true",
        default=False,
        help="Publish a full Task-1 completion boundary after all post-training validation.",
    )
    parser.add_argument(
        "--stop_after_task_boundary",
        action="store_true",
        default=False,
        help=(
            "After successful Task-1 boundary publication, cleanly exit before Task 2; "
            "requires --publish_task_boundary."
        ),
    )

    # ── CTAN args ──────────────────────────────────────────────────────
    parser.add_argument("--ctan_enable", dest="ema_adv_enable", action="store_true")
    parser.add_argument("--ctan_beta", dest="ema_adv_beta", type=float, default=0.999)
    parser.add_argument("--ctan_eps", dest="ema_adv_eps", type=float, default=1e-6)
    parser.add_argument("--ctan_bootstrap_steps", dest="ema_adv_bootstrap_steps", type=int, default=0)
    parser.add_argument("--ctan_activate_from_task", dest="ema_adv_activate_from_task", type=int, default=1)
    parser.add_argument("--ctan_min_std", dest="ema_adv_min_std", type=float, default=0.0)
    parser.add_argument("--ctan_guard_abs_max", dest="ema_adv_guard_abs_max", type=float, default=0.0)
    parser.add_argument("--ctan_bias_correction", dest="ema_adv_bias_correction", action="store_true", default=False)
    parser.add_argument("--no_ctan_bias_correction", dest="ema_adv_bias_correction", action="store_false")
    parser.add_argument("--ctan_beta_warmup_steps", dest="ema_adv_beta_warmup_steps", type=int, default=0)
    parser.add_argument("--ctan_beta_warmup_init", dest="ema_adv_beta_warmup_init", type=float, default=0.9)

    # ── Retention reward args ───────────────────────────────────────────
    parser.add_argument("--retention_reward_enable", action="store_true", default=False)
    parser.add_argument("--retention_lambda", type=float, default=0.5)
    parser.add_argument("--retention_alpha", type=float, default=20.0)
    parser.add_argument("--retention_activate_from_task", type=int, default=2)

    # ── ref / anchor activation ────────────────────────────────────────
    # ref = frozen original pretrained; anchor = frozen previous-task checkpoint.
    parser.add_argument("--rapo_activate_from_task", type=int, default=2)

    # ── Apply cil_cfg defaults (CLI args still take precedence) ───────────
    if cfg_defaults:
        parser.set_defaults(**cfg_defaults)

    return parser.parse_known_args()


def _set_env(known_args: argparse.Namespace) -> None:
    """Mirror env vars from CLI for per-worker config reading."""
    os.environ["EMA_ADV_ENABLED"] = "1" if known_args.ema_adv_enable else "0"
    os.environ["EMA_ADV_BETA"] = str(known_args.ema_adv_beta)
    os.environ["EMA_ADV_EPS"] = str(known_args.ema_adv_eps)
    os.environ["EMA_ADV_BOOTSTRAP_STEPS"] = str(known_args.ema_adv_bootstrap_steps)
    os.environ["EMA_ADV_ACTIVATE_FROM_TASK"] = str(known_args.ema_adv_activate_from_task)
    os.environ["EMA_ADV_MIN_STD"] = str(known_args.ema_adv_min_std)
    os.environ["EMA_ADV_GUARD_ABS_MAX"] = str(known_args.ema_adv_guard_abs_max)
    os.environ["EMA_ADV_BIAS_CORRECTION"] = "1" if known_args.ema_adv_bias_correction else "0"
    os.environ["EMA_ADV_BETA_WARMUP_STEPS"] = str(known_args.ema_adv_beta_warmup_steps)
    os.environ["EMA_ADV_BETA_WARMUP_INIT"] = str(known_args.ema_adv_beta_warmup_init)
    os.environ["RETENTION_REWARD_ENABLED"] = "1" if known_args.retention_reward_enable else "0"
    os.environ["RETENTION_REWARD_LAMBDA"] = str(known_args.retention_lambda)
    os.environ["RETENTION_ALPHA"] = str(known_args.retention_alpha)
    os.environ["RETENTION_REWARD_ACTIVATE_FROM_TASK"] = str(known_args.retention_activate_from_task)


# =========================================================================
# Entry point
# =========================================================================

def main() -> None:
    known_args, remaining = _parse_args()
    _set_env(known_args)

    cli_args = OmegaConf.from_cli(remaining)
    default_config = OmegaConf.structured(PPOConfig())

    if hasattr(cli_args, "config"):
        config_path = cli_args.pop("config", None)
        file_config = OmegaConf.load(config_path)
        default_config = OmegaConf.merge(default_config, file_config)

    ppo_config = OmegaConf.merge(default_config, cli_args)
    ppo_config = OmegaConf.to_object(ppo_config)
    ppo_config.deep_post_init()

    ref_cfg = AnchorRefConfig(
        activate_from_task=known_args.rapo_activate_from_task,
    )

    original_model_path = ppo_config.worker.actor.model.model_path

    print(
        "[CIL] Configuration:\n"
        f"  reference=original pretrained base (frozen KL anchor)\n"
        f"  anchor=previous-task policy (frozen retention target)\n"
        f"  activate_from_task={ref_cfg.activate_from_task}\n"
        f"  original_model_path={original_model_path}"
    )

    # Collect all CIL hyperparameters for reproducibility
    cil_config = _build_cil_cfg(known_args)

    _run_cil(ppo_config, known_args, ref_cfg, cil_config=cil_config)


if __name__ == "__main__":
    torch.cuda.empty_cache()
    main()
