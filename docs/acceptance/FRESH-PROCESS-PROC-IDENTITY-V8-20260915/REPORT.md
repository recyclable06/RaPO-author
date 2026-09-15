# FPP-V7-PROC-IDENTITY v8 独立增量验收

日期：2026-09-15。角色：`independent acceptance`。

本轮只审查 v8 对 FPP-V7-001 的进程身份修复、其新增 Linux direct/Ray raw、v7 继承边界和相关 CPU/static gate。未修改候选、生产源码、生产测试或既有验收；未启动新的 SSH/GPU/模型/训练/推理，也未重跑未改变的 42 项 CPU、完整 parser 或 v7 physical GPU probe。

## Verdict

**`READY_FOR_BOUNDED_GPU`**。

v8 已关闭本轮验收范围内的 FPP-V7-001：worker identity 不再使用报告时间戳，而是在实际 Ray worker 中读取 `/proc/<pid>/stat` field 22，保留原始 stat 行；验证阶段独立重算 PID、comm、state、field 22、来源关系，并要求两个正 PID、两个不同 Ray `worker_id` 和同节点。缺失、损坏、同 PID 伪造 field-22、重复 worker、错误来源和不完整身份均由新增 fixture 覆盖并拒绝。

该 verdict 只授予进入受控 bounded GPU C/A/B 的资格，不是 fresh-process restore、科学复现、COCO AP、paper-scale 或 paper-faithful 结果。

完整机器复核见 [raw/acceptance_probe.stdout.json](C:/Users/Administrator/Desktop/RaPO-author/docs/acceptance/FRESH-PROCESS-PROC-IDENTITY-V8-20260915/raw/acceptance_probe.stdout.json)，验收目录清单见 [HASHES.json](C:/Users/Administrator/Desktop/RaPO-author/docs/acceptance/FRESH-PROCESS-PROC-IDENTITY-V8-20260915/HASHES.json)。

## Package and inheritance integrity

- v8 候选：`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v8`。
- v8 self-excluded package：150 files / 4,471,333 bytes；package manifest `7dbfe1ea8666fed036ae9d59d0b1697ec0d0f2b265d4869e643859bde494b34b`；`HASHES_v8.json` self SHA256 `abd4ccad8d3f2159cd636505b3c78bcafb14e4890e31d1cc81656d97ddc41420`。
- v8 raw subset：88 files / 4,125,939 bytes；raw manifest `8b1dd4f3bc0fd81dee612c78aaff6b4dee50f3830c4149657dc574dde9025358`。声明与独立复算逐项一致。
- 冻结 v7 继承包：116 files / 4,393,404 bytes；package manifest `4606990ad442783ae08ff2149ac6d71a46236a660630bbaf8d2d41c60acf9fbb`；raw 65 files / 4,117,257 bytes，raw manifest `57945f80de9a53d5e137ce83bc299a08c0122b82696def0c724af1bf2a2919b3`；`HASHES_v7.json` self SHA256 `6e17de365bd2905fb821f37c88a4c441e4d2440d92437fdbf0d6729c962c2e38`。
- v8 与 v7 的 116 个共同路径逐项一致，唯一差异是 `run_v6.py` 将 `gpu_preflight_v7` import 改为 `gpu_preflight_v8`；其 `build_production_argv` 与 v7 相同，未改训练配置、状态、轨迹、指标或阈值。v7 physical raw 逐字节复用。
- v8 frozen reference 对既有 v7 coordinator acceptance 的 self hash、文件数、字节数和 `modified=false` 复核一致；没有改写既有 v7 验收。

## CPU and static results

1. `test_process_identity_v8.py` 返回 `PASS_V8_PROCESS_IDENTITY_FIXTURES`。本机 Windows 仅将当前机 `/proc` 实读子项标为 `DEFERRED_NON_LINUX`；Linux direct 与 Ray raw 提供了真实运行证据。其负例覆盖缺失/损坏 proc、错误 source、缺失身份、非正 PID、重复 worker、同 PID 伪造 field-22，以及继承的 physical mapping 错误。
2. `launcher_contract_probe_v6.py` 返回 `PASS_V6_LAUNCHER_C_AB_CONTRACT`；28 个候选 Python 文件 AST parse 通过。
3. `run_v6.py` 接线静态通过：import `gpu_preflight_v8`，preflight 仍位于 production `subprocess.Popen` 之前，schema 仍为 6，生产 argv builder 未变，未引用旧 package hash 作为运行时验证；v8 identity increment 没有退回 v7 旧身份 gate。
4. remote source-sha256 四个文件逐项与 v8 候选 bytes/hash 相同：`gpu_preflight_v8.py`、`test_process_identity_v8.py`、`process_identity_probe_v8.py`、`ray_process_identity_probe_v8.py`。

## Direct Linux process-identity raw

原始目录：`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v8/raw/remote-process-identity-20260914-211/`。

- 两次读取同一 PID `1284540` 的 `/proc/1284540/stat`，field 22 均为 `55870051`，原始行、comm=`python`、state=`R` 可独立重算。
- 子进程 PID `1284541` 的 field 22 为 `55870070`，路径和 raw line 均匹配；direct probe 与 fixture 的 exit markers 全部为 0。
- remote source hash 与候选 v8 文件逐项匹配；command/environment 明确为空 CUDA visibility，仅执行身份 fixture/collector，不构造模型、不训练。

## Zero-GPU Ray process-identity raw

原始目录：`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v8/raw/remote-ray-process-identity-20260914-211/`。

- raw result 为 `PASS`、`mapping_protocol=FPP-V7-PROC-IDENTITY`、`gpu_mapping_rerun=false`。
- 两个真实 worker 位于同一 node：
  - PID `1297623`，field 22 `55917572`，worker ID `4f68ad5e2afcb75c285559ba1df1eabfcf20b073df48e220d6048eb7`；
  - PID `1297621`，field 22 `55917571`，worker ID `dd35b81deb084444a9a72c973b6c85eafc7f02e82edf06b548384551`。
- 两份 `/proc/<pid>/stat` 原始行由独立 parser 重算，PID、field 22、comm=`ray::IdentityAc`、state=`R`、path 和 source relation 全部一致。
- `probe.exit.txt` 与 `release-check.exit.txt` 均为 0；release 的 `PROCESSES_BY_COMMAND_NAME` 区段为空。命令/environment 使用空 `CUDA_VISIBLE_DEVICES` 和 `num_gpus=0` identity-only probe，没有 GPU 映射重跑、模型、训练或 C/A/B。

因此，v8 已提供新增范围要求的真实 `/proc` 采集、原始行重算、同进程稳定性、子进程 distinct PID、同节点 Ray distinct worker identity 与释放证据。

## Scope boundary

v7 的两张 RTX 3090 physical UUID/PCI/CUDA mapping raw 由 v8 按冻结引用逐字节复用，没有在本轮重新占用 GPU；它仍是前一轮已验收的物理映射证据。当前通过的是“physical mapping + process identity readiness”组合门，下一步才是按既定授权和新鲜输出根执行 C→A→B，再独立验收 fresh-process restore、state exactness、trajectory-close 和 COCO/AP 等后续范围。
