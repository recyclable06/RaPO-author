# R3.1 fresh-process resume v3 独立验收

日期：2026-09-11。角色：`independent acceptance`。本验收只审查 fresh-process resume v3 准备包；不修准备包、不修改 R3.1 production/test，不执行 GPU、Ray、SSH、安装、训练、推理、commit 或 push。

## Verdict

`NEEDS_REVISION`（当前不具备 GPU/Ray 执行就绪资格）。

v3 的离线 identity、配置渲染、AST、负例和观测器局部探针提供了有价值的静态证据，但实际命令链存在两个会在生产前直接失败的 P1 缺陷；子进程观测的“installed”事件也没有安装 observer wrapper，无法证明关键 Ray runner/worker 已接通。另有事件序号合同缺口。故本轮不交付 `PASS_READY_FOR_GPU`，也不把 `OFFLINE_RESULTS_V3.json` 或零 GPU smoke 材料当作生产 Ray/恢复证据。

## Frozen identity

- 准备包：`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v3/`。
- 准备包 `HASHES_V3.json` 声明 24 个文件、183476 bytes；独立探针逐项核对为 24/24 bytes/hash 一致。
- 验收目标：`C:/Users/Administrator/.codex/worktrees/8ac5/RaPO-author`，R3.1 production entry 为 `examples/baselines/img_cls_cil/image_cls_cil_rapo.py`，102269 bytes，SHA256 `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3`；与 v3 expected identity 一致。
- 本目录的 `probes/v3_targeted_probe.py` 是独立验收探针，不导入 production/Ray/model，不覆盖 v3 输出；原始输出和退出码保存在 `raw/`。

## Passed checks

- v3 声明的 11 个 Python 文件均可用 AST 编译。
- expected model/input/template manifest、class order、tokenizer/model path 和 config binding 的离线检查通过；`run_v3._render_config` 的正例和 unresolved placeholder 负例均通过。
- 目标 entry 的 bytes/hash 与 expected identity 一致；未修改目标 production、准备包或 test。
- frozen-content 正例在显式注入 `known` 时通过；修改 `class_b/b.jpg` 后被 content manifest 拒绝。
- `judge_v3` 有效 synthetic fixture 通过；effective reward constant 负例被拒绝。
- 所有本轮探针均使用 CPU/静态检查；没有 GPU、Ray、production import、training 或 inference。

## Blocking findings

### FPP-V3-001：命令模板漏传必需的 `--cil-cfg`（P1）

`COMMANDS_V3.md:40-50` 的 `run_leg` 参数包含 `--config-template`，但没有把第 17 行定义的 `CIL_CFG` 传为 `--cil-cfg`。`run_v3.py:280-289` 将 `--cil-cfg` 声明为 required；`run_v3.py:94-98` 的 `_production_argv` 又读取 `args.cil_cfg`。独立探针实际调用 launcher 的缺失参数路径，退出码为 2，并且 parser 错误明确指出 `--cil-cfg`。

因此按当前 `COMMANDS_V3.md` 复制执行时，C/A/B 三腿在生产入口前即被 argparse 拒绝，无法形成任何 GPU/Ray 或 resume 证据。

返修条件：在唯一命令模板中显式传递 `$CIL_CFG`，并让命令级负例/正例检查覆盖这一参数；重新冻结 v3 清单后再验收。

### FPP-V3-002：`_verify_frozen_content` 使用未定义的 `known`（P1）

`argv_validate_v3.py:110-113` 的 `_verify_frozen_content` 签名没有 `known` 参数，但 `:154-158` 在构造 binding 时读取 `getattr(known, "cil_cfg")`。`validate_effective_argv` 在 `:362-371` 调用该函数时没有传入 `known`。独立探针记录：显式注入 `known` 的 synthetic 正例通过；不注入时得到 `NameError: name 'known' is not defined`。这不是探针伪造的输入路径，而是实际函数调用的定义/调用不一致。

该错误位于 model/input manifest 检查之后、identity payload 生成之前；即使先修复命令漏参，真实 leg 仍会在完成内容检查后因 `NameError` 退出，不能进入 production。

返修条件：把 `known` 作为显式函数参数（或等价地从已验证的 argv 上下文取得），补充真实 `validate_effective_argv` 正例和未定义变量负例，并重新冻结 hash。

