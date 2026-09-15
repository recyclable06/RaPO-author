from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import types
from pathlib import Path


ROOT = Path(r"C:\Users\Administrator\.codex\worktrees\8ac5\RaPO-author")
SOURCE = ROOT / "examples" / "baselines" / "img_cls_cil" / "image_cls_cil_rapo.py"
TEST = ROOT / "tests" / "author_fixes" / "test_cil_resume.py"
R2 = ROOT / "docs" / "remediation" / "CAND-RESUME-CIL-001" / "r2"
INTEGRATION = Path(r"C:\Users\Administrator\.codex\worktrees\5ced\RaPO-author")

EXPECTED = {
    "source_bytes": 99349,
    "source_sha256": "ba8a5da9341785178bd444112c4fc78dd352b52fe359b768218f4a4a6f5f7863",
    "test_bytes": 14217,
    "test_sha256": "331e62782cc63ef9a2fb4d2de1afe921593f629309f263c6728a7de5299e3f64",
    "r2_hashes_sha256": "3c626bad55777ab9c9e217635bd9c81371fa40bf938eb3a66b221f51df81a43a",
    "r1_source_sha256": "23cbb3c01f69704eb304c2b9c884d8165a9783a913422d6e679e63bb42d71928",
    "r1_test_sha256": "a8b17b247eac0526108fbd7388af9b98946752bb8214d24229f00121bd200896",
    "integration_manifest_sha256": "6514f4dca401ffc805ae57031d1926f742e531ce0fbb981448315538ade8b0b1",
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


def first_line(path: Path, needle: str) -> int | None:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if needle in line:
            return number
    return None


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
        "hashlib": hashlib,
        "json": json,
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


def call_records(path: Path, wanted_attrs: set[str]) -> list[dict[str, object]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    records: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            call_name = node.func.attr
            callee = ast.unparse(node.func)
        elif isinstance(node.func, ast.Name):
            call_name = node.func.id
            callee = call_name
        else:
            continue
        if call_name not in wanted_attrs:
            continue
        records.append(
            {
                "line": node.lineno,
                "callee": callee,
                "keywords": sorted(
                    keyword.arg for keyword in node.keywords if keyword.arg is not None
                ),
            }
        )
    return sorted(records, key=lambda item: (int(item["line"]), str(item["callee"])))


def model_config_fields(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ModelConfig":
            fields: list[str] = []
            for child in node.body:
                if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                    fields.append(child.target.id)
                elif isinstance(child, ast.Assign):
                    fields.extend(
                        target.id for target in child.targets if isinstance(target, ast.Name)
                    )
            return fields
    return []


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


def run() -> dict[str, object]:
    source_text = SOURCE.read_text(encoding="utf-8")
    source_tree = ast.parse(source_text, filename=str(SOURCE))
    test_tree = ast.parse(TEST.read_text(encoding="utf-8"), filename=str(TEST))
    r2_manifest_path = R2 / "HASHES.json"
    r2_manifest = json.loads(r2_manifest_path.read_text(encoding="utf-8"))
    r2_artifact_results = []
    for item in r2_manifest["r2_artifacts"]:
        path = R2 / item["path"]
        actual = artifact_record(path) if path.is_file() else {"bytes": None, "sha256": None}
        r2_artifact_results.append(
            {
                "path": item["path"],
                "declared": {"bytes": item["bytes"], "sha256": item["sha256"]},
                "actual": actual,
                "match": actual == {"bytes": item["bytes"], "sha256": item["sha256"]},
            }
        )

    identities = {
        "target_source": {"path": str(SOURCE), **artifact_record(SOURCE)},
        "target_test": {"path": str(TEST), **artifact_record(TEST)},
        "target_source_expected": {
            "bytes": EXPECTED["source_bytes"],
            "sha256": EXPECTED["source_sha256"],
        },
        "target_test_expected": {
            "bytes": EXPECTED["test_bytes"],
            "sha256": EXPECTED["test_sha256"],
        },
        "target_files_match_expected": (
            artifact_record(SOURCE)
            == {"bytes": EXPECTED["source_bytes"], "sha256": EXPECTED["source_sha256"]}
            and artifact_record(TEST)
            == {"bytes": EXPECTED["test_bytes"], "sha256": EXPECTED["test_sha256"]}
        ),
        "r2_hashes": {
            "path": str(r2_manifest_path),
            "actual_sha256": sha256_file(r2_manifest_path),
            "expected_sha256": EXPECTED["r2_hashes_sha256"],
            "self_hash_matches": sha256_file(r2_manifest_path) == EXPECTED["r2_hashes_sha256"],
            "artifacts": r2_artifact_results,
            "all_artifacts_match": all(item["match"] for item in r2_artifact_results),
        },
        "frozen_inputs": {
            "source": {
                "bytes": (R2 / "inputs" / "image_cls_cil_rapo.py").stat().st_size,
                "sha256": sha256_file(R2 / "inputs" / "image_cls_cil_rapo.py"),
            },
            "test": {
                "bytes": (R2 / "inputs" / "test_cil_resume.py").stat().st_size,
                "sha256": sha256_file(R2 / "inputs" / "test_cil_resume.py"),
            },
        },
        "integration_manifest": {
            "path": str(INTEGRATION / "docs" / "INTEGRATION_HASHES.json"),
            "sha256": sha256_file(INTEGRATION / "docs" / "INTEGRATION_HASHES.json"),
            "expected_sha256": EXPECTED["integration_manifest_sha256"],
        },
    }

    funcs = compile_target_functions(
        source_tree,
        [
            "_sha256_bytes",
            "_sha256_file",
            "_safe_join",
            "_path_within",
            "_path_overlaps_roots",
            "_artifact_manifest",
            "_manifest_hash",
            "_validate_artifact_manifest",
            "_path_identity",
            "_model_identity",
            "_source_identity",
            "_canonical_json_bytes",
        ],
    )

    with tempfile.TemporaryDirectory(prefix="cil-resume-r2-probe-", dir=str(Path.cwd())) as temp_name:
        temp_root = Path(temp_name)

        valid_root = temp_root / "valid-checkpoint"
        make_full_checkpoint(valid_root)
        valid_manifest = funcs["_artifact_manifest"](str(valid_root))
        valid_hash = funcs["_validate_artifact_manifest"](
            str(valid_root), valid_manifest, label="checkpoint"
        )
        valid_case = {"pass": True, "manifest_sha256": valid_hash, "file_count": len(valid_manifest)}

        missing_loader_root = temp_root / "missing-dataloader"
        make_full_checkpoint(missing_loader_root, include_dataloader=False)
        missing_loader_manifest = funcs["_artifact_manifest"](str(missing_loader_root))
        try:
            funcs["_validate_artifact_manifest"](
                str(missing_loader_root), missing_loader_manifest, label="checkpoint"
            )
        except CILBoundaryError as exc:
            missing_loader_case = {"pass": True, "error": str(exc)}
        else:
            missing_loader_case = {"pass": False, "error": "validator accepted missing dataloader.pt"}

        missing_rank_root = temp_root / "missing-rank-optim"
        make_full_checkpoint(missing_rank_root, missing_rank_optim=True)
        missing_rank_manifest = funcs["_artifact_manifest"](str(missing_rank_root))
        try:
            funcs["_validate_artifact_manifest"](
                str(missing_rank_root), missing_rank_manifest, label="checkpoint"
            )
        except CILBoundaryError as exc:
            missing_rank_case = {"pass": True, "error": str(exc)}
        else:
            missing_rank_case = {"pass": False, "error": "validator accepted missing native rank optimizer"}

        model_root = temp_root / "model"
        model_root.mkdir()
        (model_root / "config.json").write_text("{}", encoding="utf-8")
        (model_root / "model.safetensors").write_bytes(b"AAAA")
        model_config = types.SimpleNamespace(
            worker=types.SimpleNamespace(
                actor=types.SimpleNamespace(
                    model=types.SimpleNamespace(model_path=str(model_root), revision=None)
                )
            )
        )
        model_before = funcs["_model_identity"](model_config)
        (model_root / "model.safetensors").write_bytes(b"AAAB")
        model_after = funcs["_model_identity"](model_config)
        model_mutation_case = {
            "pass": model_before["hash"] != model_after["hash"],
            "same_size_before": 4,
            "same_size_after": (model_root / "model.safetensors").stat().st_size,
            "before_hash": model_before["hash"],
            "after_hash": model_after["hash"],
        }

        remote_config = types.SimpleNamespace(
            worker=types.SimpleNamespace(
                actor=types.SimpleNamespace(
                    model=types.SimpleNamespace(
                        model_path="org/model",
                        revision="0123456789abcdef0123456789abcdef01234567",
                    )
                )
            )
        )
        remote_identity = funcs["_model_identity"](remote_config)

        task1 = temp_root / "task_1"
        (task1 / "global_step_1").mkdir(parents=True)
        (task1 / "global_step_2").mkdir(parents=True)
        run_node = function_node(source_tree, "_run_cil")
        pruning_nodes = {
            node.lineno: node
            for node in ast.walk(run_node)
            if isinstance(node, ast.If) and node.lineno in {1899, 1915, 1956}
        }
        current_prune = compile_pruning_node(pruning_nodes[1899], funcs, "current_pruning_fixture")
        previous_prune = compile_pruning_node(pruning_nodes[1915], funcs, "previous_pruning_fixture")
        known_args = types.SimpleNamespace(save_task_ckpt="latest")
        protected = [str(task1)]
        try:
            current_prune(
                known_args,
                str(task1 / "global_step_2"),
                str(task1),
                protected,
                None,
            )
        except CILBoundaryError as exc:
            current_prune_case = {"pass": True, "error": str(exc)}
        else:
            current_prune_case = {"pass": False, "error": "current pruning did not raise"}

        task2 = temp_root / "task_2"
        (task2 / "global_step_3").mkdir(parents=True)
        try:
            previous_prune(
                known_args,
                str(task2 / "global_step_3"),
                str(task2),
                protected,
                str(task1),
            )
        except CILBoundaryError as exc:
            continuation_prune_case = {"pass": True, "error": str(exc)}
        else:
            continuation_prune_case = {"pass": False, "error": "previous-task pruning did not raise"}

    source_identity = funcs["_source_identity"]()
    source_paths = {item["path"] for item in source_identity["files"]}
    missing_runtime_dependencies = [
        path
        for path in (
            "verl/models/monkey_patch.py",
            "verl/models/transformers/qwen2_vl.py",
            "examples/reward_function/cls.py",
        )
        if path not in source_paths
    ]

    fsdp_path = ROOT / "verl" / "workers" / "fsdp_workers.py"
    reward_path = ROOT / "verl" / "workers" / "reward" / "function.py"
    tokenizer_path = ROOT / "verl" / "utils" / "tokenizer.py"
    rollout_path = ROOT / "verl" / "workers" / "rollout" / "vllm_rollout_spmd.py"
    config_path = ROOT / "verl" / "workers" / "actor" / "config.py"
    native_calls = call_records(fsdp_path, {"from_pretrained"})
    tokenizer_calls = call_records(tokenizer_path, {"from_pretrained"})
    rollout_calls = call_records(rollout_path, {"LLM"})
    all_native_revision_calls = native_calls + tokenizer_calls
    native_revision_consumed = bool(all_native_revision_calls) and all(
        "revision" in record["keywords"] for record in all_native_revision_calls
    )
    config_fields = model_config_fields(config_path)
    source_has_revision_producer = (
        'getattr(model_cfg, "revision", None)' in source_text
        and 'getattr(model_cfg, "model_revision", None)' in source_text
    )
    reward_config_text = (ROOT / "examples" / "config.yaml").read_text(encoding="utf-8")
    reward_spec_match = re.search(r"reward_function:\s*([^\s#]+)", reward_config_text)
    reward_spec = reward_spec_match.group(1) if reward_spec_match else None
    source_audit = {
        "manifest_file_count": len(source_identity["files"]),
        "manifest_sha256": source_identity["manifest_sha256"],
        "declared_roots": list(assignment_literal(source_tree, "_BOUNDARY_SOURCE_ROOTS")),
        "declared_explicit_files": list(assignment_literal(source_tree, "_BOUNDARY_SOURCE_FILES")),
        "missing_runtime_dependencies": missing_runtime_dependencies,
        "fsdp_worker_direct_model_patch_import_line": first_line(fsdp_path, "from ..models.monkey_patch"),
        "reward_config_spec": reward_spec,
        "reward_config_line": first_line(ROOT / "examples" / "config.yaml", "reward_function:"),
        "reward_dynamic_loader_line": first_line(reward_path, "spec_from_file_location"),
        "reward_file_present": (ROOT / "examples" / "reward_function" / "cls.py").is_file(),
        "model_patch_file_present": (ROOT / "verl" / "models" / "monkey_patch.py").is_file(),
    }

    native_revision_audit = {
        "producer_reads_revision": source_has_revision_producer,
        "model_config_fields": config_fields,
        "model_config_declares_revision": "revision" in config_fields,
        "producer_remote_identity_example": {
            "revision": remote_identity.get("revision"),
            "identity_hash": remote_identity.get("hash"),
        },
        "native_from_pretrained_calls": native_calls,
        "tokenizer_from_pretrained_calls": tokenizer_calls,
        "vllm_constructor_calls": rollout_calls,
        "native_loader_calls_pass_revision": native_revision_consumed,
        "consumer_revision_gap": not native_revision_consumed,
        "relevant_lines": {
            "fsdp_auto_config": first_line(fsdp_path, "AutoConfig.from_pretrained"),
            "fsdp_auto_class": first_line(fsdp_path, "AutoClass.from_pretrained"),
            "fsdp_generation_config": first_line(fsdp_path, "GenerationConfig.from_pretrained"),
            "tokenizer": first_line(tokenizer_path, "AutoTokenizer.from_pretrained"),
            "processor": first_line(tokenizer_path, "AutoProcessor.from_pretrained"),
            "vllm": first_line(rollout_path, "LLM("),
        },
    }

    current_prune_line = pruning_nodes[1899].lineno
    previous_prune_line = pruning_nodes[1915].lineno
    stop_if = next(
        node for node in ast.walk(run_node) if isinstance(node, ast.If) and node.lineno == 1948
    )
    has_break = any(isinstance(child, ast.Break) for child in ast.walk(stop_if))
    control_flow = {
        "current_pruning_node_line": current_prune_line,
        "previous_task_pruning_node_line": previous_prune_line,
        "stop_after_boundary_break_line": stop_if.lineno,
        "pruning_precedes_break": current_prune_line < stop_if.lineno and previous_prune_line < stop_if.lineno,
        "stop_if_contains_break": has_break,
        "current_task_multiple_checkpoint_fixture": current_prune_case,
        "continued_task_previous_root_fixture": continuation_prune_case,
        "published_root_is_registered_before_pruning_line": 1817,
        "boundary_marker_created_before_registration_line": 1815,
    }

    protocol_cases = {
        "valid_multi_rank_full_checkpoint": valid_case,
        "missing_dataloader_fails_closed": missing_loader_case,
        "missing_rank_optimizer_fails_closed": missing_rank_case,
        "same_size_local_model_content_mutation_changes_identity": model_mutation_case,
    }

    blockers = []
    if current_prune_case["pass"] or continuation_prune_case["pass"]:
        blockers.append(
            {
                "id": "CIL-CPU-002",
                "severity": "P2-gate",
                "finding": "The exact production pruning branches raise on a protected boundary path instead of skipping it; this reproduces failure before the stop-after-boundary break and again when a no-stop run prunes the previous Task-1 root.",
                "lines": "1899-1922",
            }
        )
    if not native_revision_consumed:
        blockers.append(
            {
                "id": "CIL-CPU-004",
                "severity": "spec-gap",
                "finding": "The producer accepts a remote 40-hex revision, but ModelConfig has no revision field and the native AutoConfig/AutoClass/tokenizer/vLLM loading calls do not pass revision, so the identity is not the revision actually consumed by the loader.",
                "lines": "image_cls_cil_rapo.py:399-419; fsdp_workers.py:178-219; tokenizer.py:21-45; vllm_rollout_spmd.py:114-130",
            }
        )
    if missing_runtime_dependencies:
        blockers.append(
            {
                "id": "CIL-CPU-005",
                "severity": "spec-gap",
                "finding": "The dynamic source manifest omits runtime production files used by the path: at least verl/models/monkey_patch.py and examples/reward_function/cls.py are loaded/imported but absent from the identity.",
                "lines": "fsdp_workers.py:42; examples/config.yaml:93; workers/reward/function.py:114-123",
            }
        )

    verdict = "FAIL_NOT_READY_FOR_GPU" if blockers else "PASS_READY_FOR_GPU"
    return {
        "schema_version": 2,
        "probe": "independent_probe.py",
        "target_root": str(ROOT),
        "source_ref": str(INTEGRATION),
        "scope": "independent R2 CPU/static acceptance; production and test read-only",
        "identities": identities,
        "control_flow": control_flow,
        "protocol_cases": protocol_cases,
        "source_identity_audit": source_audit,
        "model_revision_audit": native_revision_audit,
        "blocking_findings": blockers,
        "verdict": verdict,
        "fresh_process_resume": "not_accepted",
        "gpu_handoff": {
            "not_run": True,
            "required_after_remediation": [
                "Re-run the two OS-process Task-1 publisher and fresh Task-2 resume only after CPU/static blockers are fixed.",
                "Verify protected boundary roots are preserved without a pruning exception and the old boundary root is read-only.",
                "Verify the actual immutable model revision is passed to every native model/tokenizer/vLLM loader, or use a local content manifest.",
                "Verify the complete source/config manifest includes all runtime production and reward files, then run world-size-2 native restore and Task-2 first update.",
            ],
        },
        "test_tree": {
            "ast_parses": True,
            "new_test_file_bytes": TEST.stat().st_size,
            "new_test_file_sha256": sha256_file(TEST),
            "test_function_count": sum(
                1 for node in ast.walk(test_tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ),
        },
    }


if __name__ == "__main__":
    try:
        evidence = run()
        print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=False))
        raise SystemExit(2 if evidence["verdict"] == "FAIL_NOT_READY_FOR_GPU" else 0)
    except Exception as exc:
        print(
            json.dumps(
                {"probe": "independent_probe.py", "verdict": "PROBE_ERROR", "error": repr(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(3)
