"""Independent CPU derivations for the two intake findings; never imports old probes.

Author classes/functions are AST-selected without modifying their bodies. This
executes arithmetic and JSON helpers, not Ray, a DataLoader or a model. Author
save/load helpers write only beneath this audit directory.
"""
import ast
import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, Optional

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[4]
AUTHOR = ROOT / "RaPO_作者整理代码"
OUT = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8")
SOURCE_HASHES = {}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_module(relative, names):
    path = AUTHOR / relative
    SOURCE_HASHES[relative] = digest(path)
    tree = ast.parse(path.read_bytes(), filename=relative)
    selected = []
    for node in tree.body:
        name = getattr(node, "name", None)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        if name in names:
            selected.append(node)
    assert len(selected) == len(names)
    module = ModuleType("recheck_source_" + str(len(SOURCE_HASHES)))
    sys.modules[module.__name__] = module
    module.__dict__.update(dataclass=dataclass, argparse=argparse, Any=Any, Optional=Optional,
                           torch=torch, np=np, os=os, json=json, re=re)
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    ast_tree = ast.fix_missing_locations(ast.Module(body=[future, *selected], type_ignores=[]))
    exec(compile(ast_tree, relative, "exec"), module.__dict__)
    return module


def batch(group):
    scores = torch.tensor(group * 8, dtype=torch.float32).reshape(64, 1)
    return SimpleNamespace(batch={"token_level_rewards": scores, "response_mask": torch.ones_like(scores)},
                           non_tensor_batch={"uid": np.repeat(np.arange(8), 8)})


def check_ctan():
    m = source_module("examples/baselines/_rapo_components.py", [
        "_CIL_CFG_GROUP_MAP", "_CIL_CFG_HARDCODED_CTAN_KEYS", "_load_cil_cfg", "EMAAdvConfig",
        "EMAAdvNormalizer", "_ema_stats_file_from_task_dir", "_save_ema_state", "_load_ema_state"])
    # Execute the author's actual argument/config/env functions, without main().
    entry = source_module("examples/baselines/img_cls_cil/image_cls_cil_rapo.py", ["_parse_args", "_set_env"])
    entry._load_cil_cfg = m._load_cil_cfg
    configs = {}
    for family in ["image", "video", "det"]:
        path = AUTHOR / f"scripts/{family}/rapo_cfg.json"
        sys.argv = ["audit", "--cil_cfg", str(path), "--save_dir", str(OUT),
                    "--base_classes", "20", "--incremental_classes", "20"]
        args, remaining = entry._parse_args()
        assert not remaining
        entry._set_env(args)
        configs[family] = asdict(m.EMAAdvConfig.from_env())
    assert configs["image"] == configs["video"] == configs["det"]
    cfg = m.EMAAdvConfig(**configs["image"])
    assert cfg.enabled
    cases = []
    # Same last batch, different earlier reward history. All std values are >0.
    for name, earlier in [("history_a", [1.5, 2.5] * 4), ("history_b", [1.5, 2.25] * 4)]:
        task_dir = OUT / name / "task_1"
        path = m._ema_stats_file_from_task_dir(str(task_dir))
        t1 = m.EMAAdvNormalizer(cfg, task_id=1)
        t1.observe_batch_without_ema(batch([1, 2] * 4))
        m._save_ema_state(path, t1.state_dict(), task_id=1)
        t2 = m.EMAAdvNormalizer(cfg, initial_state=m._load_ema_state(path), task_id=2)
        for _ in range(23):
            t2.compute_grpo_advantage(batch(earlier))
        last = [1.5] * 7 + [2.5]
        t2.compute_grpo_advantage(batch(last))
        saved = t2.state_dict()
        m._save_ema_state(path, saved, task_id=2)
        loaded = m._load_ema_state(path)
        assert loaded["ema_std"] == saved["ema_std"]  # JSON did not lose the EMA.
        t3 = m.EMAAdvNormalizer(cfg, initial_state=loaded, task_id=3)
        before = t3.ema_std
        incoming = batch([1.5, 2.5] * 4)
        new_std = float(incoming.batch["token_level_rewards"].std())
        beta = t3._effective_beta()
        paper = cfg.beta * saved["ema_std"] + (1 - cfg.beta) * new_std
        carry_with_author_beta = beta * saved["ema_std"] + (1 - beta) * new_std
        t3.compute_grpo_advantage(incoming)
        advantages = incoming.batch["advantages"]
        # For these inputs guard must be inactive; compare to the unclipped formula.
        assert torch.allclose(advantages, (incoming.batch["token_level_rewards"] - 2.0) / (t3.ema_std + cfg.eps))
        cases.append({"name": name, "updates_in_task2":24, "saved_ema":saved["ema_std"],
                      "file_loaded_ema":loaded["ema_std"], "last_batch_std":saved["last_batch_reward_std"],
                      "task3_constructor_ema":before, "task3_actual_beta":beta,
                      "task3_actual_ema":t3.ema_std, "paper_carry_ema":paper,
                      "carry_with_author_beta":carry_with_author_beta,
                      "actual_positive_adv":float(advantages[1]), "paper_positive_adv":0.5/(paper+cfg.eps),
                      "guard_triggered":False})
    assert not math.isclose(cases[0]["saved_ema"], cases[1]["saved_ema"])
    assert cases[0]["task3_constructor_ema"] == cases[1]["task3_constructor_ema"]
    # Positive control: same saved EMA and last-batch std means no constructor change.
    stable = m.EMAAdvNormalizer(cfg, task_id=2, initial_state=t1.state_dict())
    for _ in range(24):
        stable.compute_grpo_advantage(batch([1, 2] * 4))
    stable_saved = stable.state_dict()
    stable_new = m.EMAAdvNormalizer(cfg, task_id=3, initial_state=stable_saved)
    assert math.isclose(stable_new.ema_std, stable_saved["ema_std"], rel_tol=1e-12)
    return {"effective_config":configs, "cases":cases,
            "positive_control_equal_ema_last_batch":True, "old_probe_imported":False}


