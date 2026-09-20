#!/usr/bin/env python3
"""Deterministic fake ``ray`` CLI used only by the external signal harness."""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time


def _write(name: str, value: str) -> None:
    pathlib.Path(os.environ[name]).write_text(value, encoding="utf-8")


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print("fake-ray-status-ready", flush=True)
        return 0
    if len(sys.argv) < 2 or sys.argv[1] != "start":
        print("fake-signal-ray expects start or status", file=sys.stderr, flush=True)
        return 64
    temp_dir = next((item.split("=", 1)[1] for item in sys.argv if item.startswith("--temp-dir=")), "")
    expected_temp = os.environ["RAPO_SIGNAL_RAY_TMP"]
    if temp_dir != expected_temp:
        print(f"unexpected temp dir: {temp_dir!r}", file=sys.stderr, flush=True)
        return 65
    pathlib.Path(temp_dir).mkdir(mode=0o700, exist_ok=True)
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)",],
        cwd=temp_dir,
        start_new_session=True,
    )
    _write("RAPO_SIGNAL_FAKE_RAY_PID", str(os.getpid()))
    _write("RAPO_SIGNAL_FAKE_RAY_CHILD_PID", str(child.pid))
    _write("RAPO_SIGNAL_FAKE_RAY_READY", "READY\n")
    print("fake-ray-head-ready", flush=True)
    time.sleep(120)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
