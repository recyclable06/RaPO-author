from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
from pathlib import Path


PREP = Path(r"C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\diagnostics\fresh-process-resume-20260911\v2")
TARGET = Path(r"C:\Users\Administrator\.codex\worktrees\8ac5\RaPO-author")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_stdlib_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    hashes = json.loads((PREP / "HASHES_V2.json").read_text(encoding="utf-8"))
    declared = {item["path"]: item for item in hashes["files"]}
    actual = {}
    for rel, item in sorted(declared.items()):
        path = PREP / rel
        actual[rel] = {
            "exists": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else None,
            "sha256": sha256(path) if path.is_file() else None,
            "declared_bytes": item["bytes"],
            "declared_sha256": item["sha256"],
        }
    hash_matches = all(
        item["exists"]
        and item["bytes"] == item["declared_bytes"]
        and item["sha256"] == item["declared_sha256"]
        for item in actual.values()
    )

    ast_results = {}
    for path in sorted(PREP.glob("*.py")):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            ast_results[path.name] = "PASS"
        except Exception as exc:  # pragma: no cover - diagnostic output
            ast_results[path.name] = f"FAIL:{type(exc).__name__}:{exc}"

    commands = (PREP / "COMMANDS_V2.md").read_text(encoding="utf-8")
    config = json.loads((PREP / "PPO_CONFIG_V2.json").read_text(encoding="utf-8"))
    expected = json.loads((PREP / "EXPECTED_IDENTITY_V2.json").read_text(encoding="utf-8"))
    run_text = (PREP / "run_v2.py").read_text(encoding="utf-8")
    argv_text = (PREP / "argv_validate.py").read_text(encoding="utf-8")
    entry_text = (PREP / "runtime_entry.py").read_text(encoding="utf-8")
    observer_text = (PREP / "runtime_observer.py").read_text(encoding="utf-8")
    target_entry = TARGET / expected["target"]["production_source"]["relative_path"]
    target_text = target_entry.read_text(encoding="utf-8")
    argv_module = load_stdlib_module("argv_validate_static_probe", PREP / "argv_validate.py")
    actual_runtime_manifest = argv_module._runtime_source_manifest(str(target_entry))

    remote_root = re.search(r"^REMOTE_ROOT=(.+)$", commands, re.MULTILINE).group(1).strip()
    source_root = re.search(r"^SOURCE_ROOT=\$REMOTE_ROOT/source$", commands, re.MULTILINE) is not None
    format_prompt = config["data"]["format_prompt"]
    reward_function = config["worker"]["reward"]["reward_function"]
    unique_root_in_config = remote_root in format_prompt or remote_root in reward_function
    old_root = "/mnt/conda/zhenglifeng/t/fresh-process-resume-20260911/v2"

    input_manifest_name = expected["input"]["manifest_file"]
    input_manifest_candidates = sorted(str(path.relative_to(PREP)) for path in PREP.rglob(input_manifest_name))
    expected_model_referenced = 'expected["model"]' in argv_text or "expected['model']" in argv_text
    expected_input_referenced = 'expected["input"]' in argv_text or "expected['input']" in argv_text

    target_identity = {
        "exists": target_entry.is_file(),
        "bytes": target_entry.stat().st_size if target_entry.is_file() else None,
        "sha256": sha256(target_entry) if target_entry.is_file() else None,
        "expected_bytes": expected["target"]["production_source"]["bytes"],
        "expected_sha256": expected["target"]["production_source"]["sha256"],
    }

    ray_child_calls = {
        "production_runner_remote_decorator": "@ray.remote(num_cpus=1)" in target_text,
        "runner_creates_worker_remote_in_child": "ray.remote(PersistentRefFSDPWorker)" in target_text,
        "runtime_entry_installs_observer": "runtime_observer.install(module)" in entry_text,
        "observer_propagates_pythonpath": '"PYTHONPATH"' in observer_text and "runtime_env" in observer_text,
        "observer_has_child_import_hook": any(
            token in observer_text
            for token in (
                "sitecustomize",
                "worker_process_setup_hook",
                "setup_worker",
                "runtime_env[\"working_dir\"]",
                "py_modules",
            )
        ),
        "observer_required_set_is_local": 'required - _PATCHED' in observer_text and "observer_install" in observer_text,
    }

    result = {
        "status": "PASS_STATIC_PROBE_WITH_FINDINGS" if hash_matches and all(value == "PASS" for value in ast_results.values()) else "FAIL_STATIC_PROBE",
        "prep": str(PREP),
        "target": str(TARGET),
        "hash_manifest": {
            "declared_file_count": hashes["file_count"],
            "actual_file_count": len(actual),
            "declared_total_bytes": hashes["total_bytes"],
            "actual_total_bytes": sum(item["bytes"] or 0 for item in actual.values()),
            "all_declared_files_match": hash_matches,
        },
        "ast_compile": ast_results,
        "target_identity": target_identity,
        "runtime_source_manifest": {
            "actual_file_count": actual_runtime_manifest["file_count"],
            "actual_manifest_sha256": actual_runtime_manifest["manifest_sha256"],
            "expected_file_count": expected["runtime_source_manifest"]["file_count"],
            "expected_manifest_sha256": expected["runtime_source_manifest"]["manifest_sha256"],
            "matches_expected": actual_runtime_manifest["file_count"] == expected["runtime_source_manifest"]["file_count"] and actual_runtime_manifest["manifest_sha256"] == expected["runtime_source_manifest"]["manifest_sha256"],
        },
        "config_root_binding": {
            "command_remote_root": remote_root,
            "command_source_root_is_remote_root_source": source_root,
            "config_format_prompt": format_prompt,
            "config_reward_function": reward_function,
            "old_non_unique_root_prefix": old_root,
            "config_uses_old_non_unique_root": old_root in format_prompt and old_root in reward_function,
            "config_uses_unique_command_root": unique_root_in_config,
            "run_v2_contains_config_rewrite": "format_prompt" in run_text or "reward_function" in run_text,
        },
        "input_identity_binding": {
            "expected_model_path": expected["model"]["path"],
            "expected_input_root": expected["input"]["root"],
            "expected_input_manifest_name": input_manifest_name,
            "input_manifest_files_inside_v2": input_manifest_candidates,
            "argv_validate_references_expected_model_object": expected_model_referenced,
            "argv_validate_references_expected_input_object": expected_input_referenced,
            "argv_validate_records_actual_model_and_input_identities": '"model": _path_identity' in argv_text and '"train_input": _path_identity' in argv_text,
        },
        "ray_child_observation_binding": ray_child_calls,
        "protocol_vs_judge": {
            "protocol_requires_uid_repetition_and_nonzero_variation": "group_reward_requires_uid_repetition" in (PREP / "DIAGNOSTIC_CONFIG_V2.json").read_text(encoding="utf-8") and "group_reward_requires_nonzero_variation" in (PREP / "DIAGNOSTIC_CONFIG_V2.json").read_text(encoding="utf-8"),
            "judge_checks_raw_variation": "raw_variation" in (PREP / "judge_v2.py").read_text(encoding="utf-8"),
            "judge_checks_effective_variation": "effective_variation" in (PREP / "judge_v2.py").read_text(encoding="utf-8"),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
