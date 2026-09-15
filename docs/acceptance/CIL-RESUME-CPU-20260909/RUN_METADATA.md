# 独立 CIL resume CPU/static 验收运行记录

## 任务与范围

- 协调任务：`01a070af-8ee0-7641-b712-0cf59648e6ca`。
- 被验收整改任务：`01a08621-da6d-7aa2-bb09-86bcf96d0140`。
- 当前项目独立验收任务入口：`01a074b8-560b-7be1-8874-1f55a7e1ae10`（以主目录 `TASK_COORDINATION.md` 台账为准）。
- 目标：`C:\Users\Administrator\.codex\worktrees\8ac5\RaPO-author`，branch `codex/remediate-cil-resume-001`，base HEAD `da0c5ad521387bab75e74dc0bf0fd47dc13a3647`。
- 对照：`C:\Users\Administrator\.codex\worktrees\5ced\RaPO-author`，integration manifest SHA-256 `6514f4dca401ffc805ae57031d1926f742e531ce0fbb981448315538ade8b0b1`。
- 角色边界：只读验收；没有 GPU、SSH、安装、训练、推理、commit 或 push。

## Interpreter/environment

- Interpreter：`D:\anaconda3\envs\rapo-b01\python.exe`
- Python：`3.10.20`
- pytest：`8.4.2`
- PyTorch：`2.5.1+cpu`
- NumPy：`1.26.4`
- Platform：`win32`

## Commands and exits

独立 probe：

```text
D:\anaconda3\envs\rapo-b01\python.exe -B docs/acceptance/CIL-RESUME-CPU-20260909/independent_probe.py --root C:\Users\Administrator\.codex\worktrees\8ac5\RaPO-author --source-ref C:\Users\Administrator\.codex\worktrees\5ced\RaPO-author --integration-ref C:\Users\Administrator\.codex\worktrees\5ced\RaPO-author
```

- exit `2`：probe 按设计在发现 CIL-CPU-001～005 后返回 failure verdict。
- stdout：[`independent-probe.stdout.txt`](independent-probe.stdout.txt)
- stderr：[`independent-probe.stderr.txt`](independent-probe.stderr.txt)，为空。
- 结构化结果：[`independent-evidence.json`](independent-evidence.json)

独立 31 项 CPU 回归（本任务只执行一次）：

```text
D:\anaconda3\envs\rapo-b01\python.exe -B -m pytest tests/author_fixes/test_cil_resume.py tests/author_fixes/test_coco.py tests/author_fixes/test_ctan.py -p no:cacheprovider -v --tb=short
```

- exit `0`；pytest：`31 passed in 11.15s`。
- stdout：[`tests-31.stdout.txt`](tests-31.stdout.txt)
- stderr：[`tests-31.stderr.txt`](tests-31.stderr.txt)。pytest 测试已通过，但进程退出清理阶段出现 `PermissionError: [WinError 5]`，不影响 exit code 0；该输出未被隐藏。
- exit：[`tests-31.exit.txt`](tests-31.exit.txt)

## Source/test hash before and after CPU run

独立 probe 在 CPU 回归前完成一次身份核对；测试后再次读取相同路径。下列值前后相同：

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `examples/baselines/img_cls_cil/image_cls_cil_rapo.py` | 93286 | `23cbb3c01f69704eb304c2b9c884d8165a9783a913422d6e679e63bb42d71928` |
| `tests/author_fixes/test_cil_resume.py` | 8722 | `a8b17b247eac0526108fbd7388af9b98946752bb8214d24229f00121bd200896` |
| `docs/remediation/CAND-RESUME-CIL-001/HASHES.json` | 3372 | `1dfbdc9efcdb853be12e5ab0ded6ffb0f6c4aabc23e811eca836c5de0b58e740` |
| `5ced/docs/INTEGRATION_HASHES.json` | 8967 | `6514f4dca401ffc805ae57031d1926f742e531ce0fbb981448315538ade8b0b1` |

整改补充索引：`SUPPLEMENT_HASHES.json` SHA-256 `3f560bec8b43990cd62f9560e43da1c4bd74d9a8eafbb0bc2c0ad3e177cd27d0`。实际 finding-only patch：`CAND-RESUME-CIL-001-vs-5ced.patch` SHA-256 `4bf2d1ccb29ad8f7f4e11100efd4890902c7bf5688bd1743c5cf6bfbbd797af2`。

## Residue

测试运行生成/更新的 target `.pyc` 不在冻结 HASHES 清单；对两个本轮新增 `.pyc` 的删除尝试受到 worktree sandbox 的 Windows access denied，未扩大权限。生产 source、test 和原 HASHES 未改变。主验收目录中的文件清单和 hash 见 [`HASHES.json`](HASHES.json)。

