from __future__ import annotations

import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


V3 = Path(r"C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\diagnostics\fresh-process-resume-20260911\v3")
TARGET = Path(r"C:\Users\Administrator\.codex\worktrees\8ac5\RaPO-author")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def file_manifest(root: Path) -> list[dict]:
    result = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        result.append({
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return result


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def read_events(root: Path) -> list[dict]:
    event_root = root / "observer" / "events"
    result = []
    for path in sorted(event_root.glob("events-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                result.append(json.loads(line))
    return result


def same_path(left: str, right: Path | str) -> bool:
    return os.path.normcase(os.path.normpath(str(left))) == os.path.normcase(os.path.normpath(str(right)))


def run_missing_cil_cfg(run_v3) -> dict:
    old_argv = sys.argv[:]
    sys.argv = [
        "run_v3.py", "--leg", "C", "--entry", "/tmp/entry.py", "--source-root", "/tmp/source",
        "--config-template", "/tmp/template.json", "--model-root", "/tmp/model", "--input-root", "/tmp/input",
        "--expected", "/tmp/expected.json", "--output-root", "/tmp/output", "--gpu-uuids", "A,B",
        "--cuda-visible-devices", "A,B", "--ray-address", "local",
    ]
    captured = io.StringIO()
    try:
        with contextlib.redirect_stderr(captured):
            try:
                run_v3._main()
                code = 0
            except SystemExit as exc:
                code = int(exc.code)
    finally:
        sys.argv = old_argv
    return {"exit_code": code, "stderr_mentions_cil_cfg": "--cil-cfg" in captured.getvalue()}


def make_frozen_content_fixture(argv_v3, root: Path) -> dict:
    expected_dir = root / "expected"
    source = root / "source"
    model = root / "model"
    inputs = root / "input"
    expected_dir.mkdir(parents=True)
    (source / "examples" / "baselines" / "img_cls_cil").mkdir(parents=True)
    (source / "examples" / "format_prompt").mkdir(parents=True)
    (source / "examples" / "reward_function").mkdir(parents=True)
    (source / "scripts" / "image").mkdir(parents=True)
    model.mkdir()
    (inputs / "class_a").mkdir(parents=True)
    (inputs / "class_b").mkdir(parents=True)

    entry = source / "examples" / "baselines" / "img_cls_cil" / "image_cls_cil_rapo.py"
    entry.write_bytes(b"entry")
    prompt = source / "examples" / "format_prompt" / "cls.jinja"
    prompt.write_bytes(b"prompt")
    reward = source / "examples" / "reward_function" / "cls.py"
    reward.write_bytes(b"reward")
    cil_cfg = source / "scripts" / "image" / "rapo_cfg.json"
    cil_cfg.write_bytes(b"cil")
    (model / "config.json").write_bytes(b"model-config")
    (model / "tokenizer.json").write_bytes(b"tokenizer")
    (inputs / "class_a" / "a.jpg").write_bytes(b"a")
    (inputs / "class_b" / "b.jpg").write_bytes(b"b")

    model_files = file_manifest(model)
    model_manifest = {
        "schema_version": 3,
        "model_path": str(model.resolve()),
        "files": model_files,
        "files_manifest_sha256": sha256_bytes(canonical(model_files)),
    }
    model_manifest_path = expected_dir / "MODEL_MANIFEST_V3.json"
    write_json(model_manifest_path, model_manifest)

    input_files = [
        {"relative_path": item["path"], "bytes": item["bytes"], "sha256": item["sha256"], "class": item["path"].split("/")[0], "task": 1}
        for item in file_manifest(inputs)
    ]
    input_manifest_files_for_hash = [
        {"path": item["relative_path"], "bytes": item["bytes"], "sha256": item["sha256"]}
        for item in input_files
    ]
    input_manifest = {
        "schema_version": 3,
        "source_root": str(inputs.resolve()),
        "class_order": ["class_a", "class_b"],
        "prompt_template": {"relative_path": "examples/format_prompt/cls.jinja", "sha256": sha256_file(prompt)},
        "files": input_files,
        "files_manifest_sha256": sha256_bytes(canonical(input_manifest_files_for_hash)),
    }
    input_manifest_path = expected_dir / "INPUT_MANIFEST_V3.json"
    write_json(input_manifest_path, input_manifest)

    expected = {
        "model": {
            "path": str(model.resolve()),
            "manifest_file": "MODEL_MANIFEST_V3.json",
            "manifest_sha256": sha256_file(model_manifest_path),
        },
        "input": {
            "root": str(inputs.resolve()),
            "manifest_file": "INPUT_MANIFEST_V3.json",
            "manifest_sha256": sha256_file(input_manifest_path),
            "class_order": ["class_a", "class_b"],
        },
        "config_bindings": {
            "cil_cfg": "scripts/image/rapo_cfg.json",
            "format_prompt": "examples/format_prompt/cls.jinja",
            "reward_function": "examples/reward_function/cls.py",
        },
        "config_bindings_sha256": {
            "cil_cfg": sha256_file(cil_cfg),
            "format_prompt": sha256_file(prompt),
            "reward_function": sha256_file(reward),
        },
    }
    config = SimpleNamespace(
        data=SimpleNamespace(format_prompt=str(prompt.resolve())),
        worker=SimpleNamespace(reward=SimpleNamespace(reward_function=str(reward.resolve()))),
    )

    without_known = None
    without_known_error = None
    if hasattr(argv_v3, "known"):
        delattr(argv_v3, "known")
    try:
        without_known = argv_v3._verify_frozen_content(
            expected_path=str(expected_dir / "EXPECTED.json"), expected=expected,
            model_path=str(model), tokenizer_path=str(model), train_path=str(inputs), val_path=str(inputs),
            entry=str(entry), config=config,
        )
    except Exception as exc:
        without_known_error = f"{type(exc).__name__}: {exc}"

    argv_v3.known = SimpleNamespace(cil_cfg=str(cil_cfg.resolve()))
    with_known = None
    with_known_error = None
    try:
        with_known = argv_v3._verify_frozen_content(
            expected_path=str(expected_dir / "EXPECTED.json"), expected=expected,
            model_path=str(model), tokenizer_path=str(model), train_path=str(inputs), val_path=str(inputs),
            entry=str(entry), config=config,
        )
    except Exception as exc:
        with_known_error = f"{type(exc).__name__}: {exc}"

    (inputs / "class_b" / "b.jpg").write_bytes(b"mutated")
    mutated_error = None
    try:
        argv_v3._verify_frozen_content(
            expected_path=str(expected_dir / "EXPECTED.json"), expected=expected,
            model_path=str(model), tokenizer_path=str(model), train_path=str(inputs), val_path=str(inputs),
            entry=str(entry), config=config,
        )
    except Exception as exc:
        mutated_error = f"{type(exc).__name__}: {exc}"
    return {
        "positive_without_implicit_known": without_known is not None,
        "positive_without_implicit_known_error": without_known_error,
        "positive_with_explicit_known": with_known is not None,
        "positive_with_explicit_known_error": with_known_error,
        "mutated_input_rejected": mutated_error is not None,
        "mutated_input_error": mutated_error,
    }


def main() -> int:
    expected = json.loads((V3 / "EXPECTED_IDENTITY_V3.json").read_text(encoding="utf-8"))
    hashes = json.loads((V3 / "HASHES_V3.json").read_text(encoding="utf-8"))
    declared = {item["path"]: item for item in hashes["files"]}
    actual_paths = {
        path.relative_to(V3).as_posix(): path
        for path in V3.rglob("*")
        if path.is_file() and path.name != "HASHES_V3.json"
    }
    hash_mismatches = []
    for rel, item in declared.items():
        path = actual_paths.get(rel)
        if path is None or path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            hash_mismatches.append(rel)
    extra_files = sorted(set(actual_paths) - set(declared))

    ast_results = {}
    for path in sorted(V3.glob("*.py")):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            ast_results[path.name] = "PASS"
        except Exception as exc:
            ast_results[path.name] = f"FAIL:{type(exc).__name__}:{exc}"

    run_v3 = load_module("run_v3_targeted_probe", V3 / "run_v3.py")
    argv_v3 = load_module("argv_validate_v3_targeted_probe", V3 / "argv_validate_v3.py")

    template = json.loads((V3 / "PPO_CONFIG_TEMPLATE_V3.json").read_text(encoding="utf-8"))
    model_manifest = json.loads((V3 / "MODEL_MANIFEST_V3.json").read_text(encoding="utf-8"))
    input_manifest = json.loads((V3 / "INPUT_MANIFEST_V3.json").read_text(encoding="utf-8"))
    manifest_checks = {
        "model_files_canonical": sha256_bytes(canonical(model_manifest["files"])) == model_manifest["files_manifest_sha256"],
        "input_files_canonical": sha256_bytes(canonical([
            {"path": item["relative_path"], "bytes": item["bytes"], "sha256": item["sha256"]}
            for item in input_manifest["files"]
        ])) == input_manifest["files_manifest_sha256"],
        "model_manifest_expected_hash": sha256_file(V3 / "MODEL_MANIFEST_V3.json") == expected["model"]["manifest_sha256"],
        "input_manifest_expected_hash": sha256_file(V3 / "INPUT_MANIFEST_V3.json") == expected["input"]["manifest_sha256"],
        "template_expected_hash": sha256_file(V3 / "PPO_CONFIG_TEMPLATE_V3.json") == expected["config_template"]["sha256"],
        "model_manifest_file_count": len(model_manifest["files"]) == 16,
        "input_manifest_file_count": len(input_manifest["files"]) == 4,
        "expected_tokenizer_equals_model": expected["model"]["tokenizer_path_must_equal_model_path"],
        "expected_class_order_equals_input_manifest": expected["input"]["class_order"] == input_manifest["class_order"],
    }

    with tempfile.TemporaryDirectory(prefix="rapo-v3-targeted-") as temporary:
        temp = Path(temporary)
        rendered_path = temp / "effective.json"
        source_root = temp / "source"
        model_root = temp / "model"
        input_root = temp / "input"
        output_root = temp / "output"
        run_v3._render_config(
            str(V3 / "PPO_CONFIG_TEMPLATE_V3.json"), str(rendered_path),
            source_root=str(source_root), model_root=str(model_root), input_root=str(input_root), output_root=str(output_root),
        )
        rendered_text = rendered_path.read_text(encoding="utf-8")
        rendered = json.loads(rendered_text)
        render_checks = {
            "positive_no_unresolved_placeholders": "${" not in rendered_text,
            "positive_source_root_bound": same_path(rendered["data"]["format_prompt"], source_root.resolve() / "examples" / "format_prompt" / "cls.jinja"),
            "positive_model_root_bound": same_path(rendered["worker"]["actor"]["model"]["model_path"], model_root.resolve()),
            "positive_input_root_bound": same_path(rendered["data"]["train_files"], input_root.resolve()),
            "positive_output_root_bound": same_path(rendered["trainer"]["save_checkpoint_path"], output_root.resolve() / "_unused"),
        }
        try:
            run_v3._render({"bad": "${UNBOUND}"}, {})
            unresolved_rejected = False
            unresolved_error = None
        except Exception as exc:
            unresolved_rejected = True
            unresolved_error = f"{type(exc).__name__}: {exc}"
        render_checks["negative_unresolved_placeholder_rejected"] = unresolved_rejected
        render_checks["negative_unresolved_placeholder_error"] = unresolved_error

        frozen_content_checks = make_frozen_content_fixture(argv_v3, temp / "frozen-content")

    command_text = (V3 / "COMMANDS_V3.md").read_text(encoding="utf-8")
    args_start = command_text.index("  args=(")
    args_end = command_text.index("  if [[", args_start)
    command_args_block = command_text[args_start:args_end]
    missing_cil_cfg = run_missing_cil_cfg(run_v3)
    command_checks = {
        "commands_run_leg_passes_cil_cfg": "--cil-cfg" in command_args_block,
        "launcher_parser_requires_cil_cfg": True,
        "actual_launcher_missing_cil_cfg_exit_code": missing_cil_cfg["exit_code"],
        "actual_launcher_missing_cil_cfg_rejected": missing_cil_cfg["exit_code"] == 2,
        "parser_error_identifies_cil_cfg": missing_cil_cfg["stderr_mentions_cil_cfg"],
    }

    child_bootstrap = load_module("child_bootstrap_v3_targeted_probe", V3 / "child_bootstrap_v3.py")
    old_env = os.environ.copy()
    child_bootstrap_result = {}
    with tempfile.TemporaryDirectory(prefix="rapo-v3-child-") as temporary:
        os.environ.update({
            "RAPO_DIAG_RUN_ROOT": temporary,
            "RAPO_DIAG_LEG": "PROBE",
            "RAPO_DIAG_SCHEMA": "3",
            "RAPO_DIAG_CHILD_BOOTSTRAP": "1",
            "RAPO_DIAG_ROLE": "ray_worker",
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        sys.modules.pop("runtime_observer_v3", None)
        report = child_bootstrap.bootstrap(role="ray_worker", rank=0, stage="acceptance_probe")
        events = read_events(Path(temporary))
        child_bootstrap_result = {
            "reported_installed": report.get("installed"),
            "runtime_observer_imported_after_bootstrap": "runtime_observer_v3" in sys.modules,
            "event_kind": events[0].get("kind") if events else None,
            "event_role": events[0].get("role") if events else None,
            "event_module_identity_hashes_present": bool(report.get("bootstrap_module", {}).get("sha256") and report.get("observer_module", {}).get("sha256")),
        }
    os.environ.clear()
    os.environ.update(old_env)

    sitecustomize_result = {}
    with tempfile.TemporaryDirectory(prefix="rapo-v3-sitecustomize-") as temporary:
        env = old_env.copy()
        env.update({
            "RAPO_DIAG_RUN_ROOT": temporary,
            "RAPO_DIAG_LEG": "PROBE_SITE",
            "RAPO_DIAG_SCHEMA": "3",
            "RAPO_DIAG_CHILD_BOOTSTRAP": "1",
            "RAPO_DIAG_ROLE": "production_driver",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(V3),
        })
        code = "import json,sys; print(json.dumps({'observer_imported': 'runtime_observer_v3' in sys.modules, 'sitecustomize_file': getattr(sys.modules.get('sitecustomize'), '__file__', None)}))"
        process = subprocess.run([sys.executable, "-B", "-c", code], env=env, capture_output=True, text=True, timeout=30)
        events = read_events(Path(temporary))
        parsed = json.loads(process.stdout.strip().splitlines()[-1]) if process.stdout.strip() else {}
        sitecustomize_result = {
            "exit_code": process.returncode,
            "observer_imported": parsed.get("observer_imported"),
            "sitecustomize_file": parsed.get("sitecustomize_file"),
            "bootstrap_event_count": len([item for item in events if item.get("kind") == "child_bootstrap_install"]),
        }

    observer = load_module("runtime_observer_v3_targeted_probe", V3 / "runtime_observer_v3.py")
    observer_child_result = {}
    with tempfile.TemporaryDirectory(prefix="rapo-v3-observer-child-") as temporary:
        os.environ.update({
            "RAPO_DIAG_RUN_ROOT": temporary,
            "RAPO_DIAG_LEG": "PROBE_OBSERVER",
            "RAPO_DIAG_ROLE": "production_driver",
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        observer._physical_gpu_observation = lambda: {"probe": True}
        observer._CHILD_BOOTSTRAP_KEYS.clear()
        observer._PROCESS_IDENTITY_KEYS.clear()
        observer._PATCHED.clear()
        observer._ensure_process("ray_runner", {"rank": 0})
        events = read_events(Path(temporary))
        sequences = [item.get("seq") for item in events]
        observer_child_result = {
            "child_observer_install_event": any(item.get("kind") == "child_observer_install" for item in events),
            "process_identity_event": any(item.get("kind") == "process_identity" for item in events),
            "patched_labels_after_ensure_process": sorted(observer._PATCHED),
            "child_event_reports_installed": [item.get("installed") for item in events if item.get("kind") == "child_observer_install"],
            "event_sequences": sequences,
            "duplicate_seq_values": sorted({value for value in sequences if sequences.count(value) > 1}),
        }
    os.environ.clear()
    os.environ.update(old_env)

    sys.path.insert(0, str(V3))
    judge = load_module("judge_v3", V3 / "judge_v3.py")
    fixture_module = load_module("test_judge_v3_targeted_probe", V3 / "test_judge_v3.py")
    base = fixture_module.valid_fixture()
    valid_result = judge.evaluate_evidence(copy.deepcopy(base), require_state=True)
    effective_constant = copy.deepcopy(base)
    effective_constant["updates"][0]["batch"]["effective_sequence_rewards"] = [0.5, 0.5, 0.5, 0.5]
    effective_constant["updates"][0]["batch"]["groups"][0]["effective"] = [0.5, 0.5, 0.5, 0.5]
    effective_constant["updates"][0]["batch"]["groups"][0]["effective_variation"] = 0.0
    effective_result = judge.evaluate_evidence(effective_constant, require_state=True)

    fake_hash = {"sha256": "a" * 64}
    fake_events = []
    for role, rank, unix in (("production_driver", None, 1.0), ("ray_runner", None, 2.0), ("ray_worker", 0, 3.0), ("ray_worker", 1, 4.0)):
        fake_events.append({
            "kind": "child_bootstrap_install",
            "role": role,
            "rank": rank,
            "installed": True,
            "bootstrap_module": fake_hash,
            "observer_module": fake_hash,
            "unix": unix,
        })
    fake_reasons = []
    judge._validate_child_bootstrap(fake_events, fake_reasons, "synthetic")
    judge_result = {
        "valid_fixture_pass": valid_result["pass"],
        "effective_constant_rejected": not effective_result["pass"],
        "effective_constant_reasons": effective_result["reasons"],
        "hash_only_child_bootstrap_gate_accepts_without_wrapper_report": not fake_reasons,
        "hash_only_child_bootstrap_gate_reasons": fake_reasons,
    }

    child_source = (V3 / "child_bootstrap_v3.py").read_text(encoding="utf-8")
    observer_source = (V3 / "runtime_observer_v3.py").read_text(encoding="utf-8")
    worker_source = (TARGET / "verl" / "workers" / "fsdp_workers.py").read_text(encoding="utf-8")
    production_source = (TARGET / "examples" / "baselines" / "img_cls_cil" / "image_cls_cil_rapo.py").read_text(encoding="utf-8")
    source_wiring = {
        "child_bootstrap_imports_runtime_observer": "import runtime_observer_v3" in child_source,
        "sitecustomize_calls_only_bootstrap": "bootstrap(stage=\"sitecustomize\")" in (V3 / "sitecustomize.py").read_text(encoding="utf-8") and "install(" not in (V3 / "sitecustomize.py").read_text(encoding="utf-8"),
        "observer_patches_checkpoint_manager": "_patch(manager_module.FSDPCheckpointManager, \"load_checkpoint\"" in observer_source,
        "observer_install_calls_process_wrappers": "_install_process_wrappers(target)" in observer_source,
        "worker_module_imports_checkpoint_manager_global": "from ..utils.checkpoint.fsdp_checkpoint_manager import FSDPCheckpointManager" in worker_source,
        "worker_instantiates_checkpoint_manager": "self.checkpoint_manager = FSDPCheckpointManager(" in worker_source,
        "runner_creates_worker_remote_in_runner": "ray.remote(PersistentRefFSDPWorker)" in production_source,
        "child_bootstrap_has_no_wrapper_install_call": "_install_process_wrappers" not in child_source and "runtime_observer_v3.install" not in child_source,
    }

    result = {
        "status": "PASS_TARGETED_PROBE_WITH_FINDINGS",
        "v3_root": str(V3),
        "target_root": str(TARGET),
        "hash_manifest": {"declared_file_count": len(declared), "actual_file_count": len(actual_paths), "mismatches": hash_mismatches, "extra_files": extra_files, "all_declared_match": not hash_mismatches and not extra_files},
        "ast_compile": ast_results,
        "target_identity": {
            "bytes": (TARGET / expected["target"]["production_source"]["relative_path"]).stat().st_size,
            "sha256": sha256_file(TARGET / expected["target"]["production_source"]["relative_path"]),
            "expected_bytes": expected["target"]["production_source"]["bytes"],
            "expected_sha256": expected["target"]["production_source"]["sha256"],
        },
        "manifest_checks": manifest_checks,
        "render_checks": render_checks,
        "frozen_content_checks": frozen_content_checks,
        "command_checks": command_checks,
        "child_bootstrap_check": child_bootstrap_result,
        "sitecustomize_check": sitecustomize_result,
        "observer_ensure_process_check": observer_child_result,
        "judge_check": judge_result,
        "source_wiring": source_wiring,
        "gpu_executed": False,
        "ray_executed": False,
        "production_imported": False,
        "training_executed": False,
        "inference_executed": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
