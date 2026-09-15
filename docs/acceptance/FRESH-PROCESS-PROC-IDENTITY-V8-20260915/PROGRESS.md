# v8 process-identity acceptance progress

- 2026-09-15：独立复算 v8 package/raw manifest；150/88 files、bytes 与清单一致。
- 2026-09-15：确认 v7 继承 116 个路径逐项不变，唯一共同路径差异为 `run_v6.py` 的 v8 preflight import；生产 argv、schema 和 v7 physical raw 保持不变。
- 2026-09-15：运行 v8 process-identity fixtures、launcher contract 和 28-file AST；全部通过，本机 `/proc` 子项按平台记录为 deferred。
- 2026-09-15：独立重算 Linux direct raw 与 zero-GPU Ray raw；field 22 稳定、子 PID distinct、Ray 两 worker 同节点且 worker ID distinct，释放检查为空。
- 2026-09-15：FPP-V7-PROC-IDENTITY 增量验收通过。

Verdict：`READY_FOR_BOUNDED_GPU`。尚未运行新的 physical GPU probe、C/A/B、模型、训练、推理或 COCO AP。
