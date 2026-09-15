"""Independent CPU/static acceptance probe for the frozen v5 candidate.

This probe reads the frozen candidate and target identities, runs only the
candidate's CPU fixtures, and exercises the candidate judge with deliberately
adversarial in-memory evidence.  It does not install dependencies, import the
production module, start Ray, construct a model, or write outside the
acceptance output supplied by the caller.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _compact(entries: Any) -> str:
    return _sha256(json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _manifest(root: Path, *, exclude: set[str] | None = None) -> list[dict[str, Any]]:
    exclude = exclude or set()
    result = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_file() and path.name not in exclude:
            result.append({
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path.read_bytes()),
            })
    return result


def _history_manifest(root: Path) -> list[dict[str, Any]]:
    result = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item).lower()):
        if path.is_file():
            result.append({
                "path": f"raw/{path.relative_to(root).as_posix()}",
                "bytes": path.stat().st_size,
                "sha256": _sha256(path.read_bytes()),
            })
    return result


def _event(kind: str, seq: int, *, label: str | None = None, call_id: str | None = None,
           role: str = "ray_worker", rank: int = 0, writer_hash: str = "a" * 64,
           status: str | None = None, before_seq: int | None = None,
           original_call_count: int | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema_version": 5,
        "kind": kind,
        "leg": "ZERO_GPU",
        "pid": 77,
        "process_start": "77:1",
        "seq": seq,
        "writer_seq": seq,
        "writer": {"module": "event_writer_v5", "path": "/not-the-frozen-writer.py", "bytes": 1, "sha256": writer_hash},
        "role": role,
        "rank": rank,
    }
    if label is not None:
        value["label"] = label
    if call_id is not None:
        value["call_id"] = call_id
    if status is not None:
        value["status"] = status
    if before_seq is not None:
        value["before_seq"] = before_seq
    if original_call_count is not None:
        value["original_call_count"] = original_call_count
    if kind.startswith("target_wrapper_call"):
        value["original"] = {"module": "fixture", "qualname": "Owner.method", "name": "method", "object_id": 1}
    return value


def _install(seq: int = 1, *, writer_hash: str = "a" * 64) -> dict[str, Any]:
    return {
        **_event("child_observer_install", seq, writer_hash=writer_hash),
        "methods": [{
            "label": "Owner.method",
            "installed": True,
            "owner": "fixture.Owner",
            "wrapped": {"name": "wrapped"},
            "original": {"name": "original"},
        }],
    }


def _call_pair(*, before_seq: int, after_seq: int, writer_hash: str = "a" * 64) -> list[dict[str, Any]]:
    call_id = "77:call"
    return [
        _event("target_wrapper_call_before", before_seq, label="Owner.method", call_id=call_id, writer_hash=writer_hash, original_call_count=0),
        _event("target_wrapper_call_after", after_seq, label="Owner.method", call_id=call_id, writer_hash=writer_hash, status="returned", before_seq=before_seq, original_call_count=1),
    ]


def _run_fixture(candidate: Path, filename: str, extra: list[str] | None = None) -> dict[str, Any]:
    command = [sys.executable, "-B", str(candidate / filename)] + (extra or [])
    completed = subprocess.run(command, cwd=str(candidate), capture_output=True, text=True, check=False)
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def run(candidate: Path, target_root: Path) -> dict[str, Any]:
    candidate = candidate.resolve()
    target_root = target_root.resolve()
    hashes = json.loads((candidate / "HASHES_V5.json").read_text(encoding="utf-8"))
    package = _manifest(candidate, exclude={"HASHES_V5.json"})
    raw = [item for item in package if item["path"].startswith("raw/")]
    package_manifest_ok = package == hashes["files"] and _compact(package) == hashes["package_manifest_sha256"]
    raw_manifest_ok = raw == [item for item in hashes["files"] if item["path"].startswith("raw/")] and _compact(raw) == hashes["raw_manifest_sha256"]

    historical_root = candidate.parent / "v3-bootstrap-supplement" / "raw"
    historical = _history_manifest(historical_root)
    packaged_history = json.loads((candidate / "raw" / "v3-bootstrap-supplement-raw-manifest.json").read_text(encoding="utf-8"))
    history_ok = historical == packaged_history["files"] and _compact(historical) == packaged_history["manifest_sha256"]

    expected = json.loads((candidate / "EXPECTED_IDENTITY_V5.json").read_text(encoding="utf-8"))
    source = target_root / expected["target"]["production_source"]["relative_path"]
    test_reference = target_root / expected["target"]["test_reference"]["relative_path"]
    template = json.loads((candidate / "PPO_CONFIG_TEMPLATE_V5.json").read_text(encoding="utf-8"))
    input_manifest = json.loads((candidate / "INPUT_MANIFEST_V5.json").read_text(encoding="utf-8"))
    task2_samples = sum(1 for item in input_manifest.get("files", []) if item.get("task") == 2)
    mini_batch = int(template["data"]["mini_rollout_batch_size"])
    target_source = (target_root / "examples/baselines/img_cls_cil/image_cls_cil.py").read_text(encoding="utf-8")
    production_steps_source = source.read_text(encoding="utf-8")
    loader_length_static = task2_samples // mini_batch if "drop_last = True" in target_source else None
    loader_recipe = {
        "task2_manifest_samples": task2_samples,
        "mini_rollout_batch_size": mini_batch,
        "drop_last_true_in_actual_builder": "drop_last = True" in target_source,
        "actual_length_from_frozen_samples": loader_length_static,
        "candidate_expected_length": expected["recipe"]["task2_loader_length"],
        "candidate_expected_updates": expected["recipe"]["task2_updates"],
        "production_uses_total_epochs_times_loader_length": "per_task_steps = config.trainer.total_epochs * len(train_dataloader)" in production_steps_source,
        "recipe_mismatch": loader_length_static != expected["recipe"]["task2_loader_length"],
    }
    source_ok = source.stat().st_size == expected["target"]["production_source"]["bytes"] and _sha256(source.read_bytes()) == expected["target"]["production_source"]["sha256"]
    test_ok = test_reference.stat().st_size == expected["target"]["test_reference"]["bytes"] and _sha256(test_reference.read_bytes()) == expected["target"]["test_reference"]["sha256"]
    ast_files = []
    for path in sorted(candidate.glob("*.py")):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        ast_files.append(path.name)

    fixture = _run_fixture(candidate, "test_v5.py")
    launcher = _run_fixture(candidate, "launcher_contract_probe_v5.py")

    sys.path.insert(0, str(candidate))
    from judge_v5 import validate_event_sequences, validate_process_association
    from state_fingerprint_v5 import state_dict_fingerprint
    import trajectory_compare_v5

    class SameState:
        def state_dict(self) -> dict[str, int]:
            return {"weight": 1}

    actor = state_dict_fingerprint(SameState(), label="actor")
    anchor = state_dict_fingerprint(SameState(), label="anchor")
    equal_state_hashes_rejected = actor["sha256"] != anchor["sha256"]

    call_before_install = [_call_pair(before_seq=1, after_seq=2)[0], _call_pair(before_seq=1, after_seq=2)[1], _install(seq=3)]
    before_install_sequence_ok, before_install_sequence_reasons = validate_event_sequences(call_before_install)
    before_install_association_ok, before_install_association_reasons = validate_process_association(
        call_before_install,
        required_per_process={"Owner.method"},
        roles={"ray_worker"},
    )

    fake_writer = [_install(seq=1, writer_hash="0" * 64), *_call_pair(before_seq=2, after_seq=3, writer_hash="0" * 64)]
    fake_writer_sequence_ok, fake_writer_sequence_reasons = validate_event_sequences(fake_writer)
    fake_writer_association_ok, fake_writer_association_reasons = validate_process_association(
        fake_writer,
        required_per_process={"Owner.method"},
        roles={"ray_worker"},
    )

    continuous: list[dict[str, Any]] = []
    resumed: list[dict[str, Any]] = []
    for rank in (0, 1):
        for index in range(4):
            continuous.append({"kind": "target_wrapper_call_after", "label": "FSDPWorker.update_actor", "rank": rank, "group": {
                "raw_rewards": {"mean": 1.0, "full_digest": {"sha256": f"c-{rank}-{index}"}},
                "effective_advantages": {"mean": 2.0, "full_digest": {"sha256": f"ca-{rank}-{index}"}},
            }})
        for index in range(2):
            resumed.append({"kind": "target_wrapper_call_after", "label": "FSDPWorker.update_actor", "rank": rank, "group": {
                "raw_rewards": {"mean": 1.0, "full_digest": {"sha256": f"b-{rank}-{index}"}},
                "effective_advantages": {"mean": 2.0, "full_digest": {"sha256": f"ba-{rank}-{index}"}},
            }})
    old_reader = trajectory_compare_v5.read_events
    try:
        trajectory_compare_v5.read_events = lambda root: continuous if root.name == "c" else resumed
        trajectory_same_means_pass = trajectory_compare_v5.compare(Path("c"), Path("b"))["status"] == "PASS"
    finally:
        trajectory_compare_v5.read_events = old_reader

    return {
        "schema_version": 5,
        "candidate": str(candidate),
        "package": {"count": len(package), "bytes": sum(item["bytes"] for item in package), "manifest": _compact(package), "declared_match": package_manifest_ok},
        "raw": {"count": len(raw), "bytes": sum(item["bytes"] for item in raw), "manifest": _compact(raw), "declared_match": raw_manifest_ok},
        "history_manifest": {"count": len(historical), "bytes": sum(item["bytes"] for item in historical), "manifest": _compact(historical), "matches_packaged": history_ok},
        "target_identity": {"source_match": source_ok, "test_match": test_ok},
        "loader_recipe": loader_recipe,
        "ast": {"count": len(ast_files), "status": "PASS_V5_AST"},
        "fixtures": {"test_v5": fixture, "launcher_contract": launcher},
        "judge_negative_probes": {
            "equal_actor_anchor_hashes_rejected": equal_state_hashes_rejected,
            "call_before_install_sequence_valid": before_install_sequence_ok,
            "call_before_install_association_passed": before_install_association_ok,
            "call_before_install_reasons": before_install_sequence_reasons + before_install_association_reasons,
            "fake_writer_sequence_valid": fake_writer_sequence_ok,
            "fake_writer_association_passed": fake_writer_association_ok,
            "fake_writer_reasons": fake_writer_sequence_reasons + fake_writer_association_reasons,
            "same_means_different_group_digests_trajectory_passed": trajectory_same_means_pass,
        },
        "scope": {"ray_started": False, "gpu_used": False, "model_constructed": False, "production_imported": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--target-root", required=True)
    args = parser.parse_args()
    result = run(Path(args.candidate), Path(args.target_root))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
