"""Read-only source inventory; writes evidence only beside this audit script."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
AUTHOR = ROOT / "RaPO_作者整理代码"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8").strip()


def main():
    destination = OUT / "intake-snapshot.json"
    if destination.exists():
        raise SystemExit("Initial snapshot already exists; do not overwrite it.")
    tracked = git("ls-files", "-z").split("\0")
    files = {}
    for name in tracked:
        path = ROOT / name
        if path.is_file():
            data = path.read_bytes()
            files[name] = {"bytes": len(data), "sha256": digest(data)}
    author_files = {}
    compile_errors = []
    imports = set()
    py_count = 0
    for path in sorted(AUTHOR.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        name = path.relative_to(AUTHOR).as_posix()
        author_files[name] = {"bytes": len(data), "sha256": digest(data)}
        if path.suffix == ".py":
            py_count += 1
            try:
                tree = ast.parse(data, filename=name)
                compile(tree, name, "exec")
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imports.update(a.name.split(".")[0] for a in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                        imports.add(node.module.split(".")[0])
            except Exception as exc:
                compile_errors.append({"path": name, "error": str(exc)})
    archive = ROOT / "RaPO_作者整理代码.zip"
    with zipfile.ZipFile(archive) as zf:
        zip_entries = {i.filename: digest(zf.read(i)) for i in zf.infolist() if not i.is_dir()}
    comparisons = []
    for name, sha in zip_entries.items():
        relative = name.split("/", 1)[1] if "/" in name else name
        record = author_files.get(relative)
        comparisons.append({"zip_path": name, "relative_path": relative,
                            "matches": bool(record and record["sha256"] == sha)})
    private_text = (ROOT / "实验室服务器使用规范.md").read_text(encoding="utf-8")
    before, after = private_text.split("RaPO 私有操作补充（2026-08-03）", 1)
    snapshot = {
        "head": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "status": git("-c", "core.quotepath=false", "status", "--short", "--branch"),
        "tracked_files": files,
        "paper_sha256": digest((ROOT / "2605.09640v1.pdf").read_bytes()),
        "archive_sha256": digest(archive.read_bytes()),
        "author_files": author_files,
        "archive_comparison": comparisons,
        "python_compile": {"count": py_count, "errors": compile_errors},
        "python_import_roots": sorted(imports),
        "private_policy": {"whole_sha256": digest((ROOT / "实验室服务器使用规范.md").read_bytes()),
                           "primary_text_sha256": digest(before.encode()),
                           "notes_text_sha256": digest(after.encode()),
                           "boundary": "RaPO 私有操作补充（2026-08-03）",
                           "content_published": False},
    }
    destination.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"head": snapshot["head"], "author_files": len(author_files),
                      "python_compile": snapshot["python_compile"], "archive_files": len(zip_entries),
                      "archive_mismatches": [c for c in comparisons if not c["matches"]],
                      "imports": sorted(imports)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
