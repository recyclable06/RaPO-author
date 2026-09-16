"""Independent incremental acceptance probe for the v9 init-compat candidate."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CANDIDATE = Path(
    r"C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\diagnostics\fresh-process-resume-20260911\v9"
)
V8 = CANDIDATE.parent / "v8"
SOURCE = Path(r"C:\Users\Administrator\.codex\worktrees\8ac5\RaPO-author")
ENTRY_REL = "examples/baselines/img_cls_cil/image_cls_cil_rapo.py"
TEST_REL = "tests/author_fixes/test_cil_resume.py"
REWARD_REL = "examples/reward_function/cls.py"
REWARD_SHA = "028b9c9721c0c1d80b0ae3652aec31c8fb458827ca4d079b1253b537099978a1"
V9_PACKAGE_SHA = "3767c12fd6bc90ef43479486a057ae92b557aaa4ec276c12d5713871597bae7a"
V9_RAW_SHA = "9d41841454ac9cc9dddd226f8d52613514675a5ab04b5188d2cd0b1f5736485c"
V9_HASHES_SELF_SHA = "45f79cbf83d004b6fd05c4e1ef61fe2f5b296dba1771aae24e45e570b890ee39"
V8_PACKAGE_SHA = "7dbfe1ea8666fed036ae9d59d0b1697ec0d0f2b265d4869e643859bde494b34b"
V8_RAW_SHA = "8b1dd4f3bc0fd81dee612c78aaff6b4dee50f3830c4149657dc574dde9025358"
V8_HASHES_SELF_SHA = "abd4ccad8d3f2159cd636505b3c78bcafb14e4890e31d1cc81656d97ddc41420"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
    # Match the frozen package algorithm: the list is path-sorted, and each
    # record is serialized in path/bytes/sha256 insertion order.
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def is_raw(path: str) -> bool:
    return path.startswith("raw/") or "/raw/" in path


def check_manifest(root: Path, hashes_path: Path, excluded_name: str) -> dict[str, Any]:
    actual = entries(root, {excluded_name})
    declared = read_json(hashes_path)
    listed = {
        str(item["path"]): (int(item["bytes"]), str(item["sha256"]))
        for item in declared["files"]
    }
    if actual != dict(sorted(listed.items())):
        missing = sorted(set(listed) - set(actual))
        extra = sorted(set(actual) - set(listed))
        changed = sorted(path for path in set(actual) & set(listed) if actual[path] != listed[path])
        raise AssertionError(f"manifest mismatch: missing={missing!r} extra={extra!r} changed={changed!r}")
    raw = {path: item for path, item in actual.items() if is_raw(path)}
    result = {
        "file_count": len(actual),
        "total_bytes": sum(item[0] for item in actual.values()),
        "manifest_sha256": compact_manifest(actual),
        "declared_manifest_sha256": declared["package_manifest_sha256"],
        "self_sha256": sha256(hashes_path),
        "raw_file_count": len(raw),
        "raw_total_bytes": sum(item[0] for item in raw.values()),
        "raw_manifest_sha256": compact_manifest(raw),
        "declared_raw_file_count": declared.get("raw_file_count"),
        "declared_raw_total_bytes": declared.get("raw_total_bytes"),
        "declared_raw_manifest_sha256": declared.get("raw_manifest_sha256"),
    }
    if result["manifest_sha256"] != result["declared_manifest_sha256"]:
        raise AssertionError(f"package compact manifest mismatch: {result!r}")
    if result["raw_file_count"] != result["declared_raw_file_count"] or result["raw_total_bytes"] != result["declared_raw_total_bytes"] or result["raw_manifest_sha256"] != result["declared_raw_manifest_sha256"]:
        raise AssertionError(f"raw compact manifest mismatch: {result!r}")
    return result


def json_log(path: Path) -> dict[str, Any]:
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        if line.lstrip().startswith("{"):
            value = json.loads(line)
            if isinstance(value, dict):
                return value
    raise AssertionError(f"no JSON object found in {path}")


def read_exit(path: Path) -> int | None:
    if not path.is_file():
        return None
    return int(path.read_text(encoding="utf-8").strip())


def file_record(path: Path, relative: str | None = None) -> dict[str, Any]:
    return {"path": relative or str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}


def runtime_manifest(entry: Path) -> dict[str, Any]:
    root = entry.resolve().parents[3]
    specs = {
        "verl": {".py"},
        "examples": {".jinja", ".json", ".py", ".yaml", ".yml"},
        "scripts/image": {".json", ".py", ".sh", ".yaml", ".yml"},
    }
    excluded = {"__pycache__", ".git", "cache", "caches", "docs", "logs", "log", "output", "outputs", "saves", "tmp", "temp"}
    relative: set[str] = set()
    for prefix, extensions in specs.items():
        base = root / prefix
        if not base.is_dir():
            raise AssertionError(f"runtime source root is missing: {base}")
        for item in base.rglob("*"):
            if not item.is_file() or item.suffix.lower() not in extensions:
                continue
            parts = set(item.relative_to(root).parts)
            if parts & excluded or item.name.startswith("."):
                continue
            relative.add(item.relative_to(root).as_posix())
    for name in ("requirements.txt", "environment.yml", "environment.lock.yml"):
        item = root / name
        if not item.is_file():
            raise AssertionError(f"runtime source identity file is missing: {item}")
        relative.add(name)
    files = [file_record(root / name, name) for name in sorted(relative)]
    return {"root": str(root), "file_count": len(files), "files": files, "manifest_sha256": hashlib.sha256(canonical(files)).hexdigest()}


def check_candidate_and_inheritance() -> dict[str, Any]:
    v9 = check_manifest(CANDIDATE, CANDIDATE / "HASHES_v9.json", "HASHES_v9.json")
    v8 = check_manifest(V8, V8 / "HASHES_v8.json", "HASHES_v8.json")
    if v9["file_count"] != 205 or v9["total_bytes"] != 4658581 or v9["manifest_sha256"] != V9_PACKAGE_SHA or v9["raw_file_count"] != 128 or v9["raw_total_bytes"] != 4185383 or v9["raw_manifest_sha256"] != V9_RAW_SHA or v9["self_sha256"] != V9_HASHES_SELF_SHA:
        raise AssertionError(f"v9 frozen package declaration differs: {v9!r}")
    if v8["file_count"] != 150 or v8["total_bytes"] != 4471333 or v8["manifest_sha256"] != V8_PACKAGE_SHA or v8["raw_file_count"] != 88 or v8["raw_total_bytes"] != 4125939 or v8["raw_manifest_sha256"] != V8_RAW_SHA or v8["self_sha256"] != V8_HASHES_SELF_SHA:
        raise AssertionError(f"v8 frozen package declaration differs: {v8!r}")

    v9_files = entries(CANDIDATE, {"HASHES_v9.json"})
    v8_files = entries(V8, {"HASHES_v8.json"})
    common = sorted(set(v9_files) & set(v8_files))
    changed = [path for path in common if v9_files[path] != v8_files[path]]
    if len(common) != 150 or changed:
        raise AssertionError(f"v9 inherited paths are not byte exact: common={len(common)} changed={changed!r}")
    expected_nonraw_delta = {
        "COMMANDS_INIT_COMPAT_v9.md",
        "EXPECTED_IDENTITY_v9.json",
        "FROZEN_V8_REFERENCE_v9.json",
        "HASHES_v8.json",
        "INIT_COMPAT_PROTOCOL_v9.md",
        "PPO_CONFIG_TEMPLATE_v9.json",
        "PROGRESS_V9.md",
        "README_V9_DELTA.md",
        "argv_validate_v9.py",
        "freeze_hashes_v9.py",
        "gpu_preflight_v9.py",
        "production_reward_probe_v9.py",
        "run_v9.py",
        "test_init_compat_v9.py",
        "vllm_numeric_init_probe_v9.py",
    }
    actual_nonraw_delta = {path for path in set(v9_files) - set(v8_files) if not is_raw(path)}
    if actual_nonraw_delta != expected_nonraw_delta:
        raise AssertionError(f"unexpected nonraw v9 delta: {sorted(actual_nonraw_delta)!r}")

    reference = read_json(CANDIDATE / "FROZEN_V8_REFERENCE_v9.json")
    inherited = reference["inherited_v8"]
    expected_inherited = {
        "relative_root": "../v8",
        "hashes_file_self_sha256": V8_HASHES_SELF_SHA,
        "package_file_count_excluding_self": 150,
        "package_total_bytes_excluding_self": 4471333,
        "package_manifest_sha256": V8_PACKAGE_SHA,
        "raw_file_count": 88,
        "raw_total_bytes": 4125939,
        "raw_manifest_sha256": V8_RAW_SHA,
        "status": "V8_GPU_GATE_PASS_INIT_EXIT1_ZERO_UPDATES",
    }
    if inherited != expected_inherited:
        raise AssertionError(f"frozen v8 reference differs: {inherited!r}")
    gpu_acceptance = reference["coordinator_v8_gpu_acceptance_reference"]
    if gpu_acceptance != {
        "relative_root": "docs/diagnostics/FRESH-PROCESS-V8-GPU-20260916",
        "delivery_manifest_self_sha256": "0f080e2e55116a770565b81533041aa28b70d4d0c60542991d74918c945bbcfb",
        "file_count": 239,
        "total_bytes": 2512119,
        "modified": False,
        "note": "Use the corrected frozen byte total; do not inherit the report's old 2511961 typo.",
    }:
        raise AssertionError("frozen coordinator v8 GPU acceptance reference changed")
    return {
        "v9": v9,
        "v8": v8,
        "v8_common_file_count": len(common),
        "v8_common_byte_exact": True,
        "nonraw_delta_paths": sorted(actual_nonraw_delta),
        "frozen_v8_reference_unchanged": True,
    }


def check_identity_and_scientific_delta() -> dict[str, Any]:
    expected = read_json(CANDIDATE / "EXPECTED_IDENTITY_v9.json")
    old = read_json(CANDIDATE / "EXPECTED_IDENTITY_v6.json")
    entry = SOURCE / ENTRY_REL
    test = SOURCE / TEST_REL
    reward = SOURCE / REWARD_REL
    if not entry.is_file() or not test.is_file() or not reward.is_file():
        raise AssertionError("frozen 8ac5 source identity files are missing")
    actual_runtime = runtime_manifest(entry)
    target = expected["target"]
    if target["production_source"] != {"relative_path": ENTRY_REL, "bytes": 102269, "sha256": "3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3"}:
        raise AssertionError("v9 production target identity declaration changed")
    if target["test_reference"] != {"relative_path": TEST_REL, "bytes": 24215, "sha256": "2bb64dccbce91409840d04344a30a58b76265ae77145ab33b4819a3613b4aadf"}:
        raise AssertionError("v9 test target identity declaration changed")
    actual_entry = file_record(entry, ENTRY_REL)
    actual_test = file_record(test, TEST_REL)
    if actual_entry["path"] != ENTRY_REL or actual_entry["bytes"] != target["production_source"]["bytes"] or actual_entry["sha256"] != target["production_source"]["sha256"] or actual_test["path"] != TEST_REL or actual_test["bytes"] != target["test_reference"]["bytes"] or actual_test["sha256"] != target["test_reference"]["sha256"]:
        raise AssertionError("8ac5 source identity does not match v9 expected identity")
    if actual_runtime["file_count"] != 91 or actual_runtime["manifest_sha256"] != "947de3842eadb716d241eb4bb4f2fff62f2cfe39305cf03ffd0fbe35abd052e1":
        raise AssertionError("8ac5 runtime source manifest does not match v9 expected identity")
    if expected["runtime_source_manifest"] != {"file_count": 91, "manifest_sha256": "947de3842eadb716d241eb4bb4f2fff62f2cfe39305cf03ffd0fbe35abd052e1"}:
        raise AssertionError("v9 runtime manifest declaration changed")
    if sha256(CANDIDATE / "MODEL_MANIFEST_v6.json") != expected["model"]["manifest_sha256"] or sha256(CANDIDATE / "INPUT_MANIFEST_v6.json") != expected["input"]["manifest_sha256"]:
        raise AssertionError("v9 model/input manifest file hashes do not match expected identity")
    if sha256(reward) != REWARD_SHA or expected["reward_identity"] != {"spec": f"{REWARD_REL}:compute_score", "function_name": "compute_score", "source_sha256": REWARD_SHA, "require_callable": True}:
        raise AssertionError("reward source identity does not match v9 expected identity")

    unchanged_keys = ("target", "model", "input", "config_bindings", "config_bindings_sha256", "recipe", "gpu", "trajectory_close_tolerances", "claims_not_authorized", "v6_requirements")
    for key in unchanged_keys:
        if expected[key] != old[key]:
            raise AssertionError(f"scientific or source identity section changed unexpectedly: {key}")
    if expected["config_template"]["file"] != "PPO_CONFIG_TEMPLATE_v9.json" or expected["config_template"]["bytes"] != 6589 or expected["config_template"]["sha256"] != "9e571e5847e8a7ea5e8696d74c47e1d19bf605860bf9762ad940989a449d3084":
        raise AssertionError("v9 template identity declaration is not frozen")
    if expected["gpu_init_compat"] != {
        "cuda_device_order": "PCI_BUS_ID",
        "cuda_visible_devices_kind": "ordered_numeric",
        "physical_selection_source": "ordered requested UUIDs",
        "worker_identity_source": "actual CUDA runtime/driver UUID+PCI and OS process identity",
    }:
        raise AssertionError("v9 GPU init compatibility declaration changed")

    template_v6 = read_json(CANDIDATE / "PPO_CONFIG_TEMPLATE_v6.json")
    template_v9 = read_json(CANDIDATE / "PPO_CONFIG_TEMPLATE_v9.json")
    reward_v6 = template_v6["worker"]["reward"]
    reward_v9 = template_v9["worker"]["reward"]
    if not str(reward_v6["reward_function"]).endswith(REWARD_REL) or str(reward_v9["reward_function"]) != "${SOURCE_ROOT}/examples/reward_function/cls.py:compute_score" or "reward_function_name" in reward_v9:
        raise AssertionError("v9 reward template does not contain the exact callable form")
    normalized_v6 = copy.deepcopy(template_v6)
    normalized_v9 = copy.deepcopy(template_v9)
    for value in (normalized_v6, normalized_v9):
        reward_value = value["worker"]["reward"]
        reward_value.pop("reward_function_name", None)
        reward_value["reward_function"] = "__REWARD_CALLABLE__"
    if normalized_v6 != normalized_v9:
        raise AssertionError("v9 template changed content outside the reward callable delta")
    return {
        "entry": file_record(entry, ENTRY_REL),
        "test_reference": file_record(test, TEST_REL),
        "runtime_source_manifest": {"file_count": actual_runtime["file_count"], "manifest_sha256": actual_runtime["manifest_sha256"]},
        "reward_source_sha256": sha256(reward),
        "model_manifest_sha256": sha256(CANDIDATE / "MODEL_MANIFEST_v6.json"),
        "input_manifest_sha256": sha256(CANDIDATE / "INPUT_MANIFEST_v6.json"),
        "scientific_recipe_byte_exact_with_v6": True,
        "template_delta_only_reward_callable": True,
    }


def run_probe(script: str, extra: list[str] | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    command = [sys.executable, "-B", script, *(extra or [])]
    result = subprocess.run(command, cwd=str(CANDIDATE), env=env, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(f"{script} failed with {result.returncode}: stdout={result.stdout!r} stderr={result.stderr!r}")
    return {"command": command, "cwd": str(CANDIDATE), "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def run_code_probe(code: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    result = subprocess.run([sys.executable, "-B", "-c", code], cwd=str(CANDIDATE), env=env, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(f"import probe failed: stdout={result.stdout!r} stderr={result.stderr!r}")
    return {"command": [sys.executable, "-B", "-c", code], "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def ast_function(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.dump(node, include_attributes=False)
    raise AssertionError(f"missing {name} in {path}")


def check_static_and_cpu() -> dict[str, Any]:
    cpu = {
        "init_compat_fixtures": run_probe("test_init_compat_v9.py"),
        "launcher_contract": run_probe("launcher_contract_probe_v6.py"),
    }
    if "PASS_V9_INIT_COMPAT_FIXTURES" not in cpu["init_compat_fixtures"]["stdout"] or "PASS_V6_LAUNCHER_C_AB_CONTRACT" not in cpu["launcher_contract"]["stdout"]:
        raise AssertionError("v9 CPU compatibility fixtures did not pass")
    import_probe = run_code_probe("import argv_validate_v9, gpu_preflight_v9, run_v9, production_reward_probe_v9, vllm_numeric_init_probe_v9, test_init_compat_v9; print('PASS_V9_AST_IMPORT')")
    py_files = sorted(CANDIDATE.glob("*.py"))
    for path in py_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    pycache = [str(path) for path in CANDIDATE.rglob("__pycache__")]
    if pycache:
        raise AssertionError(f"candidate produced bytecode cache: {pycache!r}")

    run_v9 = (CANDIDATE / "run_v9.py").read_text(encoding="utf-8")
    run_v8 = (V8 / "run_v6.py").read_text(encoding="utf-8")
    validator = (CANDIDATE / "argv_validate_v9.py").read_text(encoding="utf-8")
    preflight = (CANDIDATE / "gpu_preflight_v9.py").read_text(encoding="utf-8")
    required_run_tokens = (
        "from argv_validate_v9 import ArgvValidationError, validate_effective_argv",
        "from gpu_preflight_v9 import GPUPreflightError, MAPPING_PROTOCOL, run_preflight",
        "EXPECTED_IDENTITY_v9.json",
        "config template does not match EXPECTED_IDENTITY_v9.json",
        "--launch_script",
        "run_v9.py",
        'os.environ["CUDA_VISIBLE_DEVICES"] = args.cuda_visible_devices',
        'os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"',
        'env["CUDA_VISIBLE_DEVICES"] = args.cuda_visible_devices',
        'env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"',
        'env["RAPO_DIAG_CUDA_VISIBLE_DEVICES"] = args.cuda_visible_devices',
        'env["RAPO_DIAG_CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"',
        'env["RAPO_DIAG_SCHEMA"] = "6"',
        "runtime_entry_v6.py",
        "subprocess.Popen(",
    )
    for token in required_run_tokens:
        if token not in run_v9:
            raise AssertionError(f"run_v9.py missing required wiring token: {token}")
    if "run_v6" in run_v9 or "HASHES_v" in run_v9:
        raise AssertionError("run_v9.py retains stale v6 launcher or package-manifest wiring")
    if not (run_v9.index("os.environ[\"CUDA_VISIBLE_DEVICES\"] = args.cuda_visible_devices") < run_v9.index("render_config(template, config_path") < run_v9.index("ledger = validate_effective_argv") < run_v9.index("gpu = run_preflight(") < run_v9.index("subprocess.Popen(")):
        raise AssertionError("v9 launcher gate order is not CVD -> render -> validator -> preflight -> production")
    if "SCHEMA_VERSION = 6" not in run_v9 or "MAPPING_SCHEMA_VERSION = 9" not in preflight or 'MAPPING_PROTOCOL = "FPP-V8-INIT-COMPAT"' not in preflight:
        raise AssertionError("v9 schema/protocol wiring is not explicit")
    for token in ("_reward_callable_identity", "reward_identity", "source_sha256", "deep_post_init"):
        if token not in validator:
            raise AssertionError(f"v9 validator missing reward identity gate token: {token}")
    for token in ("resolve_driver_cuda_visible_devices", "PCI_BUS_ID", "parse_proc_stat", "process_stat_field_22", "cuda_probe", "ray_mapping", "worker_id"):
        if token not in preflight:
            raise AssertionError(f"v9 preflight missing inherited identity/mapping gate token: {token}")
    normalized_v9_argv_builder = ast_function(CANDIDATE / "run_v9.py", "build_production_argv").replace("run_v9.py", "run_v6.py")
    if normalized_v9_argv_builder != ast_function(V8 / "run_v6.py", "build_production_argv"):
        raise AssertionError("v9 changed the inherited scientific/recipe production argv")
    return {
        "cpu": cpu,
        "import_probe": import_probe,
        "top_level_python_file_count": len(py_files),
        "ast_parse_all_top_level_python": True,
        "pycache_absent": True,
        "launcher_gate_order": "CVD -> template render -> effective argv validator -> GPU preflight -> production Popen",
        "production_argv_builder_byte_equivalent_to_v8_except_launcher_filename": True,
        "v9_validator_and_preflight_wiring": True,
    }


def check_vllm_raw() -> dict[str, Any]:
    raw = CANDIDATE / "raw" / "remote-vllm-numeric-20260916-211"
    result = json_log(raw / "probe.stdout.log")
    command = (raw / "command.txt").read_text(encoding="utf-8")
    if read_exit(raw / "probe.exit.txt") != 0 or result.get("status") != "PASS" or result.get("vllm_version") != "0.8.1" or result.get("numeric_cvd") != ["2", "3"] or result.get("numeric_result") != [2, 3] or result.get("model_constructed") is not False or result.get("engine_initialized") is not False:
        raise AssertionError(f"vLLM numeric raw does not pass the frozen no-model gate: {result!r}")
    if not result.get("uuid_cvd_rejected", "").startswith("ValueError: invalid literal for int()") or "vllm_numeric_init_probe_v9.py" not in command or "--numeric-cvd 2,3" not in command:
        raise AssertionError("vLLM raw does not preserve the known numeric-vs-UUID conversion evidence")
    return {
        "status": "PASS_V9_VLLM_NUMERIC_NO_MODEL_RAW_RECHECK",
        "version": result["vllm_version"],
        "numeric_cvd": result["numeric_cvd"],
        "numeric_result": result["numeric_result"],
        "uuid_cvd_rejected": result["uuid_cvd_rejected"],
        "model_constructed": False,
        "engine_initialized": False,
        "exit_code": 0,
    }


def check_reward_raw() -> dict[str, Any]:
    raw = CANDIDATE / "raw" / "remote-reward-init-20260916-211"
    probe_paths = list(raw.rglob("probe-result.json"))
    if len(probe_paths) != 1:
        raise AssertionError(f"reward raw probe-result count is {len(probe_paths)}")
    result = read_json(probe_paths[0])
    if read_exit(raw / "exit.txt") != 0 or result.get("status") != "PASS_PRODUCTION_REWARD_INIT_COMPAT":
        raise AssertionError(f"reward raw does not pass: {result!r}")
    command = (raw / "command.txt").read_text(encoding="utf-8")
    environment = (raw / "environment.txt").read_text(encoding="utf-8")
    if "production_reward_probe_v9.py" not in command or "PPO_CONFIG_TEMPLATE_v9.json" not in command or "EXPECTED_IDENTITY_v9.json" not in command or "CUDA_VISIBLE_DEVICES=\n" not in environment or "CUDA_DEVICE_ORDER=PCI_BUS_ID" not in environment:
        raise AssertionError("reward raw command/environment is not the frozen v9 no-GPU init probe")
    effective = result["effective_reward_config"]
    post_init = result["reward_post_init"]
    serialized = result["serialized_reward_config"]
    local = result["local_reward_loader"]
    validator = result["production_validator"]
    worker = result["ray_worker_roundtrip"]["worker_report"]
    invalid = result["invalid_reward_checks"]
    if not str(effective["reward_function"]).endswith(REWARD_REL) or effective["reward_function_name"] != "compute_score" or effective["source_sha256"] != REWARD_SHA:
        raise AssertionError(f"effective reward identity mismatch: {effective!r}")
    if post_init["call_count"] != 1 or len(post_init["calls"]) != 1 or not str(post_init["calls"][0]["before_reward_function"]).endswith(":compute_score") or post_init["calls"][0]["before_reward_function_name"] is not None:
        raise AssertionError(f"RewardConfig.post_init evidence mismatch: {post_init!r}")
    if not str(serialized["reward_function"]).endswith(REWARD_REL) or ":" in str(serialized["reward_function"]) or serialized["reward_function_name"] != "compute_score":
        raise AssertionError(f"serialized RewardConfig identity mismatch: {serialized!r}")
    if local["loaded_callable_name"] != "compute_score" or worker["loaded_callable_name"] != "compute_score" or local["reward_function_name"] != "compute_score" or worker["reward_function_name"] != "compute_score":
        raise AssertionError(f"local/Ray callable identity mismatch: local={local!r} worker={worker!r}")
    if validator["status"] != "PASS" or validator["reward_identity"]["callable_name"] != "compute_score" or validator["reward_identity"]["function_name"] != "compute_score" or validator["reward_identity"]["source_sha256"] != REWARD_SHA:
        raise AssertionError(f"production validator reward identity mismatch: {validator!r}")
    if not invalid["validator_rejected_bad_callable"] or not invalid["loader_rejected_bad_callable"] or invalid["bad_reward_function_name_after_post_init"] != "main":
        raise AssertionError(f"invalid reward callable negative case did not reject: {invalid!r}")

    source_hash_stages = {
        "effective_reward_config": effective.get("source_sha256") == REWARD_SHA,
        "production_validator": validator["reward_identity"].get("source_sha256") == REWARD_SHA,
        "serialized_reward_config": serialized.get("source_sha256") == REWARD_SHA,
        "local_reward_loader": local.get("source_sha256") == REWARD_SHA,
        "ray_worker": worker.get("source_sha256") == REWARD_SHA,
    }
    missing = [name for name, present in source_hash_stages.items() if not present]
    if "source_sha256" in (CANDIDATE / "production_reward_probe_v9.py").read_text(encoding="utf-8").split("def _ray_worker_roundtrip", 1)[1].split("def _invalid_reward_checks", 1)[0]:
        raise AssertionError("unexpectedly changed source-hash interpretation of Ray worker probe")
    return {
        "status": "PASS_PRODUCTION_REWARD_INIT_COMPAT_RAW_CALLABLE_ONLY",
        "post_init_call_count": post_init["call_count"],
        "serialized_callable": serialized["reward_function_name"],
        "local_callable": local["loaded_callable_name"],
        "ray_worker_callable": worker["loaded_callable_name"],
        "validator_source_sha256": validator["reward_identity"]["source_sha256"],
        "invalid_main_rejected_by_validator": invalid["validator_rejected_bad_callable"],
        "invalid_main_rejected_by_loader": invalid["loader_rejected_bad_callable"],
        "model_constructed": result["model_constructed"],
        "training_started": result["training_started"],
        "source_hash_stages": source_hash_stages,
        "source_hash_missing_from_stages": missing,
        "strict_same_source_hash_across_serialized_local_ray": not missing,
    }


def pci_key(value: str) -> tuple[int, int, int]:
    match = re.search(r"([0-9a-fA-F]+):([0-9a-fA-F]+)\.([0-9]+)$", value)
    if not match:
        raise AssertionError(f"invalid PCI bus id: {value!r}")
    return int(match.group(1), 16), int(match.group(2), 16), int(match.group(3))


def parse_proc_stat(raw: str, expected_pid: int) -> dict[str, Any]:
    opening = raw.find("(")
    closing = raw.rfind(")")
    if opening <= 0 or closing <= opening:
        raise AssertionError(f"invalid /proc stat delimiters: {raw!r}")
    prefix = raw[:opening].strip()
    if not prefix.isdigit() or int(prefix) != expected_pid:
        raise AssertionError(f"invalid /proc stat pid: {raw!r}")
    fields = raw[closing + 1 :].strip().split()
    if len(fields) < 20 or not fields[19].isdigit():
        raise AssertionError(f"invalid /proc stat field 22: {raw!r}")
    return {"pid": expected_pid, "comm": raw[opening + 1 : closing], "state": fields[0], "field_22": fields[19]}


def check_gpu_raw() -> dict[str, Any]:
    raw = CANDIDATE / "raw" / "remote-gpu-numeric-20260916-211-r2"
    result = read_json(raw / "gpu-preflight-v9.json")
    if read_exit(raw / "probe.exit.txt") != 0 or read_exit(raw / "release-check.exit.txt") != 0 or result.get("status") != "PASS" or result.get("schema_version") != 9 or result.get("mapping_protocol") != "FPP-V8-INIT-COMPAT":
        raise AssertionError(f"v9 numeric GPU raw does not pass: {result!r}")
    if result.get("cuda_device_order") != "PCI_BUS_ID" or result.get("cuda_visible_devices") != "4,5":
        raise AssertionError("v9 GPU raw has wrong CVD/order")
    requested = [str(value).lower() for value in result["requested_uuids"]]
    selected = result["selected_host_gpus"]
    selected_uuids = [str(value["uuid_normalized"]).lower() for value in selected]
    if requested != selected_uuids or [value["pci_bus_id_normalized"] for value in selected] != ["84:00.0", "85:00.0"] or any("3090" not in value["name"] or value["memory_used_mib"] > 1024 for value in selected):
        raise AssertionError("v9 selected GPU identity/resource gate mismatch")
    host = result["host_gpu_inventory"]
    host_sorted = sorted(host, key=lambda value: pci_key(value["pci_bus_id_normalized"]))
    resolution = result["cuda_visible_devices_resolution"]
    if [value["pci_bus_id"] for value in resolution["host_pci_order"]] != [value["pci_bus_id_normalized"] for value in host_sorted]:
        raise AssertionError("v9 numeric CVD host PCI ordering is not independently reproducible")
    for token, resolved in zip(("4", "5"), resolution["resolutions"], strict=True):
        host_gpu = host_sorted[int(token)]
        if resolved["token"] != token or resolved["physical_uuid"] != host_gpu["uuid_normalized"].lower() or resolved["pci_bus_id"] != host_gpu["pci_bus_id_normalized"]:
            raise AssertionError(f"numeric CVD resolution mismatch for {token}: {resolved!r}")
    compute_apps = {str(value["gpu_uuid"]).lower() for value in result["compute_apps"]}
    if compute_apps & set(selected_uuids):
        raise AssertionError("selected GPU appears in compute-app release inventory")

    ray = result["ray_mapping"]
    workers = ray["workers"]
    validated_workers = ray["validated_workers"]
    validated_by_pid = {item.get("pid"): item for item in validated_workers}
    if len(workers) != 2 or len({worker.get("node_id") for worker in workers}) != 1 or len({worker.get("worker_id") for worker in workers}) != 2 or len({worker.get("pid") for worker in workers}) != 2:
        raise AssertionError("v9 GPU raw does not contain two distinct same-node workers")
    checked_workers = []
    for worker in workers:
        pid = worker.get("pid")
        if type(pid) is not int or pid <= 0:
            raise AssertionError(f"invalid worker PID: {worker!r}")
        stat = parse_proc_stat(worker["process_stat_raw"], pid)
        if worker.get("process_stat_path") != f"/proc/{pid}/stat" or worker.get("process_stat_field_22") != stat["field_22"] or worker.get("process_start") != stat["field_22"] or worker.get("process_stat_comm") != stat["comm"] or worker.get("process_stat_state") != stat["state"] or worker.get("process_start_source") != f"/proc/{pid}/stat:field22" or worker.get("process_identity_source") != "linux_proc_stat_field22":
            raise AssertionError(f"worker /proc identity is not independently reproducible: {worker!r}")
        probe = worker["cuda_probe"]
        runtime = probe["runtime"]
        driver = probe["driver"]
        physical = str(probe["physical_uuid"]).lower()
        if worker["cuda_device_order"] != "PCI_BUS_ID" or worker["cuda_visible_devices"] not in ("4", "5") or probe["visible_count"] != 1 or probe["local_ordinal"] != 0 or runtime["available"] is not True or runtime["device_count"] != 1 or runtime["current_device"] != 0 or driver["available"] is not True or driver["device_count"] != 1:
            raise AssertionError(f"worker CUDA visibility/runtime gate mismatch: {worker!r}")
        runtime_uuid = str(runtime["devices"][0]["uuid"]).lower()
        driver_device = driver["devices"][0]
        driver_uuid = str(driver_device["uuid"]).lower()
        driver_pci = driver_device["pci_bus_id"].removeprefix("0000:")
        expected_visible = host_sorted[int(worker["cuda_visible_devices"])]
        validated = validated_by_pid.get(pid)
        if validated is None:
            raise AssertionError(f"worker is absent from validated worker summary: {worker!r}")
        host_pci = validated["host_pci_bus_id"]
        if not (physical == runtime_uuid == driver_uuid == str(expected_visible["uuid_normalized"]).lower()) or probe["driver_pci_bus_id"] != host_pci or driver_pci != host_pci or physical not in set(selected_uuids):
            raise AssertionError(f"worker runtime/driver/host physical identity mismatch: {worker!r}")
        checked_workers.append({"pid": pid, "worker_id": worker["worker_id"], "node_id": worker["node_id"], "process_start": stat["field_22"], "cuda_visible_devices": worker["cuda_visible_devices"], "physical_uuid": physical, "pci_bus_id": host_pci})
    release = (raw / "release-check.stdout.txt").read_text(encoding="utf-8")
    release_tail = release.split("COMPUTE_APPS", 1)[-1]
    if any(uuid.upper() in release_tail.upper() for uuid in selected_uuids):
        raise AssertionError("v9 selected GPU release check is not clean")
    command = (raw / "command.txt").read_text(encoding="utf-8")
    environment = (raw / "environment.txt").read_text(encoding="utf-8")
    if "gpu_preflight_v9.py" not in command or "CUDA_VISIBLE_DEVICES=4,5" not in environment or "CUDA_DEVICE_ORDER=PCI_BUS_ID" not in environment:
        raise AssertionError("v9 GPU raw command/environment does not show the numeric PCI-ordered gate")
    first_raw = CANDIDATE / "raw" / "remote-gpu-numeric-20260916-211"
    first = {"exit_code": read_exit(first_raw / "probe.exit.txt"), "stdout": (first_raw / "stdout.txt").read_text(encoding="utf-8")}
    if first["exit_code"] != 1 or not any(token in first["stdout"].lower() for token in ("blocked", "busy", "compute", "not idle")):
        raise AssertionError("the rejected busy-GPU attempt was not preserved as a rejected attempt")
    return {
        "status": "PASS_V9_NUMERIC_PCI_GPU_MAPPING_RAW_RECHECK",
        "numeric_cvd": "4,5",
        "selected_uuids": selected_uuids,
        "selected_pci": [value["pci_bus_id_normalized"] for value in selected],
        "host_pci_numeric_resolution": True,
        "two_worker_same_node": True,
        "worker_runtime_driver_identity": True,
        "worker_process_identity": "linux_proc_stat_field22",
        "release_check": "PASS",
        "rejected_busy_gpu_attempt": first,
        "model_constructed": False,
        "training_started": False,
    }


def check_historical_failures() -> dict[str, Any]:
    ray_env = CANDIDATE / "raw" / "remote-reward-init-ray-env-20260916-211"
    wrong_source = CANDIDATE / "raw" / "remote-reward-init-wrong-source-20260916-211"
    ray_text = (ray_env / "stdout.txt").read_text(encoding="utf-8")
    wrong_exit = read_exit(wrong_source / "probe.exit.txt")
    wrong_text = (wrong_source / "stdout.log").read_text(encoding="utf-8")
    if "ModuleNotFoundError: No module named 'verl'" not in ray_text or wrong_exit != 2:
        raise AssertionError("historical rejected reward-init attempts were not preserved as failures")
    return {
        "ray_environment_failure_preserved": True,
        "ray_environment_failure_is_not_accepted": True,
        "wrong_source_exit_code": wrong_exit,
        "wrong_source_failure_preserved": True,
        "wrong_source_output_bytes": len(wrong_text.encode("utf-8")),
    }


def main() -> int:
    package = check_candidate_and_inheritance()
    identity = check_identity_and_scientific_delta()
    static = check_static_and_cpu()
    vllm = check_vllm_raw()
    reward = check_reward_raw()
    gpu = check_gpu_raw()
    history = check_historical_failures()
    blocker_id = "BLOCKED_RAY_REWARD_SOURCE_HASH_IDENTITY"
    verdict = blocker_id if not reward["strict_same_source_hash_across_serialized_local_ray"] else "READY_FOR_BOUNDED_GPU"
    results = {
        "schema_version": 1,
        "acceptance_protocol": "FPP-V8-INIT-COMPAT-INDEPENDENT-ACCEPTANCE",
        "candidate": str(CANDIDATE),
        "acceptance_root": str(ROOT),
        "verdict": verdict,
        "package_and_inheritance": package,
        "source_and_scientific_identity": identity,
        "static_and_cpu": static,
        "vllm_raw": vllm,
        "reward_raw": reward,
        "gpu_raw": gpu,
        "historical_rejections": history,
        "scope": {
            "v8_evidence_reused_byte_exact": True,
            "new_gpu_action_in_this_acceptance": False,
            "model_constructed": False,
            "training_started": False,
            "c_ab_run": False,
            "full_42_cpu_suite_rerun": False,
            "paper_faithful_claim": False,
        },
        "blockers": [] if verdict == "READY_FOR_BOUNDED_GPU" else [{
            "id": blocker_id,
            "severity": "incremental acceptance blocker",
            "criterion": "post_init/serialization/local loader/real Ray worker must retain and expose the same callable and source_sha256",
            "evidence": {
                "candidate_probe": str(CANDIDATE / "production_reward_probe_v9.py"),
                "raw_probe_result": str(next((CANDIDATE / "raw" / "remote-reward-init-20260916-211").rglob("probe-result.json"))),
                "missing_stages": reward["source_hash_missing_from_stages"],
                "effective_and_validator_hash": REWARD_SHA,
            },
            "minimum_clearance": "add an independently recomputed source_sha256 to serialized/local/real-Ray worker observations and assert equality to the frozen reward source hash; then rerun only the affected reward-init evidence and this incremental acceptance",
        }],
    }
    output = ROOT / "raw" / "acceptance_probe.stdout.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
