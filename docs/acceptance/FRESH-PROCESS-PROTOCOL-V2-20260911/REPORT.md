# R3.1 fresh-process resume v2 独立验收

日期：2026-09-11。角色：`independent acceptance`。本验收只审查 GPU diagnostics v2 准备包；不修准备包、不修改 R3.1 production/test，不执行 GPU、Ray、SSH、安装、训练、推理、commit 或 push。

## Verdict

`NEEDS_PROTOCOL_REVISION`（当前不具备 GPU 执行就绪资格）。

v2 的静态结构和离线 judge 基础能力已经有独立证据，但以下身份绑定和 Ray 子进程观测缺口会使一次“成功运行”仍不能可靠证明 frozen protocol 的原始实验身份或 `state-exact` 条件。因此本轮不交付 `PASS_READY_FOR_GPU`，也不把准备者的 `OFFLINE_RESULTS_V2.json` 当作 GPU/Ray/恢复证据。

## Frozen identity

- 准备包：`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v2/`。
- 准备包清单：`HASHES_V2.json` 声明 16 个文件、145020 bytes；独立探针逐项核对为 16/16 bytes/hash 一致。
- 验收目标：`C:/Users/Administrator/.codex/worktrees/8ac5/RaPO-author`，R3.1 production entry 为 `examples/baselines/img_cls_cil/image_cls_cil_rapo.py`，102269 bytes，SHA256 `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3`；与 `EXPECTED_IDENTITY_V2.json` 一致。
- 独立重算 target runtime source manifest：91 files，SHA256 `947de3842eadb716d241eb4bb4f2fff62f2cfe39305cf03ffd0fbe35abd052e1`，与 expected 一致。

## Passed checks

- v2 的 7 个 Python 文件均可用 AST 编译。
- `judge_v2` 的标准 synthetic fixture 通过；缺 native digest、只有一步 Task-2 window 的负例均被拒绝。
- 全部检查均使用 `-B` 和 `PYTHONDONTWRITEBYTECODE=1`；没有导入 production `main`，没有访问 GPU 或启动 Ray。
- target worktree 和 v2 prep worktree 的状态均只读核对；本验收只新增本目录工件。

## Blocking findings

### FPP-V2-001：部署根目录与配置内路径不一致（P1）

`COMMANDS_V2.md:10-12` 将远端部署根设为唯一的 `/mnt/conda/zhenglifeng/t/fresh-process-resume-20260911-v2-UNIQUE`，并令 `SOURCE_ROOT=$REMOTE_ROOT/source`；`COMMANDS_V2.md:39-46` 把该 source 和 v2 config 一起传给 `run_v2.py`。但 `PPO_CONFIG_V2.json:16` 和 `:92` 仍分别指向非唯一的 `/mnt/conda/zhenglifeng/t/fresh-process-resume-20260911/v2/source/...`。

`run_v2.py:61-65` 只构造 `config=/absolute/path` dotlist，不重写这两个路径。按命令中的正常 unique-root 部署，prompt/reward 文件要么不存在，要么来自另一份旧/并行树；这会在生产解析或运行阶段失败或误绑输入。独立 probe 的 `config_root_binding` 已记录 `config_uses_old_non_unique_root=true`、`config_uses_unique_command_root=false`、`run_v2_contains_config_rewrite=false`。

返修条件：让配置路径由实际 `$SOURCE_ROOT` 生成并把生成后的内容纳入 C/A/B identity ledger/hash，或采用等价的显式部署绑定；同时补一条在模型/生产运行前能失败的路径存在性与内容身份检查。

### FPP-V2-002：model/input expected identity 未形成硬比较（P1）

`EXPECTED_IDENTITY_V2.json:27-35` 声明了 model path、input root、`INPUT_MANIFEST.json` 和 class order，`...:37-40` 还要求 C/A/B 的 model/input/source identity 一致。但 `argv_validate.py:239-264` 只从实际解析后的 config 读取 model/tokenizer/train/val 路径并生成 `_path_identity`；它只在 `:243-250` 将 production entry 和 91-file source manifest 与 expected 比较，没有读取 `expected["model"]`、`expected["input"]`，也没有加载 `INPUT_MANIFEST.json`。v2 目录内实际没有该 manifest 文件。

因此三腿可以一致地使用同一个错误 model/input，并仍通过当前的 identity ledger。独立 probe 已记录 `argv_validate_references_expected_model_object=false`、`argv_validate_references_expected_input_object=false`、`input_manifest_files_inside_v2=[]`。这不满足原实验身份 gate。

返修条件：提供冻结的 model content manifest 和 input manifest（含 class order/样本文件内容身份），在 production import/构造模型前按 expected 内容比较并写入 ledger；仅记录运行时实际路径不足以关闭该问题。

### FPP-V2-003：Ray runner/worker 子进程的 observer 安装未被保证或证明（P1）

`runtime_entry.py:20-32` 只在新的 root production process 中导入并执行 `runtime_observer.install(module)`。`runtime_observer.py:805-832` 对 Ray 做的是 `runtime_env.env_vars`/`PYTHONPATH` 传播；文件中没有 `sitecustomize`、worker setup hook 或等价的 child-side `runtime_observer` 自动导入。`:867-882` 的 required-set 也只是当前安装进程的 `_PATCHED` 集合。

目标 production 在 `image_cls_cil_rapo.py:1259-1291` 定义 `@ray.remote` 的 `PersistentRunner`，并在 runner actor 的 `init` 中创建 `ray.remote(PersistentRefFSDPWorker)`；driver 在 `:1782-1787` 调用 `PersistentRunner.remote()` 和 `runner.init.remote(...)`。也就是说，关键 native load/update/anchor/vLLM hooks 的实际执行在 Ray runner/worker 子进程，不能只由 root process 的 local `_PATCHED` 报告推出。当前没有 GPU sidecar 可证明这些 child 已安装 wrapper。

返修条件：为每个 Ray runner/worker 提供可审计的 child-side bootstrap/install event，或实现等价的可靠传播机制，并在 judge 中要求每个 role/rank 的 observer install 和 process identity 先于关键事件出现；否则最多只能报告“未证明”，不能报告 state-exact。

### FPP-V2-004：group variation 的 judge 覆盖范围比协议窄（P2，需明确或修订）

`judge_v2.py:70-89` 只要求 repeated UID group 的 `raw_variation > 0`；它不读取或校验 `effective_variation`。独立 judge probe 将两个 update 的 `effective` 改成常量并将 `effective_variation` 设为 `0.0`，fixture 仍通过，且 `reasons=[]`。这不是 GPU 证据，但说明协议“group reward variation”若包含 effective reward，当前判定器存在可通过的 coverage gap。

返修条件：明确 frozen contract 只要求 raw reward variation，或在 judge/fixture 中显式要求 effective variation 的语义和阈值；不能让协议文字、sidecar 字段和 judge 各自表达不同要求。

## Execution boundary

本轮没有运行 `gpu_preflight.py`、Ray、production entry、C/A/B、训练、推理或远端部署；没有产生 GPU/Ray/state-exact/trajectory-close 结论。`OFFLINE_RESULTS_V2.json` 与本目录的 CPU probe 仅证明判定器 fixture 行为。

在 FPP-V2-001 至 FPP-V2-003 关闭并重新冻结 v2 清单之前，不应启动有限 GPU 执行。返修后需重新进行本独立静态验收，再由专用 GPU 角色按三腿协议执行。
