"""Read-only source checks; write verification evidence in this directory."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE = "7fe2a73291f208ad9784a8333523825718881907"
HEAD = "da0c5ad521387bab75e74dc0bf0fd47dc13a3647"
PRODUCTION = ["examples/baselines/_rapo_components.py",
              "examples/baselines/img_cls_cil/image_cls_cil_rapo.py",
              "examples/baselines/cil_det/image_det_cil_rapo.py",
              *[f"scripts/{x}/rapo_cfg.json" for x in ("image", "video", "det")]]
commands = []


def run(args):
    p = subprocess.run(args, cwd=ROOT, capture_output=True)
    commands.append(dict(command=args, exit_code=p.returncode,
                         stdout=p.stdout.decode("utf-8", errors="replace"),
                         stderr=p.stderr.decode("utf-8", errors="replace")))
    assert p.returncode == 0, commands[-1]
    return p.stdout


def git(*args):
    return run(["git", *args]).decode("utf-8").strip()


def tree_hashes(ref):
    entries = git("ls-tree", "-r", ref).splitlines()
    objects = [(line.split()[2], line.split("\t", 1)[1]) for line in entries]
    p = subprocess.run(["git", "cat-file", "--batch"], cwd=ROOT,
                       input=("\n".join(x[0] for x in objects) + "\n").encode(), capture_output=True)
    assert p.returncode == 0
    pos = 0
    result = {}
    for oid, path in objects:
        end = p.stdout.index(b"\n", pos)
        header = p.stdout[pos:end].split()
        assert header[0].decode() == oid and header[1] == b"blob"
        size = int(header[2])
        start = end + 1
        result[path] = hashlib.sha256(p.stdout[start:start + size]).hexdigest()
        pos = start + size + 1
    return result


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert git("rev-parse", "HEAD") == HEAD
assert git("rev-parse", "author-drop-20260904^{commit}") == BASE
assert git("branch", "--show-current") == "codex/auth-ctan-001"
tag_object = git("rev-parse", "author-drop-20260904")
baseline = tree_hashes(BASE)
head = tree_hashes(HEAD)
assert len(baseline) == 204
baseline_changes = [p for p, value in baseline.items() if sha(ROOT / p) != value]
head_changes = [p for p, value in head.items() if sha(ROOT / p) != value]
preexisting_governance = [p for p, value in baseline.items() if head[p] != value]
assert set(preexisting_governance) == {".gitignore", "README.md"}
assert set(baseline_changes) == set(PRODUCTION + preexisting_governance), baseline_changes
assert set(head_changes) == set(PRODUCTION), head_changes
untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
assert all(p.startswith(("tests/author_fixes/", "docs/remediation/AUTH-CTAN-001/")) for p in untracked)
git("diff", "--check")
syntax = []
for path in [ROOT / p for p in PRODUCTION if p.endswith(".py")] + sorted((ROOT / "tests/author_fixes").glob("*.py")) + [Path(__file__)]:
    compile(path.read_bytes(), str(path), "exec")
    syntax.append(path.relative_to(ROOT).as_posix())
shells = sorted((ROOT / "scripts").glob("*/*.sh"))
assert len(shells) == 6
for path in shells:
    run(["D:/Git/bin/bash.exe", "-n", path.relative_to(ROOT).as_posix()])
    source = path.read_text(encoding="utf-8")
    assert 'RAPO_CFG=${RAPO_CFG:-"$SCRIPT_DIR/rapo_cfg.json"}' in source
    assert '--cil_cfg "$RAPO_CFG"' in source

# Static source connections are recorded separately from CPU execution.
static = {}
needles = {
    PRODUCTION[0]: ["ray_trainer_module.compute_advantage = self._compute_advantage_with_hooks",
        "return self.ema_adv.compute_grpo_advantage(data)", "data, dm = _apply_retention_reward(data, self.retention_cfg)",
        "ray_trainer_module.compute_advantage = self._orig_compute_advantage"],
    PRODUCTION[1]: ["ema_initial_state = _load_ema_state(ema_state_path)", "ema_adv_state=ema_initial_state,",
        "initial_state=ema_adv_state,", "_save_ema_state(ema_state_path, ema_payload, task_id=task_id)",
        "if task_id < ref_cfg.activate_from_task:"],
    PRODUCTION[2]: ["ema_initial_state = _load_ema_state(ema_state_path)", "ema_adv_state=ema_initial_state,",
        "initial_state=ema_adv_state,", "_save_ema_state(ema_state_path, ema_payload, task_id=task_id)",
        "if task_id < ref_cfg.activate_from_task:"],
    "examples/baselines/video_cls_cil/video_cls_cil_rapo.py": ["image_cil_rapo.main()"],
    "verl/trainer/ray_trainer.py": ["batch = compute_advantage(", "actor_output = self.actor_rollout_ref_wg.update_actor(batch)"],
    "verl/workers/actor/dp_actor.py": ['advantages = model_inputs["advantages"]', 'advantages=advantages,'],
}
for path, patterns in needles.items():
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    static[path] = {}
    for pattern in patterns:
        found = [i + 1 for i, line in enumerate(lines) if pattern in line]
        assert found, (path, pattern)
        static[path][pattern] = found
    static[path]["sha256"] = sha(ROOT / path)

red = json.loads((OUT / "red-confirmed.json").read_text())
green = json.loads((OUT / "green.json").read_text())
assert red["exit_code"] == 1 and green["exit_code"] == 0
for path in (ROOT / "tests/author_fixes").glob("*.py"):
    rel = path.relative_to(ROOT).as_posix()
    assert red["source_sha256"][rel] == green["source_sha256"][rel] == sha(path)
for path in PRODUCTION:
    assert red["source_sha256"][path] == baseline[path]
    assert green["source_sha256"][path] == sha(ROOT / path)
patch = run(["git", "diff", "--binary", "author-drop-20260904", "--", *PRODUCTION])
(OUT / "production.patch").write_bytes(patch)
test_patch = ""
for p in sorted((ROOT / "tests/author_fixes").glob("*.py")):
    test_patch += "".join(difflib.unified_diff([], p.read_text(encoding="utf-8").splitlines(keepends=True),
                                               fromfile="/dev/null", tofile=p.relative_to(ROOT).as_posix()))
(OUT / "tests.patch").write_text(test_patch, encoding="utf-8", newline="")
main_root = "C:/Users/Administrator/Desktop/RaPO-author"
assert git("-C", main_root, "diff", "--name-only", "HEAD") == ""
main_status = git("-C", main_root, "status", "--short", "--branch")
main_pdf_hash = sha(Path(main_root) / "2605.09640v1.pdf")
assert main_pdf_hash == json.loads((ROOT / "docs/BASELINE.json").read_text(encoding="utf-8"))["paper_sha256"]
report = dict(worktree=str(ROOT), branch="codex/auth-ctan-001", base_head=HEAD,
              baseline_commit=BASE, annotated_tag_object=tag_object, baseline_file_count=len(baseline),
              baseline_unchanged_count=len(baseline) - len(baseline_changes),
              production_changes=head_changes, head_changes=head_changes, untracked=untracked,
              preexisting_governance_changes=preexisting_governance,
              baseline_sha256=baseline, python_syntax=syntax, shell_count=len(shells),
              static_connections=static, red_green_test_sources_identical=True,
              main_worktree_status=main_status, main_root_pdf_sha256=main_pdf_hash,
              commands=commands, result="PASS: local scope/syntax/preservation only")
(OUT / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({k: report[k] for k in ("result", "baseline_file_count", "baseline_unchanged_count", "production_changes", "python_syntax", "shell_count")}, indent=2))
