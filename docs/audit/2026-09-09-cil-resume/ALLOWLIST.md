# CAND-RESUME-CIL-001 整改文件 allowlist

本 allowlist 只覆盖图像 CIL 已完成 Task 1→Task 2 fresh-process 边界。它不是对其他 finding 或其他任务类型的授权。

## 允许修改的生产文件

| 文件 | 必要改动 | 明确不应改动 |
| --- | --- | --- |
| `examples/baselines/img_cls_cil/image_cls_cil_rapo.py` | 新增显式 boundary-resume CLI/entry；读取并 fail-closed 校验 completion record；从 record 选择 `next_task` 与 classplan；为 task2 fresh 分支显式 native disk restore；恢复后再 `copy_actor_to_anchor()`；保留 continuous 分支的 in-memory `None` 语义；在所有 post-training validation 后刷新/绑定 native checkpoint、EMA、driver/vLLM RNG 与原子 completion marker；在图像侧 `PersistentRefFSDPWorker` 暴露/恢复 sharding RNG 的最小生产 RPC；防止 fresh resume pruning 旧 boundary 根。 | 不改 CTAN/retention 数值、hook 顺序、COCO label policy、det/video runner；不增加中间 batch 容错；不把 base actor 当 anchor；不把 marker 逻辑隐式塞进通用 trainer。 |

这是唯一必须的生产文件。图像文件已有 `PersistentRefFSDPWorker` 子类，可在该文件中增加受控的 per-rank `gen_random_states` / `torch_random_states` capture/restore API，从而不扩大共享 `fsdp_vllm.py` 的影响面。

## 允许新增的测试文件

| 文件 | 必要内容 |
| --- | --- |
| `tests/author_fixes/test_cil_resume.py` | 真实生产源码的 CPU/static 协议检查：marker schema/hash、step/plan/config/input 校验、missing/corrupt/model-only failclosed、Task 2 fresh-loader policy、restore-before-anchor 顺序、normal continuous guard。不得 mock 被测生产逻辑、跳过断言、删除既有测试或弱化已有断言。 |

该文件可使用临时小型 metadata/artifact fixtures 验证协议解析；它不能把一个伪造的 actor 或伪造 checkpoint 当作“训练恢复通过”。真实 actor/optimizer/scheduler/EMA/RNG 和两个进程的 GPU 验收必须走生产入口，见 `ACCEPTANCE_CASES.md`。

## 只读输入/回归约束

以下文件可被读取和测试，但本 finding 不允许修改：

- `examples/baselines/_rapo_components.py`
- `examples/baselines/img_cls_cil/image_cls_cil.py`
- `examples/baselines/cil_det/*`
- `examples/baselines/video_cls_cil/*`
- `verl/trainer/ray_trainer.py`
- `verl/trainer/data_loader.py`
- `verl/utils/checkpoint/checkpoint_manager.py`
- `verl/utils/checkpoint/fsdp_checkpoint_manager.py`
- `verl/workers/fsdp_workers.py`
- `verl/workers/sharding_manager/fsdp_vllm.py`
- `scripts/image/*`、`scripts/video/*`、`scripts/det/*`
- `data/`、`verl/` 其他文件、`examples/reward_function/`、`docs/BASELINE.json` 和原始审计/验收证据。

如实现发现必须修改上述共享文件，当前 finding 不自动扩大 allowlist；先保留已完成的图像侧可审查结果，向协调者提交具体文件、符号、影响及回归范围后再决定。不得为了方便把恢复协议推广到视频/检测或通用 trainer。

## 允许产生的运行工件

生产运行可以在新、用户明确指定的输出根写入 `task1-complete.json`、checkpoint manifest、EMA/RNG sidecar、restore event 和 Task 2 输出。旧 boundary 根只读；不得删除、移动、覆盖 legacy 或既有证据。审查工件只能写当前 worktree 的 `docs/audit/2026-09-09-cil-resume/`。

## 必须保持的现有门禁

实现后必须重新跑现有 `tests/author_fixes/test_coco.py` 和 `test_ctan.py`（当前整合回归为 25 passed），并证明正常 continuous Task 2 仍走内存路径。任何依赖 `save_model_only=true`、旧 checkpoint、Task 1–6 legacy artifact、mock subject、删除测试或弱化 assertion 的“通过”都不属于本 allowlist。
