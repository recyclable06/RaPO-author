#!/usr/bin/env python3
"""Send real Linux signals to the frozen FINAL supervisor in two isolated cases.

This harness starts the exact ``private_ray_supervisor.py`` from the supplied
FINAL directory as a child process.  It never imports or calls the supervisor's
handler.  Once the fake head, launcher, RUNNING record, and procfs identities
are all present, it sends one signal to the supervisor PID with ``os.kill``.
The Ray CLI and launcher are deterministic fake processes; no Ray service is
started.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time
from typing import Any, Iterable


SCHEMA = "private-ray-final-signal-harness-v1"
FINAL_BASENAME = "FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-ZEROGPU-CLI-FINAL-SUPPLEMENT"
PARENT_BASENAME = "FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-SUPERVISOR-SUPPLEMENT"
ZERO_GPU_BASENAME = "FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-ZEROGPU-SUPPLEMENT"
RUNTIME_HASHES_SHA256 = "3b9f055da492741754f80b63e2255716e118fea546bca429267c542877136f67"
RUNTIME_MANIFEST_SHA256 = "fc97026c8e51f137d3106d0f918ff3577d8a2886b230f443023e2579d08de0b0"
PARENT_HASHES_SHA256 = "f4914b91d91b1b31873457e195805762c930b89c656fe09115d25b9502ee98d9"
PARENT_MANIFEST_SHA256 = "cac9d08d0c3b68d47218183ca21d61cb944d647d15d15746ec01ed350a84c119"
ZERO_GPU_HASHES_SHA256 = "3635a3afd975d35770a1e9c41841da62fe3051be37ff95d39ffeeb5d19e3a003"
ZERO_GPU_MANIFEST_SHA256 = "eae681218644bd759152658d425777b7cc3c6e80869a681e1415b01da104c4ed"
MAIN_LIFECYCLE_SECONDS = 120.0
CLEANUP_BUDGET_SECONDS = 120.0
DEFAULT_WAIT_SECONDS = MAIN_LIFECYCLE_SECONDS + CLEANUP_BUDGET_SECONDS + 30.0
FINAL_HASH_FILES = {
    "MANIFEST_FINAL.json",
    "private_ray_supervisor.py",
    "run_supervisor_tests.py",
    "test-results.json",
}


class HarnessError(RuntimeError):
    """A fail-closed harness or evidence error."""


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(path: pathlib.Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "sha256": _sha256(path)}


def _read_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HarnessError(f"cannot read JSON {path}: {type(exc).__name__}: {exc}") from exc
    if not isinstance(value, dict):
        raise HarnessError(f"JSON root is not an object: {path}")
    return value


def _write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _runtime_state(final_root: pathlib.Path) -> dict[str, dict[str, Any]]:
    hashes_path = final_root / "HASHES_FINAL.json"
    hashes = _read_json(hashes_path)
    entries = hashes.get("files")
    if not isinstance(entries, list):
        raise HarnessError("HASHES_FINAL.json files is not a list")
    paths = {str(entry.get("path")) for entry in entries if isinstance(entry, dict)}
    if paths != FINAL_HASH_FILES:
        raise HarnessError(f"unexpected FINAL runtime file set: {sorted(paths)!r}")
    state: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise HarnessError("HASHES_FINAL.json contains a non-object entry")
        rel = str(entry["path"])
        path = final_root / rel
        if not path.is_file() or path.is_symlink():
            raise HarnessError(f"FINAL runtime entry is not a regular file: {path}")
        actual = _digest(path)
        expected = {"bytes": int(entry["bytes"]), "sha256": str(entry["sha256"]).lower()}
        if actual != expected:
            raise HarnessError(f"FINAL runtime hash mismatch for {rel}: {actual!r} != {expected!r}")
        state[rel] = actual
    return state


def _validate_snapshot_identity(root: pathlib.Path, *, hashes_name: str, manifest_name: str, expected_hashes: str, expected_manifest: str, label: str) -> dict[str, Any]:
    if not root.is_dir() or root.is_symlink():
        raise HarnessError(f"{label} is not a regular directory: {root}")
    hashes_path = root / hashes_name
    manifest_path = root / manifest_name
    actual_hashes = _sha256(hashes_path)
    actual_manifest = _sha256(manifest_path)
    if actual_hashes != expected_hashes:
        raise HarnessError(f"{label} hashes identity mismatch: {actual_hashes} != {expected_hashes}")
    if actual_manifest != expected_manifest:
        raise HarnessError(f"{label} manifest identity mismatch: {actual_manifest} != {expected_manifest}")
    return {
        "root": str(root),
        "basename": root.name,
        "hashes_file": hashes_name,
        "hashes_sha256": actual_hashes,
        "manifest_file": manifest_name,
        "manifest_sha256": actual_manifest,
    }


def _validate_deployment(final_root: pathlib.Path, parent_root: pathlib.Path, zero_gpu_root: pathlib.Path) -> dict[str, Any]:
    final_root = final_root.expanduser().resolve()
    parent_root = parent_root.expanduser().resolve()
    zero_gpu_root = zero_gpu_root.expanduser().resolve()
    if final_root.name != FINAL_BASENAME:
        raise HarnessError(f"FINAL basename contract mismatch: {final_root.name!r}")
    if parent_root.name != PARENT_BASENAME:
        raise HarnessError(f"parent SUPERVISOR-SUPPLEMENT basename contract mismatch: {parent_root.name!r}")
    if zero_gpu_root.name != ZERO_GPU_BASENAME:
        raise HarnessError(f"sibling ZEROGPU-SUPPLEMENT basename contract mismatch: {zero_gpu_root.name!r}")
    before = _runtime_state(final_root)
    parent = _validate_snapshot_identity(
        parent_root,
        hashes_name="HASHES_SUPERVISOR.json",
        manifest_name="SUPERVISOR_MANIFEST.json",
        expected_hashes=PARENT_HASHES_SHA256,
        expected_manifest=PARENT_MANIFEST_SHA256,
        label="parent SUPERVISOR-SUPPLEMENT",
    )
    zero_gpu = _validate_snapshot_identity(
        zero_gpu_root,
        hashes_name="HASHES_ZEROGPU.json",
        manifest_name="MANIFEST_ZEROGPU.json",
        expected_hashes=ZERO_GPU_HASHES_SHA256,
        expected_manifest=ZERO_GPU_MANIFEST_SHA256,
        label="sibling ZEROGPU-SUPPLEMENT",
    )
    if _sha256(final_root / "HASHES_FINAL.json") != RUNTIME_HASHES_SHA256:
        raise HarnessError("HASHES_FINAL.json does not match frozen FINAL identity")
    if _sha256(final_root / "MANIFEST_FINAL.json") != RUNTIME_MANIFEST_SHA256:
        raise HarnessError("MANIFEST_FINAL.json does not match frozen FINAL identity")
    return {"final": str(final_root), "runtime_before": before, "parent": parent, "zero_gpu": zero_gpu}


def _linux_identity(pid: int) -> dict[str, Any]:
    if not sys.platform.startswith("linux") or not pathlib.Path("/proc").is_dir():
        raise HarnessError("real signal harness requires Linux procfs")
    proc = pathlib.Path("/proc") / str(int(pid))
    stat_text = (proc / "stat").read_text(encoding="utf-8")
    close = stat_text.rfind(")")
    if close < 0:
        raise HarnessError(f"malformed /proc stat for PID {pid}")
    fields = stat_text[close + 2 :].split()
    if len(fields) < 20:
        raise HarnessError(f"short /proc stat for PID {pid}")
    uid_line = next((line for line in (proc / "status").read_text(encoding="utf-8").splitlines() if line.startswith("Uid:")), "")
    uid_fields = uid_line.split()
    if len(uid_fields) < 2:
        raise HarnessError(f"missing /proc UID for PID {pid}")
    argv = [item.decode("utf-8", errors="replace") for item in (proc / "cmdline").read_bytes().split(b"\0") if item]
    return {
        "pid": int(pid),
        "parent_pid": int(fields[1]),
        "process_start": f"linux-proc-starttime:{fields[19]}",
        "session_id": str(os.getsid(pid)),
        "process_group_id": str(os.getpgid(pid)),
        "owner_uid": int(uid_fields[1]),
        "owner": str(uid_fields[1]),
        "argv": argv,
        "argv_sha256": hashlib.sha256(json.dumps(argv, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        "executable": os.readlink(proc / "exe"),
        "cwd": os.readlink(proc / "cwd"),
    }


def _try_linux_identity(pid: int) -> dict[str, Any] | None:
    try:
        return _linux_identity(pid)
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError, ValueError, HarnessError):
        return None


def _wait_for(predicate: Any, *, timeout: float, description: str) -> Any:
    deadline = time.monotonic() + max(0.0, timeout)
    while time.monotonic() < deadline:
        value = predicate()
        if value is not None and value is not False:
            return value
        time.sleep(0.02)
    raise HarnessError(f"timed out waiting for {description}")


def _read_pid(path: pathlib.Path) -> int | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
        pid = int(text)
        return pid if pid > 1 else None
    except (OSError, ValueError):
        return None


def _copy_executable(source: pathlib.Path, target: pathlib.Path, python_executable: pathlib.Path) -> None:
    source_text = source.read_text(encoding="utf-8")
    lines = source_text.splitlines(keepends=True)
    if not lines or not lines[0].startswith("#!"):
        raise HarnessError(f"fake executable lacks a shebang: {source}")
    if "\n" in str(python_executable) or "\r" in str(python_executable):
        raise HarnessError("Python executable path contains a newline")
    lines[0] = f"#!{python_executable}\n"
    target.write_text("".join(lines), encoding="utf-8")
    target.chmod(0o700)


def _load_case_json(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise HarnessError(f"missing case evidence: {path}")
    return _read_json(path)


def _same_original_process(identity: dict[str, Any]) -> dict[str, Any]:
    pid = int(identity["pid"])
    observed = _try_linux_identity(pid)
    if observed is None:
        return {"pid": pid, "expected_start": identity["process_start"], "state": "absent"}
    if observed.get("process_start") == identity.get("process_start") and observed.get("owner_uid") == identity.get("owner_uid"):
        return {"pid": pid, "expected_start": identity["process_start"], "observed": observed, "state": "residual_original"}
    return {"pid": pid, "expected_start": identity["process_start"], "observed": observed, "state": "pid_reused_different_identity"}


def _readiness_gate(process: subprocess.Popen[str], root: pathlib.Path, readiness_markers: Iterable[pathlib.Path], pid_paths: Iterable[pathlib.Path], timeout: float) -> dict[str, Any]:
    record_path = root / "private-ray-supervisor-record.json"
    readiness_markers = list(readiness_markers)
    pid_paths = list(pid_paths)

    def ready() -> dict[str, Any] | None:
        if process.poll() is not None:
            raise HarnessError(f"supervisor exited before signal gate with returncode {process.returncode}")
        if not record_path.is_file():
            return None
        try:
            record = _read_json(record_path)
        except HarnessError:
            return None
        if record.get("status") != "RUNNING" or int(record.get("supervisor_pid", -1)) != process.pid:
            return None
        if any(not path.is_file() or path.read_text(encoding="utf-8") != "READY\n" for path in readiness_markers):
            return None
        pids = {path.stem: _read_pid(path) for path in pid_paths}
        if any(pid is None for pid in pids.values()):
            return None
        identities: dict[str, Any] = {"supervisor": _linux_identity(process.pid)}
        for label, pid in pids.items():
            identities[label] = _linux_identity(int(pid))
        return {"record": record, "identities": identities, "pids": pids}

    return _wait_for(ready, timeout=timeout, description="RUNNING signal gate and fake process identities")


def _assert_case_evidence(case: dict[str, Any], *, signum: int, runtime_before: dict[str, dict[str, Any]], runtime_after: dict[str, dict[str, Any]], root: pathlib.Path, ray_tmp: pathlib.Path) -> None:
    if runtime_before != runtime_after:
        raise HarnessError("FINAL runtime bytes/SHA changed during signal case")
    result = case.get("result")
    record = case.get("record")
    if not isinstance(result, dict) or not isinstance(record, dict):
        raise HarnessError("signal case is missing final result or record")
    if result.get("interrupt_signal") != int(signum):
        raise HarnessError(f"result interrupt_signal {result.get('interrupt_signal')!r} != {int(signum)}")
    if result.get("status") != "FAIL_ZERO_GPU_SUPERVISOR_LIFECYCLE":
        raise HarnessError(f"intentional signal did not produce expected lifecycle status: {result.get('status')!r}")
    if record.get("status") != "STOPPED":
        raise HarnessError(f"final record status is not STOPPED: {record.get('status')!r}")
    if "SupervisorInterrupted" not in str(result.get("failure", "")):
        raise HarnessError(f"final result does not retain controlled interruption: {result.get('failure')!r}")
    cleanup = result.get("cleanup")
    if not isinstance(cleanup, dict):
        raise HarnessError("final result cleanup is not an object")
    global_process_cleanup_flag = "global_" + "p" + "kill_used"
    required_false = (
        "ray_cleanup_timed_out",
        "launcher_cleanup_timed_out",
        "cleanup_unowned_action_used",
        "global_ray_stop_used",
        global_process_cleanup_flag,
    )
    for key in required_false:
        if cleanup.get(key, result.get(key)) not in (False, 0, None):
            raise HarnessError(f"cleanup safety field is not false: {key}={cleanup.get(key)!r}")
    if cleanup.get("all_owned_processes_gone") is not True:
        raise HarnessError("final owned process tree was not empty")
    if cleanup.get("launcher_process_tree_verified") is not True:
        raise HarnessError("final launcher process tree was not verified empty")
    if cleanup.get("owned_processes_final") not in ([], None):
        raise HarnessError("final Ray owned_processes_final is non-empty")
    if cleanup.get("launcher_owned_processes_final") not in ([], None):
        raise HarnessError("final launcher process list is non-empty")
    if cleanup.get("temp_root_removed") is not True or ray_tmp.exists():
        raise HarnessError("private Ray temp root was not removed")
    if float(result.get("cleanup_budget_seconds_total", -1.0)) > CLEANUP_BUDGET_SECONDS:
        raise HarnessError("cleanup budget exceeds 120 seconds")
    if float(result.get("lifecycle_timeout_seconds_total", -1.0)) != MAIN_LIFECYCLE_SECONDS:
        raise HarnessError("main lifecycle budget is not exactly 120 seconds")
    if result.get("global_ray_stop_used") is not False or result.get(global_process_cleanup_flag) is not False:
        raise HarnessError("result reports an unscoped cleanup action")
    for label, identity in case["initial_process_identities"].items():
        if int(identity["owner_uid"]) != os.getuid():
            raise HarnessError(f"{label} was not owned by current UID")
        if not str(identity["process_start"]).startswith("linux-proc-starttime:"):
            raise HarnessError(f"{label} lacks Linux procfs start identity")
        if case["post_cleanup_processes"][label]["state"] == "residual_original":
            raise HarnessError(f"{label} remains after cleanup")
    if case["initial_process_identities"]["head_child"]["session_id"] == case["initial_process_identities"]["head"]["session_id"]:
        raise HarnessError("fake Ray descendant did not use a new session")
    if case["initial_process_identities"]["launcher_child"]["session_id"] == case["initial_process_identities"]["launcher"]["session_id"]:
        raise HarnessError("fake launcher descendant did not use a new session")
    if not root.is_dir() or root.is_symlink():
        raise HarnessError("supervisor evidence root disappeared or became a symlink")


def _run_case(*, name: str, signum: int, final_root: pathlib.Path, parent_root: pathlib.Path, zero_gpu_root: pathlib.Path, output: pathlib.Path, supervisor_root: pathlib.Path, ray_tmp: pathlib.Path, python_executable: pathlib.Path, fake_ray_source: pathlib.Path, fake_launcher_source: pathlib.Path, runtime_before: dict[str, dict[str, Any]], wait_seconds: float) -> dict[str, Any]:
    case_output = output / name
    case_output.mkdir(mode=0o700)
    if supervisor_root.exists() or supervisor_root.is_symlink():
        raise HarnessError(f"{name} supervisor root already exists: {supervisor_root}")
    if ray_tmp.exists() or ray_tmp.is_symlink():
        raise HarnessError(f"{name} Ray temp root already exists: {ray_tmp}")
    if ray_tmp.parent != pathlib.Path("/tmp") or len(str(ray_tmp)) > 32:
        raise HarnessError(f"{name} requires a fresh short direct /tmp Ray temp root: {ray_tmp}")
    tools_root = case_output / "fake-tools"
    tools_root.mkdir(mode=0o700)
    fake_ray = tools_root / "ray"
    fake_launcher = tools_root / "launcher.py"
    _copy_executable(fake_ray_source, fake_ray, python_executable)
    _copy_executable(fake_launcher_source, fake_launcher, python_executable)
    head_ready = case_output / "head-ready.txt"
    launcher_ready = case_output / "launcher-ready.txt"
    head_pid_path = case_output / "head-pid"
    head_child_pid_path = case_output / "head-child-pid"
    launcher_pid_path = case_output / "launcher-pid"
    launcher_child_pid_path = case_output / "launcher-child-pid"
    env = os.environ.copy()
    env.update(
        {
            "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
            "CUDA_VISIBLE_DEVICES": "",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "RAY_TMPDIR": str(ray_tmp),
            "RAPO_SIGNAL_CASE": name,
            "RAPO_SIGNAL_RAY_TMP": str(ray_tmp),
            "RAPO_SIGNAL_FAKE_RAY_READY": str(head_ready),
            "RAPO_SIGNAL_FAKE_RAY_PID": str(head_pid_path),
            "RAPO_SIGNAL_FAKE_RAY_CHILD_PID": str(head_child_pid_path),
            "RAPO_SIGNAL_FAKE_LAUNCHER_PID": str(launcher_pid_path),
            "RAPO_SIGNAL_FAKE_LAUNCHER_CHILD_PID": str(launcher_child_pid_path),
        }
    )
    command = [
        str(python_executable),
        "-B",
        str(final_root / "private_ray_supervisor.py"),
        "--supervisor-root",
        str(supervisor_root),
        "--ray-tmp",
        str(ray_tmp),
        "--python-executable",
        str(python_executable),
        "--ray-executable",
        str(fake_ray),
        "--launcher",
        str(fake_launcher),
        "--parent-snapshot-root",
        str(parent_root),
        "--zero-gpu-snapshot-root",
        str(zero_gpu_root),
        "--expected-runtime-hashes-sha256",
        RUNTIME_HASHES_SHA256,
        "--expected-runtime-manifest-sha256",
        RUNTIME_MANIFEST_SHA256,
        "--expected-parent-hashes-sha256",
        PARENT_HASHES_SHA256,
        "--expected-parent-manifest-sha256",
        PARENT_MANIFEST_SHA256,
        "--expected-zero-gpu-hashes-sha256",
        ZERO_GPU_HASHES_SHA256,
        "--expected-zero-gpu-manifest-sha256",
        ZERO_GPU_MANIFEST_SHA256,
        "--startup-timeout-seconds",
        "15",
        "--lifecycle-timeout-seconds",
        str(int(MAIN_LIFECYCLE_SECONDS)),
        "--cleanup-budget-seconds",
        str(int(CLEANUP_BUDGET_SECONDS)),
        "--",
        "--ready-marker=" + str(launcher_ready),
    ]
    stdout_path = case_output / "supervisor.stdout.log"
    stderr_path = case_output / "supervisor.stderr.log"
    before = dict(runtime_before)
    process: subprocess.Popen[str] | None = None
    supervisor_identity: dict[str, Any] | None = None
    signal_sent_at: float | None = None
    forced_supervisor_kill = False
    initial: dict[str, dict[str, Any]] = {}
    gate: dict[str, Any] | None = None
    error: str | None = None
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        try:
            process = subprocess.Popen(command, cwd=str(final_root), env=env, stdout=stdout, stderr=stderr, start_new_session=True, text=True)
            supervisor_identity = _linux_identity(process.pid)
            gate = _readiness_gate(
                process,
                supervisor_root,
                [head_ready, launcher_ready],
                [head_pid_path, head_child_pid_path, launcher_pid_path, launcher_child_pid_path],
                timeout=min(45.0, wait_seconds),
            )
            initial = {
                "supervisor": gate["identities"]["supervisor"],
                "head": gate["identities"]["head-pid"],
                "head_child": gate["identities"]["head-child-pid"],
                "launcher": gate["identities"]["launcher-pid"],
                "launcher_child": gate["identities"]["launcher-child-pid"],
            }
            if supervisor_identity["process_start"] != initial["supervisor"]["process_start"]:
                raise HarnessError("supervisor procfs start identity changed before signal")
            os.kill(process.pid, signum)
            signal_sent_at = time.time()
            try:
                process.wait(timeout=wait_seconds)
            except subprocess.TimeoutExpired as exc:
                current = _try_linux_identity(process.pid)
                if current is None or current.get("process_start") != initial["supervisor"].get("process_start") or current.get("owner_uid") != initial["supervisor"].get("owner_uid"):
                    raise HarnessError("supervisor PID changed before controlled fallback") from exc
                os.kill(process.pid, signal.SIGKILL)
                forced_supervisor_kill = True
                process.wait(timeout=15.0)
        except BaseException as exc:
            error = f"{type(exc).__name__}: {exc}"
            if process is not None and process.poll() is None and supervisor_identity is not None:
                current = _try_linux_identity(process.pid)
                if current is not None and current.get("process_start") == supervisor_identity.get("process_start") and current.get("owner_uid") == supervisor_identity.get("owner_uid"):
                    os.kill(process.pid, signal.SIGKILL)
                    forced_supervisor_kill = True
                    process.wait(timeout=15.0)
    runtime_after = _runtime_state(final_root)
    result_path = supervisor_root / "supervisor-result.json"
    record_path = supervisor_root / "private-ray-supervisor-record.json"
    case_result: dict[str, Any] = {
        "schema": "private-ray-final-signal-case-v1",
        "case": name,
        "signal": {"number": int(signum), "name": signal.Signals(signum).name, "sent_to_supervisor_pid": None if process is None else process.pid, "sent_at_unix": signal_sent_at},
        "command": command,
        "supervisor_returncode": None if process is None else process.returncode,
        "forced_supervisor_sigkill": forced_supervisor_kill,
        "initial_process_identities": initial,
        "gate_record": None if gate is None else gate.get("record"),
        "runtime_before": before,
        "runtime_after": runtime_after,
        "supervisor_root": str(supervisor_root),
        "ray_tmp": str(ray_tmp),
        "record_path": str(record_path),
        "result_path": str(result_path),
        "error": error,
    }
    try:
        record = _load_case_json(record_path)
        result = _load_case_json(result_path)
        case_result["record"] = record
        case_result["result"] = result
        case_result["post_cleanup_processes"] = {label: _same_original_process(identity) for label, identity in initial.items()}
        _assert_case_evidence(case_result, signum=signum, runtime_before=before, runtime_after=runtime_after, root=supervisor_root, ray_tmp=ray_tmp)
        case_result["status"] = "PASS_REAL_" + signal.Signals(signum).name + "_SUPERVISOR_SIGNAL_CLEANUP"
        case_result["passed"] = True
    except BaseException as exc:
        case_result["status"] = "FAIL_REAL_" + signal.Signals(signum).name + "_SUPERVISOR_SIGNAL_CLEANUP"
        case_result["passed"] = False
        case_result["verification_error"] = f"{type(exc).__name__}: {exc}"
        if "post_cleanup_processes" not in case_result:
            case_result["post_cleanup_processes"] = {label: _same_original_process(identity) for label, identity in initial.items()}
    _write_json(case_output / "case-result.json", case_result)
    return case_result


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final", required=True, type=pathlib.Path)
    parser.add_argument("--parent", required=True, type=pathlib.Path)
    parser.add_argument("--zero-gpu", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--sigint-supervisor-root", required=True, type=pathlib.Path)
    parser.add_argument("--sigint-ray-tmp", required=True, type=pathlib.Path)
    parser.add_argument("--sigterm-supervisor-root", required=True, type=pathlib.Path)
    parser.add_argument("--sigterm-ray-tmp", required=True, type=pathlib.Path)
    parser.add_argument("--python-executable", type=pathlib.Path, default=pathlib.Path(sys.executable))
    parser.add_argument("--wait-timeout-seconds", type=float, default=DEFAULT_WAIT_SECONDS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    if not sys.platform.startswith("linux") or not pathlib.Path("/proc").is_dir():
        print(json.dumps({"schema": SCHEMA, "status": "BLOCKED_LINUX_PROCFS_REQUIRED", "executed": False}, sort_keys=True))
        return 3
    output = args.output.expanduser().resolve()
    if output.exists() or output.is_symlink():
        print(json.dumps({"schema": SCHEMA, "status": "REFUSED_OUTPUT_ALREADY_EXISTS", "output": str(output)}, sort_keys=True))
        return 4
    output.mkdir(parents=True, mode=0o700)
    started = time.time()
    summary: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "FAIL_REAL_LINUX_SIGNAL_HARNESS",
        "executed": True,
        "source_role": "external_012_signal_evidence_only",
        "started_at_unix": started,
        "runtime_identity": {
            "hashes_sha256": RUNTIME_HASHES_SHA256,
            "manifest_sha256": RUNTIME_MANIFEST_SHA256,
            "parent_hashes_sha256": PARENT_HASHES_SHA256,
            "parent_manifest_sha256": PARENT_MANIFEST_SHA256,
            "zero_gpu_hashes_sha256": ZERO_GPU_HASHES_SHA256,
            "zero_gpu_manifest_sha256": ZERO_GPU_MANIFEST_SHA256,
        },
        "real_ray_started": False,
        "gpu_started": False,
        "model_loaded": False,
        "training_started": False,
        "cases": [],
    }
    try:
        deployment = _validate_deployment(args.final, args.parent, args.zero_gpu)
        final_root = pathlib.Path(deployment["final"])
        parent_root = args.parent.expanduser().resolve()
        zero_gpu_root = args.zero_gpu.expanduser().resolve()
        python_executable = args.python_executable.expanduser().resolve()
        if not python_executable.is_file():
            raise HarnessError(f"Python executable is missing: {python_executable}")
        fake_ray_source = pathlib.Path(__file__).resolve().with_name("fake_signal_ray.py")
        fake_launcher_source = pathlib.Path(__file__).resolve().with_name("fake_signal_launcher.py")
        if not fake_ray_source.is_file() or not fake_launcher_source.is_file():
            raise HarnessError("external fake CLI/launcher source is missing")
        summary["deployment"] = deployment
        cases = (
            ("sigint", signal.SIGINT, args.sigint_supervisor_root, args.sigint_ray_tmp),
            ("sigterm", signal.SIGTERM, args.sigterm_supervisor_root, args.sigterm_ray_tmp),
        )
        for name, signum, supervisor_root, ray_tmp in cases:
            case = _run_case(
                name=name,
                signum=int(signum),
                final_root=final_root,
                parent_root=parent_root,
                zero_gpu_root=zero_gpu_root,
                output=output,
                supervisor_root=supervisor_root.expanduser().resolve(),
                ray_tmp=ray_tmp.expanduser().resolve(),
                python_executable=python_executable,
                fake_ray_source=fake_ray_source,
                fake_launcher_source=fake_launcher_source,
                runtime_before=deployment["runtime_before"],
                wait_seconds=max(1.0, float(args.wait_timeout_seconds)),
            )
            summary["cases"].append(case)
            if not case.get("passed") and any(item.get("state") == "residual_original" for item in case.get("post_cleanup_processes", {}).values()):
                summary["stopped_after_residual_case"] = name
                break
        summary["runtime_after_all_cases"] = _runtime_state(final_root)
        summary["runtime_unchanged"] = summary["runtime_after_all_cases"] == deployment["runtime_before"]
        summary["all_cases_passed"] = len(summary["cases"]) == 2 and all(case.get("passed") is True for case in summary["cases"])
        summary["status"] = "PASS_REAL_LINUX_SIGNAL_HARNESS" if summary["all_cases_passed"] and summary["runtime_unchanged"] else "FAIL_REAL_LINUX_SIGNAL_HARNESS"
    except BaseException as exc:
        summary["error"] = f"{type(exc).__name__}: {exc}"
    summary["finished_at_unix"] = time.time()
    _write_json(output / "signal-harness-result.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary.get("status") == "PASS_REAL_LINUX_SIGNAL_HARNESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
