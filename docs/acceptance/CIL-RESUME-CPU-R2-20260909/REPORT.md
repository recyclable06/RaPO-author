# CAND-RESUME-CIL-001 R2 独立 CPU/static 验收报告

日期：2026-09-09。角色：独立验收。对象：`C:/Users/Administrator/.codex/worktrees/8ac5/RaPO-author` R2 冻结快照；对照树：`C:/Users/Administrator/.codex/worktrees/5ced/RaPO-author`。

## 裁决

`code/CPU verdict = FAIL_NOT_READY_FOR_GPU`。

R2 的 full native checkpoint 合同、同大小本地模型内容身份、stop-after 入口和 source manifest 动态枚举均有新增测试或静态证据；但独立复核仍发现三个不能交给 GPU 的阻塞项：

1. `CIL-CPU-002` 的保护逻辑对已发布 boundary path **抛出异常**，而不是跳过保护路径。独立执行了生产 pruning 分支的精确 AST 节点：Task 1 有多个 checkpoint 时，在 `break` 之前抛出；不启用 stop、进入 Task 2 时，对已发布 Task 1 根的 previous-task pruning 也抛出。
2. `CIL-CPU-004` 的 producer 接受远端 40-hex revision，但 `ModelConfig` 没有 revision 字段，且 native `AutoConfig`、`AutoClass`、tokenizer、processor 和 vLLM loader 调用均未传入 revision；身份绑定的 revision 不是实际 loader 消费的 revision。
3. `CIL-CPU-005` 的 65 项 source manifest 遗漏实际运行时依赖：`verl/models/monkey_patch.py` 被 `fsdp_workers.py:42` 直接导入，`examples/reward_function/cls.py` 被 `examples/config.yaml:93` 配置并由 `workers/reward/function.py:117` 动态加载；二者均不在 manifest 中。

因此 `fresh_process_resume=not_accepted`，不启动 GPU/SSH/训练，也不关闭 finding。

## 身份冻结

- 目标 production image：99,349 bytes，SHA-256 `ba8a5da9341785178bd444112c4fc78dd352b52fe359b768218f4a4a6f5f7863`。
- 目标新增测试：14,217 bytes，SHA-256 `331e62782cc63ef9a2fb4d2de1afe921593f629309f263c6728a7de5299e3f64`。
- R2 `HASHES.json` SHA-256：`3c626bad55777ab9c9e217635bd9c81371fa40bf938eb3a66b221f51df81a43a`；其 8 个声明工件均逐项 bytes/hash 匹配。
- 5ced 对照 `docs/INTEGRATION_HASHES.json` SHA-256：`6514f4dca401ffc805ae57031d1926f742e531ce0fbb981448315538ade8b0b1`。
- R2 动态 source manifest：65 个文件，manifest SHA-256 `44f5dcd664c050d4c98bea29883ce7b77f8c3b039b41e19c661e4806f68258ae`。
- R2 目标 source/test hash 在回归前后均未变化；对照见 [`hash-start-end.json`](hash-start-end.json)。

## 独立方法与结果

[`independent_probe.py`](independent_probe.py) 只使用标准库读取目标源码，按 AST 提取并执行 production serializer/validator、model identity、source identity 及 pruning 分支；fixture 只写入当前主仓库验收目录下的临时目录，未导入训练入口、未启动 Ray/GPU。

协议 fixture 结果：

| 用例 | 结果 |
| --- | --- |
| world-size 2、每 rank model/optim/extra-state + `dataloader.pt` 的完整 checkpoint | pass |
| 删除 `dataloader.pt`，刷新 manifest 后 fail closed | pass |
| 删除 rank-1 optimizer，刷新 manifest 后 fail closed | pass |
| 同大小本地权重内容改变后 model identity 改变 | pass |

### CIL-CPU-002 的实际控制流复现

生产源码在 `1815-1817` 先登记发布 marker 根；当前任务 pruning 位于 `1899-1909`，previous-task pruning 位于 `1915-1922`，stop-after 的 `break` 位于 `1948-1954`。

独立 probe 将源码中这两个实际 `if` 节点提取为可执行 fixture，在临时目录创建 `task_1/global_step_1`、`task_1/global_step_2` 并把 `task_1` 作为 protected root。当前任务分支复现：

```text
refusing to prune a protected boundary path
```

