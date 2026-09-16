# v9 GPU timeout evidence review

状态：已完成窄范围独立复核；结论保持 `BLOCKED_C_TIMEOUT_AFTER_TASK1`。

- 已复核 observer events、结构化 experiment log、Task 1 metrics、Ray logs、timeout policy 和原始 checkpoint inventory。
- 已确认 Task 1 为 2/2 个 rank-synchronized actor updates；Task 2 为 0/2；总计 2/4。
- 已确认 900 秒 outer timeout、SSH exit code 1，以及缺失 `run-result.json`、`process-end.json` 和完整 production stdout/stderr。
- 已将本地部分 checkpoint transfer 明确排除，不将它用于 identity、resume 或 judge 判断。
- 未执行 SSH、GPU、模型/完整 checkpoint 传输、CPU/v9 readiness 重跑，也未修改 production code。
- 当前工作区正在进行的其他 R2 实验不在本复核范围内，也未被替换或判定。

交付物：

- `REPORT.md`：结论、时间线、异常扫描解释和限制。
- `acceptance_probe.py`：只读、可重跑的独立字段级探针。
- `raw/acceptance_probe.stdout.json`：本次探针输出。
- `HASHES.json`：本验收目录的文件清单与 SHA-256（manifest 自排除）。
