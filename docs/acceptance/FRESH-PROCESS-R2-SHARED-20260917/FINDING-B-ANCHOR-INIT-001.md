# FINDING-B-ANCHOR-INIT-001

状态：`OPEN — internal abort cause unresolved`  
范围：Fresh-process R2 leg B；仅基于共享原件与 frozen source review。

## 判定

B 不是“从未构造模型/训练未开始”的已证事实。B 已完成模型、FSDP、vLLM 与 persistent worker 初始化；两个 FSDP worker 都进入 `PersistentRefFSDPWorker.init_anchor`，但都没有 `after`。在当前 observer 覆盖范围内，没有进入 Task 2 `run_task`、native checkpoint load/restore、vLLM boundary restore 或 `fit`。

## 证据

- `evidence/B-root/process-end.json`：PID 1153372，`exit_code=-6`，child end `2026-09-17 00:17:44.816206+08:00`。
- `evidence/B-root/process.stdout.log:148-171`：HuggingFace/FSDP/vLLM/persistent worker 初始化输出。
- `evidence/B-observer-events/events-1161595.jsonl`：`PersistentRefFSDPWorker.init_anchor` before，rank 0，PID 1161595，无 after。
- `evidence/B-observer-events/events-1162100.jsonl`：`PersistentRefFSDPWorker.init_anchor` before，rank 1，PID 1162100，无 after。
- `evidence/B-observer-events`：实际 `PersistentRunner.run_task`、`PersistentCILTrainer._load_checkpoint`、`PersistentCILTrainer.restore_boundary_checkpoint`、`FSDPCheckpointManager.load_checkpoint`、`PersistentCILTrainer.fit` 均为 0。
- `evidence/B-supervisor/timeline.log`：child 已于 deadline 前退出；`child_term_sent=0`、`child_kill_sent=0`。
- `evidence/B-root/process.stderr.log:25`：无 owner/PID 的 aggregated `SIGTERM` 行，不能归因给 supervisor；Raylet/dashboard 的 SIGTERM 更晚，属于后续清理候选。

## 根因边界

`run_v9.py:232` 将 `model_constructed` 与 `training_started` 写成 `process.returncode == 0`，所以 B `run-result.json` 的两个 false 是派生状态，不是阶段观测。`image_cls_cil_rapo.py:1789-1796` 规定 anchor worker init 先于 driver RNG restore；`run_task` 的 native restore 与 fit 还要更晚。因此现有证据足以定位阶段，但不足以确定 signal 6 的内部原因。

## 最小补证

只请求源端 PID 1161595（rank 0）与 PID 1162100（rank 1）的 Ray worker stdout/stderr。shared inventory 未保存这两个文件的确切文件名，不能在报告中虚构路径。没有必要复制完整 Ray worker 日志树，也不应在补证前重跑 B。

