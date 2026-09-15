# Finding：CAND-RESUME-CIL-001

## 裁决

- 状态：`confirmed operational gap`（静态源码证据充分；fresh-process GPU 运行尚未执行）。
- 严重度：`P2`，仅针对图像 CIL 已完成任务边界的运行恢复能力。
- 不是：论文算法 P1、CTAN/COCO finding、同进程连续路径故障、任意中间 batch 容错 finding。

## 具名问题

图像 CIL 只有从 task 0 开始的标准 `_run_cil()` 入口和同一 `PersistentRunner` 的内存续跑分支，没有一个受支持的生产入口能够在 Task 1 完成、进程终止后，于新进程中选择并校验 Task 1 完成 checkpoint，恢复 actor/optimizer/scheduler/RNG/EMA/任务计划，并从 Task 2 新 dataloader 起点开始训练。

## 直接证据

1. `C:/Users/Administrator/.codex/worktrees/5ced/RaPO-author/examples/baselines/img_cls_cil/image_cls_cil_rapo.py:686–702` 从 `task_idx=0` 遍历全部 `class_splits`，没有 `start_task`、completed-boundary record 或 fresh-process resume 参数；`:583–590` 还为每次启动追加新的时间戳输出根。
2. 同文件 `:224–235` 的 `PersistentCILTrainer._load_checkpoint()` 在 `_preset_global_step` 存在时只恢复 global step；`:259–266` 对 task 2+ 清空 disk load path 并设置 preset step。
3. 同文件 `:454` 明确传入 `load_checkpoint_path=config.trainer.load_checkpoint_path if task_id == 1 else None`。这解释了 continuous runtime 中 Task 2 的 `None` 是正常内存设计，也证明它不是新进程加载入口。
4. `C:/Users/Administrator/.codex/worktrees/5ced/RaPO-author/verl/trainer/ray_trainer.py:308–372` 的 generic checkpoint 只由 actor/critic native worker checkpoint、`dataloader.pt` 和 tracker 组成；tracker 只有 `best_global_step`、`last_global_step`、`last_actor_path`。
5. `C:/Users/Administrator/.codex/worktrees/5ced/RaPO-author/examples/baselines/img_cls_cil/image_cls_cil.py:249–263` 的 CIL loader 只加载 model/worker checkpoint，故意不加载 dataloader cursor。Task 2 应当新建 loader，但当前没有完成边界协议来告诉新进程这样做并绑定其 class plan。
6. `C:/Users/Administrator/.codex/worktrees/5ced/RaPO-author/examples/baselines/_rapo_components.py:615–676` 的 EMA 通过 run parent JSON sidecar 保存/读取；`:672` 的文件写入没有 atomic replace 或 checkpoint hash 绑定。`FSDPCheckpointManager` 不保存 anchor module。
7. `C:/Users/Administrator/.codex/worktrees/5ced/RaPO-author/verl/workers/sharding_manager/fsdp_vllm.py:68–74,189–216` 的 `gen_random_states` / `torch_random_states` 是 sharding manager 内存属性，当前没有 checkpoint serialization path。

## 影响

在 Task 1 已完成但进程被终止的现实场景，新进程不能仅用现有标准 launcher 从 Task 2 开始。把 Task 1 checkpoint 作为普通 `trainer.load_checkpoint_path` 传入会仍然进入 task 0/task 1 循环；把它机械传入现有 task 2 branch 又会被清空，不能在 anchor copy 前恢复 actor。即使手工拼接路径，EMA、anchor、classplan、输入/配置身份和 vLLM/driver RNG 也没有一个原子完成记录可校验。

这会阻断 fresh-process exact-resume 的可复现性和昂贵任务的安全续跑，但不改变正常 continuous path 的训练语义。已有同进程 GPU 证据：

`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/cross-task-resume-20260909/REPORT.md` 明确为 `pass_limited_continuous_runtime`；其独立验收 `C:/Users/Administrator/Desktop/RaPO-author/docs/acceptance/CONTINUOUS-TASK12-20260909/REPORT.md` 明确写出跨进程 exact resume 未证明且 finding 仍开放。

## 根因分层

- 入口层：没有 `completed_task → next_task` 选择与校验。
- 恢复顺序层：现有 Task 2 branch 以 preset global step 代替 native load；anchor copy 位于 `run_task()` 早于 trainer reinit/fit，fresh process 若照搬会从 base actor 建 anchor。
- 状态协议层：native manager 没有 anchor/EMA/classplan/config/input/vLLM RNG/driver RNG 的完整原子绑定。
- 数据语义层：Task 2 需要新 loader、cursor=0；不能把 Task 1 `dataloader.pt` 当作 Task 2 游标，但这一 policy 没有被完成记录和 fresh entry 显式表达。
- 发布层：tracker、EMA sidecar 与 checkpoint 没有最后发布的 fail-closed completion marker。

## 最小关闭条件

只有在不修改论文算法系数和正常连续路径的前提下，完成以下条件后才可将 finding 标为 independently accepted：

1. 新进程 CLI/production `_run_cil` 能读取唯一的 `task1-complete` record，验证 source/model/input/config/classplan 与完整 checkpoint manifest，缺件、错 hash、step/任务不一致立即退出。
2. 新进程先用 native manager 恢复 Task 1 actor、optimizer、scheduler 和 worker RNG，再通过生产 `copy_actor_to_anchor()` 重建 previous-task anchor；不从 base actor copy，不保存无必要的完整重复 anchor。
3. EMA payload/hash、driver RNG、vLLM per-rank generation RNG 与 completion record 绑定；marker 在所有 artifact 校验完成后原子发布。
4. Task 2 使用 record 指定的 current/seen classes 和新建 dataloader，cursor 从 0 开始，不加载 Task 1 dataloader state；global step 从 Task 1 末值延续。
5. CPU 正负例、既有 25 项 CTAN/COCO regression、同栈 2GPU continuous regression 和真正两个进程的 Task 1→Task 2 acceptance 全部通过。

## 明确排除

本 finding 不要求中间 batch/任意时刻抢占恢复、不要求通用容错框架、不扩展到视频/检测、不改变 CTAN/COCO 已验收字节、不承诺非确定 CUDA kernel 下逐 token bitwise 相同。
