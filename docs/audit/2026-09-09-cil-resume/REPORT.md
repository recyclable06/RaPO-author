# CIL 任务边界恢复独立审查报告

日期：2026-09-09。角色：独立代码审查。对象：`CAND-RESUME-CIL-001`，范围冻结为图像 CIL 已完成 Task 1 边界到新进程 Task 2 起点；不承担整改或验收。

## 结论

`CAND-RESUME-CIL-001` 结论为 **confirmed operational gap / P2（不是论文算法 P1）**：当前整合线有可运行的同进程连续 CIL 路径，但没有受支持的“Task 1 完成后进程结束、全新进程从 Task 2 开始”的生产入口和完整状态协议。因此当前不能声称支持 fresh-process Task 1→Task 2 exact resume；这不阻断正常的同进程连续训练，也不据此推断论文算法或论文结果错误。

已有 GPU 证据只通过了有界的同进程路径：同一个 `PersistentRunner`、同一个 world-size-2 worker group 从 Task 1 global step 2 连续进入 Task 2，并延续 actor、optimizer/scheduler、anchor、CTAN/EMA 和 checkpoint。其独立验收明确保留 `CAND-RESUME-CIL-001`，没有把 `Task 2 load_checkpoint_path=None` 判为失败。

现有 native checkpoint manager 的覆盖是部分的：`save_model_only=false` 时每个 FSDP worker 保存 actor、optimizer、scheduler 和 worker 侧 CPU/CUDA/NumPy/Python RNG；trainer 另保存 `dataloader.pt` 和 `checkpoint_tracker.json`。但 CIL 的 `RayPPOContinualTrainer._load_checkpoint` 有意跳过 dataloader 恢复，且 native manager 不保存独立 previous-task anchor、EMA sidecar、任务游标/seen-class plan、配置/输入身份或 vLLM sharding manager 的 `gen_random_states` / `torch_random_states`。这些缺口在新进程 Task 2 边界上不能靠当前 tracker 或连续 worker 内存补齐。

## 输入身份与证据

目标只读代码树：`C:/Users/Administrator/.codex/worktrees/5ced/RaPO-author`，分支 `codex/integrate-accepted-fixes`，HEAD `da0c5ad521387bab75e74dc0bf0fd47dc13a3647`；作者基线 tag `author-drop-20260904` 为 `7fe2a73291f208ad9784a8333523825718881907`。目标工作树是未提交整合线，不把 `main` 当作目标源码。

关键目标源码当前 hash（审查前快照；审查后复核相同）如下：

| 文件 | SHA-256 |
| --- | --- |
| `examples/baselines/img_cls_cil/image_cls_cil_rapo.py` | `8a13974e3dfa7756a076844ce25ef6d66c71c29751fd2dec2f00a52b49092f3d` |
| `examples/baselines/_rapo_components.py` | `58499b6642943cd7b8360c39173dba266231516cd50e7c01d61a724054180155` |
| `verl/trainer/ray_trainer.py` | `54b9cb7fccc78513440ed05f9c53fe80c43bf86425ae6067ea4a7d41d25017ca` |
| `verl/utils/checkpoint/fsdp_checkpoint_manager.py` | `525fdef04dcc8aba2973407428dc6f600f064187625a892b7d39f205db199179` |
| `verl/utils/checkpoint/checkpoint_manager.py` | `af20ef83b0289591dbd1ccbd91c46dc4a4aadf0094bd6f89edfd743c39f4904f` |
| `verl/workers/sharding_manager/fsdp_vllm.py` | `0066978584494778b7396fb4ccd20dffef557ae6ad165db39967e472b5c02308` |

整合身份以目标 `docs/INTEGRATION_HASHES.json` 为准；该台账自身 SHA-256 为 `6514f4dca401ffc805ae57031d1926f742e531ce0fbb981448315538ade8b0b1`，6 个生产文件和 4 个测试文件身份均已逐字节匹配。静态诊断目录 `C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/cross-task-resume-20260909/` 的 `HASHES.json` 为 12 文件、自身 SHA-256 `0814e7fe716c112aac078fae45f2b5962f838e53a1d2043b237627caddf0aae8`；连续运行证据目录的 `HASHES.json` 为 45 文件、自身 SHA-256 `21e57f9d6c0432fbad0a7c8d11080251353d8f2f1b8ee6dc2b2d9f452490465f`。

复用但未改写的运行/验收证据：

