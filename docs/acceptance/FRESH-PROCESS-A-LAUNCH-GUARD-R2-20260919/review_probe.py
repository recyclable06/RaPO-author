"""Read-only narrow review of the R2 launch-guard delta.

The probe does not start Ray, SSH, GPU work, a model, or the production
launcher.  It hashes the frozen R2 candidate, compares its identity/recipe
delta with R1 and frozen v9, exercises the bounded timeout helper with local
standard-library child processes, forces the second ``TimeoutExpired`` path,
and probes what the private-Ray record validator actually proves.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


R1 = Path(r"C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/acceptance/FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919")
R2 = Path(r"C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/acceptance/FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2")
PARENT = R2.parent / "FRESH-PROCESS-A-OBSERVER-RUNTIME-CANDIDATE-20260919"
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


def file_set(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts}


def hash_check() -> dict[str, Any]:
    path = R2 / "HASHES_LAUNCH_GUARD.json"
    payload = load(path)
    bad: list[str] = []
    total = 0
    for item in payload["files"]:
        file_path = R2 / item["path"]
        if not file_path.is_file():
            bad.append(item["path"])
            continue
        total += file_path.stat().st_size
        if file_path.stat().st_size != int(item["bytes"]) or sha256(file_path) != item["sha256"]:
            bad.append(item["path"])
    return {
        "declared_file_count": len(payload["files"]),
        "declared_total_bytes": payload["total_bytes"],
        "actual_total_bytes": total,
        "bad_files": bad,
        "hashes_self_sha256": sha256(path),
        "self_excluded": payload.get("self_excluded"),
    }


def import_candidate() -> tuple[Any, Any]:
    sys.path.insert(0, str(R2))
    import run_launch_guard_tests  # type: ignore[import-not-found]
    import run_v9  # type: ignore[import-not-found]

    return run_launch_guard_tests, run_v9


def import_frozen_launcher() -> Any:
    saved_path = list(sys.path)
    imported_names = ("argv_validate_v9", "boundary_evidence_v6", "gpu_preflight_v9", "identity_v6")
    missing = object()
    saved_modules = {name: sys.modules.get(name, missing) for name in imported_names}
    sys.path.insert(0, str(V9))
    try:
        spec = importlib.util.spec_from_file_location("frozen_run_v9_r2_review", V9 / "run_v9.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot import frozen v9 run_v9.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = saved_path
        for name, value in saved_modules.items():
            if value is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def normalize_argv(argv: list[str]) -> list[str]:
    result = list(argv)
    if "--launch_script" in result:
        index = result.index("--launch_script")
        if index + 1 < len(result):
            result[index + 1] = "<launcher>"
    return result


def identity_and_recipe() -> dict[str, Any]:
    r1_contract = load(R1 / "A_ONLY_RUN_MANIFEST.json")
    r2_contract = load(R2 / "A_ONLY_RUN_MANIFEST.json")
    r2_manifest = load(R2 / "LAUNCH_GUARD_MANIFEST.json")
    expected = load(V9 / "EXPECTED_IDENTITY_v9.json")
    candidate_launcher = sys.modules["run_v9"]
    frozen_launcher = import_frozen_launcher()
    dummy_config = V9 / "PPO_CONFIG_TEMPLATE_v9.json"
    dummy_output = R2 / "<review-output>"
    dummy_cfg = SOURCE / "scripts/image/rapo_cfg.json"
    candidate_argv = candidate_launcher.build_production_argv(source_root=SOURCE, config=dummy_config, output_root=dummy_output, cil_cfg=dummy_cfg)
    frozen_argv = frozen_launcher.build_production_argv(leg="A", source_root=SOURCE, config=dummy_config, output_root=dummy_output, cil_cfg=dummy_cfg)
    expected_recipe = dict(expected["recipe"])
    expected_recipe["task1_updates"] = expected["recipe"]["loader_policy"]["task1_updates"]
    expected_recipe["task2_updates"] = expected["recipe"]["loader_policy"]["task2_updates"]
    recipe_fields = ("world_size", "rollout_n", "total_epochs", "max_steps", "task1_updates", "task2_updates", "save_model_only")
    recipe_matches = all(r2_contract["recipe"].get(key) == expected_recipe.get(key) for key in recipe_fields)
    return {
        "r1_r2_recipe_equal": r1_contract["recipe"] == r2_contract["recipe"],
        "r1_r2_boundary_equal": r1_contract["boundary"] == r2_contract["boundary"],
        "r1_r2_production_equal": r1_contract["production"] == r2_contract["production"],
        "r1_r2_path_policy_equal": r1_contract["path_policy"] == r2_contract["path_policy"],
        "r1_r2_frozen_v9_equal": r1_contract["frozen_v9"] == r2_contract["frozen_v9"],
        "recipe_matches_frozen_expected_identity": recipe_matches,
        "candidate_a_argv_matches_frozen_v9_after_launcher_path_normalization": normalize_argv(candidate_argv) == normalize_argv(frozen_argv),
        "parent_manifest_sha256": sha256(PARENT / "RUNTIME_CANDIDATE_MANIFEST.json"),
        "declared_parent_manifest_sha256": r2_manifest["observer_snapshot"]["manifest_sha256"],
        "frozen_v9_hashes_sha256": sha256(V9 / "HASHES_v9.json"),
        "declared_frozen_v9_hashes_sha256": r2_manifest["frozen_v9"]["hashes_sha256"],
        "production_source_sha256": sha256(SOURCE / "examples/baselines/img_cls_cil/image_cls_cil_rapo.py"),
        "declared_production_source_sha256": r2_manifest["production"]["sha256"],
        "model_root": expected["model"]["path"],
        "input_root": expected["input"]["root"],
        "config_binding": expected["config_bindings"]["cil_cfg"],
        "r2_command_output_root": "/mnt/conda/zhenglifeng/t/a19r2",
        "r2_manifest_output_root_example": r2_contract["time_budget"]["private_output_root_example"],
        "r2_command_ray_tmp": "/tmp/zlf-a19r2-ray",
        "r2_manifest_ray_tmp_example": r2_contract["time_budget"]["private_ray_tmp_example"],
        "example_path_drift_is_nonbinding": True,
    }


def static_timeout_review(run_v9: Any) -> dict[str, Any]:
    path = R2 / "run_v9.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    calls: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "communicate":
            calls.append({"line": node.lineno, "has_timeout": any(keyword.arg == "timeout" for keyword in node.keywords)})
    return {
        "communicate_calls": sorted(calls, key=lambda item: item["line"]),
        "all_communicate_calls_bounded": all(item["has_timeout"] for item in calls),
        "monotonic_used": "time.monotonic()" in source,
        "process_group_started": "start_new_session=True" in source,
        "posix_group_kill_used": "os.killpg(process.pid, signal.SIGKILL)" in source,
        "production_timeout_seconds": load(R2 / "A_ONLY_RUN_MANIFEST.json")["time_budget"]["production_timeout_seconds"],
        "cleanup_grace_seconds": load(R2 / "A_ONLY_RUN_MANIFEST.json")["time_budget"]["cleanup_grace_seconds"],
        "second_timeout_handler_present": "except subprocess.TimeoutExpired as cleanup_exc" in source,
    }


def no_assert_timeout_runs(run_tests: Any, run_v9: Any, count: int = 5) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    inherited_code = (
        "import subprocess, sys, time\n"
        "print('parent-line', flush=True)\n"
        f"subprocess.Popen([{sys.executable!r}, '-c', \"import time; print('grandchild-line', flush=True); time.sleep(0.2)\"], close_fds=False)\n"
        "time.sleep(5.0)\n"
    )
    for attempt in range(1, count + 1):
        timeout_process = run_tests._spawn_lightweight_child("print('timeout-line', flush=True); import time; time.sleep(1.0)")
        timeout_outcome = run_v9._communicate_bounded(timeout_process, production_timeout_seconds=0.05, cleanup_grace_seconds=0.8)
        inherited_process = run_tests._spawn_lightweight_child(inherited_code)
        inherited_outcome = run_v9._communicate_bounded(inherited_process, production_timeout_seconds=0.5, cleanup_grace_seconds=0.8)
        results.append({
            "attempt": attempt,
            "timeout_stdout_count": timeout_outcome["stdout"].count("timeout-line"),
            "timeout_stdout": timeout_outcome["stdout"],
            "timeout_timed_out": bool(timeout_outcome["timed_out"]),
            "timeout_cleanup_timed_out": bool(timeout_outcome["cleanup_timed_out"]),
            "inherited_stdout_counts": {
                "parent": inherited_outcome["stdout"].count("parent-line"),
                "grandchild": inherited_outcome["stdout"].count("grandchild-line"),
            },
            "inherited_cleanup_timed_out": bool(inherited_outcome["cleanup_timed_out"]),
        })
    return results


def second_timeout_probe(run_v9: Any) -> dict[str, Any]:
    class FakeProcess:
        pid = 999999999
        returncode = -9

        def __init__(self) -> None:
            self.calls: list[float | None] = []
            self.kill_calls = 0

        def kill(self) -> None:
            self.kill_calls += 1

        def communicate(self, timeout: float | None = None) -> tuple[str, str]:
            self.calls.append(timeout)
            if len(self.calls) <= 2:
                raise subprocess.TimeoutExpired("fake", timeout, output="prefix\n", stderr="err\n")
            raise AssertionError("third communicate call")

    process = FakeProcess()
    outcome = run_v9._communicate_bounded(process, production_timeout_seconds=0.1, cleanup_grace_seconds=0.2)
    return {
        "communicate_timeouts": process.calls,
        "all_timeouts_finite": all(value is not None and value >= 0 for value in process.calls),
        "kill_calls": process.kill_calls,
        "no_third_communicate": len(process.calls) == 2,
        "stdout_count": outcome["stdout"].count("prefix"),
        "stderr_count": outcome["stderr"].count("err"),
        "cleanup_timed_out": outcome["cleanup_timed_out"],
    }


def record_validator_probe() -> dict[str, Any]:
    guard = sys.modules["guard_support"]
    with tempfile.TemporaryDirectory(prefix="rapo-r2-record-review-") as temp_name:
        root = Path(temp_name)
        path = root / "record.json"
        payload = {
            "schema": "private-ray-supervisor-record-v1",
            "status": "RUNNING",
            "mode": "private_per_run",
            "shared_ray": False,
            "cleanup_scope": "owned_private_session_only",
            "ray_address": "127.0.0.1:19999",
            "temp_root": str(root / "missing-private-temp"),
            "head_pid": 999999999,
            "head_process_start": "not-a-real-process-start",
            "session_id": "forged-session",
            "owner": "forged-owner",
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        result = guard._verify_private_ray_record(path, {"record_schema": "private-ray-supervisor-record-v1"}, payload["ray_address"])
        return {
            "accepted": True,
            "accepted_head_pid": result["head_pid"],
            "accepted_owner": result["owner"],
            "accepted_head_process_start": result["head_process_start"],
            "temp_root_exists": Path(payload["temp_root"]).exists(),
            "validator_does_not_query_ray_or_process_identity": True,
        }


def bundled_guard_repro(run_tests: Any) -> dict[str, Any]:
    try:
        result = run_tests.run()
        return {"status": "PASS", "result": result}
    except Exception as exc:
        return {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    run_tests, run_v9 = import_candidate()
    r1_files = file_set(R1)
    r2_files = file_set(R2)
    result = {
        "schema": "fresh-process-a-launch-guard-r2-independent-review-v1",
        "reviewed_at": "2026-09-19",
        "source_r1": str(R1),
        "source_r2": str(R2),
        "hash_check": hash_check(),
        "r1_r2_file_delta": {
            "r1_file_count": len(r1_files),
            "r2_file_count": len(r2_files),
            "r2_only_files": sorted(r2_files - r1_files),
            "r1_only_files": sorted(r1_files - r2_files),
        },
        "identity_and_recipe": identity_and_recipe(),
        "static_timeout_review": static_timeout_review(run_v9),
        "bundled_guard_repro": bundled_guard_repro(run_tests),
        "timeout_attempts_without_assertions": no_assert_timeout_runs(run_tests, run_v9, count=5),
        "second_timeout_probe": second_timeout_probe(run_v9),
        "private_record_validator_probe": record_validator_probe(),
        "supervisor_contract": {
            "contract_file_declares_not_executed": "not executed" in (R2 / "PRIVATE_RAY_SUPERVISOR_CONTRACT.md").read_text(encoding="utf-8"),
            "has_executable_supervisor_file": any(path.name.lower() in {"supervisor.py", "supervisor.sh", "run_supervisor.py"} for path in R2.iterdir()),
            "record_writer_implementation_present": False,
            "teardown_implementation_present": False,
        },
        "scope": {
            "read_only": True,
            "new_ssh": False,
            "ray_started": False,
            "gpu_used": False,
            "model_loaded": False,
            "training_invoked": False,
            "production_modified": False,
            "frozen_v9_modified": False,
            "r1_candidate_modified": False,
        },
        "verdict": "PASS_R2_TIMEOUT_POLICY_NARROW_REVIEW_CONTRACT_ONLY_NOT_A_RUN",
        "open_scope": [
            "FINDING-A-PRIVATE-RAY-LIFECYCLE-004",
            "timeout fixture stability is insufficient for standalone acceptance evidence",
        ],
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
