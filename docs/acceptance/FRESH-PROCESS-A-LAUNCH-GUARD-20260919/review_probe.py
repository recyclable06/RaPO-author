"""Read-only independent review of the frozen A launch-guard candidate.

This probe hashes the frozen candidate, re-runs its standard-library fixture
tests without invoking the candidate's file-writing test entry point, compares
the A-only recipe with the frozen v9 identity, and records static timeout/Ray
lifecycle evidence.  It does not start Ray, SSH, GPU work, a model, or the
production subprocess.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


WORKSPACE = Path(r"C:/Users/Administrator/Desktop/RaPO-author")
CANDIDATE = Path(r"C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/acceptance/FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919")
PARENT = CANDIDATE.parent / "FRESH-PROCESS-A-OBSERVER-RUNTIME-CANDIDATE-20260919"
V9 = Path(r"C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v9")
SOURCE = Path(r"C:/Users/Administrator/.codex/worktrees/8ac5/RaPO-author")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def line_number(path: Path, pattern: str) -> int | None:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if re.search(pattern, line):
            return number
    return None


def candidate_hash_check() -> dict[str, Any]:
    hashes_path = CANDIDATE / "HASHES_LAUNCH_GUARD.json"
    payload = load(hashes_path)
    bad: list[str] = []
    actual_total = 0
    for item in payload["files"]:
        path = CANDIDATE / item["path"]
        if not path.is_file():
            bad.append(item["path"])
            continue
        actual_bytes = path.stat().st_size
        actual_sha = sha256(path)
        actual_total += actual_bytes
        if actual_bytes != int(item["bytes"]) or actual_sha != item["sha256"]:
            bad.append(item["path"])
    return {
        "declared_file_count": len(payload["files"]),
        "declared_total_bytes": payload["total_bytes"],
        "actual_total_bytes": actual_total,
        "bad_files": bad,
        "hashes_self_sha256": sha256(hashes_path),
        "self_excluded": payload.get("self_excluded"),
    }


def import_local_tests() -> dict[str, Any]:
    sys.path.insert(0, str(CANDIDATE))
    import run_launch_guard_tests  # type: ignore[import-not-found]

    # run(), unlike main(), does not overwrite the candidate's test-results.json.
    return run_launch_guard_tests.run()


def import_old_launcher() -> Any:
    sys.path.insert(0, str(V9))
    spec = importlib.util.spec_from_file_location("old_run_v9_for_review", V9 / "run_v9.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen v9 run_v9.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def normalized_a_argv(argv: list[str]) -> list[str]:
    result = list(argv)
    if "--launch_script" in result:
        index = result.index("--launch_script")
        if index + 1 < len(result):
            result[index + 1] = "<launcher>"
    return result


def identity_and_recipe_check() -> dict[str, Any]:
    launch_manifest = load(CANDIDATE / "LAUNCH_GUARD_MANIFEST.json")
    contract = load(CANDIDATE / "A_ONLY_RUN_MANIFEST.json")
    expected = load(V9 / "EXPECTED_IDENTITY_v9.json")
    parent_manifest = PARENT / "RUNTIME_CANDIDATE_MANIFEST.json"
    production_entry = SOURCE / "examples/baselines/img_cls_cil/image_cls_cil_rapo.py"
    command_text = (CANDIDATE / "A_ONLY_LAUNCH_COMMAND.md").read_text(encoding="utf-8")
    candidate_launcher = importlib.import_module("run_v9")
    old_launcher = import_old_launcher()
    dummy_config = V9 / "PPO_CONFIG_TEMPLATE_v9.json"
    dummy_output = CANDIDATE / "<review-output>"
    dummy_cfg = SOURCE / "scripts/image/rapo_cfg.json"
    candidate_argv = candidate_launcher.build_production_argv(
        source_root=SOURCE,
        config=dummy_config,
        output_root=dummy_output,
        cil_cfg=dummy_cfg,
    )
    old_argv = old_launcher.build_production_argv(
        leg="A",
        source_root=SOURCE,
        config=dummy_config,
        output_root=dummy_output,
        cil_cfg=dummy_cfg,
    )
    expected_recipe = expected["recipe"]
    contract_recipe = contract["recipe"]
    recipe_fields = ("world_size", "rollout_n", "total_epochs", "max_steps", "task1_updates", "task2_updates", "save_model_only")
    expected_effective_recipe = dict(expected_recipe)
    expected_effective_recipe["task1_updates"] = expected_recipe["loader_policy"]["task1_updates"]
    expected_effective_recipe["task2_updates"] = expected_recipe["loader_policy"]["task2_updates"]
    recipe_matches = all(contract_recipe.get(key) == expected_effective_recipe.get(key) for key in recipe_fields)
    return {
        "parent_manifest_actual_sha256": sha256(parent_manifest),
        "parent_manifest_declared_sha256": launch_manifest["observer_snapshot"]["manifest_sha256"],
        "frozen_v9_hashes_actual_sha256": sha256(V9 / "HASHES_v9.json"),
        "frozen_v9_hashes_declared_sha256": launch_manifest["frozen_v9"]["hashes_sha256"],
        "production_entry_actual_sha256": sha256(production_entry),
        "production_entry_declared_sha256": launch_manifest["production"]["sha256"],
        "production_entry_bytes": production_entry.stat().st_size,
        "expected_recipe": expected_effective_recipe,
        "contract_recipe": contract_recipe,
        "recipe_matches_frozen_expected_identity": recipe_matches,
        "model_and_input_paths_match_frozen_expected_identity": contract.get("path_policy", {}).get("model_and_input_must_equal_EXPECTED_IDENTITY_v9") is True and expected["model"]["path"] in command_text and expected["input"]["root"] in command_text,
        "model_path": expected["model"]["path"],
        "input_path": expected["input"]["root"],
        "cil_cfg_relative": expected["config_bindings"]["cil_cfg"],
        "candidate_a_argv_matches_frozen_v9_after_launcher_path_normalization": normalized_a_argv(candidate_argv) == normalized_a_argv(old_argv),
        "candidate_a_argv": candidate_argv,
        "frozen_v9_a_argv": old_argv,
    }


def static_contract_review() -> dict[str, Any]:
    guard_path = CANDIDATE / "guard_support.py"
    launcher_path = CANDIDATE / "run_v9.py"
    command_path = CANDIDATE / "A_ONLY_LAUNCH_COMMAND.md"
    guard_text = guard_path.read_text(encoding="utf-8")
    launcher_text = launcher_path.read_text(encoding="utf-8")
    command_text = command_path.read_text(encoding="utf-8")
    timeout_tree = ast.parse(launcher_text, filename=str(launcher_path))
    communicate_calls: list[dict[str, Any]] = []
    for node in ast.walk(timeout_tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "communicate":
            communicate_calls.append({
                "line": node.lineno,
                "has_timeout_keyword": any(keyword.arg == "timeout" for keyword in node.keywords),
            })
    ray_start_tokens = [token for token in ("ray start", "ray.init", "ray.init(") if token in command_text or token in launcher_text or token in guard_text]
    ray_stop_tokens = [token for token in ("ray stop", "ray.shutdown", "supervisor", "cleanup") if token in command_text or token in launcher_text or token in guard_text]
    return {
        "guard_timeout_seconds_line": line_number(guard_path, r'"timeout_seconds": 1920'),
        "guard_production_timeout_line": line_number(guard_path, r'"production_timeout_seconds": 1800'),
        "guard_cleanup_grace_line": line_number(guard_path, r'"cleanup_grace_seconds": 120'),
        "launcher_process_popen_line": line_number(launcher_path, r"subprocess\.Popen"),
        "launcher_first_communicate_line": line_number(launcher_path, r"communicate\(timeout="),
        "launcher_kill_line": line_number(launcher_path, r"process\.kill\(\)"),
        "launcher_timeout_tail_communicate_line": line_number(launcher_path, r"tail_stdout, tail_stderr = process\.communicate\(\)"),
        "communicate_calls": communicate_calls,
        "timeout_contract": {
            "guard_timeout_seconds": 1920,
            "declared_production_timeout_seconds": 1800,
            "declared_cleanup_grace_seconds": 120,
            "uses_1800_plus_120_as_separate_deadlines": False,
            "timeout_exception_cleanup_is_bounded": False,
        },
        "ray_address_nonempty_check_line": line_number(guard_path, r"if not str\(ray_address\)\.strip\(\)"),
        "ray_address_command_line": line_number(command_path, r"FRESH_RAY_ADDRESS"),
        "ray_address_placeholder": "FRESH_RAY_ADDRESS",
        "command_says_existing_ray": "existing-Ray" in command_text,
        "ray_start_or_init_tokens": ray_start_tokens,
        "ray_stop_or_supervisor_tokens": ray_stop_tokens,
        "dedicated_ray_lifecycle_owner_declared": False,
        "ray_lifecycle_gap": True,
    }


def remote_evidence_review() -> dict[str, Any]:
    guard = (CANDIDATE / "raw/remote-211-guard-check.stdout.txt").read_text(encoding="utf-8").strip()
    precheck = (CANDIDATE / "raw/remote-211-path-precheck.stdout.txt").read_text(encoding="utf-8").strip()
    return {
        "guard_check": json.loads(guard),
        "path_precheck": json.loads(precheck),
        "evidence_boundary": {
            "python_only": True,
            "popen_production_run_performed": False,
            "ray_started": False,
            "model_loaded": False,
            "training_started": False,
        },
    }


def main() -> None:
    local = import_local_tests()
    result = {
        "schema": "fresh-process-a-launch-guard-independent-review-v1",
        "reviewed_at": "2026-09-19",
        "source_candidate": str(CANDIDATE),
        "source_frozen_v9": str(V9),
        "source_production_fixture": str(SOURCE),
        "candidate_hash_check": candidate_hash_check(),
        "local_standard_library_tests": local,
        "identity_and_recipe_check": identity_and_recipe_check(),
        "static_contract_review": static_contract_review(),
        "remote_evidence_review": remote_evidence_review(),
        "scope": {
            "read_only_review": True,
            "new_ssh": False,
            "ray_started": False,
            "gpu_used": False,
            "model_loaded": False,
            "training_invoked": False,
            "production_modified": False,
            "frozen_v9_modified": False,
        },
        "verdict": "NOT_READY_FOR_BOUNDED_A_ONLY",
        "open_findings": [
            "FINDING-A-TIMEOUT-CONTRACT-003",
            "FINDING-A-RAY-LIFECYCLE-004",
        ],
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
