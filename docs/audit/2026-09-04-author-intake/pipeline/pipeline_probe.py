"""Trace unmodified author advantage hooks on CPU; not a Ray/model run."""
import argparse
import ast
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, Optional

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[4]
AUTHOR = ROOT / "RaPO_作者整理代码"
OUT = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8")
HASHES = {}


def select(relative, names, methods=()):
    path = AUTHOR / relative
    HASHES[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    tree = ast.parse(path.read_bytes(), filename=relative)
    nodes = []
    for node in tree.body:
        name = getattr(node, "name", None)
        if isinstance(node, ast.AnnAssign):
            name = getattr(node.target, "id", None)
        elif isinstance(node, ast.Assign):
            name = getattr(node.targets[0], "id", None)
        if name in names:
            nodes.append(node)
        elif isinstance(node, ast.ClassDef):
            nodes.extend(m for m in node.body if isinstance(m, ast.FunctionDef) and (node.name, m.name) in methods)
    assert len(nodes) == len(names) + len(methods)
    module = ModuleType("pipeline_subject_" + str(len(HASHES)))
    sys.modules[module.__name__] = module
    module.__dict__.update(argparse=argparse, dataclass=dataclass, Enum=Enum, defaultdict=defaultdict,
                           Any=Any, Optional=Optional, torch=torch, np=np, os=os, json=json)
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    code = ast.fix_missing_locations(ast.Module(body=[future, *nodes], type_ignores=[]))
    exec(compile(code, relative, "exec"), module.__dict__)
    return module


def new_batch():
    rewards = torch.tensor(([1., 2.] * 4) * 8).reshape(64, 1)
    return SimpleNamespace(batch={"token_level_rewards":rewards,"response_mask":torch.ones_like(rewards),
                                  "old_log_probs":torch.full_like(rewards,-1),
                                  "ref_log_probs":torch.full_like(rewards,-1),
                                  "anchor_log_probs":torch.full_like(rewards,-1)},
                           non_tensor_batch={"uid":np.repeat(np.arange(8),8)})


def main():
    core = select("verl/trainer/core_algos.py", ["AdvantageEstimator", "ADV_ESTIMATOR_MAP",
                  "register_adv_estimator", "compute_advantage_return", "compute_grpo_outcome_advantage"])
    runner = select("verl/trainer/ray_trainer.py", ["compute_advantage"])
    runner.compute_advantage_return = core.compute_advantage_return
    shared = select("examples/baselines/_rapo_components.py", ["EMAAdvConfig", "EMAAdvNormalizer",
                    "_CIL_CFG_GROUP_MAP", "_CIL_CFG_HARDCODED_CTAN_KEYS", "_load_cil_cfg",
                    "_first_defined_env", "RetentionRewardConfig", "_apply_retention_reward"],
                    [("RayPPOContinualRaPOTrainer","_compute_advantage_with_hooks")])
    shared.AdvantageEstimator = core.AdvantageEstimator
    entries = {}
    for name, rel in [("image","img_cls_cil/image_cls_cil_rapo.py"), ("det","cil_det/image_det_cil_rapo.py")]:
        entries[name] = select("examples/baselines/" + rel, ["_parse_args","_set_env"])
        entries[name]._load_cil_cfg = shared._load_cil_cfg
    configs = {}
    for family in ["image", "video", "det"]:
        entry = entries["det" if family == "det" else "image"]
        sys.argv = ["probe","--cil_cfg",str(AUTHOR/f"scripts/{family}/rapo_cfg.json"),"--prompt_seen_labels"]
        args, remaining = entry._parse_args()
        assert not remaining
        entry._set_env(args)
        configs[family] = {"ctan":vars(shared.EMAAdvConfig.from_env()),
                           "retention":vars(shared.RetentionRewardConfig.from_env())}
    assert all(c["ctan"]["enabled"] and c["retention"]["enabled"] for c in configs.values())
    cases = []
    prior = None
    for label, task, enabled, retention in [("task1_enabled",1,True,True), ("task2_enabled",2,True,True),
                                           ("task2_ctan_disabled",2,False,True)]:
        cfg = shared.EMAAdvConfig(**{**configs["image"]["ctan"],"enabled":enabled})
        normalizer = shared.EMAAdvNormalizer(cfg, initial_state=prior, task_id=task) if enabled else None
        context = SimpleNamespace(ema_adv=normalizer, _task_id=task, _anchor_available=task>=2,
                                  retention_cfg=shared.RetentionRewardConfig(**{**configs["image"]["retention"],"enabled":retention}),
                                  _orig_compute_advantage=runner.compute_advantage, _pending_retention_metrics={})
        calls = []
        def observe(frame, event, arg):
            if event == "call" and frame.f_code.co_filename in HASHES:
                calls.append({"file":frame.f_code.co_filename,"function":frame.f_code.co_name,"line":frame.f_code.co_firstlineno})
        data = new_batch()
        sys.setprofile(observe)
        try:
            returned = shared._compute_advantage_with_hooks(context, data, "grpo")
        finally:
            sys.setprofile(None)
        names = [c["function"] for c in calls]
        if label == "task1_enabled":
            assert "observe_batch_without_ema" in names and "compute_grpo_outcome_advantage" in names
            assert "compute_grpo_advantage" not in names and "_apply_retention_reward" not in names
            prior = normalizer.state_dict()
        elif label == "task2_enabled":
            assert "compute_grpo_advantage" in names and "compute_grpo_outcome_advantage" not in names
            assert names.index("_apply_retention_reward") < names.index("compute_grpo_advantage")
            assert normalizer.update_count == 1
        else:
            assert "compute_grpo_advantage" not in names and "compute_grpo_outcome_advantage" in names
        assert returned is data and "advantages" in data.batch
        cases.append({"case":label,"calls":calls,"ema_updates":normalizer.update_count if normalizer else None,
                      "positive_adv":float(data.batch["advantages"][1]),
                      "first_reward":float(data.batch["token_level_rewards"][0])})

    # Exact default behavior when the actor's environment lacks these settings.
    # This is not a simulated Ray success: only the author's from_env defaults.
    relevant = [key for key in os.environ if key.startswith("EMA_ADV_") or key.startswith("RETENTION_")]
    for key in relevant:
        del os.environ[key]
    absent = {"ctan":shared.EMAAdvConfig.from_env().enabled,
              "retention":shared.RetentionRewardConfig.from_env().enabled}
    assert absent == {"ctan":False,"retention":False}
    runtime_envs = {}
    for path in ["examples/baselines/img_cls_cil/image_cls_cil.py", "examples/baselines/cil_det/image_det_cil.py"]:
        tree = ast.parse((AUTHOR/path).read_bytes())
        fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_ensure_ray")
        assignment = next(n for n in ast.walk(fn) if isinstance(n,ast.Assign)
                          and any(isinstance(t,ast.Name) and t.id=="runtime_env" for t in n.targets))
        runtime_envs[path] = ast.literal_eval(assignment.value)["env_vars"]
    assert not any(k.startswith("EMA_ADV_") or k.startswith("RETENTION_")
                   for env in runtime_envs.values() for k in env)
    intake = json.loads((OUT.parent/"intake-snapshot.json").read_text(encoding="utf-8"))
    actual = {p.relative_to(AUTHOR).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
              for p in AUTHOR.rglob("*") if p.is_file()}
    assert actual == {p:v["sha256"] for p,v in intake["author_files"].items()}
    result = {"python":sys.version,"torch":torch.__version__,"cases":cases,"effective_configs":configs,
              "absent_env_defaults":absent,"explicit_ray_env_vars":runtime_envs,"source_sha256":HASHES,
              "author_files_unchanged":len(actual),"actual_ray_or_gpu_execution":False}
    (OUT/"results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"cases":[{**c,"calls":[x["function"] for x in c["calls"]]} for c in cases],
                      "absent_env_defaults":absent,"author_files_unchanged":len(actual)},indent=2))


if __name__ == "__main__":
    main()