### FPP-V3-003：child “installed” 只表示 bootstrap 记录，没有安装 observer wrappers（P1）

静态和实际 CPU 探针共同确认：

- `child_bootstrap_v3.py:87-113` 的 `bootstrap()` 只计算模块身份并写出 `child_bootstrap_install`，将 `installed=True` 作为记录字段；它不导入 `runtime_observer_v3`，也不调用 `runtime_observer.install()`。
- `sitecustomize.py:8-16` 只调用 `child_bootstrap_v3.bootstrap()` 并吞掉异常；探针中 `observer_imported=false`。
- `runtime_observer_v3.py:156-192` 的 `_ensure_process()` 在 runner/worker 子进程只做 bootstrap 和 `process_identity` 事件；`_install_process_wrappers()` 仅由 root-side `install()` 在 `:846-860` 调用。
- 实际 child probe 看到 `child_observer_install_event=true`、`child_event_reports_installed=[true]`，但同一进程的 `patched_labels_after_ensure_process=[]`；judge 的 hash-only child gate 也能在没有 wrapper report 时接受。

目标生产链不是只在 root 进程执行：`verl/workers/fsdp_workers.py:46,471,490-495` 导入、实例化并使用 `FSDPCheckpointManager`；`image_cls_cil_rapo.py:1259-1291,1782-1787` 在 Ray runner 中创建 `PersistentRefFSDPWorker` remote。目标的 `_ensure_ray`（`image_cls_cil.py:502-515`）只提供普通 runtime environment 变量。v3 的 root observer 可能依赖 Ray 序列化 patched class，也可能不会；本探针没有强行主张所有 root monkeypatch 都不可序列化，但 v3 没有在 fresh child import 路径中安装 checkpoint/process wrappers，也没有用真实 PersistentRunner/PersistentRefFSDPWorker 证明这一点。因此“bootstrap installed”不能推出关键 native load/save、actor update、anchor/vLLM 或 resume hook 已安装。

另外，现有 `ray_bootstrap_smoke.py` 自己定义的 smoke `Runner`/`Worker` 显式调用 `bootstrap()`，不是目标 production runner/worker；准备包的 `SMOKE_RESULTS_V3.json` 当前为 `ModuleNotFoundError: No module named 'ray'`。即使该 smoke 可运行，也只能证明手工 bootstrap 的传播，不足以关闭本 finding。

返修条件：为真实 Ray runner/worker 提供可审计且 fail-closed 的 child-side observer install（或等价可靠机制），让 judge 要求每个 role/rank 在关键事件前同时有 wrapper install 与 process identity；并增加真实 production class wiring 的 CPU/可替代验证，不能只接受 hash-only bootstrap event。

### FPP-V3-004：事件序号不是同一事件文件内的全局单调序列（P2）

独立 `observer_ensure_process` probe 在同一个 event file 中得到 `event_sequences=[1,1,2]`，`duplicate_seq_values=[1]`。原因是 `child_bootstrap_v3.py` 与 `runtime_observer_v3.py` 各自维护模块级 `_SEQ`；同一 PID 中 child bootstrap 和 observer 写事件时会产生重复序号。当前 judge 的 child timing 使用 Unix 时间字段（`judge_v3.py:392-435`），没有将序号当作排序/唯一性合同，因此这是证据可追溯性和合同一致性缺口，不是本轮第三个 P1。

返修条件：要么明确 `seq` 只在模块内有效并改名/记录 writer identity，要么改为同一 run/PID 的原子全局序列，并在 judge 中验证唯一性和先后关系。同步收紧 hash-only child bootstrap gate，避免没有 wrapper report 时接受 child 安装。

## Execution boundary

本轮没有运行 `gpu_preflight_v3.py`、Ray、production entry、C/A/B、训练、推理或远端部署；没有产生 GPU、Ray、state-exact、trajectory-close 或实验指标结论。`OFFLINE_RESULTS_V3.json`、`SMOKE_RESULTS_V3.json` 和本目录 CPU probe 仅证明离线判定器、静态结构及局部观测行为。

在 FPP-V3-001、FPP-V3-002、FPP-V3-003 关闭并重新冻结 v3 清单之前，不应启动有限 GPU 执行。返修后需重新进行本独立验收，再由专用 GPU 角色按三腿协议执行。
