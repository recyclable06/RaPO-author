# v7 GPU mapping acceptance progress

- 2026-09-14：独立复算 v7 package/raw manifest；116/65 files、bytes 与 manifest 一致。
- 2026-09-14：确认 59 个继承 v6 文件仅 `run_v6.py` 有字节差异；生产 argv builder unchanged，launcher 映射接线与 schema 6 通过 static gate。
- 2026-09-14：运行 v7 mapping fixtures、v6 C/A/B launcher contract；AST 23 个 Python 文件通过；真实 raw mapping 独立重放通过。
- 2026-09-14：确认真实 no-model raw 的两 worker CUDA runtime/driver/UUID/PCI 映射、host idle gate、actor/Ray release 均通过。
- 2026-09-14：发现并冻结 `FPP-V7-001`：v7 用 `time.time_ns()` 伪作 worker `process_start`，未保留 v6 的真实 OS process-start identity；bounded GPU readiness 暂停。

Verdict：`NEEDS_PROTOCOL_REVISION`。尚未运行 C/A/B、模型、训练、推理或 COCO AP。
