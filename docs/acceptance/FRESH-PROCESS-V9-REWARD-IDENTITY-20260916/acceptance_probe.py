"""Independent acceptance probe for the v9 reward-identity supplement."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parent
SUPPLEMENT = Path(
    r"C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\acceptance\FRESH-PROCESS-INIT-COMPAT-V9-20260916\v9-reward-identity-supplement-20260916"
)
V9 = Path(
    r"C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\diagnostics\fresh-process-resume-20260911\v9"
)
ORIGINAL_ACCEPTANCE = Path(
    r"C:\Users\Administrator\Desktop\RaPO-author\docs\acceptance\FRESH-PROCESS-INIT-COMPAT-V9-20260916"
)
REWARD_REL = "examples/reward_function/cls.py"
REWARD_SHA = "028b9c9721c0c1d80b0ae3652aec31c8fb458827ca4d079b1253b537099978a1"
V9_HASHES_SELF = "45f79cbf83d004b6fd05c4e1ef61fe2f5b296dba1771aae24e45e570b890ee39"
V9_PACKAGE_SHA = "3767c12fd6bc90ef43479486a057ae92b557aaa4ec276c12d5713871597bae7a"
V9_PACKAGE_COUNT = 205
V9_PACKAGE_BYTES = 4658581
SUPPLEMENT_HASHES_SELF = "da6ad19c30cf5cffc5ed47b5b1ef7983b9d9008c21e0ad57e7c350b739eb789a"
SUPPLEMENT_PACKAGE_SHA = "2935c0c6ff3d34adc44d727c2356b71b22d73714becc28b360f443e445737c56"
SUPPLEMENT_PACKAGE_COUNT = 14
SUPPLEMENT_PACKAGE_BYTES = 47813
SUPPLEMENT_RAW_SHA = "c978ac2c9910fed038b2f936fb5a78cc0be3b69fa8f627d6d526f2d2820a97ca"
SUPPLEMENT_RAW_COUNT = 8
SUPPLEMENT_RAW_BYTES = 21382


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def compact(records: list[dict[str, Any]]) -> str:
    payload = json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def records(root: Path, excluded_name: str) -> list[dict[str, Any]]:
    result = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_file() and path.name != excluded_name:
            result.append({
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })
    return result


def check_manifest(root: Path, hashes_path: Path, excluded_name: str, expected: dict[str, Any], raw_prefix: str) -> dict[str, Any]:
    actual = records(root, excluded_name)
    declared = read_json(hashes_path)
    if actual != declared["files"]:
        actual_by_path = {item["path"]: item for item in actual}
        declared_by_path = {item["path"]: item for item in declared["files"]}
        missing = sorted(set(declared_by_path) - set(actual_by_path))
        extra = sorted(set(actual_by_path) - set(declared_by_path))
        changed = sorted(path for path in set(actual_by_path) & set(declared_by_path) if actual_by_path[path] != declared_by_path[path])
        raise AssertionError(f"manifest mismatch: missing={missing!r} extra={extra!r} changed={changed!r}")
    if raw_prefix == "raw-v9":
        raw = [item for item in actual if item["path"].startswith("raw/") or item["path"].startswith("r2-evidence/raw/")]
    else:
        raw = [item for item in actual if item["path"].startswith(raw_prefix)]
    result = {
        "file_count": len(actual),
        "total_bytes": sum(item["bytes"] for item in actual),
        "package_manifest_sha256": compact(actual),
        "declared_package_manifest_sha256": declared["package_manifest_sha256"],
        "raw_file_count": len(raw),
        "raw_total_bytes": sum(item["bytes"] for item in raw),
        "raw_manifest_sha256": compact(raw),
        "declared_raw_manifest_sha256": declared["raw_manifest_sha256"],
        "hashes_file_self_sha256": sha256(hashes_path),
    }
    for key, value in expected.items():
        if result[key] != value:
            raise AssertionError(f"{root} {key} differs: {result[key]!r} != {value!r}")
    if result["package_manifest_sha256"] != result["declared_package_manifest_sha256"] or result["raw_manifest_sha256"] != result["declared_raw_manifest_sha256"]:
        raise AssertionError(f"{root} declared manifest does not match independent recomputation: {result!r}")
    return result


def check_frozen_bindings() -> dict[str, Any]:
    supplement_manifest = check_manifest(
        SUPPLEMENT,
        SUPPLEMENT / "HASHES_SUPPLEMENT.json",
        "HASHES_SUPPLEMENT.json",
        {
            "file_count": SUPPLEMENT_PACKAGE_COUNT,
            "total_bytes": SUPPLEMENT_PACKAGE_BYTES,
            "package_manifest_sha256": SUPPLEMENT_PACKAGE_SHA,
            "raw_file_count": SUPPLEMENT_RAW_COUNT,
            "raw_total_bytes": SUPPLEMENT_RAW_BYTES,
            "raw_manifest_sha256": SUPPLEMENT_RAW_SHA,
            "hashes_file_self_sha256": SUPPLEMENT_HASHES_SELF,
        },
        "raw/",
    )
    v9_manifest = check_manifest(
        V9,
        V9 / "HASHES_v9.json",
        "HASHES_v9.json",
        {
            "file_count": V9_PACKAGE_COUNT,
            "total_bytes": V9_PACKAGE_BYTES,
            "package_manifest_sha256": V9_PACKAGE_SHA,
            "raw_file_count": 128,
            "raw_total_bytes": 4185383,
            "raw_manifest_sha256": "9d41841454ac9cc9dddd226f8d52613514675a5ab04b5188d2cd0b1f5736485c",
            "hashes_file_self_sha256": V9_HASHES_SELF,
        },
        "raw-v9",
    )
    reference = read_json(SUPPLEMENT / "REFERENCE_V9.json")
    frozen = reference["frozen_v9"]
    expected_frozen = {
        "relative_root_from_supplement": "../../../diagnostics/fresh-process-resume-20260911/v9",
        "hashes_file": "HASHES_v9.json",
        "hashes_file_self_sha256": V9_HASHES_SELF,
        "package_file_count": V9_PACKAGE_COUNT,
        "package_total_bytes": V9_PACKAGE_BYTES,
        "package_manifest_sha256": V9_PACKAGE_SHA,
        "protocol": "FPP-V8-INIT-COMPAT",
        "launcher": "run_v9.py",
    }
    if frozen != expected_frozen:
        raise AssertionError(f"supplement frozen v9 reference changed: {frozen!r}")
    if v9_manifest["hashes_file_self_sha256"] != frozen["hashes_file_self_sha256"] or v9_manifest["package_manifest_sha256"] != frozen["package_manifest_sha256"]:
        raise AssertionError("supplement frozen v9 binding does not match the actual v9 package")
    reward_reference = reference["reward_identity"]
    if reward_reference != {
        "spec": "examples/reward_function/cls.py:compute_score",
        "source_sha256": REWARD_SHA,
        "must_be_computed_from_loaded_callable": True,
        "stages": ["serialized_reward_config", "local_reward_loader", "ray_worker_roundtrip.worker_report"],
    }:
        raise AssertionError("supplement reward identity reference changed")

    original_hashes = ORIGINAL_ACCEPTANCE / "HASHES.json"
    original_declared = read_json(original_hashes)
    original_actual = records(ORIGINAL_ACCEPTANCE, "HASHES.json")
    if original_actual != original_declared["files"] or sha256(original_hashes) != "74fdd89b1f297d1b7ae75d74783bde2a6a69c4906fdc3d19ca530d63e712cae4" or original_declared["package_manifest_sha256"] != "d77d2d99f22ab6674def614185901a19f4d844f050d54a6ff3f719faabdfe388" or original_declared["file_count"] != 5 or original_declared["total_bytes"] != 57690:
        raise AssertionError("original v9 acceptance manifest was changed")
    original_probe = read_json(ORIGINAL_ACCEPTANCE / "raw" / "acceptance_probe.stdout.json")
    if original_probe.get("verdict") != "BLOCKED_RAY_REWARD_SOURCE_HASH_IDENTITY":
        raise AssertionError("original v9 acceptance no longer records the pre-supplement blocker")
    if read_json(V9 / "HASHES_v9.json")["package_manifest_sha256"] != V9_PACKAGE_SHA:
        raise AssertionError("v9 package manifest binding changed")
    supplement_paths = {item["path"] for item in records(SUPPLEMENT, "HASHES_SUPPLEMENT.json")}
    if any(path in supplement_paths for path in ("run_v9.py", "PPO_CONFIG_TEMPLATE_v9.json", "EXPECTED_IDENTITY_v9.json", "HASHES_v9.json")):
        raise AssertionError("supplement copied a frozen v9 package file")
    return {
        "supplement": supplement_manifest,
        "frozen_v9": v9_manifest,
        "original_v9_acceptance_unchanged": True,
        "supplement_does_not_copy_v9_package": True,
    }


def check_probe_source() -> dict[str, Any]:
    path = SUPPLEMENT / "reward_identity_supplement_probe.py"
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=str(path))
    required = (
        "def actual_callable_identity",
        "inspect.getsourcefile",
        "inspect.getfile",
        "source_path.read_bytes()",
        "hashlib.sha256",
        "def stage_record",
        "identity = actual_callable_identity(manager.reward_fn)",
        "ray_cloudpickle.dumps",
        "ray_cloudpickle.loads",
        "def assert_stage_identity",
        "missing_source_sha256",
        "mismatched_source_sha256",
        "from run_v9 import build_production_argv, render_config",
        "ray.init(",
        "num_gpus=0",
        "ray.kill(actor, no_restart=True)",
        "ray.shutdown()",
    )
    for token in required:
        if token not in source:
            raise AssertionError(f"supplement probe missing independent identity token: {token}")
    worker_start = source.index("class RewardIdentityWorker")
    worker_end = source.index("actor = RewardIdentityWorker.remote()")
    worker_body = source[worker_start:worker_end]
    for token in ("_inspect.getsourcefile", "_inspect.getfile", "_hashlib.sha256", "source_path.read_bytes()", '"source_sha256": digest'):
        if token not in worker_body:
            raise AssertionError(f"Ray worker does not independently compute source hash: {token}")
    if source.index("serialized_bytes = ray_cloudpickle.dumps") > source.index("serialized_manager = _load_manager(deserialized_reward_config)"):
        raise AssertionError("serialized RewardConfig was loaded before cloudpickle round-trip")
    if source.index("identity = actual_callable_identity(manager.reward_fn)") > source.index("score = manager.reward_fn(SAMPLE_REWARD_INPUT)"):
        raise AssertionError("stage source identity is recorded after the callable invocation")
    if "run_preflight" in source or "subprocess.Popen" in source or "torch" in source:
        raise AssertionError("supplement probe contains out-of-scope GPU/model execution")
    return {
        "ast_parse": True,
        "loaded_callable_source_lookup": True,
        "independent_hash_from_source_bytes": True,
        "cloudpickle_roundtrip": True,
        "real_ray_worker_hash_lookup": True,
        "hash_negative_fixtures": True,
        "uses_frozen_run_v9_renderer_and_argv": True,
        "zero_gpu_and_no_model_static": True,
    }


def stage_relative(stage: dict[str, Any], source_root: str) -> str:
    root = PurePosixPath(source_root)
    path = PurePosixPath(str(stage["real_path"]))
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise AssertionError(f"loaded callable source escapes source root: {stage!r}") from exc


def check_stage(stage: dict[str, Any], expected_name: str, expected_relative: str, expected_hash: str, source_root: str) -> dict[str, Any]:
    if stage.get("stage") is None or stage.get("callable_name") != expected_name or stage.get("callable_qualname") != expected_name or not stage.get("real_path") or stage.get("source_sha256") != expected_hash:
        raise AssertionError(f"loaded callable identity mismatch: {stage!r}")
    if stage_relative(stage, source_root) != expected_relative:
        raise AssertionError(f"loaded callable source path mismatch: {stage!r}")
    if stage.get("reward_function_name") != expected_name or stage.get("reward_type") != "sequential":
        raise AssertionError(f"RewardConfig derived name/type mismatch: {stage!r}")
    if stage.get("sample_score", {}).get("overall") != 2.0:
        raise AssertionError(f"loaded reward callable did not return sample overall=2.0: {stage!r}")
    return {
        "stage": stage["stage"],
        "callable_name": stage["callable_name"],
        "real_path": stage["real_path"],
        "source_sha256": stage["source_sha256"],
        "sample_overall": stage["sample_score"]["overall"],
    }


def check_raw_evidence() -> dict[str, Any]:
    raw = SUPPLEMENT / "raw" / "reward-identity-20260916-211"
    result_path = raw / "reward-identity-20260916-r1" / "probe-result.json"
    result = read_json(result_path)
    if (raw / "probe.exit.txt").read_text(encoding="utf-8").strip() != "0" or result.get("status") != "PASS_V9_REWARD_IDENTITY_SUPPLEMENT":
        raise AssertionError(f"supplement raw did not pass: {result!r}")
    command = (raw / "command.txt").read_text(encoding="utf-8")
    environment = (raw / "environment.txt").read_text(encoding="utf-8")
    if "reward_identity_supplement_probe.py" not in command or "run_v9" not in result.get("launcher", "") or "CUDA_VISIBLE_DEVICES=\n" not in environment or "CUDA_DEVICE_ORDER=PCI_BUS_ID" not in environment or "PYTHONDONTWRITEBYTECODE=1" not in environment:
        raise AssertionError("supplement raw command/environment is not the frozen zero-GPU run_v9 path")
    frozen = result["frozen_v9_reference"]
    if frozen["hashes_file_self_sha256"] != V9_HASHES_SELF or frozen["package_manifest_sha256"] != V9_PACKAGE_SHA or frozen["package_file_count"] != V9_PACKAGE_COUNT or frozen["package_total_bytes"] != V9_PACKAGE_BYTES:
        raise AssertionError("supplement raw does not bind the frozen v9 package")
    if result.get("model_constructed") is not False or result.get("training_started") is not False or result.get("gpu_used") is not False or result.get("ray_released") is not True or result["ray_worker_roundtrip"].get("ray_released") is not True:
        raise AssertionError("supplement raw violates no-GPU/no-model/Ray-release scope")
    post_init = result["post_init"]
    if post_init.get("call_count") != 1 or len(post_init.get("calls", [])) != 1 or not str(post_init["calls"][0]["before_reward_function"]).endswith(":compute_score") or post_init["calls"][0]["before_reward_function_name"] is not None:
        raise AssertionError(f"post_init raw evidence mismatch: {post_init!r}")
    identity = result["frozen_reward_identity"]
    if identity != {"relative_path": REWARD_REL, "function_name": "compute_score", "source_sha256": REWARD_SHA}:
        raise AssertionError("frozen reward identity in supplement raw changed")
    expected_relative = identity["relative_path"]
    expected_name = identity["function_name"]
    source_root = result["source_root"]
    stages = {
        "serialized_reward_config": check_stage(result["serialized_reward_config"], expected_name, expected_relative, REWARD_SHA, source_root),
        "local_reward_loader": check_stage(result["local_reward_loader"], expected_name, expected_relative, REWARD_SHA, source_root),
        "ray_worker_roundtrip.worker_report": check_stage(result["ray_worker_roundtrip"]["worker_report"], expected_name, expected_relative, REWARD_SHA, source_root),
    }
    serialized = result["serialized_reward_config"]
    if serialized.get("serialization", {}).get("format") != "ray.cloudpickle" or serialized.get("serialization", {}).get("bytes", 0) <= 0 or serialized.get("serialized_config", {}).get("reward_function_name") != "compute_score":
        raise AssertionError("serialized RewardConfig cloudpickle evidence is incomplete")
    if not result["hash_rejection_checks"]["missing_source_sha256"]["rejected"] or not result["hash_rejection_checks"]["mismatched_source_sha256"]["rejected"]:
        raise AssertionError("missing/mismatched source hash negative checks did not reject")
    invalid = result["invalid_reward_checks"]
    if invalid.get("derived_name") != "main" or not invalid.get("identity_name_mismatch_detected") or not invalid.get("loader_rejected_bad_callable"):
        raise AssertionError(f"invalid :main reward did not reject: {invalid!r}")
    stdout = (raw / "stdout.txt").read_text(encoding="utf-8")
    final_line = next((line for line in reversed(stdout.splitlines()) if line.lstrip().startswith("{")), "")
    final = json.loads(final_line)
    expected_summary_stages = {
        "serialized_reward_config": REWARD_SHA,
        "local_reward_loader": REWARD_SHA,
        "ray_worker_roundtrip": REWARD_SHA,
    }
    if final.get("status") != result["status"] or final.get("post_init_call_count") != 1 or final.get("ray_released") is not True or final.get("stages") != expected_summary_stages:
        raise AssertionError(f"supplement stdout summary does not match probe result: {final!r}")
    return {
        "status": result["status"],
        "post_init_call_count": 1,
        "stages": stages,
        "same_callable": True,
        "same_source_sha256": True,
        "sample_overall": 2.0,
        "cloudpickle_roundtrip": True,
        "invalid_main_loader_rejected": True,
        "missing_hash_rejected": True,
        "mismatched_hash_rejected": True,
        "gpu_used": False,
        "model_constructed": False,
        "training_started": False,
        "ray_released": True,
        "exit_code": 0,
    }


def main() -> int:
    bindings = check_frozen_bindings()
    probe_source = check_probe_source()
    raw = check_raw_evidence()
    result = {
        "schema_version": 1,
        "acceptance_protocol": "FPP-V9-REWARD-IDENTITY-INDEPENDENT-ACCEPTANCE",
        "acceptance_root": str(ROOT),
        "supplement": str(SUPPLEMENT),
        "verdict": "READY_FOR_BOUNDED_GPU",
        "frozen_bindings": bindings,
        "supplement_probe_source": probe_source,
        "supplement_raw": raw,
        "combined_v9_verdict": {
            "original_v9_acceptance_blocker": "BLOCKED_RAY_REWARD_SOURCE_HASH_IDENTITY",
            "supplement_status": "PASS_V9_REWARD_IDENTITY_SUPPLEMENT",
            "only_original_blocker_cleared": True,
            "ready_for_bounded_gpu": True,
        },
        "scope": {
            "new_gpu_action": False,
            "ssh_action": False,
            "model_constructed": False,
            "training_started": False,
            "c_ab_run": False,
            "full_42_cpu_suite_rerun": False,
            "v8_evidence_reused": True,
            "v9_original_acceptance_reused": True,
            "paper_faithful_claim": False,
        },
    }
    output = ROOT / "raw" / "acceptance_probe.stdout.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
