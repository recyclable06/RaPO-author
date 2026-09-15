"""Record CPU test command, source identity, environment and raw output."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/remediation/AUTH-CTAN-001"
PRODUCTION = ["examples/baselines/_rapo_components.py",
              "examples/baselines/img_cls_cil/image_cls_cil_rapo.py",
              "examples/baselines/cil_det/image_det_cil_rapo.py",
              *[f"scripts/{family}/rapo_cfg.json" for family in ("image", "video", "det")]]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    label = sys.argv[1]
    assert label in {"red-confirmed", "green"}
    assert not (OUT / f"{label}.json").exists(), "Evidence is write-once; choose a new reviewed run."
    cmd = [sys.executable, "-B", "-m", "pytest", "tests/author_fixes/test_ctan.py",
           "-p", "no:cacheprovider", "-v", "--tb=short"]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    # Hash before running; includes unmodified underlying GRPO and selected hook sources.
    paths = PRODUCTION + ["verl/trainer/core_algos.py", "verl/trainer/ray_trainer.py"]
    paths += [p.relative_to(ROOT).as_posix() for p in (ROOT / "tests/author_fixes").glob("*.py")]
    hashes = {p: sha(ROOT / p) for p in paths}
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True)
    (OUT / f"{label}.stdout.txt").write_bytes(p.stdout)
    (OUT / f"{label}.stderr.txt").write_bytes(p.stderr)
    import torch
    import numpy
    record = dict(command=cmd, cwd=str(ROOT), exit_code=p.returncode,
                  python=sys.version, platform=platform.platform(), torch=torch.__version__,
                  numpy=numpy.__version__, environment_overrides={k: env[k] for k in
                  ("PYTHONIOENCODING", "PYTHONDONTWRITEBYTECODE")}, source_sha256=hashes,
                  dependencies={k: importlib.util.find_spec(k) is not None for k in
                  ("torch", "numpy", "scipy", "pytest", "jinja2", "ray", "datasets", "transformers", "vllm")})
    (OUT / f"{label}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(p.stdout.decode("utf-8"))
    print("Recorded exit code:", p.returncode)
    sys.exit(p.returncode)
