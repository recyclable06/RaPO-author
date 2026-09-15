# CAND-RESUME-CIL-001 独立静态/CPU 验收报告

更新：2026-09-09。角色：独立验收。对象：整改工作树 `C:/Users/Administrator/.codex/worktrees/8ac5/RaPO-author` 的冻结源码、测试和补充归档；对照树为 `C:/Users/Administrator/.codex/worktrees/5ced/RaPO-author`。

## 裁决

`code/CPU verdict = FAIL_NOT_READY_FOR_GPU`。

整改快照的源码身份、AST、纯协议正例、缺件负例和 31 项 CPU 回归均有证据；但独立静态检查发现 fresh-process 边界发布仍有阻断缺陷，不能交给 GPU 两进程验收：

1. `--publish_task_boundary` 写出 Task 1 marker 后，production task loop 没有停止或返回，仍会在同一进程继续进入 Task 2。
2. 发布进程的 `resume_boundary` 为 `None`；默认 `save_task_ckpt=latest` 的后续 pruning 只保护 `resume_boundary` 不为空的 fresh-resume 分支，可能删除刚发布的 Task 1 checkpoint。
3. boundary validator 接受一个显式排除 `dataloader.pt` 的 checkpoint manifest，未满足冻结规格要求的 native full checkpoint artifact set。
4. model identity 只强制绝对路径加少量 metadata 或可选 revision，不强制不可变 revision 或完整 model-weight/content manifest。
5. source identity 只列 6 个 boundary 相关文件，不能等价绑定 native restore、optimizer/RNG 和 loader 所依赖的完整 production source。

因此 `fresh_process_resume=not_accepted`，不启动 GPU/SSH/训练，不关闭 finding。

## 身份与冻结检查

- 目标分支：`codex/remediate-cil-resume-001`；base HEAD：`da0c5ad521387bab75e74dc0bf0fd47dc13a3647`。
- 目标 `docs/remediation/CAND-RESUME-CIL-001/HASHES.json` SHA-256：`1dfbdc9efcdb853be12e5ab0ded6ffb0f6c4aabc23e811eca836c5de0b58e740`；声明文件全部匹配。
- production image CIL：`93,286` bytes，SHA-256 `23cbb3c01f69704eb304c2b9c884d8165a9783a913422d6e679e63bb42d71928`。
- 新增测试：`8,722` bytes，SHA-256 `a8b17b247eac0526108fbd7388af9b98946752bb8214d24229f00121bd200896`。
- 5ced 对照 `docs/INTEGRATION_HASHES.json` SHA-256：`6514f4dca401ffc805ae57031d1926f742e531ce0fbb981448315538ade8b0b1`。
- 整改补充索引 `SUPPLEMENT_HASHES.json` SHA-256：`3f560bec8b43990cd62f9560e43da1c4bd74d9a8eafbb0bc2c0ad3e177cd27d0`；实际 finding-only patch SHA-256：`4bf2d1ccb29ad8f7f4e11100efd4890902c7bf5688bd1743c5cf6bfbbd797af2`。

独立 probe 在 CPU 测试前后都观察到相同的 production/test/HASHES/integration hash；测试没有改动冻结源码、测试或原 `HASHES.json`。目标 Git 状态因 worktree ownership 被 Git safe-directory 拒绝读取，身份判断使用逐文件 hash，不依赖该状态。

## 独立方法与结果

[`independent_probe.py`](independent_probe.py) 使用 AST 读取 production source，只执行 boundary serializer/validator 的纯函数节点和小型真实文件 fixture；不导入训练入口，不创建 model，不启动 Ray/GPU，不修改目标树。

结果：

- 目标 manifest 声明的 11 个源码/测试文件全部匹配；production AST 解析通过。
- CLI 的 `--publish_task_boundary` / `--resume_task_boundary`、fresh branch、native restore→anchor copy 顺序、Task-2 cursor=0 检查、marker atomic-last 和正常 continuous `load_checkpoint_path=None` 静态存在。
- 生产序列化的有效小 fixture 可被 validator 接受；删除 checkpoint shard 的负例 fail closed。
- 独立构造一个去掉 `dataloader.pt`、同步刷新 manifest 和 state fingerprint 的 marker，validator 仍接受，直接复现 CIL-CPU-003。
- 独立 probe 退出码为 `2`，因为发现上述阻断项；probe stderr 为空。原始 probe stdout/exit/stderr 已归档。

## 逐项缺陷证据

### CIL-CPU-001：发布没有结束 Task 1 进程

在 `image_cls_cil_rapo.py:1648-1714`，`for task_idx, task_class_ids ...` 会继续枚举后续 task；`run_task` 调用只传入 `publish_task_boundary=(known_args.publish_task_boundary and task_id == 1)`，发布后没有 `break`、`return` 或显式 stop-after-boundary 分支。因此 FRESH-RESUME-01 所需的“进程 A 完成 Task 1、发布 marker、正常退出”没有 production entry。

