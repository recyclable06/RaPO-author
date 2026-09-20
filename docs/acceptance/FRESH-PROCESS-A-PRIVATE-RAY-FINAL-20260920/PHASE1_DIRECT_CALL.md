# Phase 1 independent direct-call contract

用途：在 host 211 上运行 final bundle 的 Linux/procfs fake-child check，且不
执行 `run_supervisor_tests.py:main()`，从而不覆盖冻结的
`Final/test-results.json`。

`Final`、父 snapshot 和 zero-GPU snapshot 必须先按 `FINAL_COMMAND.md` 部署；
`Output` 必须是 Final 目录之外的新目录。使用 `python -B` 并设置
`PYTHONDONTWRITEBYTECODE=1`，保证导入不会产生新的 runtime 文件。

```bash
set -euo pipefail

Final=/mnt/conda/zhenglifeng/t/rapo-author-a-private-ray-supervisor-final-20260920
Output=/mnt/conda/zhenglifeng/t/rapo-author-a-private-ray-supervisor-phase1-output-20260920
Python=/mnt/conda/zhenglifeng/rapo-author-diagnostic-20260908/env/rapo-author/bin/python

export RAPO_LINUX_SUPERVISOR_ROOT=/tmp/zlf-s20p
export RAPO_LINUX_RAY_TMP=/tmp/zlf-s20l
export PYTHONDONTWRITEBYTECODE=1
test ! -e "$Output"
test ! -e "$RAPO_LINUX_SUPERVISOR_ROOT"
test ! -e "$RAPO_LINUX_RAY_TMP"

exec "$Python" -B -c '
import hashlib, importlib.util, json, sys
from pathlib import Path

final = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
output.mkdir(mode=0o700)

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return (path.stat().st_size, h.hexdigest())

def runtime_state():
    hashes = json.loads((final / "HASHES_FINAL.json").read_text(encoding="utf-8"))
    return {entry["path"]: digest(final / entry["path"]) for entry in hashes["files"]}

before = runtime_state()
sys.path.insert(0, str(final))
spec = importlib.util.spec_from_file_location("phase1_direct_tests", final / "run_supervisor_tests.py")
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load run_supervisor_tests.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.run_linux_process_check()
(output / "linux-process-check.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
after = runtime_state()
if before != after:
    raise RuntimeError("final runtime bytes changed during direct Phase 1 call")
(output / "runtime-unchanged.json").write_text(json.dumps({"unchanged": True, "files": before}, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, sort_keys=True))
' "$Final" "$Output"
```

This contract covers Linux `/proc` identity, fake CLI process-tree cleanup,
file-backed logs and timeout budget without mutating Final. It does not cover
real SIGINT/SIGTERM delivery to the supervisor; use a separate signal harness
for that evidence before describing Phase 1 as signal-complete.
