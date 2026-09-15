# CAND-RESUME-CIL-001 测试原始证据

工作目录：`C:/Users/Administrator/.codex/worktrees/8ac5/RaPO-author`

## Environment

```text
interpreter: D:/anaconda3/envs/rapo-b01/python.exe
Python: 3.10.20
pytest: 8.4.2
platform: win32
```

## Commands and raw result

### Syntax

```text
$ python -m py_compile examples/baselines/img_cls_cil/image_cls_cil_rapo.py tests/author_fixes/test_cil_resume.py
py_compile: PASS
exit=0
```

### New CPU protocol

```text
$ D:/anaconda3/envs/rapo-b01/python.exe -m pytest tests/author_fixes/test_cil_resume.py -p no:cacheprovider -v --tb=short
============================= test session starts =============================
platform win32 -- Python 3.10.20, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\Administrator\.codex\worktrees\8ac5\RaPO-author
collected 6 items
......                                                                   [100%]
============================== 6 passed in 21.80s ==============================
exit=0
```

### Existing CTAN/COCO regression

```text
$ D:/anaconda3/envs/rapo-b01/python.exe -B -m pytest tests/author_fixes/test_coco.py tests/author_fixes/test_ctan.py -p no:cacheprovider -v --tb=short
collected 25 items
.................................                                        [100%]
============================= 25 passed in 18.36s =============================
exit=0
```

### Combined rerun

```text
$ python -m py_compile examples/baselines/img_cls_cil/image_cls_cil_rapo.py tests/author_fixes/test_cil_resume.py
py_compile: PASS
$ D:/anaconda3/envs/rapo-b01/python.exe -m pytest tests/author_fixes/test_cil_resume.py tests/author_fixes/test_coco.py tests/author_fixes/test_ctan.py -p no:cacheprovider -q
........................                                         [100%]
31 passed in 8.31s
exit=0
```

The final combined command above was executed after the last production edit.

### Diff check

```text
$ git diff --check
stdout: <empty>
stderr: <empty>
exit=0
```

The fixture tests create real temporary checkpoint, tracker, EMA and RNG files, publish them through the production serializer, then validate their byte/hash manifests. They do not create an actor model, run rollout, or claim native restore evidence.
