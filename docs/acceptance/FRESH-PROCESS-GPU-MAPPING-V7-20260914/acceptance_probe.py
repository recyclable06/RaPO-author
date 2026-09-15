"""Independent, read-only acceptance probe for the v7 GPU mapping increment."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CANDIDATE = Path(r"C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\diagnostics\fresh-process-resume-20260911\v7")
V6 = CANDIDATE.parent / "v6"
V7_GPU_RAW = CANDIDATE / "raw" / "remote-v7-gpu-preflight-20260914-211"
R2 = CANDIDATE / "r2-evidence"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entries(root: Path, excluded_names: set[str]) -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    for path in root.rglob("*"):
        if path.is_file() and path.name not in excluded_names:
            result[path.relative_to(root).as_posix()] = (path.stat().st_size, sha256(path))
    return dict(sorted(result.items()))


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


def manifest_check(root: Path, manifest_path: Path, excluded_name: str) -> dict[str, Any]:
    actual = entries(root, {excluded_name})
    manifest = read_json(manifest_path)
    listed = {
        item["path"]: (int(item["bytes"]), item["sha256"])
        for item in manifest["files"]
    }
    return {
        "actual_file_count": len(actual),
        "actual_total_bytes": sum(item[0] for item in actual.values()),
        "listed_file_count": len(listed),
        "listed_total_bytes": sum(item[0] for item in listed.values()),
        "missing": sorted(set(listed) - set(actual)),
        "extra": sorted(set(actual) - set(listed)),
        "mismatches": sorted(path for path in set(actual) & set(listed) if actual[path] != listed[path]),
        "manifest_sha256_recomputed": compact_manifest(actual),
        "manifest_sha256_declared": manifest.get("package_manifest_sha256"),
        "self_sha256": sha256(manifest_path),
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
    return {
        "script": script,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "pass": result.returncode == 0,
    }


def load_gpu_module() -> Any:
    path = CANDIDATE / "gpu_preflight_v7.py"
    spec = importlib.util.spec_from_file_location("gpu_preflight_v7_acceptance", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replay_raw_mapping(module: Any, payload: dict[str, Any]) -> dict[str, Any]:
    mapping = payload["ray_mapping"]
    replay = module.validate_worker_reports(
        mapping["workers"],
        payload["requested_uuids"],
        payload["host_gpu_inventory"],
    )
    if replay["worker_physical_uuid_coverage"] != mapping["worker_physical_uuid_coverage"]:
        raise AssertionError("replayed physical coverage differs from the raw result")
    return {
        "status": "PASS_REPLAY_V7_RAW_MAPPING",
        "worker_count": len(replay["workers"]),
        "coverage": replay["worker_physical_uuid_coverage"],
        "worker_smi_policy": replay["nvidia_smi_worker_visibility_policy"],
    }


def validate_gpu_raw(module: Any) -> dict[str, Any]:
    payload = read_json(V7_GPU_RAW / "gpu-preflight-v7.json")
    requested = [module.normalize_uuid(item) for item in payload["requested_uuids"]]
    host = payload["host_gpu_inventory"]
    host_by_uuid = {module.normalize_uuid(item["uuid"]): item for item in host}
    mapping = payload["ray_mapping"]
    workers = mapping["workers"]
    reports = []
    for worker in workers:
        cuda = worker["cuda_probe"]
        runtime = cuda["runtime"]
        driver = cuda["driver"]
        runtime_device = runtime["devices"][0]
        driver_device = driver["devices"][0]
        runtime_uuid = module.normalize_uuid(runtime_device["uuid"])
        driver_uuid = module.normalize_uuid(driver_device["uuid"])
        physical_uuid = module.normalize_uuid(cuda["physical_uuid"])
        driver_pci = module.normalize_pci_bus_id(cuda["driver_pci_bus_id"])
        host_pci = module.normalize_pci_bus_id(host_by_uuid[physical_uuid]["pci_bus_id"])
        cvd_tokens = [item.strip() for item in worker["cuda_visible_devices"].split(",") if item.strip()]
        ray_ids = list(worker["ray_gpu_ids"])
        if len(cvd_tokens) != 1 or module.normalize_uuid(cvd_tokens[0]) != physical_uuid:
            raise AssertionError(f"invalid worker CVD mapping: {worker!r}")
        if len(ray_ids) != 1 or module.normalize_uuid(ray_ids[0]) != physical_uuid:
            raise AssertionError(f"invalid worker Ray UUID mapping: {worker!r}")
        if runtime.get("available") is not True or runtime.get("device_count") != 1 or runtime.get("current_device") != 0:
            raise AssertionError(f"invalid CUDA runtime visibility: {worker!r}")
        if driver.get("available") is not True or driver.get("device_count") != 1:
            raise AssertionError(f"invalid CUDA driver visibility: {worker!r}")
        if not (runtime_uuid == driver_uuid == physical_uuid == module.normalize_uuid(runtime_device["uuid"])):
            raise AssertionError(f"runtime/driver UUID mismatch: {worker!r}")
        if driver_pci != host_pci:
            raise AssertionError(f"CUDA/host PCI mismatch: {worker!r}")
        if len(worker.get("ray_accelerator_ids", {}).get("GPU", [])) != 1:
            raise AssertionError(f"invalid Ray accelerator id evidence: {worker!r}")
        smi_uuids = {
            module.normalize_uuid(line.split(",", 1)[0])
            for line in worker["nvidia_smi_visible"].splitlines()
            if line.strip()
        }
        if smi_uuids != set(module.normalize_uuid(item["uuid"]) for item in host):
            raise AssertionError("worker diagnostic nvidia-smi output was not the recorded full host inventory")
        reports.append(
            {
                "pid": worker["pid"],
                "process_start": worker["process_start"],
                "node_id": worker["node_id"],
                "physical_uuid": physical_uuid,
                "runtime_count": runtime["device_count"],
                "driver_count": driver["device_count"],
                "driver_pci": driver_pci,
                "host_pci": host_pci,
                "cvd_tokens": cvd_tokens,
                "ray_id_kind": "uuid",
            }
        )
    selected = payload["selected_host_gpus"]
    selected_ids = [module.normalize_uuid(item["uuid"]) for item in selected]
    if selected_ids != requested or [item["index"] for item in selected] != [2, 3]:
        raise AssertionError(f"selected host GPU order changed: {selected!r}")
    if any("RTX 3090" not in item["name"] or item["memory_used_mib"] > 1024 for item in selected):
        raise AssertionError("selected host GPU idle/model gate is not evidenced")
    if any(module.normalize_uuid(item["gpu_uuid"]) in set(requested) for item in payload["compute_apps"]):
        raise AssertionError("selected GPU has a compute application in the raw result")
    if len(reports) != 2 or len({item["pid"] for item in reports}) != 2 or len({item["process_start"] for item in reports}) != 2:
        raise AssertionError("worker process identities are not distinct in the raw result")
    if len({item["node_id"] for item in reports}) != 1:
        raise AssertionError("workers are not on one node")
    if set(item["physical_uuid"] for item in reports) != set(requested):
        raise AssertionError("worker physical UUID coverage is not exact")
    if mapping["nvidia_smi_worker_visibility_policy"] != "diagnostic_only_not_a_worker_visibility_gate":
        raise AssertionError("worker nvidia-smi policy is not diagnostic-only")
    if payload["status"] != "PASS" or payload["checked_before_model_construction"] is not True:
        raise AssertionError("preflight raw result is not a pre-model PASS")
    command = (V7_GPU_RAW / "command.txt").read_text(encoding="utf-8")
    stdout = (V7_GPU_RAW / "probe.stdout.log").read_text(encoding="utf-8")
    stderr = (V7_GPU_RAW / "probe.stderr.log").read_text(encoding="utf-8")
    forbidden = ("run_v6.py", "runtime_entry_v6.py", "image_cls_cil_rapo.py", "model construction", "training")
    if "gpu_preflight_v7.py" not in command or any(token in command.lower() for token in forbidden):
        raise AssertionError("real probe command is not limited to the v7 preflight")
    if '"status": "PASS"' not in stdout or "GPUPreflightError" in stderr:
        raise AssertionError("real probe stdout/stderr does not evidence a clean PASS")
    for name in ("probe.exit.txt", "release-check.exit.txt", "final-check.exit.txt"):
        if (V7_GPU_RAW / name).read_text(encoding="utf-8").strip() != "0":
            raise AssertionError(f"{name} is not zero")
    release = (V7_GPU_RAW / "release-check.stdout.txt").read_text(encoding="utf-8")
    final = (V7_GPU_RAW / "final-check.stdout.txt").read_text(encoding="utf-8")
    if any(uuid.upper() not in release.upper() for uuid in payload["requested_uuids"]):
        raise AssertionError("release check does not include both selected UUIDs")
    final_apps = final.split("APPS", 1)[1].split("USER_PROCESSES", 1)[0]
    if any(uuid.lower() in final_apps.lower() for uuid in payload["requested_uuids"]):
        raise AssertionError("a selected UUID remains in the final process list")
    user_processes = final.split("USER_PROCESSES", 1)[1].strip()
    if user_processes:
        raise AssertionError(f"final user-process check is not empty: {user_processes!r}")
    if any(token in final.lower() for token in ("raylet", "gcs_server", "run_v6", "runtime_entry_v6", "image_cls_cil_rapo")):
        raise AssertionError("final check retains a probe process")
    return {
        "status": "PASS_V7_REAL_MAPPING_RAW_RECHECK",
        "requested_uuids": requested,
        "selected_indices": [item["index"] for item in selected],
        "host_gpu_count": len(host),
        "worker_reports": reports,
        "coverage": sorted(item["physical_uuid"] for item in reports),
        "worker_smi_full_host_confirmed": True,
        "release_exit_codes": {name: (V7_GPU_RAW / name).read_text(encoding="utf-8").strip() for name in ("probe.exit.txt", "release-check.exit.txt", "final-check.exit.txt")},
        "model_constructed": False,
        "training_started": False,
    }


def ast_file_check() -> dict[str, Any]:
    files = sorted(CANDIDATE.glob("*.py"))
    errors = []
    for path in files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:
            errors.append({"path": path.name, "error": f"{type(exc).__name__}: {exc}"})
    return {"python_file_count": len(files), "errors": errors, "pass": not errors}


def function_ast(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.dump(node, include_attributes=False)
    raise AssertionError(f"missing function {name} in {path}")


def static_wiring_check() -> dict[str, Any]:
    source = (CANDIDATE / "run_v6.py").read_text(encoding="utf-8")
    v6_source = (V6 / "run_v6.py").read_text(encoding="utf-8")
    required = [
        "from gpu_preflight_v7 import GPUPreflightError, MAPPING_PROTOCOL, run_preflight",
        "gpu_mapping_protocol",
        "PASS_GPU_PREFLIGHT_ONLY",
        "gpu = run_preflight(",
        "SCHEMA_VERSION = 6",
    ]
    if any(token not in source for token in required):
        raise AssertionError("v7 launcher mapping wiring is incomplete")
    if any(token in source for token in ("HASHES_v6", "HASHES_v7")):
        raise AssertionError("launcher unexpectedly validates a stale package manifest")
    if function_ast(CANDIDATE / "run_v6.py", "build_production_argv") != function_ast(V6 / "run_v6.py", "build_production_argv"):
        raise AssertionError("v7 changed the inherited production argv builder")
    common_v6 = entries(V6, {"HASHES_v6.json"})
    common_v7 = entries(CANDIDATE, {"HASHES_v7.json"})
    common = sorted(set(common_v6) & set(common_v7))
    diffs = [path for path in common if common_v6[path] != common_v7[path]]
    if diffs != ["run_v6.py"]:
        raise AssertionError(f"unexpected inherited v6 byte changes: {diffs!r}")
    if source.index("gpu = run_preflight(") > source.index("subprocess.Popen("):
        raise AssertionError("GPU preflight is not before production subprocess launch")
    return {
        "status": "PASS_V7_LAUNCHER_WIRING_STATIC",
        "common_v6_file_count": len(common),
        "only_inherited_v6_difference": diffs,
        "production_argv_builder_unchanged": True,
        "stale_hash_manifest_reference": False,
        "preflight_before_production_popen": True,
        "result_schema_version": 6,
    }


def process_identity_check() -> dict[str, Any]:
    v7_source = (CANDIDATE / "gpu_preflight_v7.py").read_text(encoding="utf-8")
    v6_source = (V6 / "gpu_preflight_v6.py").read_text(encoding="utf-8")
    v7_line = next(index for index, line in enumerate(v7_source.splitlines(), 1) if '"process_start": str(time.time_ns())' in line)
    v6_proc_line = next(index for index, line in enumerate(v6_source.splitlines(), 1) if 'with open(f"/proc/' in line)
    return {
        "status": "BLOCKER_FPP_V7_PROCESS_IDENTITY",
        "finding_id": "FPP-V7-001",
        "v7_process_start_line": v7_line,
        "v7_uses_report_timestamp": '"process_start": str(time.time_ns())' in v7_source,
        "v7_reads_proc_process_start": "/proc/" in v7_source and "fields[21]" in v7_source,
        "v6_actual_process_start_line": v6_proc_line,
        "raw_values_are_epoch_nanoseconds": True,
        "impact": "The worker identity guard can accept two reports from one process because process_start is generated at report time; it is not an OS process-start identity.",
    }


def main() -> int:
    v7_manifest = manifest_check(CANDIDATE, CANDIDATE / "HASHES_v7.json", "HASHES_v7.json")
    v6_manifest = manifest_check(V6, V6 / "HASHES_v6.json", "HASHES_v6.json")
    v7_actual = entries(CANDIDATE, {"HASHES_v7.json"})
    v7_raw = {
        path: value
        for path, value in v7_actual.items()
        if path.startswith("raw/") or path.startswith("r2-evidence/raw/")
    }
    v7_manifest["raw_file_count"] = len(v7_raw)
    v7_manifest["raw_total_bytes"] = sum(value[0] for value in v7_raw.values())
    v7_manifest["raw_manifest_sha256_recomputed"] = compact_manifest(v7_raw)
    v7_manifest["raw_manifest_sha256_declared"] = read_json(CANDIDATE / "HASHES_v7.json")["raw_manifest_sha256"]

    r2_manifest = read_json(R2 / "DELIVERY_MANIFEST-r2.json")
    r2_actual = entries(R2, {"DELIVERY_MANIFEST-r2.json"})
    r2_listed = {
        item["path"]: (int(item["bytes"]), item["sha256"])
        for item in r2_manifest["files"]
    }
    if r2_actual != dict(sorted(r2_listed.items())):
        raise AssertionError("copied r2 delivery manifest does not match its files")

    module = load_gpu_module()
    raw_payload = read_json(V7_GPU_RAW / "gpu-preflight-v7.json")
    results: dict[str, Any] = {
        "schema_version": 1,
        "candidate": str(CANDIDATE),
        "acceptance_root": str(ROOT),
        "package": {"v7": v7_manifest, "inherited_v6": v6_manifest},
        "r2_delivery": {
            "file_count": len(r2_actual),
            "total_bytes": sum(item[0] for item in r2_actual.values()),
            "manifest_self_sha256": sha256(R2 / "DELIVERY_MANIFEST-r2.json"),
            "declared_file_count": r2_manifest["file_count"],
            "declared_total_bytes": r2_manifest["total_bytes"],
            "matches": True,
        },
        "cpu": {
            "mapping_fixtures": run_cpu_probe("test_gpu_mapping_v7.py"),
            "launcher_contract": run_cpu_probe("launcher_contract_probe_v6.py"),
            "ast": ast_file_check(),
            "raw_replay": replay_raw_mapping(module, raw_payload),
            "launcher_static": static_wiring_check(),
        },
        "real_raw": validate_gpu_raw(module),
        "parser_identity_boundary": {
            "inherited_v6_parser_identity": read_json(CANDIDATE / "FROZEN_V6_REFERENCE_v7.json")["inherited_v6"]["parser_identity_sha256"],
            "r2_parser_identity": read_json(R2 / "FROZEN_V6_IDENTITY.json")["parser_probe"]["identity_sha256"],
            "equal": False,
            "source_entry_sha256_equal": read_json(CANDIDATE / "FROZEN_V6_REFERENCE_v7.json")["inherited_v6"]["source_entry_sha256"] == read_json(R2 / "FROZEN_V6_IDENTITY.json")["production_source"]["sha256"],
            "r2_remote_source_root": read_json(R2 / "FROZEN_V6_IDENTITY.json")["production_source"]["remote_root"],
            "interpretation": "The r2 parser hash is path/config-bound and is not substituted for the inherited v6 parser identity.",
        },
        "process_identity": process_identity_check(),
        "verdict": "NEEDS_PROTOCOL_REVISION",
        "finding": {
            "id": "FPP-V7-001",
            "severity": "blocking_for_bounded_gpu_readiness",
            "summary": "gpu_preflight_v7.py records time.time_ns() at report time as process_start instead of carrying the real OS process-start identity used by v6.",
            "required_fix": "Restore an actual worker process-start identity (for example /proc/<pid>/stat field 22 on Linux) and validate that the required identity fields are present before accepting two workers.",
        },
        "scope": {
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
