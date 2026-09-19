# Fresh-process R2 shared evidence — independent review

审查日期：2026-09-19（Asia/Shanghai）  
角色：独立只读证据复核。未修改生产代码，未重跑实验，未触碰源端数据。

## 结论

本轮交付应保留为 `PARTIAL_EVIDENCE_SUPPLEMENT`。R2 scientific reproduction gate 仍未关闭。

最重要的更正是：B 的 `run-result.json` 中 `model_constructed=false` 与 `training_started=false` 不是独立观测事实，而是 `run_v9.py:232` 用 `process.returncode == 0` 派生出来的字段。B 的原始 stdout 与 observer 反而明确证明模型、FSDP、vLLM 和 persistent workers 已经初始化；两个 FSDP rank 都进入了 `PersistentRefFSDPWorker.init_anchor`，但没有对应的 `after` 事件。

因此，B 的真实可定位边界是：anchor 初始化阶段中止，尚未观测到 Task 2 的 `run_task`、native checkpoint restore、driver RNG restore、vLLM boundary restore 或 `fit`。进程退出码 `-6` 只说明子进程以 signal 6 结束；内部 abort 原因仍未由现有原件确定。

## 共享交付完整性

- delivery manifest：252 个文件、38,692,471 bytes；SHA256 `0a6d7c601db17be196c3d457c7a5acbc849e17b9ffde11758a48ac40ae0e284f`。
- evidence index：215 个证据文件、38,523,445 bytes；最大单文件 12,830,694 bytes；SHA256 `cc30ab4dce800a08697dea21ae8327a9edce3f4933c4b3bdd828da3307051dc0`。
- manifest 与 index 的计数、总字节数、文件 SHA 均通过；未发现额外或缺失文件。
- `tensor_or_weight_files_copied=false`；未把权重树或排除的二进制带入共享包。

完整机器可复核输出见 `raw/review_probe.stdout.json`，复核脚本见 `review_probe.py`。

## A：边界原件已补齐，但 observer-derived proof 仍不完整

`evidence/A-boundary/task1-complete.json` 的 SHA256 为 `c7b8c132de4346bba8c570d429bdcbef603c0bbeea6bfd8803fea84175d4f795`，状态为 Task 1 complete、`global_step=2`、`next_task=2`。marker 引用的 driver RNG、EMA 和两个 vLLM RNG 文件均已在共享包中找到，并逐一与 marker 中的 SHA256 相符。

但 `evidence/A-root/boundary-expected.json` 仍为 `complete=false`，唯一错误是 `A actual post-publication driver RNG capture is missing`。81 个 observer JSONL 共 435 条记录；实际 `PersistentRunner.run_task` wrapper call 数为 0，driver RNG expected 观测也没有形成可验收记录。故 A 的问题已从“共享包遗漏 marker-linked 文件”缩小为“post-publication driver observer/derivation proof 不完整”，不能据此判定生产实现本身错误，也不能关闭 A boundary finding。

## B：最后阶段与信号时间线

### 已证实的最后成功阶段

B root stdout 的关键行显示：

- `process.stdout.log:148,150,154,156`：rank 0/1 的 HuggingFace model 与 FSDP module 初始化完成；
- `process.stdout.log:161`：vLLM 初始化完成；
- `process.stdout.log:165`：`[CIL] Workers initialised (persistent).`；
- `process.stdout.log:169,171`：随后再次完成 HuggingFace model 与 FSDP module 初始化，与 anchor 构造路径相符。

B observer 共 81 个 JSONL、388 条记录。实际目标调用只有：

- `PersistentRefFSDPWorker.init_anchor`：rank 0 PID 1161595 只有 `before`（`1789572776.472536`），rank 1 PID 1162100 只有 `before`（`1789572777.2901604`）；
- `PersistentRunner.run_task`、`PersistentCILTrainer._load_checkpoint`、`PersistentCILTrainer.restore_boundary_checkpoint`、`FSDPCheckpointManager.load_checkpoint`、`PersistentCILTrainer.fit`：均为 0 次实际 wrapper call。

这与 frozen production source 的调用顺序一致：`image_cls_cil_rapo.py:1789-1796` 先执行 `init_anchor_on_workers`，随后才进入 driver RNG restore；`run_task` 内的 `reinit_for_task`、`restore_boundary_checkpoint`、vLLM restore 和 `fit` 位于更后面。`PersistentRefFSDPWorker.init_anchor` 在 `image_cls_cil_rapo.py:984-1014` 内构造 anchor model/FSDP module。对应 frozen production source SHA256 为 `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3`。

### 退出与 supervisor 顺序

- B child PID 1153372 在 `2026-09-17 00:17:44.816206+08:00` 记录 `exit_code=-6`。
- supervisor 在 `00:18:32` 才到 deadline；`00:18:33` 明确记录 child 已退出或 identity changed，未发送 child signal；最终 `child_term_sent=0`、`child_kill_sent=0`、`launcher_rc=125`。
- aggregated B stderr 中的 `*** SIGTERM received at time=1789574336 ...` 对应约 `23:58:56`，没有 owner/PID，且早于 child 的 `00:17:44` 退出；现有原件不能把它归因给 supervisor，也不能把它当作 child 的最终 signal。
- Raylet 的 SIGTERM 出现在 `00:18:53`，dashboard/dashboard-agent 的退出在 `00:18:43–00:18:54`，均晚于 child 退出和 supervisor deadline，更符合后续 Ray 清理，不是已证实的原始失败原因。

### 边界 manifest 的含义

B before/after boundary manifest 相同，SHA256 均为 `78f0b2c1664b1bad1ca6603bef17ef1b0393e64756a071116017d3ff43695837`。这只能证明共享边界树没有发生可见写入，不能证明 native checkpoint restore 已完成；observer 中也没有 `FSDPCheckpointManager.load_checkpoint` 的实际调用。

## 最小下一步

1. 暂不把 B 标成“restore-stage timeout”或“训练未开始”；准确标签应为“anchor init 中的 signal-6 abort，内部原因未定”。
2. 若需要继续做 B 的根因归因，只请求源端 Ray worker PID 1161595（rank 0）和 1162100（rank 1）对应的 stdout/stderr 原件。当前 shared inventory 没有记录这两个 worker 日志的文件名，不能凭空补写路径，也不需要复制完整 worker log tree。
3. A 先补齐实际 `PersistentRunner.run_task` 与 post-publication driver RNG 观测，再决定是否能关闭 A finding。
4. Host 211 cleanup 仍为 `UNCONFIRMED`；本复核没有改变该状态。