随后以 `task_2/global_step_3` 和 `previous_task_dir=task_1` 执行 previous-task 分支，得到相同异常。也就是说，保护已生效，但实现把“受保护”表达成了 abort；在多个 Task-1 checkpoint 时无法到达正常 `break`，在继续 Task 2 的路径上也不能完成 pruning。

### CIL-CPU-004 的 producer/consumer 对照

`image_cls_cil_rapo.py:399-419` 会从 model config 读取 `revision`/`model_revision`，并允许 40-hex 值；独立 fixture 成功生成了带该 revision 的 remote identity。但 `verl/workers/actor/config.py:43-50` 的 `ModelConfig` 字段没有 revision。实际 consumer 的 AST 调用参数如下：

- `verl/workers/fsdp_workers.py:178` `AutoConfig.from_pretrained`：无 `revision`；
- `verl/workers/fsdp_workers.py:188` `GenerationConfig.from_pretrained`：无 `revision`；
- `verl/workers/fsdp_workers.py:211` `AutoClass.from_pretrained`：无 `revision`；
- `verl/utils/tokenizer.py:23,45` tokenizer/processor：无 `revision`；
- `verl/workers/rollout/vllm_rollout_spmd.py:114` `LLM`：无 `revision`。

因此远端分支尚未形成 producer→native consumer 的同一不可变身份闭包。local model directory 的完整流式 content manifest 及同大小内容变更测试本身通过，但不能替代远端分支缺口。

### CIL-CPU-005 的依赖闭包复核

R2 manifest 动态覆盖 6 个 root（65 项），但不包含 `verl/models`。`fsdp_workers.py:42` 直接使用 `from ..models.monkey_patch import apply_ulysses_patch`。同时，实际 image 配置在 `examples/config.yaml:93` 指向 `./examples/reward_function/cls.py:compute_score`，`verl/workers/reward/function.py:117` 通过 `spec_from_file_location` 动态载入该文件；`examples/reward_function/cls.py` 也不在 source manifest。数量“65”不能证明运行时 source identity 完整。

## CPU 回归

独立执行命令、环境、原始流和 exit 证据见 [`RUN_METADATA.md`](RUN_METADATA.md)：

```text
D:/anaconda3/envs/rapo-b01/python.exe -B -m pytest tests/author_fixes/test_cil_resume.py tests/author_fixes/test_coco.py tests/author_fixes/test_ctan.py -p no:cacheprovider -v --tb=short
```

结果为新增 CIL 12 项 + CTAN/COCO 25 项，共 **37 passed in 10.36s**，pytest exit code `0`。进程退出清理阶段另有 Windows `PermissionError (WinError 5)`，已归档到独立 stderr，不改变 pytest 37 项结果。

| 范围 | 独立覆盖 | 判定 |
| --- | --- | --- |
| CIL-CPU-001 stop-after | CLI 成对要求、loop break 与顺序静态检查 | partial；被 CIL-CPU-002 的 break 前异常阻断 |
| CIL-CPU-002 pruning | 两个真实生产 pruning 分支的临时目录执行 | fail |
| CIL-CPU-003 native full checkpoint | world-size/rank/dataloader 正负 fixture | pass |
| CIL-CPU-004 model identity | local content 正例 + remote producer/consumer 对照 | fail |
| CIL-CPU-005 source identity | 65 项 manifest 与实际 import/dynamic reward 依赖对照 | fail |
| CTAN/COCO regression | 25 项既有测试 | pass |
| FRESH-RESUME-01/02/03 | 两 OS process、native restore、Task-2 首次真实 update | 未执行 |
| STATE-EXACT / TRAJECTORY-CLOSE | GPU 状态和轨迹验收 | 未接受/未执行 |

## GPU 边界

只有修复并重新通过本 CPU/static gate 后，才可进入专用 GPU 任务：

1. 发布进程在多个 checkpoint 和默认 pruning 策略下完整结束，并保留 boundary 根而不以异常中止；
2. 确认 remote model revision 实际传入 native model/tokenizer/processor/vLLM loader，或仅使用已绑定完整内容的 local model；
3. 将 `verl/models`、动态 reward 文件及其他实际运行时 source/config 依赖纳入确定 manifest，并验证新增、删除、同路径内容变化均改变身份；
4. 再执行两个 OS process 的 world-size-2 native restore、driver/vLLM RNG 恢复、anchor 重建、Task-2 cursor=0、首个真实 update，以及 state-exact/trajectory-close 分开判定。

本轮没有修改目标 production source、test 或 R2 原始证据，没有 GPU/SSH/install/train/inference/commit/push。
