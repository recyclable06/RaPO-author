# Progress — fresh-process resume v4 independent acceptance

日期：2026-09-13。状态：`LIMITED_ACCEPTANCE_NOT_GPU_READY`。

已完成：

- 独立核对 v4 `HASHES_V4.json`：30/30 文件、218524 bytes；package manifest 和 17-file raw manifest 均可复算。
- 独立核对 v3 supplement：9/9 key files bytes/hash 一致，raw 目录实际 99 files / 744350 bytes；确认声明的 raw aggregate 目前缺少可复算的逐文件 manifest/算法。
- 独立复核 parser-only raw：C/A/B 正例、缺 `--cil-cfg`、内容 hash 负例、跨腿 identity 一致；确认 `total_epochs=1` 只是 parser compatibility，实际 runner 按 `total_epochs * len(train_dataloader)` 计算。
- 独立复核 v4 raw Ray evidence：canonical target modules、11 labels、63 events、writer identity、每 PID 序列、original call once 和两个 rank-labelled child 的 raw call reports。
- 独立 CPU synthetic negative 证明 `judge_v4` 会把不同 PID/rank 的 labels 全局拼接而通过；已记录为 FPP-V4-001。
- 未启动 GPU/Ray/SSH/安装/模型/训练/推理；未修改准备包、生产或测试。

待处理：

- 收紧 v4 judge，按 role/rank/process 要求 required labels、wrapper install 和 call pair；明确 RawChildProbe 与真实 FSDP worker 的证据类型。
- 为 v3 supplement 增加 99 项 raw manifest 和确定的 aggregate 算法，或提供可重复生成命令。
- 在 v5 完成真实 launcher、合法 epochs/loader 两步预算、native/RNG/anchor/vLLM 状态和 C/A/B 集成后重新独立验收。

证据入口：`REPORT.md`、`probes/v4_acceptance_probe.py`、`raw/01_v4_acceptance_probe.stdout.json`、`raw/01_v4_acceptance_probe.exit.txt`。
