#!/usr/bin/env python3
"""Static, local-only checks for the external 012 signal harness."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import pathlib
import sys


REQUIRED_FILES = (
    "run_signal_harness.py",
    "fake_signal_ray.py",
    "fake_signal_launcher.py",
    "SIGNAL_HARNESS_COMMAND.md",
    "REPORT.md",
    "RUN_METADATA.json",
)
FORBIDDEN_RUNTIME_TEXT = ("ray stop", "pkill", "killall", "os.killpg", "_handle_interrupt")


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(root: pathlib.Path) -> dict[str, object]:
    files = {path.name: path for path in root.iterdir() if path.is_file()}
    missing = [name for name in REQUIRED_FILES if name not in files]
    if missing:
        raise AssertionError(f"missing harness files: {missing}")
    parsed: dict[str, ast.AST] = {}
    for name in ("run_signal_harness.py", "fake_signal_ray.py", "fake_signal_launcher.py"):
        path = files[name]
        parsed[name] = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        text = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_RUNTIME_TEXT:
            if forbidden in text:
                raise AssertionError(f"forbidden global/direct-handler operation {forbidden!r} in {name}")
    harness_text = files["run_signal_harness.py"].read_text(encoding="utf-8")
    required_text = (
        "os.kill(process.pid, signum)",
        "signal.SIGINT",
        "signal.SIGTERM",
        "_linux_identity",
        "process_start",
        "owner_uid",
        "session_id",
        "new_session",
        "runtime_before",
        "runtime_after",
        "RUNTIME_HASHES_SHA256",
        "MAIN_LIFECYCLE_SECONDS = 120.0",
        "CLEANUP_BUDGET_SECONDS = 120.0",
    )
    missing_text = [item for item in required_text if item not in harness_text]
    if missing_text:
        raise AssertionError(f"missing required harness coverage markers: {missing_text}")
    command_text = files["SIGNAL_HARNESS_COMMAND.md"].read_text(encoding="utf-8")
    for required in (
        "FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-ZEROGPU-CLI-FINAL-SUPPLEMENT",
        "FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-SUPERVISOR-SUPPLEMENT",
        "FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-ZEROGPU-SUPPLEMENT",
        "/tmp/zlf-s20i",
        "/tmp/zlf-s20t",
        "SIGINT",
        "SIGTERM",
        "test-results.json",
        "120",
    ):
        if required not in command_text:
            raise AssertionError(f"command contract lacks {required!r}")
    return {
        "schema": "private-ray-final-signal-harness-static-test-v1",
        "status": "PASS_PRIVATE_RAY_FINAL_SIGNAL_HARNESS_STATIC_TESTS",
        "executed_linux_signal_cases": False,
        "executed_ssh": False,
        "executed_ray": False,
        "executed_gpu": False,
        "parsed_python_files": sorted(parsed),
        "checked_required_files": list(REQUIRED_FILES),
        "source_sha256": {name: sha256(files[name]) for name in REQUIRED_FILES},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    result = check(args.root.expanduser().resolve())
    output = args.output.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise SystemExit(f"refusing to overwrite static test output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
