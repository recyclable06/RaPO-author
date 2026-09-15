# CAND-RESUME-CIL-001 整改进度

更新：2026-09-09。独立整改分支：`codex/remediate-cil-resume-001`。

## 已完成

- 核验冻结决定、allowlist、验收用例、整合 manifest 和只读审查身份。
- 从 5ced 原样初始化 6 个已验收生产/配置文件与 4 个既有测试；保存初始化 hash 证据。
- 在唯一允许生产文件 `examples/baselines/img_cls_cil/image_cls_cil_rapo.py` 增加显式 `--publish_task_boundary` 与 `--resume_task_boundary`。
- 增加 `task1-complete.json` 的原子最后发布、完整 checkpoint 文件 manifest、tracker/global-step 交叉校验、EMA/driver/vLLM RNG sidecar 和 source/model/input/config/classplan 身份校验。
- 增加图像 worker 的最小 per-rank vLLM RNG capture/restore RPC；未改通用 trainer/checkpoint/sharding、检测或视频路径。
- fresh Task 2 分支先 native restore actor/optimizer/scheduler/worker RNG，再恢复 vLLM RNG，随后通过生产 `copy_actor_to_anchor()`，再写 restore event 和启动训练；正常 continuous Task 2 仍为 preset/in-memory `load_checkpoint_path=None`。
- 新增 CPU 真实文件 fixture 测试：有效边界、缺件/损坏、cursor 语义、model-only 和分支顺序 fail-closed。
- `py_compile` 通过；新增 6 项协议测试通过；既有 CTAN/COCO 25 项通过；合计 31 项通过；`git diff --check` 通过。

## 当前结论

`ready_for_independent_acceptance`。本结论只表示源码与 CPU 协议证据已交付，不表示 fresh-process GPU accepted，也不关闭 finding。

## 未验证/后续边界

- 未执行 SSH、GPU、训练、推理或真实两个 OS process 的 Task 1→Task 2 运行。
- 未证明 native actor/optimizer/scheduler、真实 driver/vLLM RNG、anchor fingerprint 和 Task 2 首步在目标 GPU 栈上的轨迹；这些留给独立验收/GPU 任务。
- 按冻结决定，本轮不要求 `task2-complete` 或 Task 3 恢复 marker。
- 未 commit/push；未删除或移动任何旧资产。
