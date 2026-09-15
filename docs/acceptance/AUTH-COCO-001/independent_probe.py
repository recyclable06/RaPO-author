"""Independent CPU-local acceptance probes for AUTH-COCO-001.

This file is evidence tooling in the acceptance worktree.  It reads the
candidate, CTAN source, and main-tree governance files; it does not modify
any of them and does not import the Ray/datasets/model execution stack.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import Any, Iterable, Optional

import numpy as np


EXPECTED_HASHES_SELF = (
    "e6f54e82a577822f8d6ba8ac887b29c5017c6f8894488cf17851b62ff69d148f"
)
EXPECTED_CTAN_MANIFEST_SELF = (
    "1c2365642756bb24c37e2e12fbd734e3d29d5d30863ce0dfe55a44cb7351c0ef"
)
EXPECTED_AUTHOR_COMMIT = "7fe2a73291f208ad9784a8333523825718881907"
EXPECTED_BASE_HEAD = "da0c5ad521387bab75e74dc0bf0fd47dc13a3647"

SEED_SPECS = (
    {
        "tasks": 5,
        "base_classes": 16,
        "incremental_classes": 16,
        "seeds": (136, 377, 639),
        "counts": (
            (16, 19, 11, 64, 96),
            (16, 17, 27, 58, 88),
            (22, 19, 22, 56, 87),
        ),
    },
    {
        "tasks": 10,
        "base_classes": 8,
        "incremental_classes": 8,
        "seeds": (277, 305, 738),
        "counts": (
            (13, 14, 10, 16, 13, 16, 20, 20, 41, 43),
            (11, 10, 21, 10, 14, 15, 10, 23, 39, 53),
            (10, 12, 13, 13, 11, 14, 23, 23, 45, 42),
        ),
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rel_files(root: Path) -> set[str]:
    return {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def git_bytes(root: Path, revision_path: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), "show", revision_path],
        check=True,
        capture_output=True,
    )
    return result.stdout


def function_node(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_bytes(), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing top-level function {name} in {path}")


def keyword(call: ast.Call, name: str) -> ast.keyword:
    for item in call.keywords:
        if item.arg == name:
            return item
    raise AssertionError(f"missing keyword {name}")


def load_det_helpers(det_source: Path) -> dict[str, Any]:
    names = {
        "_normalize_label_name",
        "_filter_annotations_by_classes",
        "_infer_example_task_id_from_answer",
        "_build_class_order",
        "_build_class_to_task_map",
        "_chunk_classes",
    }
    tree = ast.parse(det_source.read_bytes(), filename=str(det_source))
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    assert {node.name for node in nodes} == names
    namespace = {
        "json": json,
        "np": np,
        "os": os,
        "Any": Any,
        "Iterable": Iterable,
        "Optional": Optional,
    }
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(det_source), "exec"),
        namespace,
    )
    return {name: namespace[name] for name in names}


def run_task_call(rapo_source: Path) -> ast.Call:
    run_cil = function_node(rapo_source, "_run_cil")
    calls = [
        node for node in ast.walk(run_cil)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "remote"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "run_task"
        )
    ]
    assert len(calls) == 1, f"expected one runner.run_task.remote call, got {len(calls)}"
    return calls[0]


def eval_allowed(
    expression: ast.AST,
    rapo_source: Path,
    prompt_seen_labels: bool,
    seen: list[str],
    novel: list[str],
) -> list[str]:
    namespace = {
        "known_args": SimpleNamespace(prompt_seen_labels=prompt_seen_labels),
        "seen_class_names": seen,
        "ordered_task_class_names": novel,
        "prompt_label_list": seen if prompt_seen_labels else None,
    }
    result = eval(
        compile(ast.Expression(expression), str(rapo_source), "eval"),
        {"__builtins__": {}},
        namespace,
    )
    assert isinstance(result, list)
    return result


def ast_and_truth_table(target: Path) -> dict[str, Any]:
    det_source = target / "examples/baselines/cil_det/image_det_cil.py"
    rapo_source = target / "examples/baselines/cil_det/image_det_cil_rapo.py"
    categories = read_json(target / "data/object_det_cil_dataset/categories.json")["categories"]
    helpers = load_det_helpers(det_source)
    call = run_task_call(rapo_source)
    allowed = keyword(call, "allowed_classes").value
    task_filter = keyword(call, "task_id_filter").value
    class_map = keyword(call, "class_to_task").value
    assert isinstance(allowed, ast.IfExp)
    assert isinstance(task_filter, ast.Name) and task_filter.id == "task_idx"
    assert isinstance(class_map, ast.Name) and class_map.id == "class_to_task"
    names = {node.id for node in ast.walk(allowed) if isinstance(node, ast.Name)}
    assert {"seen_class_names", "ordered_task_class_names"} <= names
    test_names = {
        node.id for node in ast.walk(allowed.test) if isinstance(node, ast.Name)
    }
    test_attrs = {
        node.attr for node in ast.walk(allowed.test) if isinstance(node, ast.Attribute)
    }
    assert "known_args" in test_names and "prompt_seen_labels" in test_attrs

    build = function_node(det_source, "_build_dataloader")
    task_ifs = [
        node for node in ast.walk(build)
        if isinstance(node, ast.If)
        and any(
            isinstance(part, ast.Name) and part.id == "task_id_filter"
            for part in ast.walk(node.test)
        )
    ]
    label_ifs = [
        node for node in ast.walk(build)
        if isinstance(node, ast.If)
        and any(
            isinstance(part, ast.Name) and part.id == "allowed_classes"
            for part in ast.walk(node.test)
        )
    ]
    assert len(task_ifs) == 1 and len(label_ifs) == 1
    task_if, label_if = task_ifs[0], label_ifs[0]
    assert task_if.lineno < label_if.lineno
    filter_calls = [
        node for node in ast.walk(label_if)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_filter_annotations_by_classes"
    ]
    assert len(filter_calls) == 2

    rows: list[dict[str, Any]] = []
    checked_tasks = 0
    for spec in SEED_SPECS:
        for seed, expected_counts in zip(spec["seeds"], spec["counts"]):
            order = helpers["_build_class_order"](80, None, seed)
            splits = helpers["_chunk_classes"](
                order,
                spec["base_classes"],
                spec["incremental_classes"],
                spec["tasks"],
            )
            class_to_task = helpers["_build_class_to_task_map"](splits, categories)
            seen: list[str] = []
            for task_id, class_ids in enumerate(splits):
                novel = [categories[index] for index in class_ids]
                seen.extend(novel)
                seen_result = eval_allowed(allowed, rapo_source, True, seen, novel)
                novel_result = eval_allowed(allowed, rapo_source, False, seen, novel)
                assert seen_result == seen
                assert novel_result == novel
                checked_tasks += 1
            rows.append(
                {
                    "tasks": spec["tasks"],
                    "seed": seed,
                    "counts": list(expected_counts),
                    "split_class_counts": [len(part) for part in splits],
                }
            )

    return {
        "callpoint": {
            "allowed_classes_ast": ast.unparse(allowed),
            "task_id_filter_ast": ast.unparse(task_filter),
            "class_to_task_ast": ast.unparse(class_map),
            "task_filter_line": task_if.lineno,
            "label_filter_line": label_if.lineno,
            "answer_filter_calls": len(filter_calls),
        },
        "truth_table": {
            "seed_runs": rows,
            "task_rows_checked": checked_tasks,
            "result": "pass",
        },
    }


def synthetic_filter_probe(target: Path) -> dict[str, Any]:
    det_source = target / "examples/baselines/cil_det/image_det_cil.py"
    helpers = load_det_helpers(det_source)
    normalize = helpers["_normalize_label_name"]
    infer = helpers["_infer_example_task_id_from_answer"]
    filter_annotations = helpers["_filter_annotations_by_classes"]
    class_to_task = {"old": 0, "new": 1, "latest": 2}
    answer_rows = [
        {
            "id": "old-only",
            "answer": [
                {"category": "old", "bbox": [1, 2, 3, 4], "instance": 10},
            ],
            "answer_seg": [
                {"category": "old", "segmentation": [[1, 2]], "instance": 10},
            ],
        },
        {
            "id": "cross-01",
            "answer": [
                {"category": "old", "bbox": [5, 6, 7, 8], "instance": 11},
                {"category": "new", "bbox": [9, 10, 11, 12], "instance": 12},
            ],
            "answer_seg": [
                {"category": "old", "segmentation": [[3, 4]], "instance": 11},
                {"category": "new", "segmentation": [[5, 6]], "instance": 12},
            ],
        },
        {
            "id": "cross-12",
            "answer": [
                {"category": "new", "bbox": [13, 14, 15, 16], "instance": 13},
                {"category": "latest", "bbox": [17, 18, 19, 20], "instance": 14},
            ],
            "answer_seg": [
                {"category": "new", "segmentation": [[7, 8]], "instance": 13},
                {"category": "latest", "segmentation": [[9, 10]], "instance": 14},
            ],
        },
    ]
    assigned = {
        row["id"]: infer(json.dumps(row["answer"]), class_to_task)
        for row in answer_rows
    }
    assert assigned == {"old-only": 0, "cross-01": 1, "cross-12": 2}

    def apply_task_then_label(task_id: int, allowed: set[str]) -> list[str]:
        selected = [row for row in answer_rows if assigned[row["id"]] == task_id]
        output: list[str] = []
        for row in selected:
            actual_answer = json.loads(
                filter_annotations(
                    json.dumps(row["answer"]),
                    {normalize(name) for name in allowed},
                )
            )
            actual_seg = json.loads(
                filter_annotations(
                    json.dumps(row["answer_seg"]),
                    {normalize(name) for name in allowed},
                )
            )
            expected_answer = [
                item for item in row["answer"]
                if normalize(item["category"]) in {normalize(name) for name in allowed}
            ]
            expected_seg = [
                item for item in row["answer_seg"]
                if normalize(item["category"]) in {normalize(name) for name in allowed}
            ]
            assert actual_answer == expected_answer
            assert actual_seg == expected_seg
            output.append(row["id"])
        return output

    # Task 1 must not receive old-only even though old is an allowed label;
    # cross-01 keeps both objects for the seen path and only new for novel.
    assert apply_task_then_label(1, {"old", "new"}) == ["cross-01"]
    cross = next(row for row in answer_rows if row["id"] == "cross-01")
    assert json.loads(
        filter_annotations(json.dumps(cross["answer"]), {"old", "new"})
    ) == cross["answer"]
    assert json.loads(
        filter_annotations(json.dumps(cross["answer_seg"]), {"new"})
    ) == [cross["answer_seg"][1]]
    assert apply_task_then_label(2, {"old", "new", "latest"}) == ["cross-12"]

    return {
        "assigned_tasks": assigned,
        "task_first_exclusion": "old-only excluded from task 1 before label filtering",
        "seen_answer_and_answer_seg": "cross-01 retains exact object dictionaries and order",
        "novel_answer_seg": "cross-01 retains only new segmentation object",
        "result": "pass",
    }


def reward_witness_probe(target: Path) -> dict[str, Any]:
    train = target / "data/object_det_cil_dataset/train_5shots.jsonl"
    row = next(
        json.loads(line)
        for line in train.read_text(encoding="utf-8").splitlines()
        if line.strip()
        and json.loads(line).get("images") == ["train2017/000000018783.jpg"]
    )
    ground_truth = row["answer"]
    detections = json.loads(ground_truth)
    assert len(detections) == 8
    car_only = json.dumps(
        [item for item in detections if item["category"] == "car"],
        ensure_ascii=False,
    )
    reward_path = target / "examples/reward_function/det.py"
    spec = importlib.util.spec_from_file_location("acceptance_author_det_reward", reward_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    response = lambda answer: f"<think>valid analysis</think><answer>{answer}</answer>"
    full = module.compute_score({"response": response(ground_truth), "ground_truth": ground_truth})
    car = module.compute_score({"response": response(car_only), "ground_truth": ground_truth})
    assert full["overall"] == 3.0
    assert car["overall"] == 1.25
    assert full["overall"] - car["overall"] == 1.75
    assert full["overall"] - (car["overall"] + 0.5) > 0
    return {
        "image": "train2017/000000018783.jpg",
        "ground_truth_boxes": len(detections),
        "full_answer": full,
        "car_only_answer": car,
        "overall_gap": full["overall"] - car["overall"],
        "retention_cap": 0.5,
        "result": "pass",
    }


def hash_and_scope_probe(target: Path, ctan: Path, main: Path) -> dict[str, Any]:
    coco_dir = target / "docs/remediation/AUTH-COCO-001"
    hashes_path = coco_dir / "HASHES.json"
    hashes_doc = read_json(hashes_path)
    listed = dict(hashes_doc["files"])
    actual = {
        rel: sha256(target / rel) if (target / rel).is_file() else None
        for rel in listed
    }
    listed_mismatches = [
        rel for rel, expected in listed.items() if actual[rel] != expected
    ]
    pre_path = coco_dir / "PRE_BATCH_HASHES.json"
    ctan_manifest_path = ctan / "docs/remediation/AUTH-CTAN-001/SHA256SUMS.json"
    ctan_doc = read_json(ctan_manifest_path)
    ctan_files = dict(ctan_doc["files"])
    ctan_manifest_actual = sha256(ctan_manifest_path)
    ctan_manifest_hash_mismatches = [
        rel for rel, expected in ctan_files.items()
        if not (ctan / rel).is_file() or sha256(ctan / rel) != expected
    ]

    tree_mismatches: list[str] = []
    for rel in ctan_files:
        candidate = target / rel
        source = ctan / rel
        if not candidate.is_file() or not source.is_file():
            tree_mismatches.append(rel)
        elif candidate.read_bytes() != source.read_bytes():
            tree_mismatches.append(rel)
    expected_tree_mismatches = {
        "AGENTS.md",
        "examples/baselines/cil_det/image_det_cil_rapo.py",
    }

    target_extra = sorted(rel_files(target) - rel_files(ctan))
    allowed_extra_prefix = "docs/remediation/AUTH-COCO-001/"
    unexpected_extra = [
        rel for rel in target_extra
        if rel != "tests/author_fixes/test_coco.py"
        and not rel.startswith(allowed_extra_prefix)
    ]

    agents_target = sha256(target / "AGENTS.md")
    agents_main = sha256(main / "AGENTS.md")
    production_rel = "examples/baselines/cil_det/image_det_cil_rapo.py"
    production_diff = list(
        difflib.unified_diff(
            (ctan / production_rel).read_text(encoding="utf-8").splitlines(),
            (target / production_rel).read_text(encoding="utf-8").splitlines(),
            fromfile="ctan-source",
            tofile="coco-target",
            lineterm="",
        )
    )

    author_commit = git(target, "rev-parse", "author-drop-20260904^{commit}")
    baseline_same = {}
    for rel in (
        "examples/baselines/cil_det/image_det_cil.py",
        "examples/reward_function/det.py",
        "data/object_det_cil_dataset/categories.json",
        "data/object_det_cil_dataset/metadata.json",
        "data/object_det_cil_dataset/train_5shots.jsonl",
        "data/object_det_cil_dataset/val.jsonl",
    ):
        baseline_same[rel] = (target / rel).read_bytes() == git_bytes(
            target, f"author-drop-20260904:{rel}"
        )

    return {
        "coco_hash_manifest": {
            "listed_files": len(listed),
            "manifest_self_sha256": sha256(hashes_path),
            "manifest_self_expected": EXPECTED_HASHES_SELF,
            "manifest_self_matches": sha256(hashes_path) == EXPECTED_HASHES_SELF,
            "listed_mismatches": listed_mismatches,
            "pre_batch_sha256": sha256(pre_path),
        },
        "ctan_manifest": {
            "listed_files": len(ctan_files),
            "manifest_self_sha256": ctan_manifest_actual,
            "manifest_self_expected": EXPECTED_CTAN_MANIFEST_SELF,
            "manifest_self_matches": ctan_manifest_actual == EXPECTED_CTAN_MANIFEST_SELF,
            "listed_mismatches": ctan_manifest_hash_mismatches,
        },
        "target_vs_ctan_source": {
            "matching_files": len(ctan_files) - len(tree_mismatches),
            "mismatches": tree_mismatches,
            "expected_mismatches": sorted(expected_tree_mismatches),
            "only_expected_mismatches": set(tree_mismatches) == expected_tree_mismatches,
            "target_extra_files": target_extra,
            "unexpected_extra_files": unexpected_extra,
        },
        "governance": {
            "target_agents_sha256": agents_target,
            "main_agents_sha256": agents_main,
            "same_as_main": agents_target == agents_main,
        },
        "author_baseline": {
            "resolved_commit": author_commit,
            "expected_commit": EXPECTED_AUTHOR_COMMIT,
            "commit_matches": author_commit == EXPECTED_AUTHOR_COMMIT,
            "base_head_expected": EXPECTED_BASE_HEAD,
            "unchanged_files": baseline_same,
        },
        "coco_diff_vs_ctan": {
            "path": production_rel,
            "unified_diff": production_diff,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--ctan", type=Path, required=True)
    parser.add_argument("--main", type=Path, required=True)
    args = parser.parse_args()
    result = {
        "python": sys.version,
        "target": str(args.target),
        "ctan": str(args.ctan),
        "main": str(args.main),
        "hash_and_scope": hash_and_scope_probe(args.target, args.ctan, args.main),
        "static_callpoint_and_six_seed_truth_table": ast_and_truth_table(args.target),
        "synthetic_task_first_filter_and_field_integrity": synthetic_filter_probe(args.target),
        "real_reward_witness": reward_witness_probe(args.target),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    import sys

    main()
