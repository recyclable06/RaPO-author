# v6 acceptance progress

- 2026-09-14：完成候选包和 raw manifest 独立复算；59/26 files、bytes 与声明逐项一致。
- 2026-09-14：完成冻结目标 entry/test/runtime identity 复核；20 个候选 Python 文件 AST parse 通过。
- 2026-09-14：运行 `test_v6.py`、`launcher_contract_probe_v6.py`，并完成额外 install-order/writer/digest CPU 正负检查。
- 2026-09-14：从保留的远程 parser raw 和 zero-GPU event raw 独立重放判定；zero-GPU 129 events / 2 Ray workers，v6 judge pass。
- Verdict：`READY_FOR_BOUNDED_GPU`。
- 明确未做：GPU preflight、C/A/B production run、模型、训练、推理、COCO AP、paper-scale 或 paper-faithful claim。
