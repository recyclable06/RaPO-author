"""Read-only narrow review of the private-Ray supervisor supplement.

This probe verifies the supplement identity, runs its standard-library fake
head/launcher tests through ``run()`` (without writing the candidate result),
and performs static/evidence-boundary checks.  It never starts Ray, SSH, GPU,
model, or the production launcher.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


SUPPLEMENT = Path(r"C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/acceptance/FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-SUPERVISOR-SUPPLEMENT")
ZERO_GPU = Path(r"C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/acceptance/FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-ZEROGPU-SUPPLEMENT")
CLI_PREFLIGHT = Path(r"C:/Users/Administrator/.codex/worktrees/71a6/RaPO-author/docs/diagnostics/RAY-CLI-ENTRY-PREFLIGHT-20260920")
R2 = Path(r"C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/acceptance/FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2")
PARENT = Path(r"C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/acceptance/FRESH-PROCESS-A-OBSERVER-RUNTIME-CANDIDATE-20260919")


def sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def line(path: Path, pattern: str) -> int | None:
    for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if re.search(pattern, text):
            return number
    return None


def hash_check() -> dict[str, Any]:
    hashes_path = SUPPLEMENT / "HASHES_SUPERVISOR.json"
    payload = load(hashes_path)
    bad: list[str] = []
    total = 0
    for item in payload["files"]:
        path = SUPPLEMENT / item["path"]
        if not path.is_file():
            bad.append(item["path"])
            continue
        total += path.stat().st_size
        if path.stat().st_size != int(item["bytes"]) or sha256(path) != item["sha256"]:
            bad.append(item["path"])
    manifest = load(SUPPLEMENT / "SUPERVISOR_MANIFEST.json")
    manifest_bad: list[str] = []
    for item in manifest["runtime_files"]:
        path = SUPPLEMENT / item["path"]
        if not path.is_file() or path.stat().st_size != int(item["bytes"]) or sha256(path) != item["sha256"]:
            manifest_bad.append(item["path"])
    return {
        "declared_file_count": len(payload["files"]),
        "declared_total_bytes": payload["total_bytes"],
        "actual_total_bytes": total,
        "bad_hash_files": bad,
        "hashes_self_sha256": sha256(hashes_path),
        "manifest_sha256": sha256(SUPPLEMENT / "SUPERVISOR_MANIFEST.json"),
        "manifest_runtime_bad_files": manifest_bad,
        "parent_r2_hashes_sha256": sha256(R2 / "HASHES_LAUNCH_GUARD.json"),
        "parent_observer_manifest_sha256": sha256(PARENT / "RUNTIME_CANDIDATE_MANIFEST.json"),
    }


def zero_gpu_hash_check() -> dict[str, Any]:
    hashes_path = ZERO_GPU / "HASHES_ZEROGPU.json"
    payload = load(hashes_path)
    bad: list[str] = []
    total = 0
    for item in payload["files"]:
        path = ZERO_GPU / item["path"]
        if not path.is_file():
            bad.append(item["path"])
            continue
        total += path.stat().st_size
        if path.stat().st_size != int(item["bytes"]) or sha256(path) != item["sha256"]:
            bad.append(item["path"])
    manifest = load(ZERO_GPU / "MANIFEST_ZEROGPU.json")
    manifest_bad: list[str] = []
    for group in ("runtime_files", "artifact_files"):
        for item in manifest[group]:
            path = ZERO_GPU / item["path"]
            if not path.is_file() or path.stat().st_size != int(item["bytes"]) or sha256(path) != item["sha256"]:
                manifest_bad.append(item["path"])
    return {
        "declared_file_count": payload["file_count"],
        "declared_total_bytes": payload["total_bytes"],
        "actual_declared_files_total_bytes": total,
        "bad_hash_files": bad,
        "hashes_self_sha256": sha256(hashes_path),
        "manifest_sha256": sha256(ZERO_GPU / "MANIFEST_ZEROGPU.json"),
        "manifest_bad_files": manifest_bad,
        "parent_supervisor_hashes_sha256": sha256(SUPPLEMENT / "HASHES_SUPERVISOR.json"),
    }


def cli_preflight_check() -> dict[str, Any]:
    summary = load(CLI_PREFLIGHT / "SUMMARY.json")
    hashes = load(CLI_PREFLIGHT / "HASHES.json")
    bad: list[str] = []
    total = 0
    for item in hashes["entries"]:
        path = CLI_PREFLIGHT / item["path"]
        if not path.is_file():
            bad.append(item["path"])
            continue
        total += path.stat().st_size
        if path.stat().st_size != int(item["bytes"]) or sha256(path) != item["sha256"]:
            bad.append(item["path"])
    entries = {item["entry"]: item for item in summary["entry_results"]}
    return {
        "artifact_file_count": hashes["file_count"],
        "artifact_total_bytes": hashes["total_bytes"],
        "artifact_actual_bytes": total,
        "artifact_bad_hash_files": bad,
        "hashes_self_sha256": sha256(CLI_PREFLIGHT / "HASHES.json"),
        "host": summary["host"],
        "python_version": summary["environment"]["python_version"],
        "ray_version": summary["environment"]["ray_version"],
        "python_module_ray_start_help_exit": entries["python -m ray start --help"]["exit_code"],
        "python_module_ray_status_help_exit": entries["python -m ray status --help"]["exit_code"],
        "python_module_ray_start_help_stderr": entries["python -m ray start --help"]["stderr"],
        "python_module_ray_status_help_stderr": entries["python -m ray status --help"]["stderr"],
        "ray_script_start_help_exit": entries["/mnt/conda/zhenglifeng/rapo-author-diagnostic-20260908/env/rapo-author/bin/ray start --help"]["exit_code"],
        "ray_script_status_help_exit": entries["/mnt/conda/zhenglifeng/rapo-author-diagnostic-20260908/env/rapo-author/bin/ray status --help"]["exit_code"],
        "ray_script_shebang": summary["script_shebang"],
        "service_started": summary["recommendation"]["service_started"],
    }


def run_fake_tests() -> dict[str, Any]:
    sys.path.insert(0, str(SUPPLEMENT))
    import run_supervisor_tests  # type: ignore[import-not-found]

    # run() writes only temporary directories; main() is intentionally not used.
    return run_supervisor_tests.run()


def run_zero_gpu_fake_tests() -> dict[str, Any]:
    sys.path.insert(0, str(ZERO_GPU))
    import run_zero_gpu_supervisor_tests  # type: ignore[import-not-found]

    return run_zero_gpu_supervisor_tests.run()


def static_review() -> dict[str, Any]:
    supervisor_path = SUPPLEMENT / "private_ray_supervisor.py"
    supervisor_text = supervisor_path.read_text(encoding="utf-8")
    command_text = (SUPPLEMENT / "SUPERVISOR_COMMAND.md").read_text(encoding="utf-8")
    zero_start = command_text.index("## Future real-Ray, zero-GPU lifecycle check")
    zero_end = command_text.index("## Future two-GPU A invocation")
    zero_command = command_text[zero_start:zero_end]
    r2_launcher_text = (R2 / "run_v9.py").read_text(encoding="utf-8")
    zero_gpu_text = (ZERO_GPU / "zero_gpu_supervisor.py").read_text(encoding="utf-8")
    zero_gpu_command_text = (ZERO_GPU / "ZERO_GPU_COMMAND.md").read_text(encoding="utf-8")
    zero_gpu_tests_text = (ZERO_GPU / "run_zero_gpu_supervisor_tests.py").read_text(encoding="utf-8")
    ray_available = importlib.util.find_spec("ray") is not None
    return {
        "real_mode_requires_linux_procfs": "sys.platform.startswith(\"linux\")" in supervisor_text and "Path(\"/proc\").is_dir()" in supervisor_text,
        "linux_identity_reads_proc_stat_status_cmdline_exe": all(token in supervisor_text for token in ('proc / "stat"', 'proc / "status"', 'proc / "cmdline"', 'proc / "exe"')),
        "record_atomic_replace": "os.replace(temporary, self.record_path)" in supervisor_text,
        "record_readback": "loaded != dict(payload)" in supervisor_text,
        "record_live_recheck": "self._assert_live_head_identity()" in supervisor_text and "_discover_owned_processes" in supervisor_text,
        "ray_head_command_uses_python_module_ray": all(token in supervisor_text for token in ('"-m"', '"ray"', '"start"', '"--head"', '"--block"')),
        "ray_status_command_uses_python_module_ray": all(token in supervisor_text for token in ('"-m", "ray", "status"', '"--address"')),
        "supervisor_manifest_checked_before_head_start": "SUPERVISOR_MANIFEST" in supervisor_text or "HASHES_SUPERVISOR" in supervisor_text,
        "supervisor_manifest_referenced_by_command": "SUPERVISOR_MANIFEST" in command_text or "HASHES_SUPERVISOR" in command_text,
        "signal_handlers_installed": "signal.signal(" in supervisor_text,
        "finally_block_in_execute": bool(re.search(r"def execute[\s\S]*?finally:", supervisor_text)),
        "head_stdout_pipe": "stdout=subprocess.PIPE" in supervisor_text,
        "head_stderr_pipe": "stderr=subprocess.PIPE" in supervisor_text,
        "head_pipe_read_during_wait": False,
        "head_logs_saved_only_after_cleanup": "ray-head.stdout.log" in supervisor_text and "communicate(timeout=0)" in supervisor_text,
        "supervisor_launcher_new_session": "**_creation_kwargs()" in supervisor_text,
        "r2_production_child_new_session": "start_new_session=True" in r2_launcher_text,
        "supervisor_process_discovery_includes_launcher_or_production": any(token in supervisor_text for token in ("launcher_pid", "production_pid", "_discover_launcher", "RAPO_DIAG_RUN_ROOT")),
        "launcher_group_kill_line": line(supervisor_path, r"def _kill_launcher_group"),
        "launcher_popen_line": line(supervisor_path, r"process = subprocess\.Popen\("),
        "r2_production_popen_line": line(R2 / "run_v9.py", r"process = subprocess\.Popen\("),
        "execute_line": line(supervisor_path, r"def execute"),
        "execute_exception_line": line(supervisor_path, r"except Exception as exc"),
        "parent_zero_gpu_command_uses_1800_seconds": "--production-timeout-seconds 1800" in zero_command,
        "parent_zero_gpu_command_sets_empty_cuda_visible_devices": bool(re.search(r"CUDA_VISIBLE_DEVICES\s*=\s*['\"]?['\"]?", zero_command)),
        "parent_zero_gpu_head_sets_num_gpus_zero": "--num-gpus=0" in zero_command,
        "parent_zero_gpu_head_sets_cpu_cap": "--num-cpus" in zero_command,
        "parent_zero_gpu_runid_is_dynamic_long_path": "RunId=\"${RUN_ID:-a19r2-ray-$(date +%s)-$$}\"" in zero_command,
        "local_python_has_ray": ray_available,
        "local_ray_cli_verified": False,
        "real_ray_2_46_lifecycle_evidence_present": False,
        "zero_gpu_wrapper_manifest_checked_before_head_start": "MANIFEST_ZEROGPU" in zero_gpu_text or "HASHES_ZEROGPU" in zero_gpu_text,
        "zero_gpu_parent_hash_checked_before_load": "f4914b91d91b1b31873457e195805762c930b89c656fe09115d25b9502ee98d9" in zero_gpu_text or "HASHES_SUPERVISOR" in zero_gpu_text,
        "zero_gpu_head_sets_num_gpus_zero": "--num-gpus={ZERO_GPU_NUM_GPUS}" in zero_gpu_text and "ZERO_GPU_NUM_GPUS = 0" in zero_gpu_text,
        "zero_gpu_head_sets_cpu_cap": "--num-cpus={ZERO_GPU_NUM_CPUS}" in zero_gpu_text and "ZERO_GPU_NUM_CPUS = 3" in zero_gpu_text,
        "zero_gpu_sets_empty_cuda_visible_devices": 'os.environ["CUDA_VISIBLE_DEVICES"] = ""' in zero_gpu_text,
        "zero_gpu_tmp_requires_direct_tmp_child": 'path.parent != Path("/tmp")' in zero_gpu_text,
        "zero_gpu_tmp_length_cap": "MAX_SHORT_RAY_TMP_LENGTH = 32" in zero_gpu_text and "len(str(path)) > MAX_SHORT_RAY_TMP_LENGTH" in zero_gpu_text,
        "zero_gpu_main_deadline_set_before_head_start": zero_gpu_text.index("self._main_deadline =") < zero_gpu_text.index("self._start_head()"),
        "zero_gpu_readiness_uses_remaining_main_budget": "self._remaining_main_budget()" in zero_gpu_text and "startup_timeout_seconds = min" in zero_gpu_text,
        "zero_gpu_cleanup_subtracts_launcher_elapsed": "cleanup_budget_seconds - launcher_cleanup_elapsed" in zero_gpu_text,
        "zero_gpu_real_head_path_exercised_by_fake_tests": "head_command=[sys.executable" not in zero_gpu_tests_text,
        "zero_gpu_lifecycle_timeout_cli_is_capped_at_120": False,
        "zero_gpu_cleanup_timeout_cli_is_capped_at_120": False,
        "zero_gpu_command_has_120_main_budget": "--lifecycle-timeout-seconds 120" in zero_gpu_command_text,
        "zero_gpu_command_has_120_cleanup_budget": "--cleanup-budget-seconds 120" in zero_gpu_command_text,
        "zero_gpu_command_has_read_only_cli_help_preflight": "-m ray start --help" in zero_gpu_command_text and "-m ray status --help" in zero_gpu_command_text,
        "delta_zero_gpu_command_sets_empty_cuda_visible_devices": bool(re.search(r"CUDA_VISIBLE_DEVICES\s*=\s*['\"]['\"]", zero_gpu_command_text)),
        "delta_zero_gpu_command_sets_num_gpus_zero": "--num-gpus=0" in zero_gpu_command_text,
        "delta_zero_gpu_command_sets_cpu_cap": "--num-cpus=3" in zero_gpu_command_text,
        "delta_zero_gpu_command_uses_short_fixed_ray_tmp": "RayTmp=/tmp/zlf-s20a" in zero_gpu_command_text and "RunId=" not in zero_gpu_command_text,
        "delta_zero_gpu_command_uses_120_production_budget": "--lifecycle-timeout-seconds 120" in zero_gpu_command_text,
        "delta_zero_gpu_command_uses_120_cleanup_budget": "--cleanup-budget-seconds 120" in zero_gpu_command_text,
    }


def main() -> None:
    fake_tests = run_fake_tests()
    zero_gpu_fake_tests = run_zero_gpu_fake_tests()
    result = {
        "schema": "fresh-process-a-private-ray-supervisor-and-zero-gpu-independent-review-v2",
        "reviewed_at": "2026-09-20",
        "source_supplement": str(SUPPLEMENT),
        "source_zero_gpu_delta": str(ZERO_GPU),
        "source_cli_preflight": str(CLI_PREFLIGHT),
        "hash_check": hash_check(),
        "zero_gpu_hash_check": zero_gpu_hash_check(),
        "cli_preflight_check": cli_preflight_check(),
        "fake_standard_library_tests": fake_tests,
        "zero_gpu_fake_standard_library_tests": zero_gpu_fake_tests,
        "static_review": static_review(),
        "evidence_boundary": {
            "fake_head_or_launcher_only": True,
            "linux_procfs_exercised": False,
            "real_python_module_ray_exercised": False,
            "ray_2_46_exercised": False,
            "ssh": False,
            "ray_started": False,
            "gpu_used": False,
            "model_loaded": False,
            "training_started": False,
        },
        "verdict": "NOT_READY_FOR_BOUNDED_ZERO_GPU",
        "open_findings": [
            "FINDING-A-SUPERVISOR-MANIFEST-GUARD-005",
            "FINDING-A-SUPERVISOR-INTERRUPT-CLEANUP-006",
            "FINDING-A-SUPERVISOR-LAUNCHER-DESCENDANT-007",
            "FINDING-A-SUPERVISOR-HEAD-PIPE-008",
            "FINDING-A-ZEROGPU-MANIFEST-GUARD-009",
            "FINDING-A-ZEROGPU-CLI-ENTRYPOINT-010",
            "REAL-RAY-CLI-2.46-EVIDENCE-MISSING",
        ],
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
