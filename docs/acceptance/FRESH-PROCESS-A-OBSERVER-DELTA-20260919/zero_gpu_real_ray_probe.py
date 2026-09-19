"""Real Ray, zero-GPU dispatch probe for the A observer delta.

This probe intentionally does not use a fake Ray module and does not call the
production runner's init/model/training path.  It is a wiring/serialization
check only; a PASS here is not an A boundary PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any


CANONICAL_TARGET = "examples.baselines.img_cls_cil.image_cls_cil_rapo"
ENV_NAMES = (
    "RAPO_DIAG_RUN_ROOT",
    "RAPO_DIAG_LEG",
    "RAPO_DIAG_SCHEMA",
    "RAPO_DIAG_CHILD_BOOTSTRAP",
    "RAPO_DIAG_FAIL_CLOSED",
    "PYTHONPATH",
    "PYTHONDONTWRITEBYTECODE",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def put_paths(delta_root: Path, v9_root: Path, source_root: Path) -> str:
    ordered = [str(delta_root.resolve()), str(v9_root.resolve()), str(source_root.resolve())]
    for item in reversed(ordered):
        if item not in sys.path:
            sys.path.insert(0, item)
    inherited = os.environ.get("PYTHONPATH", "")
    return os.pathsep.join(ordered + ([inherited] if inherited else []))


def read_events(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted((root / "observer" / "events").glob("events-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                record["_event_file"] = path.name
                records.append(record)
    return records


def run(args: argparse.Namespace) -> dict[str, Any]:
    delta_root = Path(args.delta_root).resolve()
    v9_root = Path(args.v9_root).resolve()
    source_root = Path(args.source_root).resolve()
    run_root = Path(args.run_root).resolve()
    delta_observer = delta_root / "child_observer_v6.py"
    if run_root.exists() and any(run_root.iterdir()):
        raise RuntimeError(f"run root is not fresh: {run_root}")
    run_root.mkdir(parents=True, exist_ok=True)

    pythonpath = put_paths(delta_root, v9_root, source_root)
    os.environ.update(
        {
            "RAPO_DIAG_RUN_ROOT": str(run_root),
            "RAPO_DIAG_LEG": "ZERO_GPU_DELTA",
            "RAPO_DIAG_SCHEMA": "6",
            "RAPO_DIAG_CHILD_BOOTSTRAP": "1",
            "RAPO_DIAG_FAIL_CLOSED": "1",
            "RAPO_DIAG_ROLE": "production_driver",
            "RAPO_DIAG_RANK": "",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": pythonpath,
        }
    )

    identity = {
        "delta_observer": {"path": str(delta_observer), "sha256": sha256_file(delta_observer)},
        "v9_child_bootstrap": {"path": str(v9_root / "child_bootstrap_v6.py"), "sha256": sha256_file(v9_root / "child_bootstrap_v6.py")},
        "v9_event_writer": {"path": str(v9_root / "event_writer_v6.py"), "sha256": sha256_file(v9_root / "event_writer_v6.py")},
        "v9_runtime_entry": {"path": str(v9_root / "runtime_entry_v6.py"), "sha256": sha256_file(v9_root / "runtime_entry_v6.py")},
        "production_source": {"path": str(source_root / "examples/baselines/img_cls_cil/image_cls_cil_rapo.py"), "sha256": sha256_file(source_root / "examples/baselines/img_cls_cil/image_cls_cil_rapo.py")},
        "pythonpath_order": [str(delta_root), str(v9_root), str(source_root)],
    }

    try:
        import ray
    except Exception as exc:
        return {
            "schema": "fresh-process-a-observer-delta-real-ray-zero-gpu-v1",
            "status": "BLOCKED_REAL_RAY_UNAVAILABLE",
            "gpu_requested": False,
            "model_path_used": False,
            "training_invoked": False,
            "identity": identity,
            "error": f"{type(exc).__name__}: {exc}",
        }

    import child_observer_v6 as observer

    observer.install_import_hook()
    target = importlib.import_module(CANONICAL_TARGET)
    if target.__name__ != CANONICAL_TARGET:
        raise AssertionError(f"non-canonical target module: {target.__name__!r}")

    runtime_env = {"env_vars": {name: os.environ[name] for name in ENV_NAMES if name in os.environ}}
    ray.init(
        address="local",
        num_gpus=0,
        num_cpus=3,
        include_dashboard=False,
        log_to_driver=False,
        runtime_env=runtime_env,
    )
    runner_error: str | None = None
    worker_report: dict[str, Any] | None = None

    @ray.remote(num_gpus=0, num_cpus=0.25)
    class ProbeActor:
        def inspect(self) -> dict[str, Any]:
            os.environ["RAPO_DIAG_ROLE"] = "ray_worker"
            import child_bootstrap_v6

            bootstrap = child_bootstrap_v6.bootstrap(role="ray_worker", stage="ray_actor_method")
            importlib.import_module(CANONICAL_TARGET)
            worker_observer = importlib.import_module("child_observer_v6")
            return {
                "pid": os.getpid(),
                "bootstrap": bootstrap,
                "observer_module": str(Path(worker_observer.__file__).resolve()),
            }

    try:
        runner = target.PersistentRunner.remote()
        try:
            ray.get(
                runner.run_task.remote(
                    config=None,
                    task_id=1,
                    val_progress=False,
                    val_write_predictions=False,
                    val_output_dir=None,
                    publish_task_boundary=True,
                )
            )
        except Exception as exc:
            runner_error = f"{type(exc).__name__}: {exc}"
        worker_report = ray.get(ProbeActor.remote().inspect.remote())
        ray.kill(runner, no_restart=True)
    finally:
        ray.shutdown()

    records = read_events(run_root)
    run_before = [
        record for record in records if record.get("kind") == "target_wrapper_call_before" and record.get("label") == "PersistentRunner.run_task"
    ]
    run_after = [
        record for record in records if record.get("kind") == "target_wrapper_call_after" and record.get("label") == "PersistentRunner.run_task"
    ]
    bootstrap_records = [record for record in records if record.get("kind") == "child_bootstrap_install"]
    remote_install_records = [record for record in records if record.get("kind") == "ray_remote_wrapper_install"]
    matching_calls = bool(run_before and run_after and run_before[0].get("call_id") == run_after[0].get("call_id"))
    delta_bootstrap_records = [
        record for record in bootstrap_records if record.get("observer", {}).get("sha256") == identity["delta_observer"]["sha256"]
    ]
    conditions = {
        "real_ray": True,
        "zero_gpu": True,
        "canonical_target": target.__name__ == CANONICAL_TARGET,
        "delta_bootstrap_seen": bool(delta_bootstrap_records),
        "remote_wrapper_installed": any(record.get("installed") is True for record in remote_install_records),
        "run_task_before_after_same_call": matching_calls,
        "runner_inert_error_observed": runner_error is not None,
        "model_path_used_by_probe": False,
        "training_invoked_by_probe": False,
    }
    status = "PASS_REAL_RAY_ZERO_GPU_DISPATCH" if all(conditions.values()) else "FAIL_REAL_RAY_ZERO_GPU_DISPATCH"
    return {
        "schema": "fresh-process-a-observer-delta-real-ray-zero-gpu-v1",
        "status": status,
        "gpu_requested": False,
        "model_path_used": False,
        "training_invoked": False,
        "identity": identity,
        "conditions": conditions,
        "runner_error": runner_error,
        "worker_report": worker_report,
        "run_task_before": [{key: record.get(key) for key in ("_event_file", "call_id", "pid", "role", "status")} for record in run_before],
        "run_task_after": [{key: record.get(key) for key in ("_event_file", "call_id", "pid", "role", "status")} for record in run_after],
        "bootstrap_count": len(bootstrap_records),
        "delta_bootstrap_count": len(delta_bootstrap_records),
        "remote_wrapper_install_count": len(remote_install_records),
        "event_count": len(records),
        "event_files": sorted({record["_event_file"] for record in records}),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delta-root", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--v9-root", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    try:
        result = run(args)
        code = 0 if result["status"] == "PASS_REAL_RAY_ZERO_GPU_DISPATCH" else 2
    except Exception as exc:
        result = {
            "schema": "fresh-process-a-observer-delta-real-ray-zero-gpu-v1",
            "status": "FAIL_REAL_RAY_ZERO_GPU_DISPATCH",
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    output = Path(args.result).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result.get("status"), "event_count": result.get("event_count", 0)}, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
