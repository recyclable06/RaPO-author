"""Execute selected, unmodified source AST nodes without GPU-stack imports."""
import argparse
import ast
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

import torch

ROOT = Path(__file__).resolve().parents[2]
SHARED = "examples/baselines/_rapo_components.py"
IMAGE = "examples/baselines/img_cls_cil/image_cls_cil_rapo.py"
DET = "examples/baselines/cil_det/image_det_cil_rapo.py"
SOURCE_HASHES = {}


def select(path, names, namespace, parent=None):
    source = (ROOT / path).read_bytes()
    SOURCE_HASHES[path] = hashlib.sha256(source).hexdigest()
    tree = ast.parse(source, filename=str(ROOT / path))
    nodes = tree.body
    if parent:
        nodes = next(n for n in nodes if isinstance(n, ast.ClassDef) and n.name == parent).body
    selected = []
    for node in nodes:
        name = getattr(node, "name", None)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        if name in names:
            selected.append(node)
    assert len(selected) == len(names), (path, names)
    # No AST rewriting, decorator removal, or algorithm substitution.
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(ROOT / path), "exec"), namespace)
    return namespace


def load():
    ns = dict(globals(), DataProto=SimpleNamespace)
    select("verl/trainer/core_algos.py", {
        "AdvantageEstimator", "ADV_ESTIMATOR_MAP", "register_adv_estimator",
        "compute_advantage_return", "compute_grpo_outcome_advantage",
    }, ns)
    select("verl/trainer/ray_trainer.py", {"compute_advantage"}, ns)
    select(SHARED, {
        "_CIL_CFG_GROUP_MAP", "_CIL_CFG_HARDCODED_CTAN_KEYS", "_load_cil_cfg",
        "EMAAdvConfig", "EMAAdvNormalizer", "_first_defined_env", "RetentionRewardConfig",
        "_apply_retention_reward", "_ema_stats_file_from_task_dir", "_load_ema_state", "_save_ema_state",
    }, ns)
    select(SHARED, {"_compute_advantage_with_hooks"}, ns, "RayPPOContinualRaPOTrainer")
    return ns
