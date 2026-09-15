# 同进程连续 Task 1→Task 2 独立验收进度

更新：2026-09-09。

## 当前裁决

`PASS_LIMITED_CONTINUOUS_RUNTIME_WITH_SCOPE_NOTES`。

同一 production `PersistentRunner` 和同一 world-size-2 worker group 连续完成 Task 1→Task 2 的有界运行证据。Task 1 结束于 global step 2，Task 2 从 step 2 延续到 step 4；actor/anchor、CTAN、EMA、optimizer/scheduler、checkpoint 和生产调用链检查均通过。

这不是跨进程 exact resume 证据。`CAND-RESUME-CIL-001` 保持开放，阶段 5 仍未通过。

## 已完成

- 独立解析固定的 rejudged runtime result、Task 1/Task 2 raw records、production retention log、EMA sidecar、checkpoint manifest 和 postflight 资源记录。
- 核对运行 source entry、diagnostic config、input manifest、model token 和集成源码清单身份；10 个集成 key file hash 全部匹配。
- 核对同一 runner PID、同一 worker group、Task boundary global steps 和 Task 2 的 in-memory continuation 分支。
- 核对物理 GPU 4/6、CUDA-visible device、Ray GPU ID 和 UUID 映射；记录 optional pre-model mapping 属性缺失。
- 核对 Task 1/2 actor 更新、边界连续性、Task 2 anchor copy/freeze、4 个 CTAN advantage calls、group reward variation、finite/nonzero advantages。
- 用 production `experiment_log.jsonl` 重算 retention 聚合：step 3 为 `4.0`，step 4 为 `3.837252140045166`，均与记录精确一致；保留直接 tensor 字段缺失的 scope note。
- 核对 EMA `2 → reinit 2 → 4`、递推 payload、sidecar，以及两个 rank 的 optimizer/scheduler 对象和状态连续性。
- 核对 Task 1/2 checkpoint manifest：各 18 个文件、各 `18,157,120,496` bytes，必要 payload 和 tracker step 均存在。
- 起止复核目标诊断 12 个文件和固定运行证据 45 个文件，manifest hash 与逐文件结果保持不变。

## 证据入口

- [`independent_probe.py`](independent_probe.py)：只读独立验收探针。
- [`independent-evidence.json`](independent-evidence.json)：独立 gates、身份、逐项 scope note 和 raw evidence 索引。
- [`hash-start-end-compare.json`](hash-start-end-compare.json)：目标诊断和运行证据的起止 manifest 对照。
- 目标诊断目录：`C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\diagnostics\cross-task-resume-20260909`。
- 固定运行证据目录：`C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\diagnostics\continuous-runtime-evidence-20260909`。

## 未完成 / 不得宣称

- 没有跨进程 Task 1→Task 2 恢复入口、task cursor/seen-class plan、anchor/EMA/checkpoint coupling、RNG 和数据游标协议的证据。
- 没有 standalone shell exitcode、stdout、stderr 和 Ray shutdown 归档；cleanup 只能标为 limited。
- 没有全参数 actor/anchor equality 证明，也没有 retention 逐样本 tensor formula 证据。
- 不得把本轮结果写成 paper-scale training、COCO AP、原始实验身份或正式 reproduction pass。

下一步只应在取得对应的跨进程运行与独立验收范围后，另行验证 `CAND-RESUME-CIL-001`；本进度不授权 GPU 重跑、源码修复、删除证据或正式训练。

