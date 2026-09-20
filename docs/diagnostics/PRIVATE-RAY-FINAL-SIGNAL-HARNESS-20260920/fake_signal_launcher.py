#!/usr/bin/env python3
"""Deterministic fake launcher used only by the external signal harness."""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time


def _arg(name: str) -> str:
    prefix = name + "="
    for item in sys.argv[1:]:
        if item.startswith(prefix):
            return item[len(prefix) :]
    raise SystemExit(f"missing {name}")


def _write(name: str, value: str) -> None:
    pathlib.Path(os.environ[name]).write_text(value, encoding="utf-8")


def main() -> int:
    ready_marker = _arg("--ready-marker")
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)",],
        cwd=os.path.dirname(ready_marker),
        start_new_session=True,
    )
    _write("RAPO_SIGNAL_FAKE_LAUNCHER_PID", str(os.getpid()))
    _write("RAPO_SIGNAL_FAKE_LAUNCHER_CHILD_PID", str(child.pid))
    pathlib.Path(ready_marker).write_text("READY\n", encoding="utf-8")
    print("fake-launcher-ready", flush=True)
    time.sleep(120)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
