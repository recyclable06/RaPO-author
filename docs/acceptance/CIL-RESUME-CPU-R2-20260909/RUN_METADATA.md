# R2 独立 CPU/static 验收运行记录

## 身份

- target worktree：`C:/Users/Administrator/.codex/worktrees/8ac5/RaPO-author`
- target source：`examples/baselines/img_cls_cil/image_cls_cil_rapo.py`，99,349 bytes，SHA-256 `ba8a5da9341785178bd444112c4fc78dd352b52fe359b768218f4a4a6f5f7863`
- target test：`tests/author_fixes/test_cil_resume.py`，14,217 bytes，SHA-256 `331e62782cc63ef9a2fb4d2de1afe921593f629309f263c6728a7de5299e3f64`
- R2 manifest SHA-256：`3c626bad55777ab9c9e217635bd9c81371fa40bf938eb3a66b221f51df81a43a`
- Python：`D:/anaconda3/envs/rapo-b01/python.exe`，Python 3.10.20；pytest 8.4.2

## 独立 probe

命令：

```text
D:/anaconda3/envs/rapo-b01/python.exe -B docs/acceptance/CIL-RESUME-CPU-R2-20260909/independent_probe.py
```

环境：`PYTHONDONTWRITEBYTECODE=1`。probe 退出语义为 `2`（PowerShell `$LASTEXITCODE=2`），因为裁决为 `FAIL_NOT_READY_FOR_GPU`；完整 stdout、stderr、exit 已分别归档。

Probe 使用标准库 AST 提取目标源码中的真实函数/控制流节点，并在主仓库验收目录下建立临时 fixture；不导入训练入口，不启动 Ray/GPU，不修改目标树。临时目录在 probe 结束时清理。

## CPU 回归

命令：

```text
D:/anaconda3/envs/rapo-b01/python.exe -B -m pytest tests/author_fixes/test_cil_resume.py tests/author_fixes/test_coco.py tests/author_fixes/test_ctan.py -p no:cacheprovider -v --tb=short
```

环境：`PYTHONDONTWRITEBYTECODE=1`，`-B`，`-p no:cacheprovider`，工作目录为目标 R2 worktree。结果：`37 passed in 10.36s`，process/pytest exit `0`。退出清理阶段 stderr 记录了 Windows `PermissionError (WinError 5)`，不影响已完成的 37 项测试；未扩大权限，未删除目标原有文件。

原始文件：

- [`tests-37.stdout.txt`](tests-37.stdout.txt)
- [`tests-37.stderr.txt`](tests-37.stderr.txt)
- [`tests-37.exit.txt`](tests-37.exit.txt)

## Hash 前后

回归前 probe 和回归后 probe 均观察到相同 source/test bytes 与 SHA-256；详见 [`hash-start-end.json`](hash-start-end.json)。没有修改目标 production source、test、R2 manifest 或 R2 raw evidence。

## 范围排除

本轮未执行 GPU、SSH、依赖安装、训练、推理、commit 或 push；未把 CPU fixture 当作 native two-process resume、state-exact、trajectory-close 或 paper-scale 结果。