- `C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/cross-task-resume-20260909/REPORT.md`，SHA-256 `483ebc6c2f2dec2976c8178186b754535ac7afbc76a5dd0bcfa123f9ad4764c4`；`static-results.json`，SHA-256 `133e00f4170ddce09abdb153a33207c820656dd0cf169782dfd75f18170356f8`；`RUNTIME_SUMMARY.json`，SHA-256 `f826bd19a7f15a1731d1663f9605a516937ce9d35c0d307abcc3b52aee37664d`。
- `C:/Users/Administrator/Desktop/RaPO-author/docs/acceptance/CONTINUOUS-TASK12-20260909/REPORT.md`，SHA-256 `de6f7879c155112614d1eaf1d4e56e41f9db140c0a0ec28e4e14153ab9a22e45`，结论为 `PASS_LIMITED_CONTINUOUS_RUNTIME_WITH_SCOPE_NOTES`。
- `C:/Users/Administrator/Desktop/RaPO-author/docs/acceptance/GPU-ONE-STEP-20260909/REPORT.md`，SHA-256 `87ceaab2f61cfdb5a1743e97df9dd7096c039269040efa0f4e1f1f9b8da9d2b7`；该报告保留实际写入 model-only checkpoint 的 scope exception。

两份新 checkpoint 仅按既有 manifest 使用容量和组成摘要：各 18 文件、各 `18,157,120,496` bytes，未下载权重。

## 生产调用链核验

### 正常 Task 1 与连续 Task 2

1. `main()` 解析配置后进入 `_run_cil()`；标准图像 launcher `scripts/image/10task.sh` 没有 resume/task-start 参数。
2. `_run_cil()` 在 `image_cls_cil_rapo.py:583–590` 给输出根追加时间戳，`686–702` 从 `task_idx=0` 遍历完整 `class_splits`，并为 Task 1 设置初始任务配置。它没有读取已完成任务记录，也没有从 Task 2 起点进入循环。
3. Task 1 在 `run_task()` 中把配置的 checkpoint path 传给 `PersistentCILTrainer.reinit_for_task()`；Task 1 的 `_load_checkpoint()` 调用父 CIL trainer，父实现再通过 worker checkpoint manager 恢复 actor/optimizer/scheduler/RNG。
4. Task 1 完成后，`_run_cil()` 从 tracker 得到 `last_checkpoint`，但连续 Task 2 的 `run_task()` 在 `image_cls_cil_rapo.py:454` 明确传 `load_checkpoint_path=... if task_id == 1 else None`。`reinit_for_task()` 在 `:261–266` 将 Task 2 的 disk path 清空，在 `:265` 设置 `_preset_global_step=last_global_step`；`PersistentCILTrainer._load_checkpoint()` 在 `:230–233` 只把 global step 设回去。
5. 该 `None` 分支依赖同一 `PersistentRunner` 内存中的 actor、optimizer、scheduler 和已初始化 worker；Task 2 前的 `copy_actor_to_anchor()` 是正常连续路径的 actor→anchor 操作。GPU continuous evidence 已验证这一分支的 actor 更新、optimizer/scheduler 连续、anchor freeze、EMA 2→4 递推和 Task 2 step 3–4。

因此，`Task2 load None` 在同进程连续设计中是预期行为；它同时说明该设计不能被当作新进程恢复入口。

### Native checkpoint 能力及缺口

`verl/trainer/ray_trainer.py:308–340` 的 `_save_checkpoint()` 调用 worker `save_checkpoint()`，保存 `dataloader.pt`，最后直接写 `checkpoint_tracker.json`。`:342–372` 的通用 loader 能读回 actor/critic、dataloader 和 global step；但图像 CIL 的 `RayPPOContinualTrainer._load_checkpoint()`（`examples/baselines/img_cls_cil/image_cls_cil.py:249–263`）故意只恢复 model/worker checkpoint，跳过 Task 1 dataloader，以免把旧任务耗尽游标带进新任务。

`verl/utils/checkpoint/fsdp_checkpoint_manager.py:61–119` 通过 `set_state_dict()` 恢复 actor/optimizer、scheduler 和 worker extra state；`extra_state` 的 `rng` 来自 `BaseCheckpointManager.get_rng_state()`（`verl/utils/checkpoint/checkpoint_manager.py:94–108`），包含当前 worker 的 torch CPU、当前 CUDA、NumPy 和 Python `random` 状态。这个能力仅表示 generic/native worker state path 存在，不表示 CIL fresh-process entry 已接通。

anchor 在 `PersistentRefFSDPWorker.init_anchor()` 中作为单独 FSDP module 创建，`copy_actor_to_anchor()` 仅在同一 worker 内存中执行；native manager 绑定的是 `self.fsdp_module`、optimizer 和 scheduler，不包含 `anchor_fsdp_module`。因此新进程必须先恢复 actor，再使用生产 copy 重建 previous-task anchor，不能在加载前从 base actor copy，也不必无理由再存一份完整 anchor 权重。

### 完成边界、评估与 RNG

当前 `PersistentRunner.run_task()`（`image_cls_cil_rapo.py:461–536`）的顺序是：

