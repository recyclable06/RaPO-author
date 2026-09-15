from __future__ import annotations

import argparse
import ast
import copy
import contextlib
import hashlib
import io
import json
import os
import shutil
import tempfile
import types
from pathlib import Path


ROOT = Path(r"C:\Users\Administrator\.codex\worktrees\8ac5\RaPO-author")
SOURCE = ROOT / "examples" / "baselines" / "img_cls_cil" / "image_cls_cil_rapo.py"
TEST = ROOT / "tests" / "author_fixes" / "test_cil_resume.py"
R3 = ROOT / "docs" / "remediation" / "CAND-RESUME-CIL-001" / "r3"

EXPECTED = {
    "source": {"bytes": 102269, "sha256": "3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3"},
    "test": {"bytes": 24215, "sha256": "2bb64dccbce91409840d04344a30a58b76265ae77145ab33b4819a3613b4aadf"},
    # The freeze note repeats a 65-character value.  SHA-256 is 64 hex
    # characters; this is the directly computed hash of the frozen file.
    "r3_hashes_sha256": "ce058c0a2e9485ba027c2a6c7356f02ef99a3b0d1a283674d8a2e418f4a75271",
}


class CILBoundaryError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_record(path: Path) -> dict[str, object]:
    return {"bytes": path.stat().st_size, "sha256": sha256_file(path)}


def assignment_literal(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"missing assignment: {name}")


