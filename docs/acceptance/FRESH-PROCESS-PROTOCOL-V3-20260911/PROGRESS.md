# Progress — fresh-process resume v3 independent acceptance

日期：2026-09-11。状态：`NEEDS_REVISION`。

已完成：

- 只读核对 v3 prep 目录 24/24 declared bytes/hash；11 个 Python 文件 AST 编译通过。
- 独立核对 R3.1 target entry 身份；102269 bytes 和 SHA256 `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3` 均一致。
- 独立运行 CPU-only targeted probe：配置渲染正/负例、model/input/template manifest、frozen-content 正/负例、child bootstrap、sitecustomize、observer `_ensure_process`、judge valid/effective-constant 和命令缺参路径均有原始输出。
- 确认命令模板漏传 `--cil-cfg`、`_verify_frozen_content` 的 `known` NameError、child bootstrap 不安装 observer wrapper，以及 event seq 重复四项发现。
- 所有探针均未启动 GPU/Ray/SSH/安装/训练/推理；未修改 prep、production 或 test。

待处理：

- 修订并重新冻结 `COMMANDS_V3.md` 的 `--cil-cfg` 绑定。
- 修复并真实调用 `known` 上下文，补上 `validate_effective_argv` 的正例/负例。
- 为真实 Ray runner/worker 提供并判定 child-side observer wrapper 安装；收紧 hash-only child gate。
- 明确并验证 event `seq` 的唯一性/排序合同。
- 返修后重新做本独立验收；通过后再由独立 GPU 角色执行。

证据入口：`REPORT.md`、`probes/v3_targeted_probe.py`、`raw/01_targeted_probe.stdout.json`、`raw/01_targeted_probe.exit.txt`。