### CIL-CPU-002：发布根没有被 pruning 保护

`image_cls_cil_rapo.py:1795-1823,1846-1856` 只在 `resume_boundary and _path_within(...)` 时阻止删除源 boundary。发布进程从 `resume_boundary=None` 开始；如果继续 Task 2，`previous_task_dir` 是 Task 1 目录，默认 `save_task_ckpt=latest` 会进入旧 checkpoint pruning，可能 `shutil.rmtree` `global_step_*`，使刚发布 marker 指向缺失 checkpoint。

### CIL-CPU-003：完整 checkpoint 要求不完整

`image_cls_cil_rapo.py:563-585` 的 validator 要求 optimizer 和 worker extra-state，但没有要求 `dataloader.pt`；`678-728` 的 publisher 也只检查 optimizer/extra-state。小 fixture 证明只要 manifest 与 fingerprint 同步更新，缺 `dataloader.pt` 仍可被视为 `complete`。虽然 Task 2 不应加载 Task 1 dataloader cursor，但冻结规格仍要求 boundary 绑定完整 native checkpoint artifact set。

### CIL-CPU-004/005：模型与 source 身份覆盖不足

`image_cls_cil_rapo.py:319-339` 在没有 revision 时只选择 `config.json`、`generation_config.json`、`tokenizer_config.json` 等 metadata；模型权重内容改变而路径和这些 metadata 不变时，boundary identity 仍可能相同。`82-89,270-283` 的 `_BOUNDARY_SOURCE_FILES` 只有 6 个文件，未覆盖完整 native restore、optimizer/RNG 和 loader 实现依赖。

## CPU 测试与 case coverage

独立运行命令、环境、hash 和原始流见 [`RUN_METADATA.md`](RUN_METADATA.md) 及对应 raw 文件。必要的 31 项组合命令 exit `0`，pytest 报告 `31 passed in 11.15s`；退出清理阶段另有 Windows `PermissionError`，已单独归档，不改变 pytest 的 31 项结果。

| 用例 | 独立覆盖 | 判定 |
| --- | --- | --- |
| CPU-RESUME-01 有效 boundary | production serializer/validator 小型真实文件 fixture | pass |
| CPU-RESUME-02 缺件/损坏 | model shard delete/append；独立 probe 复核缺件 | pass（覆盖有限） |
| CPU-RESUME-03 语义不一致 | cursor、model-only；未覆盖全部 step/tracker/EMA/RNG/identity 变体 | partial |
| CPU-RESUME-04 入口保护 | AST/static + 生产调用顺序 | fail，见 CIL-CPU-001/002 |
| REG-RESUME-01 | CTAN/COCO 25 项及新增 CIL 测试合计 31 项 | pass |
| REG-RESUME-02 | 同栈 2GPU continuous | 未执行，GPU 专用任务 |
| FRESH-RESUME-01/02/03 | 两个 OS process、native restore、首个真实 Task 2 update | 未执行 |
| STATE-EXACT-01 / TRAJECTORY-CLOSE-01 | 完整状态与短窗口轨迹 | 未接受/未执行 |

整改者补充归档的 `04_combined` 31-passed raw evidence 已核对身份，但本报告的裁决来自上述独立 probe 和独立一次 CPU 运行，不把整改者自测当作独立通过证明。

## GPU handoff 清单

只有修复并重新通过本 CPU/static gate 后，才可进入独立 GPU 任务：

1. 进程 A 使用显式 boundary publisher，Task 1 marker 发布后正常退出；验证 marker 最后发布且 source boundary 根保持只读。
2. 进程 B 使用新 output root 和新 runner/worker group，从 marker 校验后启动 Task 2；记录两进程身份差异。
3. 在首个 rollout 前验证 native actor/optimizer/scheduler/worker RNG、driver RNG、per-rank vLLM RNG 已恢复，且 actor restore 先于生产 `copy_actor_to_anchor()`。
4. 验证 Task 2 新 loader cursor=0、current/seen classes、restore event、首个真实 update、EMA increment 和新 checkpoint；不得以 `None`、preset-only、mock rollout 或直接 `load_weights` 代替。
5. 分别报告 `state-exact` 与 `trajectory-close`；不承诺逐 token/逐参数 bitwise equality。通过真实两个 OS process 后才能把 `fresh_process_resume` 改为 accepted。

## 范围与清理

本验收没有修改目标 production source、test 或原 `HASHES.json`，没有 GPU/SSH/install/训练/inference/commit/push。测试进程生成的两个目标 `.pyc` 文件不在冻结 manifest 中；尝试删除时受到 worktree sandbox 的 Windows access denied，未继续扩大权限，源码 hash 未变。