1. `trainer.fit()`；其 `RayPPOTrainer.fit()`（`ray_trainer.py:561–703`）在训练后先做内置 final validation，再调用 `_save_checkpoint()`。
2. 返回后在 `run_task():469–471` 保存根目录 `ema_online_stats.json`。
3. `run_task():481–507` 为 `extra_val_splits` 创建 overall-seen validation loader，并再次调用 `_validate()`。
4. `run_task():511–536` 读取 tracker 并返回 checkpoint path。

所以“`run_task` 保存/评估完成”的逻辑边界晚于 native checkpoint。额外 validation 经过 `generate_sequences()`；`FSDPVLLMShardingManager.load_vllm_and_sync_weights()` / `offload_vllm()` 在 `fsdp_vllm.py:189–216` 之间切换当前 CUDA RNG 与独立的 `gen_random_states`。现有 manager checkpoint 没有保存该独立生成状态；根 EMA sidecar 也通过 `_save_ema_state()` 的直接 `open(path, "w")` 写入，没有与 checkpoint 或 tracker 原子绑定。tracker 同样是直接写文件，没有完整 artifact/hash 校验。

整改边界必须把 `task1-complete` 定义在全部 post-training validation 完成之后，并在最终 marker 发布前重新使用 native manager 保存/刷新完整 checkpoint 状态，或以同等可审查的 post-validation RNG sidecar 补齐；不能把 fit 内部较早的 checkpoint 单独当成完整任务边界。

## 状态覆盖矩阵

| 状态 | 当前连续路径 | 新进程 Task 2 所需 | 当前结论 |
| --- | --- | --- | --- |
| actor | 同一 worker 内存连续；native checkpoint 有 shard | 先由 Task 1 checkpoint 恢复并校验 | generic 能力有，CIL fresh entry 无 |
| optimizer / scheduler | 同一对象连续；native manager 有保存/加载 | 从同一 checkpoint 恢复并校验 step/LR 状态 | 可复用 native manager |
| worker CPU/CUDA/NumPy/Python RNG | native `extra_state` 有 | preflight 检查每 rank extra state，恢复后校验 | 部分覆盖 |
| vLLM `gen_random_states` / `torch_random_states` | 只在 sharding manager 内存 | 需要 per-rank sidecar/API，且在首个 Task 2 rollout 前恢复 | 未覆盖 |
| driver RNG | checkpoint 不保存 driver state | 需要 driver state sidecar；至少覆盖 torch/NumPy/Python 与 DataLoader worker seed 前状态 | 未覆盖 |
| Task 1 dataloader cursor | generic checkpoint 有 `dataloader.pt`，CIL loader 恢复被跳过 | Task 2 必须重建新 loader，cursor=0，不继承 Task 1 | 设计上应跳过，协议未记录 |
| Task 2 sampler/worker seed | 每个 loader 使用 `config.seed` 建 local `torch.Generator`；DataLoader worker seed 还受 driver state影响 | 记录 seed/loader recipe，恢复 driver state 后构建新 Task 2 loader | 只有隐式配置，未绑定 |
| previous-task anchor | 同一 worker `copy_actor_to_anchor()` | actor disk restore 后再生产 copy 重建 | native checkpoint 不含 |
| EMA | 根目录 JSON sidecar，任务间连续 | marker 绑定精确 payload/hash，缺失或错 hash failclosed | 非原子、无入口 |
| next task / classplan / seen classes | `_run_cil()` 每次从 task 0 重建 | marker authoritative；Task 2 current/seen 需逐项匹配 | 未恢复 |
| config / input / base reference | snapshots/path 存在，但 tracker 不绑定 hash/revision | source/model/input/config hash 必须匹配；仅允许输出根变化 | 未恢复 |
| completion status | tracker 只有 best/last step/actor path | 原子 `task1-complete` marker 最后发布 | 未存在 |

## 不升级为 P1 的理由

本 finding 证明的是实现/运行能力缺失：标准论文描述和本地论文抽取中没有 exact-resume 或 checkpoint-restart 契约；缺失该运维能力不会改变 CTAN、retention、anchor reward 或 COCO 标签算法。它会使长时间图像 CIL 在 Task 1 完成后无法以受支持方式从 Task 2 继续，因而阻断“fresh-process exact resume 已支持”的声明，级别为 P2。只有发现恢复入口在标准论文实验中被声明为算法步骤，或恢复不一致直接改变已承诺的论文算法路径，才需要另行升级；当前没有这样的证据。

## 交付与下一步

可直接整改的 finding、最小规格、文件 allowlist 和 acceptance cases 分别见同目录 `FINDING.md`、`SPEC_DRAFT.md`、`ALLOWLIST.md`、`ACCEPTANCE_CASES.md`。本轮没有修改目标生产代码、输入、旧工程、checkpoint 或 GPU 运行证据；只在当前审查 worktree 写入本目录文档。`PROGRESS.md` 记录剩余边界，`HASHES.json` 保全本报告和输入身份。