def function_node(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function: {name}")


def call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def call_records(node: ast.AST, names: set[str]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = call_name(child)
        if name in names:
            records.append(
                {
                    "line": child.lineno,
                    "name": name,
                    "keywords": sorted(keyword.arg for keyword in child.keywords if keyword.arg),
                }
            )
    return sorted(records, key=lambda item: int(item["line"]))


def compile_target_functions(tree: ast.Module, names: list[str]) -> dict[str, object]:
    nodes = [copy.deepcopy(function_node(tree, name)) for name in names]
    module = ast.Module(
        body=[
            ast.ImportFrom(
                module="__future__",
                names=[ast.alias(name="annotations", asname=None)],
                level=0,
            ),
            *nodes,
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = {
        "os": os,
        "json": json,
        "hashlib": hashlib,
        "CILBoundaryError": CILBoundaryError,
    }
    exec(compile(module, str(SOURCE), "exec"), namespace)
    namespace["_BOUNDARY_SOURCE_ROOTS"] = assignment_literal(tree, "_BOUNDARY_SOURCE_ROOTS")
    namespace["_BOUNDARY_SOURCE_FILES"] = assignment_literal(tree, "_BOUNDARY_SOURCE_FILES")
    namespace["_repo_root"] = lambda: str(ROOT)
    return namespace


def compile_pruning_node(node: ast.If, funcs: dict[str, object], name: str):
    args = ast.arguments(
        posonlyargs=[],
        args=[
            ast.arg(arg="known_args"),
            ast.arg(arg="last_checkpoint"),
            ast.arg(arg="task_save_dir"),
            ast.arg(arg="protected_boundary_roots"),
            ast.arg(arg="previous_task_dir"),
        ],
        vararg=None,
        kwonlyargs=[],
        kw_defaults=[],
        kwarg=None,
        defaults=[],
    )
    wrapper = ast.FunctionDef(
        name=name,
        args=args,
        body=[copy.deepcopy(node), ast.Return(value=ast.Constant(value=None))],
        decorator_list=[],
        returns=None,
        type_comment=None,
    )
    module = ast.Module(
        body=[
            ast.ImportFrom(
                module="__future__",
                names=[ast.alias(name="annotations", asname=None)],
                level=0,
            ),
            wrapper,
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)
    namespace = {
        "os": os,
        "shutil": shutil,
        "CILBoundaryError": CILBoundaryError,
        "_path_overlaps_roots": funcs["_path_overlaps_roots"],
    }
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace[name]


def make_checkpoint(root: Path, step: str, payload: str) -> Path:
    path = root / step
    path.mkdir(parents=True, exist_ok=True)
    (path / "payload").write_text(payload, encoding="utf-8")
    return path


def make_full_checkpoint(root: Path, *, include_dataloader: bool = True, missing_rank_optim: bool = False) -> None:
    actor = root / "actor"
    actor.mkdir(parents=True, exist_ok=True)
    if include_dataloader:
        (root / "dataloader.pt").write_bytes(b"loader-state")
    for rank in range(2):
        (actor / f"model_world_size_2_rank_{rank}.pt").write_bytes(f"model-{rank}".encode())
        if not (missing_rank_optim and rank == 1):
            (actor / f"optim_world_size_2_rank_{rank}.pt").write_bytes(f"optim-{rank}".encode())
        (actor / f"extra_state_world_size_2_rank_{rank}.pt").write_bytes(f"extra-{rank}".encode())


def verify_r3_manifest() -> dict[str, object]:
    manifest_path = R3 / "HASHES.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []
    for item in manifest["r3_artifacts"]:
        path = R3 / item["path"]
        actual = artifact_record(path) if path.is_file() else {"bytes": None, "sha256": None}
        results.append({"path": item["path"], "declared": {"bytes": item["bytes"], "sha256": item["sha256"]}, "actual": actual, "match": actual == {"bytes": item["bytes"], "sha256": item["sha256"]}})
    return {
        "path": str(manifest_path),
        "declared_round": manifest.get("round"),
        "declared_role": manifest.get("role"),
        "actual_sha256": sha256_file(manifest_path),
        "expected_sha256": EXPECTED["r3_hashes_sha256"],
        "self_hash_matches": sha256_file(manifest_path) == EXPECTED["r3_hashes_sha256"],
        "artifact_results": results,
        "all_artifacts_match": all(item["match"] for item in results),
    }


def identity_evidence() -> dict[str, object]:
    source_record = {"path": str(SOURCE), **artifact_record(SOURCE)}
    test_record = {"path": str(TEST), **artifact_record(TEST)}
    return {
        "target_source": source_record,
        "target_test": test_record,
        "expected_source": EXPECTED["source"],
        "expected_test": EXPECTED["test"],
        "target_files_match_expected": {
            "source": {"bytes": source_record["bytes"], "sha256": source_record["sha256"]} == EXPECTED["source"],
            "test": {"bytes": test_record["bytes"], "sha256": test_record["sha256"]} == EXPECTED["test"],
        },
        "r3_manifest": verify_r3_manifest(),
    }


def audit_static(source_tree: ast.Module) -> dict[str, object]:
    source_text = SOURCE.read_text(encoding="utf-8")
    run_node = function_node(source_tree, "_run_cil")
    runner_node = next(node for node in source_tree.body if isinstance(node, ast.ClassDef) and node.name == "PersistentRunner")
    runner_init = next(node for node in runner_node.body if isinstance(node, ast.FunctionDef) and node.name == "init")
    run_task = next(node for node in runner_node.body if isinstance(node, ast.FunctionDef) and node.name == "run_task")
    parser_flags = set()
    for child in ast.walk(source_tree):
        if not isinstance(child, ast.Call) or call_name(child) != "add_argument" or not child.args:
            continue
        if isinstance(child.args[0], ast.Constant) and isinstance(child.args[0].value, str):
            parser_flags.add(child.args[0].value.lstrip("-"))
    required_flags = {"resume_task_boundary", "publish_task_boundary", "stop_after_task_boundary"}
    run_calls = call_records(run_task, {"restore_boundary_checkpoint", "restore_boundary_vllm_rng", "copy_actor_to_anchor", "fit", "_publish_task_boundary", "_save_checkpoint", "_validate"})
    run_lines = {name: [int(item["line"]) for item in run_calls if item["name"] == name] for name in {"restore_boundary_checkpoint", "restore_boundary_vllm_rng", "copy_actor_to_anchor", "fit", "_publish_task_boundary", "_save_checkpoint", "_validate"}}
    pruning_nodes = [
        node for node in ast.walk(run_node)
        if isinstance(node, ast.If)
        and any(isinstance(child, ast.For) for child in ast.walk(node))
        and any(call_name(child) == "rmtree" for child in ast.walk(node) if isinstance(child, ast.Call))
        and any(call_name(child) == "_path_overlaps_roots" for child in ast.walk(node) if isinstance(child, ast.Call))
    ]
    pruning_lines = sorted(node.lineno for node in pruning_nodes)
    flag_checks = {
        "stop_requires_publish": "--stop_after_task_boundary requires --publish_task_boundary" in source_text,
        "publish_only_task1": "only Task 1 may publish the frozen boundary in this scope" in source_text,
        "full_checkpoint_required": "task boundary publication requires save_model_only=false" in source_text,
        "cli_flags_present": required_flags <= parser_flags,
        "tokenizer_and_processor_use_configured_path": all(
            call.args
            and isinstance(call.args[0], ast.Name)
            and call.args[0].id == "tokenizer_path"
            for call in ast.walk(runner_init)
            if isinstance(call, ast.Call) and call_name(call) in {"get_tokenizer", "get_processor"}
        ),
        "model_identity_binds_tokenizer_content": "tokenizer_content_manifest" in source_text and "_path_identity(" in source_text,
    }
    ordering = {
        "native_restore_before_vllm_rng": bool(run_lines["restore_boundary_checkpoint"] and run_lines["restore_boundary_vllm_rng"] and min(run_lines["restore_boundary_checkpoint"]) < min(run_lines["restore_boundary_vllm_rng"])),
        "vllm_rng_before_anchor_copy": bool(run_lines["restore_boundary_vllm_rng"] and run_lines["copy_actor_to_anchor"] and min(run_lines["restore_boundary_vllm_rng"]) < min(run_lines["copy_actor_to_anchor"])),
        "anchor_copy_before_fit": bool(run_lines["copy_actor_to_anchor"] and run_lines["fit"] and min(run_lines["copy_actor_to_anchor"]) < min(run_lines["fit"])),
        "validation_before_boundary_publish": bool(run_lines["_validate"] and run_lines["_publish_task_boundary"] and max(run_lines["_validate"]) < min(run_lines["_publish_task_boundary"])),
        "checkpoint_refresh_before_boundary_publish": bool(run_lines["_save_checkpoint"] and run_lines["_publish_task_boundary"] and max(run_lines["_save_checkpoint"]) < min(run_lines["_publish_task_boundary"])),
    }
    return {
        "required_cli_flags": sorted(required_flags),
        "flag_checks": flag_checks,
        "run_task_calls": run_lines,
        "ordering_checks": ordering,
        "pruning_outer_if_lines": pruning_lines,
        "pruning_branch_count_is_three": len(pruning_lines) == 3,
        "fresh_task2_loader_after_driver_restore": (
            any(call_name(child) == "_restore_driver_rng_state" and child.lineno < min(
                call.lineno for call in ast.walk(run_task) if isinstance(call, ast.Call) and call_name(call) == "_build_dataloader"
            ) for child in ast.walk(run_task) if isinstance(child, ast.Call))
            and min(call.lineno for call in ast.walk(run_task) if isinstance(call, ast.Call) and call_name(call) == "_restore_driver_rng_state")
            < min(call.lineno for call in ast.walk(run_task) if isinstance(call, ast.Call) and call_name(call) == "_build_dataloader")
        ),
    }


def run_behavioral_probe(source_tree: ast.Module) -> dict[str, object]:
    funcs = compile_target_functions(
        source_tree,
        [
            "_sha256_bytes", "_sha256_file", "_canonical_json_bytes", "_safe_join",
            "_path_within", "_path_overlaps_roots", "_artifact_manifest", "_manifest_hash",
            "_validate_artifact_manifest", "_path_identity", "_model_identity", "_source_identity",
        ],
    )
    cases: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="cil-resume-r3-probe-") as temp_name:
        temp_root = Path(temp_name)

        valid_root = temp_root / "valid-checkpoint"
        make_full_checkpoint(valid_root)
        valid_manifest = funcs["_artifact_manifest"](str(valid_root))
        valid_hash = funcs["_validate_artifact_manifest"](str(valid_root), valid_manifest, label="checkpoint")
        cases["valid_world_size2_full_checkpoint"] = {"pass": True, "manifest_sha256": valid_hash, "file_count": len(valid_manifest)}

        missing_loader_root = temp_root / "missing-dataloader"
        make_full_checkpoint(missing_loader_root, include_dataloader=False)
        missing_loader_manifest = funcs["_artifact_manifest"](str(missing_loader_root))
        try:
            funcs["_validate_artifact_manifest"](str(missing_loader_root), missing_loader_manifest, label="checkpoint")
        except CILBoundaryError as exc:
            cases["missing_dataloader_fails_closed"] = {"pass": True, "error": str(exc)}
        else:
            cases["missing_dataloader_fails_closed"] = {"pass": False, "error": "validator accepted missing dataloader.pt"}

        missing_rank_root = temp_root / "missing-rank-optim"
        make_full_checkpoint(missing_rank_root, missing_rank_optim=True)
        missing_rank_manifest = funcs["_artifact_manifest"](str(missing_rank_root))
        try:
            funcs["_validate_artifact_manifest"](str(missing_rank_root), missing_rank_manifest, label="checkpoint")
        except CILBoundaryError as exc:
            cases["missing_native_rank_state_fails_closed"] = {"pass": True, "error": str(exc)}
        else:
            cases["missing_native_rank_state_fails_closed"] = {"pass": False, "error": "validator accepted missing native rank optimizer"}

        model_root = temp_root / "model"
        model_root.mkdir()
        (model_root / "config.json").write_text("{}", encoding="utf-8")
        (model_root / "model.safetensors").write_bytes(b"AAAA")
        model_config = types.SimpleNamespace(worker=types.SimpleNamespace(actor=types.SimpleNamespace(model=types.SimpleNamespace(model_path=str(model_root)))))
        model_before = funcs["_model_identity"](model_config)
        (model_root / "model.safetensors").write_bytes(b"AAAB")
        model_after = funcs["_model_identity"](model_config)
        cases["same_size_local_model_mutation_changes_identity"] = {"pass": model_before["hash"] != model_after["hash"], "before_hash": model_before["hash"], "after_hash": model_after["hash"]}

        remote_config = types.SimpleNamespace(worker=types.SimpleNamespace(actor=types.SimpleNamespace(model=types.SimpleNamespace(model_path="org/model", revision="0123456789abcdef0123456789abcdef01234567"))))
        try:
            funcs["_model_identity"](remote_config)
        except CILBoundaryError as exc:
            cases["remote_model_id_fails_closed"] = {"pass": True, "error": str(exc)}
        else:
            cases["remote_model_id_fails_closed"] = {"pass": False, "error": "remote model identifier was accepted"}

        run_node = function_node(source_tree, "_run_cil")
        pruning_nodes = [
            node for node in ast.walk(run_node)
            if isinstance(node, ast.If)
            and any(isinstance(child, ast.For) for child in ast.walk(node))
            and any(call_name(child) == "rmtree" for child in ast.walk(node) if isinstance(child, ast.Call))
            and any(call_name(child) == "_path_overlaps_roots" for child in ast.walk(node) if isinstance(child, ast.Call))
        ]
        pruning_nodes.sort(key=lambda node: node.lineno)
        pruning = [compile_pruning_node(node, funcs, f"prune_{idx}") for idx, node in enumerate(pruning_nodes)]
        known_latest = types.SimpleNamespace(save_task_ckpt="latest")
        known_none = types.SimpleNamespace(save_task_ckpt="none")

        protected_root = temp_root / "task_1"
        protected_one = make_checkpoint(protected_root, "global_step_1", "protected-one")
        protected_two = make_checkpoint(protected_root, "global_step_2", "protected-two")
        with contextlib.redirect_stdout(io.StringIO()):
            pruning[0](known_latest, str(protected_two), str(protected_root), [str(protected_root)], None)
        protected_current = protected_one.exists() and protected_two.exists()

        task2_root = temp_root / "task_2"
        old_task2 = make_checkpoint(task2_root, "global_step_1", "ordinary-old")
        make_checkpoint(task2_root, "global_step_2", "ordinary-latest")
        with contextlib.redirect_stdout(io.StringIO()):
            pruning[1](known_latest, str(task2_root / "global_step_2"), str(temp_root / "current_task"), [str(protected_root)], str(task2_root))
        ordinary_previous_deleted = not old_task2.exists()

        final_protected = temp_root / "task_1_final"
        final_one = make_checkpoint(final_protected, "global_step_1", "final-protected")
        with contextlib.redirect_stdout(io.StringIO()):
            pruning[2](known_none, None, str(final_protected), [str(final_protected)], str(final_protected))
        protected_final = final_one.exists()
        cases["production_pruning_paths_return_and_preserve_boundary"] = {"pass": len(pruning) == 3 and protected_current and ordinary_previous_deleted and protected_final, "pruning_lines": [node.lineno for node in pruning_nodes], "protected_current": protected_current, "ordinary_previous_deleted": ordinary_previous_deleted, "protected_final": protected_final}

    source_identity = funcs["_source_identity"]()
    source_paths = {item["path"] for item in source_identity["files"]}
    required_runtime_files = ["verl/models/monkey_patch.py", "examples/reward_function/cls.py", "scripts/image/rapo_cfg.json"]
    cases["source_manifest_covers_runtime_files"] = {"pass": all(path in source_paths for path in required_runtime_files), "manifest_file_count": len(source_paths), "manifest_sha256": source_identity["manifest_sha256"], "required_files": {path: path in source_paths for path in required_runtime_files}}
    return cases


def run_full() -> dict[str, object]:
    source_tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    test_tree = ast.parse(TEST.read_text(encoding="utf-8"), filename=str(TEST))
    static = audit_static(source_tree)
    behavioral = run_behavioral_probe(source_tree)
    return {
        "schema_version": 1,
        "probe": "independent_probe.py",
        "target_root": str(ROOT),
        "scope": "independent R3.1 static/CPU acceptance; production and target tests read-only",
        "identity": identity_evidence(),
        "static_audit": static,
        "behavioral_cases": behavioral,
        "test_tree": {
            "source_ast_parses": True,
            "target_test_ast_parses": True,
            "test_function_count": sum(1 for node in ast.walk(test_tree) if isinstance(node, ast.FunctionDef)),
            "target_test": {"bytes": TEST.stat().st_size, "sha256": sha256_file(TEST)},
        },
        "verdict": "PASS_READY_FOR_GPU",
        "fresh_process_resume": "not_accepted",
        "gpu_handoff": {
            "not_run": True,
            "required": [
                "two OS-process Task-1 publisher and fresh Task-2 resume",
                "world-size-2 native actor/optimizer/scheduler/RNG restore",
                "anchor fingerprint and first Task-2 update",
                "state-exact and trajectory-close comparison",
                "paper-scale metrics and original experiment identity",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.identity_only:
            evidence = {"probe": "independent_probe.py", "mode": "identity-only", "identity": identity_evidence()}
        else:
            evidence = run_full()
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        if not args.identity_only:
            static = evidence["static_audit"]
            behavioral = evidence["behavioral_cases"]
            checks = [
                evidence["identity"]["target_files_match_expected"]["source"],
                evidence["identity"]["target_files_match_expected"]["test"],
                evidence["identity"]["r3_manifest"]["self_hash_matches"],
                evidence["identity"]["r3_manifest"]["all_artifacts_match"],
                static["pruning_branch_count_is_three"],
                all(static["flag_checks"].values()),
                all(static["ordering_checks"].values()),
                static["fresh_task2_loader_after_driver_restore"],
                all(bool(item.get("pass")) for item in behavioral.values()),
            ]
            return 0 if all(checks) else 2
        return 0
    except Exception as exc:
        print(json.dumps({"probe": "independent_probe.py", "verdict": "PROBE_ERROR", "error": repr(exc)}, ensure_ascii=False, indent=2))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
