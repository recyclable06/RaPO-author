"""Independent, read-only acceptance probe for the v8 process-identity delta."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CANDIDATE = Path(r"C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\diagnostics\fresh-process-resume-20260911\v8")
V7 = CANDIDATE.parent / "v7"
V7_ACCEPTANCE = Path(r"C:\Users\Administrator\Desktop\RaPO-author\docs\acceptance\FRESH-PROCESS-GPU-MAPPING-V7-20260914")
DIRECT_RAW = CANDIDATE / "raw" / "remote-process-identity-20260914-211"
RAY_RAW = CANDIDATE / "raw" / "remote-ray-process-identity-20260914-211"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entries(root: Path, excluded_names: set[str]) -> dict[str, tuple[int, str]]:
    values: dict[str, tuple[int, str]] = {}
    for path in root.rglob("*"):
        if path.is_file() and path.name not in excluded_names:
            values[path.relative_to(root).as_posix()] = (path.stat().st_size, sha256(path))
    return dict(sorted(values.items()))


def compact_manifest(values: dict[str, tuple[int, str]]) -> str:
    payload = [
        {"path": path, "bytes": size, "sha256": digest}
        for path, (size, digest) in sorted(values.items())
    ]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_log(path: Path) -> dict[str, Any]:
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        if line.lstrip().startswith("{"):
            value = json.loads(line)
            if isinstance(value, dict):
                return value
    raise AssertionError(f"no JSON object found in {path}")


def check_manifest(root: Path, manifest_path: Path, excluded_name: str) -> dict[str, Any]:
    actual = entries(root, {excluded_name})
    manifest = read_json(manifest_path)
    listed = {
        item["path"]: (int(item["bytes"]), item["sha256"])
        for item in manifest["files"]
    }
    if actual != dict(sorted(listed.items())):
        missing = sorted(set(listed) - set(actual))
        extra = sorted(set(actual) - set(listed))
        mismatches = sorted(path for path in set(actual) & set(listed) if actual[path] != listed[path])
        raise AssertionError(f"manifest mismatch: missing={missing!r} extra={extra!r} mismatches={mismatches!r}")
    return {
        "file_count": len(actual),
        "total_bytes": sum(item[0] for item in actual.values()),
        "manifest_sha256": compact_manifest(actual),
        "declared_manifest_sha256": manifest["package_manifest_sha256"],
        "self_sha256": sha256(manifest_path),
        "raw_file_count": manifest.get("raw_file_count"),
        "raw_total_bytes": manifest.get("raw_total_bytes"),
        "raw_manifest_sha256": manifest.get("raw_manifest_sha256"),
    }


def run_cpu_probe(script: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", script],
        cwd=str(CANDIDATE),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"{script} failed: {result.stdout}\n{result.stderr}")
    return {"script": script, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def parse_proc_stat_independent(raw: str, expected_pid: int) -> dict[str, Any]:
    text = str(raw)
    opening = text.find("(")
    closing = text.rfind(")")
    if opening <= 0 or closing <= opening:
        raise AssertionError(f"invalid proc stat delimiters: {text!r}")
    prefix = text[:opening].strip()
    if not prefix.isdigit() or int(prefix) != expected_pid:
        raise AssertionError(f"invalid proc stat pid prefix: {prefix!r}")
    comm = text[opening + 1 : closing]
    fields = text[closing + 1 :].strip().split()
    if len(fields) < 20:
        raise AssertionError(f"invalid proc stat field count: {len(fields)}")
    state = fields[0]
    field_22 = fields[19]
    if not field_22.isdigit():
        raise AssertionError(f"invalid proc field 22: {field_22!r}")
    return {"pid": expected_pid, "comm": comm, "state": state, "field_22": field_22, "raw": text}


def check_identity_record(record: dict[str, Any]) -> dict[str, Any]:
    pid = record.get("pid")
    if type(pid) is not int or pid <= 0:
        raise AssertionError(f"non-positive identity PID: {record!r}")
    expected_path = f"/proc/{pid}/stat"
    if record.get("process_stat_path") != expected_path:
        raise AssertionError(f"non-canonical stat path: {record!r}")
    raw = record.get("process_stat_raw")
    if not isinstance(raw, str) or not raw:
        raise AssertionError(f"missing raw stat line: {record!r}")
    parsed = parse_proc_stat_independent(raw, pid)
    if record.get("process_stat_field_22") != parsed["field_22"] or record.get("process_start") != parsed["field_22"]:
        raise AssertionError(f"field-22 identity is not reproducible: {record!r}")
    if record.get("process_stat_comm") != parsed["comm"] or record.get("process_stat_state") != parsed["state"]:
        raise AssertionError(f"comm/state is not reproducible: {record!r}")
    if record.get("process_start_source") != f"{expected_path}:field22":
        raise AssertionError(f"process-start source is not /proc field 22: {record!r}")
    if record.get("process_identity_source") != "linux_proc_stat_field22":
        raise AssertionError(f"process identity source is not Linux /proc: {record!r}")
    return {
        "pid": pid,
        "process_start": parsed["field_22"],
        "process_stat_comm": parsed["comm"],
        "process_stat_state": parsed["state"],
        "process_stat_path": expected_path,
    }


def check_direct_raw() -> dict[str, Any]:
    identity = json_log(DIRECT_RAW / "identity-probe.stdout.log")
    first = check_identity_record(identity["same_process_first"])
    second = check_identity_record(identity["same_process_second"])
    child = check_identity_record(identity["child"])
    if first["pid"] != second["pid"] or first["process_start"] != second["process_start"]:
        raise AssertionError("same-process field 22 is not stable")
    if child["pid"] == first["pid"]:
        raise AssertionError("child PID is not distinct")
    if identity.get("status") != "PASS" or identity.get("cuda_visible_devices") != "":
        raise AssertionError(f"direct identity probe has unexpected status/environment: {identity!r}")
    fixture_stdout = (DIRECT_RAW / "fixture.stdout.log").read_text(encoding="utf-8")
    if "PASS_V8_PROCESS_IDENTITY_FIXTURES" not in fixture_stdout:
        raise AssertionError("remote process-identity fixture did not pass")
    for name in ("identity-probe.exit.txt", "fixture.exit.txt", "probe.exit.txt"):
        if (DIRECT_RAW / name).read_text(encoding="utf-8").strip() != "0":
            raise AssertionError(f"direct raw exit is not zero: {name}")
    if (DIRECT_RAW / "identity-probe.stderr.log").read_text(encoding="utf-8"):
        raise AssertionError("direct identity probe emitted stderr")
    return {
        "status": "PASS_V8_DIRECT_PROC_IDENTITY_RAW_RECHECK",
        "same_process": first,
        "child": child,
        "fixture_pass": True,
        "exit_codes": {name: (DIRECT_RAW / name).read_text(encoding="utf-8").strip() for name in ("identity-probe.exit.txt", "fixture.exit.txt", "probe.exit.txt")},
    }


def check_ray_raw() -> dict[str, Any]:
    result = json_log(RAY_RAW / "probe.stdout.log")
    workers = result.get("workers")
    if result.get("status") != "PASS" or result.get("mapping_protocol") != "FPP-V7-PROC-IDENTITY" or result.get("gpu_mapping_rerun") is not False:
        raise AssertionError(f"unexpected Ray identity result header: {result!r}")
    if not isinstance(workers, list) or len(workers) != 2:
        raise AssertionError(f"Ray identity result does not contain two workers: {result!r}")
    identities = [check_identity_record(worker) for worker in workers]
    node_ids = {worker.get("node_id") for worker in workers}
    worker_ids = {worker.get("worker_id") for worker in workers}
    pids = {worker["pid"] for worker in identities}
    starts = {worker["process_start"] for worker in identities}
    if len(node_ids) != 1 or None in node_ids:
        raise AssertionError(f"Ray workers are not on one node: {workers!r}")
    if len(worker_ids) != 2 or None in worker_ids or "" in worker_ids:
        raise AssertionError(f"Ray worker IDs are not distinct/positive: {workers!r}")
    if len(pids) != 2 or len(starts) != 2:
        raise AssertionError(f"Ray worker PID/start identity is not distinct: {workers!r}")
    validated = result.get("validated_identities")
    if sorted(validated, key=lambda item: item["pid"]) != sorted([
        {"node_id": worker["node_id"], "worker_id": worker["worker_id"], "pid": worker["pid"], "process_start": worker["process_start"]}
        for worker in workers
    ], key=lambda item: item["pid"]):
        raise AssertionError("Ray validated identity summary differs from worker reports")
    command = (RAY_RAW / "command.txt").read_text(encoding="utf-8")
    environment = (RAY_RAW / "environment.txt").read_text(encoding="utf-8")
    probe_stderr = (RAY_RAW / "probe.stderr.log").read_text(encoding="utf-8")
    if "ray_process_identity_probe_v8.py" not in command or "CUDA_VISIBLE_DEVICES=" not in command:
        raise AssertionError("Ray identity command is not the zero-GPU command")
    if "CUDA_VISIBLE_DEVICES=" not in environment or "CUDA_VISIBLE_DEVICES=\n" not in environment:
        raise AssertionError("Ray identity environment does not show empty CVD")
    forbidden = ("run_v6", "runtime_entry", "image_cls", "training", "model")
    if any(token in (command + environment + probe_stderr).lower() for token in forbidden):
        raise AssertionError("Ray identity raw contains model/training/production execution")
    for name in ("probe.exit.txt", "release-check.exit.txt"):
        if (RAY_RAW / name).read_text(encoding="utf-8").strip() != "0":
            raise AssertionError(f"Ray identity raw exit is not zero: {name}")
    release = (RAY_RAW / "release-check.stdout.txt").read_text(encoding="utf-8")
    if release.split("PROCESSES_BY_COMMAND_NAME", 1)[-1].strip():
        raise AssertionError(f"Ray release check retained processes: {release!r}")
    return {
        "status": "PASS_V8_RAY_PROC_IDENTITY_RAW_RECHECK",
        "node_id": next(iter(node_ids)),
        "worker_count": len(workers),
        "workers": identities,
        "worker_ids": sorted(worker_ids),
        "exit_codes": {name: (RAY_RAW / name).read_text(encoding="utf-8").strip() for name in ("probe.exit.txt", "release-check.exit.txt")},
        "gpu_mapping_rerun": False,
        "release_process_section_empty": True,
    }


def function_ast(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.dump(node, include_attributes=False)
    raise AssertionError(f"missing function {name} in {path}")


def static_check() -> dict[str, Any]:
    v8_source = (CANDIDATE / "gpu_preflight_v8.py").read_text(encoding="utf-8")
    launcher = (CANDIDATE / "run_v6.py").read_text(encoding="utf-8")
    if "time.time_ns()" in v8_source:
        raise AssertionError("v8 GPU/process identity source retains a wall-clock fallback")
    for token in ("parse_proc_stat", "read_process_identity", "validate_process_identity_reports", "process_stat_field_22", "worker_id"):
        if token not in v8_source:
            raise AssertionError(f"v8 identity implementation is missing {token}")
    if "from gpu_preflight_v8 import GPUPreflightError, MAPPING_PROTOCOL, run_preflight" not in launcher:
        raise AssertionError("run_v6.py did not switch to gpu_preflight_v8")
    if "HASHES_v6" in launcher or "HASHES_v7" in launcher or "SCHEMA_VERSION = 6" not in launcher:
        raise AssertionError("launcher schema or stale package-manifest behavior changed")
    if launcher.index("gpu = run_preflight(") > launcher.index("subprocess.Popen("):
        raise AssertionError("preflight is after production launch")
    if function_ast(CANDIDATE / "run_v6.py", "build_production_argv") != function_ast(V7 / "run_v6.py", "build_production_argv"):
        raise AssertionError("v8 changed inherited production argv")
    v7_files = entries(V7, {"HASHES_v7.json"})
    v8_files = entries(CANDIDATE, {"HASHES_v8.json"})
    common = sorted(set(v7_files) & set(v8_files))
    diffs = [path for path in common if v7_files[path] != v8_files[path]]
    if diffs != ["run_v6.py"]:
        raise AssertionError(f"unexpected inherited v7 changes: {diffs!r}")
    v7_raw = {path: value for path, value in v7_files.items() if path.startswith("raw/")}
    if any(v8_files.get(path) != value for path, value in v7_raw.items()):
        raise AssertionError("inherited v7 raw evidence was rewritten")
    return {
        "status": "PASS_V8_STATIC_PROCESS_IDENTITY_WIRING",
        "v7_common_file_count": len(common),
        "only_inherited_v7_difference": diffs,
        "inherited_v7_raw_byte_exact": True,
        "production_argv_unchanged": True,
        "preflight_before_production_popen": True,
        "stale_hash_manifest_reference": False,
        "schema_version": 6,
        "wall_clock_process_fallback": False,
    }


def ast_check() -> dict[str, Any]:
    files = sorted(CANDIDATE.glob("*.py"))
    errors = []
    for path in files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:
            errors.append({"path": path.name, "error": f"{type(exc).__name__}: {exc}"})
    if errors:
        raise AssertionError(f"AST errors: {errors!r}")
    return {"status": "PASS_V8_AST", "python_file_count": len(files), "errors": []}


def source_hash_check() -> dict[str, Any]:
    expected: dict[str, str] = {}
    for root in (DIRECT_RAW / "source-sha256.txt", RAY_RAW / "source-sha256.txt"):
        for line in root.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, remote_path = line.split(None, 1)
            expected[Path(remote_path).name] = digest
    actual = {name: sha256(CANDIDATE / name) for name in ("gpu_preflight_v8.py", "test_process_identity_v8.py", "process_identity_probe_v8.py", "ray_process_identity_probe_v8.py")}
    if expected != actual:
        raise AssertionError(f"remote/source hashes differ: expected={expected!r} actual={actual!r}")
    return {"status": "PASS_V8_REMOTE_SOURCE_HASHES", "files": actual}


def main() -> int:
    v8_manifest = check_manifest(CANDIDATE, CANDIDATE / "HASHES_v8.json", "HASHES_v8.json")
    v8_files = entries(CANDIDATE, {"HASHES_v8.json"})
    v8_raw = {path: value for path, value in v8_files.items() if path.startswith("raw/") or path.startswith("r2-evidence/raw/")}
    if len(v8_raw) != 88 or sum(item[0] for item in v8_raw.values()) != 4125939 or compact_manifest(v8_raw) != "8b1dd4f3bc0fd81dee612c78aaff6b4dee50f3830c4149657dc574dde9025358":
        raise AssertionError("v8 raw aggregate differs from the frozen declaration")
    v7_manifest = read_json(V7 / "HASHES_v7.json")
    v8_reference = read_json(CANDIDATE / "FROZEN_V7_REFERENCE_v8.json")
    inherited = v8_reference["inherited_v7"]
    if inherited["hashes_file_self_sha256"] != sha256(V7 / "HASHES_v7.json") or inherited["package_file_count_excluding_self"] != 116 or inherited["package_total_bytes_excluding_self"] != 4393404 or inherited["package_manifest_sha256"] != v7_manifest["package_manifest_sha256"] or inherited["raw_file_count"] != 65 or inherited["raw_total_bytes"] != 4117257 or inherited["raw_manifest_sha256"] != v7_manifest["raw_manifest_sha256"]:
        raise AssertionError("v8 frozen v7 reference does not match the copied v7 package")
    old_hashes = V7_ACCEPTANCE / "HASHES.json"
    if sha256(old_hashes) != v8_reference["coordinator_acceptance_reference"]["hashes_self_sha256"] or read_json(old_hashes)["file_count"] != 5 or read_json(old_hashes)["total_bytes"] != 35270:
        raise AssertionError("v8 changed the frozen v7 coordinator acceptance reference")
    results = {
        "schema_version": 1,
        "candidate": str(CANDIDATE),
        "acceptance_root": str(ROOT),
        "verdict": "READY_FOR_BOUNDED_GPU",
        "package": v8_manifest,
        "inherited_v7": {
            "package_file_count": 116,
            "package_total_bytes": 4393404,
            "package_manifest_sha256": v7_manifest["package_manifest_sha256"],
            "raw_file_count": 65,
            "raw_total_bytes": 4117257,
            "raw_manifest_sha256": v7_manifest["raw_manifest_sha256"],
            "hashes_self_sha256": sha256(V7 / "HASHES_v7.json"),
            "coordinator_acceptance_reference_unchanged": True,
        },
        "cpu": {
            "process_identity_fixtures": run_cpu_probe("test_process_identity_v8.py"),
            "launcher_contract": run_cpu_probe("launcher_contract_probe_v6.py"),
            "ast": ast_check(),
        },
        "source_hashes": source_hash_check(),
        "direct_raw": check_direct_raw(),
        "ray_raw": check_ray_raw(),
        "static": static_check(),
        "scope": {
            "physical_gpu_mapping_rerun": False,
            "physical_gpu_mapping_reused_byte_exact": True,
            "model_constructed": False,
            "training_started": False,
            "c_ab_run": False,
            "paper_faithful_claim": False,
        },
    }
    output = ROOT / "raw" / "acceptance_probe.stdout.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
