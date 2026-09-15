# Progress — fresh-process resume v2 independent acceptance

日期：2026-09-11。状态：`NEEDS_PROTOCOL_REVISION`。

已完成：

- 只读核对 v2 prep 目录 16/16 declared bytes/hash；7 个 Python 文件 AST 编译通过。
- 独立核对 R3.1 target entry 身份和 91-file runtime source manifest，均与 expected 一致。
- 独立运行 CPU-only judge probe：valid fixture 通过；缺 digest、单步 window 被拒绝；有效 reward variation 为零的 fixture 当前仍通过。
- 完成对 unique deployment root、model/input identity binding、Ray runner/worker child observer bootstrap 的静态审查。
- 所有探针均未启动 GPU/Ray/SSH/安装/训练/推理；未修改 prep、production 或 test。

待处理：

- 修订并重新冻结配置部署根目录绑定。
- 提供并强制比较 model/input content manifest，尤其是 `INPUT_MANIFEST.json`。
- 证明或实现 Ray runner/worker 子进程的 observer bootstrap，并让 judge 要求 child install evidence。
- 明确 raw/effective group variation 合同；如需 effective variation，收紧 judge 和 fixture。
- 返修后重新做本验收；通过后再由独立 GPU 角色执行。

证据入口：`REPORT.md`、`probes/static_probe.py`、`probes/judge_probe.py`、`raw/01_static_probe.stdout.json`、`raw/02_judge_probe.stdout.json`。
