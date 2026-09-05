"""Verify source preservation and run bounded, local intake checks only."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
AUTHOR = ROOT / "RaPO_作者整理代码"
SNAPSHOT = json.loads((OUT / "intake-snapshot.json").read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {"command": args, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def inventory(name):
    files, size, errors = 0, 0, []
    def onerror(exc):
        errors.append(str(exc))
    for folder, dirs, names in os.walk(ROOT / name, onerror=onerror, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(folder) / d).is_symlink()]
        for item in names:
            path = Path(folder) / item
            if path.is_symlink():
                continue
            try:
                size += path.stat().st_size
                files += 1
            except OSError as exc:
                errors.append(str(exc))
    return {"files": files, "bytes": size, "errors": errors, "symlinks_followed": False}


def main():
    actual = {p.relative_to(AUTHOR).as_posix(): sha(p) for p in AUTHOR.rglob("*") if p.is_file()}
    expected = {name: record["sha256"] for name, record in SNAPSHOT["author_files"].items()}
    author_changes = sorted(name for name in actual.keys() | expected.keys() if actual.get(name) != expected.get(name))
    tracked_changes = [name for name, record in SNAPSHOT["tracked_files"].items()
                       if not (ROOT / name).is_file() or sha(ROOT / name) != record["sha256"]]
    allowed = {"AGENTS.md", "README.md", "docs/reproduction_spec.md", "docs/upstream.md",
               "docs/trainer_integration.md", "docs/data_and_evaluation.md", "docs/smoke_test.md"}
    syntax_errors = []
    python_files = list(AUTHOR.rglob("*.py"))
    for path in python_files:
        try:
            compile(ast.parse(path.read_bytes(), filename=str(path)), str(path), "exec")
        except Exception as exc:
            syntax_errors.append({"path": path.relative_to(AUTHOR).as_posix(), "error": str(exc)})
    scripts = sorted(AUTHOR.rglob("*.sh"))
    checks = [run(["D:/Git/bin/bash.exe", "-n", p.relative_to(ROOT).as_posix()]) for p in scripts]
    probe = run(["D:/anaconda3/envs/rapo-b01/python.exe", str(OUT / "cpu_probes.py")])
    (OUT / "cpu-probes-stdout.txt").write_text(probe["stdout"] + probe["stderr"], encoding="utf-8")
    probe["stdout"] = "See cpu-probes-stdout.txt and cpu-probes.json"
    result = {"python_for_syntax_check": sys.version,
              "author_preservation": {"files": len(actual), "changed": author_changes},
              "archive_unchanged": sha(ROOT / "RaPO_作者整理代码.zip") == SNAPSHOT["archive_sha256"],
              "paper_unchanged": sha(ROOT / "2605.09640v1.pdf") == SNAPSHOT["paper_sha256"],
              "private_policy_unchanged": sha(ROOT / "实验室服务器使用规范.md") == SNAPSHOT["private_policy"]["whole_sha256"],
              "tracked_changes_since_intake": tracked_changes,
              "outside_document_allowlist": [name for name in tracked_changes if name not in allowed],
              "python_syntax": {"count": len(python_files), "errors": syntax_errors},
              "shell_syntax": checks, "cpu_probes": probe,
              "legacy_inventory": {name: inventory(name) for name in ["src", "tests", "scripts", "configs", "patches", "tmp", ".venv", ".pytest_cache"]},
              "git_diff_check": run(["git", "diff", "--check"]),
              "git_status": run(["git", "-c", "core.quotepath=false", "status", "--short", "--branch"])}
    (OUT / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in {"shell_syntax", "git_status"}}, ensure_ascii=False, indent=2))
    assert not author_changes and not result["outside_document_allowlist"]
    assert result["archive_unchanged"] and result["paper_unchanged"] and result["private_policy_unchanged"]
    assert not syntax_errors and all(c["exit_code"] == 0 for c in checks)
    assert probe["exit_code"] == 0 and result["git_diff_check"]["exit_code"] == 0


if __name__ == "__main__":
    main()
