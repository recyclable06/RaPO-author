"""Execute unchanged, AST-selected author functions on CPU; no GPU/launcher imports.

This is an audit harness, not an end-to-end runtime test or a repair. Dataclasses,
numerical functions, and pure data helpers are compiled from the hashed source.
SimpleNamespace supplies only the input batch fields those functions consume.
"""
import ast
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, Optional

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
AUTHOR = ROOT / "RaPO_作者整理代码"
OUT = Path(__file__).resolve().parent
SOURCES = {}


def selected_module(relative, names):
    path = AUTHOR / relative
    source = path.read_bytes()
    SOURCES[relative] = hashlib.sha256(source).hexdigest()
    parsed = ast.parse(source, filename=relative)
    nodes = [n for n in parsed.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    module = ModuleType("audit_selected_" + str(len(SOURCES)))
    sys.modules[module.__name__] = module
    module.__dict__.update(dataclass=dataclass, Any=Any, Optional=Optional,
                           torch=torch, np=np, os=os, re=re, json=json, DataProto=SimpleNamespace)
    tree = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes], type_ignores=[])
    ast.fix_missing_locations(tree)
    exec(compile(tree, relative, "exec"), module.__dict__)
    return module


def batch(scores):
    values = torch.tensor(scores, dtype=torch.float32).reshape(-1, 1)
    return SimpleNamespace(batch={"token_level_rewards": values,
                                  "response_mask": torch.ones_like(values)},
                           non_tensor_batch={"uid": [i // 8 for i in range(len(scores))]})


def ctan_and_retention():
    m = selected_module("examples/baselines/_rapo_components.py", ["EMAAdvConfig", "EMAAdvNormalizer", "RetentionRewardConfig", "_apply_retention_reward"])
    cfg = m.EMAAdvConfig(enabled=True)
    task1 = m.EMAAdvNormalizer(cfg, task_id=1)
    task1.observe_batch_without_ema(batch([0, 2] * 32))
    task2 = m.EMAAdvNormalizer(cfg, task_id=2, initial_state=task1.state_dict())
    betas = [task2._effective_beta()]
    task2.compute_grpo_advantage(batch([0, 2] * 32))
    betas.append(task2._effective_beta())
    task2.compute_grpo_advantage(batch([1] * 64))
    saved = task2.state_dict()
    task3 = m.EMAAdvNormalizer(cfg, task_id=3, initial_state=json.loads(json.dumps(saved)))
    loaded = task3.ema_std
    task3_batch = batch([0, 2] * 32)
    paper_std = cfg.beta * saved["ema_std"] + (1 - cfg.beta) * float(task3_batch.batch["token_level_rewards"].std())
    task3.compute_grpo_advantage(task3_batch)
    actual_adv = float(task3_batch.batch["advantages"][1])
    expected_adv = 1.0 / (paper_std + cfg.eps)
    assert loaded != saved["ema_std"]
    assert loaded == saved["last_batch_reward_std"]
    assert not math.isclose(actual_adv, expected_adv, rel_tol=1e-5)
    # Independent formula check: unequal lengths, negative drift, ignored padding.
    old = torch.tensor([[-0.9, -1.0, 9.0], [-1.4, -1.2, -1.3], [-1.0, -1.0, 7.0]], requires_grad=True)
    anchor = torch.tensor([[-1.0, -1.0, -9.0], [-1.0, -1.0, -1.0], [-1.0, -1.0, -7.0]], requires_grad=True)
    mask = torch.tensor([[1., 1., 0.], [1., 1., 1.], [1., 1., 0.]])
    data = SimpleNamespace(batch={"old_log_probs": old, "anchor_log_probs": anchor,
                                  "response_mask": mask, "token_level_rewards": torch.zeros_like(mask)})
    result, metrics = m._apply_retention_reward(data, m.RetentionRewardConfig(enabled=True))
    actual_reward = result.batch["token_level_rewards"].sum(-1)
    expected_reward = torch.tensor([0.5 * math.exp(-1), 0.5, 0.5])
    assert torch.allclose(actual_reward, expected_reward, atol=1e-6)
    assert not result.batch["token_level_rewards"].requires_grad
    return {"ctan": {"task2_betas": betas, "task2_saved_ema_std": saved["ema_std"],
                     "task2_last_batch_std": saved["last_batch_reward_std"], "task3_loaded_ema_std": loaded,
                     "task3_actual_ema_std": task3.ema_std, "task3_paper_ema_std": paper_std,
                     "task3_positive_adv_actual": actual_adv, "task3_positive_adv_paper": expected_adv,
                     "verdict": "paper divergence reproduced on normal 8-by-8 rollout-shaped rewards"},
            "retention": {"actual_totals": actual_reward.tolist(), "expected_totals": expected_reward.tolist(),
                          "detached": True, "verdict": "Eq. 2-4 arithmetic matches"}}


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def data_assets():
    stats = {}
    for path in sorted((AUTHOR / "data/image_cls_cil/fewshot_lists").glob("*.jsonl")):
        rows = read_jsonl(path)
        counts = Counter(r["class_name"] for r in rows)
        keys = [r["relative_path"] for r in rows]
        stats[path.name] = {"rows": len(rows), "classes_with_samples": len(counts),
                            "duplicates": len(keys) - len(set(keys)),
                            "class_count_histogram": dict(Counter(counts.values()))}
    for name in ["imagenet_r", "imagenet_a"]:
        folder = AUTHOR / "data/image_cls_cil"
        train = read_jsonl(folder / f"split_lists/{name}_train.jsonl")
        test = read_jsonl(folder / f"split_lists/{name}_test.jsonl")
        few = read_jsonl(folder / f"fewshot_lists/{name}_train_5shots.jsonl")
        key = lambda r: (r["class_name"], r["file_name"])
        train_keys, test_keys, few_keys = ({key(r) for r in rows} for rows in [train, test, few])
        stats[name + "_split"] = {"train": len(train), "test": len(test),
                                  "train_test_overlap": len(train_keys & test_keys),
                                  "fewshot_outside_train": len(few_keys - train_keys),
                                  "train_duplicates": len(train) - len(train_keys),
                                  "test_duplicates": len(test) - len(test_keys)}
    helper = selected_module("examples/baselines/cil_det/image_det_cil.py", ["_normalize_label_name", "_load_categories", "_build_class_order", "_chunk_classes", "_build_class_to_task_map", "_infer_example_task_id_from_answer", "_filter_annotations_by_classes"])
    categories = helper._load_categories(str(AUTHOR / "data/object_det_cil_dataset/categories.json"))
    rows = read_jsonl(AUTHOR / "data/object_det_cil_dataset/train_5shots.jsonl")
    val = read_jsonl(AUTHOR / "data/object_det_cil_dataset/val.jsonl")
    train_ids, val_ids = ({r["images"][0] for r in items} for items in [rows, val])
    per_category = Counter(c for row in rows for c in {d["category"] for d in json.loads(row["answer"])})
    stats["coco"] = {"train_rows": len(rows), "val_rows": len(val), "category_count": len(categories),
                     "train_duplicates": len(rows) - len(train_ids), "val_duplicates": len(val) - len(val_ids),
                     "train_val_overlap": len(train_ids & val_ids),
                     "raw_category_image_counts": dict(sorted(per_category.items())), "partitions": []}
    for tasks, seeds in [(5, [136, 377, 639]), (10, [277, 305, 738])]:
        for seed in seeds:
            order = helper._build_class_order(len(categories), None, seed)
            splits = helper._chunk_classes(order, 80 // tasks, 80 // tasks, tasks)
            task_map = helper._build_class_to_task_map(splits, categories)
            assignments = [helper._infer_example_task_id_from_answer(r["answer"], task_map) for r in rows]
            count = Counter(assignments)
            # Execute the author's actual label filter, matching _build_dataloader.
            learned_counts = Counter()
            for row, task in zip(rows, assignments):
                allowed = {c for c, t in task_map.items() if t == task}
                filtered = helper._filter_annotations_by_classes(row["answer"], allowed)
                learned_counts.update({d["category"] for d in json.loads(filtered)})
            stats["coco"]["partitions"].append({"tasks": tasks, "seed": seed,
                "task_counts": [count[t] for t in range(tasks)],
                "batches_per_epoch_drop_last8": [count[t] // 8 for t in range(tasks)],
                "zero_batch_tasks_1based": [t + 1 for t in range(tasks) if count[t] < 8],
                "unassigned": count[-1], "classes_without_train_labels": [c for c in categories if not learned_counts[c]],
                "class_to_task_1based": {c: t + 1 for c, t in task_map.items()},
                "max_class_training_images": max(learned_counts.values()),
                "class_training_counts": dict(sorted(learned_counts.items()))})
    video = read_jsonl(AUTHOR / "data/video_cls_cil/fewshot_lists/ucf101_split01_train_5shots.jsonl")
    counts = Counter(row["class_name"] for row in video)
    stats["ucf101"] = {"rows": len(video), "classes_with_samples": len(counts),
                       "class_count_histogram": dict(Counter(counts.values()))}
    return stats


if __name__ == "__main__":
    result = {"environment": {"python": sys.version, "torch": torch.__version__, "numpy": np.__version__, "device": "CPU"}}
    result.update(ctan_and_retention())
    result["data_assets"] = data_assets()
    result["source_sha256"] = SOURCES
    (OUT / "cpu-probes.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ctan": result["ctan"], "retention": result["retention"],
                      "data": {k: v for k, v in result["data_assets"].items() if k != "coco"},
                      "coco_partitions": [{k: v for k, v in p.items() if k != "class_training_counts"} for p in result["data_assets"]["coco"]["partitions"]]}, indent=2, ensure_ascii=False))
