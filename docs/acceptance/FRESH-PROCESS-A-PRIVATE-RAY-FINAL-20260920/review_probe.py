"""Read-only review of the final combined supervisor and Phase 1 contract.

This probe imports the final test module without executing its ``main`` and
calls the portable ``run()`` suite.  It never calls ``run_linux_process_check``
on this Windows host, never starts Ray, and never writes into the frozen final
runtime directory.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


FINAL = Path(r"C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/acceptance/FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-ZEROGPU-CLI-FINAL-SUPPLEMENT")
PARENT = Path(r"C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/acceptance/FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-SUPERVISOR-SUPPLEMENT")
ZERO_GPU = Path(r"C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/acceptance/FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-ZEROGPU-SUPPLEMENT")
CLI_PREFLIGHT = Path(r"C:/Users/Administrator/.codex/worktrees/71a6/RaPO-author/docs/diagnostics/RAY-CLI-ENTRY-PREFLIGHT-20260920")


def sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot_hash_check(root: Path, hashes_name: str, manifest_name: str) -> dict[str, Any]:
    hashes_path = root / hashes_name
    manifest_path = root / manifest_name
    hashes = load(hashes_path)
    manifest = load(manifest_path)
    bad: list[str] = []
    total = 0
    for entry in hashes["files"]:
        path = root / entry["path"]
        if not path.is_file() or path.stat().st_size != int(entry["bytes"]) or sha256(path) != entry["sha256"]:
            bad.append(entry["path"])
        else:
            total += path.stat().st_size
    return {
        "declared_file_count": hashes.get("file_count", len(hashes["files"])),
        "declared_total_bytes": hashes.get("total_bytes"),
        "actual_declared_total_bytes": total,
        "bad_hash_files": bad,
        "hashes_self_sha256": sha256(hashes_path),
        "manifest_sha256": sha256(manifest_path),
        "manifest_runtime_files": len(manifest.get("runtime_files", [])),
        "manifest_artifact_files": len(manifest.get("artifact_files", [])),
    }


def run_portable_tests() -> dict[str, Any]:
    sys.path.insert(0, str(FINAL))
    spec = importlib.util.spec_from_file_location("final_supervisor_tests_direct_review", FINAL / "run_supervisor_tests.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load final test module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run()


def cli_preflight() -> dict[str, Any]:
    summary = load(CLI_PREFLIGHT / "SUMMARY.json")
    hashes = load(CLI_PREFLIGHT / "HASHES.json")
    bad: list[str] = []
    total = 0
    for entry in hashes["entries"]:
        path = CLI_PREFLIGHT / entry["path"]
        if not path.is_file() or path.stat().st_size != int(entry["bytes"]) or sha256(path) != entry["sha256"]:
            bad.append(entry["path"])
        else:
            total += path.stat().st_size
    entries = {entry["entry"]: entry for entry in summary["entry_results"]}
    return {
        "file_count": hashes["file_count"],
        "declared_total_bytes": hashes["total_bytes"],
        "actual_total_bytes": total,
        "bad_hash_files": bad,
        "hashes_self_sha256": sha256(CLI_PREFLIGHT / "HASHES.json"),
        "host": summary["host"],
        "python_version": summary["environment"]["python_version"],
        "ray_version": summary["environment"]["ray_version"],
        "python_module_ray_start_help_exit": entries["python -m ray start --help"]["exit_code"],
        "python_module_ray_status_help_exit": entries["python -m ray status --help"]["exit_code"],
        "ray_script_start_help_exit": entries["/mnt/conda/zhenglifeng/rapo-author-diagnostic-20260908/env/rapo-author/bin/ray start --help"]["exit_code"],
        "ray_script_status_help_exit": entries["/mnt/conda/zhenglifeng/rapo-author-diagnostic-20260908/env/rapo-author/bin/ray status --help"]["exit_code"],
        "service_started": summary["recommendation"]["service_started"],
    }


def static_review() -> dict[str, Any]:
    source = (FINAL / "private_ray_supervisor.py").read_text(encoding="utf-8")
    tests = (FINAL / "run_supervisor_tests.py").read_text(encoding="utf-8")
    linux_start = tests.index("def run_linux_process_check")
    linux_end = tests.index("def main", linux_start)
    linux_check = tests[linux_start:linux_end]
    execute_start = source.index("    def execute")
    execute = source[execute_start:]
    return {
        "runtime_manifest_guard_before_head": source.index("self._validate_before_head()") < source.index("self._start_head()"),
        "parent_snapshot_guard": "parent_snapshot_root" in source and "frozen_parent_supervisor" in source,
        "zero_gpu_snapshot_guard": "zero_gpu_snapshot_root" in source and "frozen_zero_gpu_delta" in source,
        "record_validation_atomic": "self._atomic_write_json(self.preflight_validation_path, validation)" in source,
        "signal_handlers_installed": "signal.signal(signum, self._handle_interrupt)" in source,
        "execute_catches_baseexception": "except BaseException as exc" in execute,
        "execute_finally_restores_signal_handlers": "finally:" in execute and "self._restore_signal_handlers()" in execute,
        "launcher_descendant_monitor": "_launcher_monitor_loop" in source and "launcher-descendant-chain" in source,
        "launcher_tree_tracks_after_reparent": "self.launcher_owned_processes" in source and "launcher_process_tree_verified" in source,
        "file_backed_head_logs": "stdout=self._head_stdout_handle" in source and "stderr=self._head_stderr_handle" in source,
        "file_backed_launcher_logs": "stdout=self._launcher_stdout_handle" in source and "stderr=self._launcher_stderr_handle" in source,
        "validated_bin_ray_command": 'str(self.ray_executable),\n            "start"' in source and 'str(self.ray_executable), "status", "--address"' in source,
        "python_module_ray_runtime_argv_used": bool(re.search(r"[\"']-m[\"']", source)),
        "main_budget_capped_at_120": "if self.lifecycle_timeout_seconds > PRODUCTION_TIMEOUT_SECONDS" in source,
        "cleanup_budget_capped_at_120": "if self.cleanup_budget_seconds > TOTAL_CLEANUP_BUDGET_SECONDS" in source,
        "linux_process_check_requires_procfs": "sys.platform.startswith(\"linux\")" in linux_check and "Path(\"/proc\").is_dir()" in linux_check,
        "linux_process_check_writes_frozen_test_results": "test-results.json" in linux_check,
        "main_overwrites_frozen_test_results": "(ROOT / \"test-results.json\").write_text" in tests,
        "linux_process_check_writes_external_result": "output" in linux_check.lower() and "write_text" in linux_check,
        "linux_process_check_delivers_sigint_or_sigterm_to_supervisor": "SIGINT" in linux_check or "SIGTERM" in linux_check or "_handle_interrupt" in linux_check,
        "portable_suite_directly_calls_handler": "_handle_interrupt(signal.SIGINT" in tests and "_handle_interrupt(signal.SIGTERM" in tests,
        "linux_process_check_starts_fake_new_session_descendants": "start_new_session=True" in linux_check,
        "linux_process_check_calls_real_ray": "import ray" in linux_check or "bin/ray" in linux_check,
    }


def main() -> None:
    result = {
        "schema": "fresh-process-a-private-ray-final-independent-review-v1",
        "reviewed_at": "2026-09-20",
        "source_final": str(FINAL),
        "source_parent": str(PARENT),
        "source_zero_gpu": str(ZERO_GPU),
        "source_cli_preflight": str(CLI_PREFLIGHT),
        "final_hash_check": snapshot_hash_check(FINAL, "HASHES_FINAL.json", "MANIFEST_FINAL.json"),
        "portable_standard_library_tests": run_portable_tests(),
        "static_review": static_review(),
        "cli_preflight": cli_preflight(),
        "local_linux_procfs_available": sys.platform.startswith("linux") and Path("/proc").is_dir(),
        "linux_process_check_executed_here": False,
        "real_ray_started": False,
        "gpu_used": False,
        "model_loaded": False,
        "training_started": False,
        "ssh_used_here": False,
        "verdict": "NOT_READY_FOR_BOUNDED_LINUX_STDLIB_AS_WRITTEN",
        "open_findings": [
            "FINDING-A-FINAL-PHASE1-FROZEN-OUTPUT-011",
            "FINDING-A-FINAL-PHASE1-SIGNAL-COVERAGE-012",
            "REAL-LINUX-PROCFS-CHECK-NOT-EXECUTED",
            "REAL-RAY-ZERO-GPU-LIFECYCLE-NOT-EXECUTED",
        ],
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