def check_coco():
    m = source_module("examples/baselines/cil_det/image_det_cil.py", ["_normalize_label_name", "_load_categories",
        "_build_class_order", "_resolve_task_plan", "_chunk_classes", "_build_class_to_task_map",
        "_infer_example_task_id_from_answer", "_filter_annotations_by_classes"])
    folder = AUTHOR / "data/object_det_cil_dataset"
    categories = json.loads((folder / "categories.json").read_text(encoding="utf-8"))["categories"]
    assert categories == m._load_categories(str(folder / "categories.json"))
    rows = [json.loads(s) for s in (folder / "train_5shots.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
    partitions = []
    for count, seeds in [(5, [136, 377, 639]), (10, [277, 305, 738])]:
        for seed in seeds:
            order = np.random.RandomState(seed).permutation(80).tolist()
            assert order == m._build_class_order(80, None, seed)
            width = 80 // count
            task_for_class = {categories[idx]: pos // width for pos, idx in enumerate(order)}
            task_plan = m._resolve_task_plan(80, width, width)
            assert m._build_class_to_task_map(m._chunk_classes(order, width, width, task_plan[0]), categories) == task_for_class
            class_images, raw_class_images, tasks = Counter(), Counter(), Counter()
            witness = []
            for line, row in enumerate(rows, 1):
                labels = {d["category"] for d in json.loads(row["answer"])}
                assert labels <= set(categories)
                raw_class_images.update(labels)
                # Independent set equation, then agreement with the author helpers.
                assigned = max(task_for_class[c] for c in labels)
                kept = {c for c in labels if task_for_class[c] == assigned}
                assert assigned == m._infer_example_task_id_from_answer(row["answer"], task_for_class)
                author_kept = json.loads(m._filter_annotations_by_classes(row["answer"],
                                         {c for c, t in task_for_class.items() if t == assigned}))
                assert kept == {d["category"] for d in author_kept}
                tasks[assigned] += 1
                class_images.update(kept)
                if count == 5 and seed == 136 and "bicycle" in labels:
                    witness.append({"jsonl_line":line,"image":row["images"][0],"packaged_task_id":row.get("task_id"),
                        "category_tasks_1based":{c:task_for_class[c]+1 for c in sorted(labels)},
                        "assigned_task_1based":assigned+1,"kept_labels":sorted(kept)})
            partitions.append({"tasks":count,"seed":seed,"raw_class_images":dict(raw_class_images),
                "class_training_images":{c:class_images[c] for c in categories},
                "class_task_1based":{c:t+1 for c,t in task_for_class.items()},
                "task_image_counts":[tasks[t] for t in range(count)],
                "zero_label_classes":[c for c in categories if not class_images[c]],
                "classes_over_five":{c:n for c,n in class_images.items() if n>5},
                "bicycle_witnesses":witness})
    # A representative one-label control and multi-label mechanism example.
    controlled = []
    mapping = {"early":0,"late":1}
    for labels in [["early"], ["early","late"]]:
        answer = json.dumps([{"category":c,"bbox":[0,0,10,10]} for c in labels])
        assigned = m._infer_example_task_id_from_answer(answer, mapping)
        kept = json.loads(m._filter_annotations_by_classes(answer, {c for c,t in mapping.items() if t==assigned}))
        controlled.append({"input":labels,"task_1based":assigned+1,"retained":[d["category"] for d in kept]})
    assert controlled[0]["retained"] == ["early"] and controlled[1]["retained"] == ["late"]
    # A concrete packaged row: exact GT-derived predictions, not model inference.
    reward_path = AUTHOR / "examples/reward_function/det.py"
    SOURCE_HASHES["examples/reward_function/det.py"] = digest(reward_path)
    reward_module = {"__name__":"recheck_detection_reward"}
    exec(compile(reward_path.read_bytes(), str(reward_path), "exec"), reward_module)
    witness = partitions[0]["bicycle_witnesses"][0]
    original = rows[witness["jsonl_line"] - 1]["answer"]
    filtered = m._filter_annotations_by_classes(original, set(witness["kept_labels"]))
    wrap = lambda answer: "<think>I identify the visible objects and their boxes.</think><answer>" + answer + "</answer>"
    score = reward_module["compute_score"]
    reward_effect = {"image":witness["image"],"jsonl_line":witness["jsonl_line"],
                    "raw_boxes":len(json.loads(original)),"retained_boxes":len(json.loads(filtered)),
                    "all_boxes_predicted_filtered_gt":score({"response":wrap(original),"ground_truth":filtered}),
                    "retained_boxes_predicted_filtered_gt":score({"response":wrap(filtered),"ground_truth":filtered}),
                    "all_boxes_predicted_original_gt":score({"response":wrap(original),"ground_truth":original}),
                    "model_inference":False}
    return {"rows":len(rows),"unique_image_ids":len({r["images"][0] for r in rows}),
            "partitions":partitions,"controls":controlled,"reward_effect":reward_effect,"raw_images_opened":False}


def main():
    intake = json.loads((OUT.parent / "intake-snapshot.json").read_text(encoding="utf-8"))
    before = {p.relative_to(AUTHOR).as_posix():digest(p) for p in AUTHOR.rglob("*") if p.is_file()}
    assert before == {p:v["sha256"] for p,v in intake["author_files"].items()}
    baseline = OUT / "before.json"
    if not baseline.exists():
        tracked = subprocess.check_output(["git","ls-files","-z"],cwd=ROOT).decode().split("\0")
        baseline.write_text(json.dumps({p:digest(ROOT/p) for p in tracked if p and (ROOT/p).is_file()},indent=2)+"\n",encoding="utf-8")
    result = {"environment":{"python":sys.version,"torch":torch.__version__,"numpy":np.__version__,"device":"CPU"},
              "ctan":check_ctan(),"coco":check_coco(),"source_sha256":SOURCE_HASHES,
              "paper_sha256":digest(ROOT / "2605.09640v1.pdf")}
    after = {p.relative_to(AUTHOR).as_posix():digest(p) for p in AUTHOR.rglob("*") if p.is_file()}
    assert before == after
    result["author_files_preserved"] = len(after)
    (OUT / "results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"ctan_cases":result["ctan"]["cases"],"coco":[{
        "tasks":p["tasks"],"seed":p["seed"],"zero_label_classes":len(p["zero_label_classes"]),
        "max_class_images":max(p["class_training_images"].values())} for p in result["coco"]["partitions"]],
        "author_files_preserved":len(after)},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
