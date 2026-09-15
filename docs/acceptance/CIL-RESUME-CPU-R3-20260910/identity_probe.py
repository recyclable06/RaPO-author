from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


TARGET = Path(r"C:\Users\Administrator\.codex\worktrees\8ac5\RaPO-author")
R3 = TARGET / "docs" / "remediation" / "CAND-RESUME-CIL-001" / "r3"
R3_HASHES = R3 / "HASHES.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record(path: Path) -> dict[str, object]:
    return {"bytes": path.stat().st_size, "sha256": sha256(path)}


def main() -> dict[str, object]:
    manifest = json.loads(R3_HASHES.read_text(encoding="utf-8"))
    manifest_sha = sha256(R3_HASHES)
    artifacts = []
    for item in manifest["r3_artifacts"]:
        path = R3 / item["path"]
        actual = record(path) if path.is_file() else {"bytes": None, "sha256": None}
        artifacts.append(
            {
                "path": item["path"],
                "declared": {"bytes": item["bytes"], "sha256": item["sha256"]},
                "actual": actual,
                "match": actual == {"bytes": item["bytes"], "sha256": item["sha256"]},
            }
        )

    target_records = []
    for item in manifest["current_target_files"]:
        path = TARGET / item["path"]
        actual = record(path) if path.is_file() else {"bytes": None, "sha256": None}
        target_records.append(
            {
                "path": item["path"],
                "declared": {"bytes": item["bytes"], "sha256": item["sha256"]},
                "actual": actual,
                "match": actual == {"bytes": item["bytes"], "sha256": item["sha256"]},
            }
        )

    source = TARGET / "examples" / "baselines" / "img_cls_cil" / "image_cls_cil_rapo.py"
    test = TARGET / "tests" / "author_fixes" / "test_cil_resume.py"
    first = {"source": record(source), "test": record(test)}
    second = {"source": record(source), "test": record(test)}
    target_match = all(item["match"] for item in target_records)
    evidence_match = all(item["match"] for item in artifacts)
    return {
        "schema_version": 1,
        "probe": "identity_probe.py",
        "target_root": str(TARGET),
        "r3_manifest": {
            "path": str(R3_HASHES),
            "declared_sha256": "85424f75e03f67e7095867de898edbbb1b9545dac4579dc0baab553724ef2b79",
            "actual_sha256": manifest_sha,
            "self_matches": manifest_sha
            == "85424f75e03f67e7095867de898edbbb1b9545dac4579dc0baab553724ef2b79",
            "r3_artifacts": artifacts,
            "all_r3_artifacts_match": evidence_match,
        },
        "target_current_files": target_records,
        "target_identity_stable_during_probe": first == second,
        "before_after_observed": {"before": first, "after": second},
        "cpu_regression": {
            "status": "not_run",
            "reason": "target files do not match the delegated R3 frozen identity",
        },
        "verdict": "BLOCKED_IDENTITY_DRIFT",
        "delegated_r3_target_matches": target_match,
        "required_next_action": "refresh the authoritative target snapshot and HASHES.json, or restore the delegated R3 files before CPU acceptance",
    }


if __name__ == "__main__":
    evidence = main()
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    raise SystemExit(2)
