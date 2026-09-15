# FPP-V6-GPU-MAP v7 独立验收

日期：2026-09-14。角色：`independent acceptance`。

本轮只审查冻结的 v7 GPU 映射增量、其候选包/raw evidence、v6 继承字节身份、r2 路径绑定身份差异以及相关 CPU/static gate。未修改候选、生产源码、生产测试或既有 v6 验收；未启动新的 SSH/GPU/Ray/模型/训练/推理，也未重跑未改变的 42 项 CPU 测试。

## Verdict

**`NEEDS_PROTOCOL_REVISION`**。

v7 的真实 no-model 映射 raw 已独立通过物理 CUDA/Ray 映射检查，但候选实现有一个阻断 bounded-GPU readiness 的证据语义缺陷：`gpu_preflight_v7.py` 把报告时的 `time.time_ns()` 写入 `process_start`，没有记录真实 OS worker process-start identity。这个字段随后被用来证明两个 Ray worker 身份，因此当前门在同一进程分时产生两份报告时可能被错误满足。该问题不是本次 raw 中两张卡实际映射失败；本次 raw 的两个 PID 确实不同，但候选 gate 本身尚未 fail-closed 地证明“两个真实 worker”。

具体 finding：`FPP-V7-001`。

## Package and inherited identity

- v7 候选：`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v7`。
- v7 self-excluded package：116 files / 4,393,404 bytes；package manifest `4606990ad442783ae08ff2149ac6d71a46236a660630bbaf8d2d41c60acf9fbb`；`HASHES_v7.json` self SHA256 `6e17de365bd2905fb821f37c88a4c441e4d2440d92437fdbf0d6729c962c2e38`。
- v7 raw subset：65 files / 4,117,257 bytes；raw manifest `57945f80de9a53d5e137ce83bc299a08c0122b82696def0c724af1bf2a2919b3`。包内声明与独立复算逐项一致。
- 继承 v6：59 files / 4,268,936 bytes；package manifest `60e5d5ee5b161f212466976af1f7689a632dbeffb0911615a27440115365ce54`；`HASHES_v6.json` self SHA256 `e0c671e00f481efbffb0097cc361673aca1e504914356ebe603a2f1d75c3c820`。v7 与 v6 的 59 个共同文件中只有 `run_v6.py` 发生字节变化；`build_production_argv` 保持不变。
- r2 delivery：37 files / 56,608 bytes；delivery manifest self SHA256 `3d3ab9f61a9dbce1c416267c99acfd66a56bf0df84330b6977b28a98f3d3095e`，复制后的文件逐项匹配。

完整机器复核见 [raw/acceptance_probe.stdout.json](C:/Users/Administrator/Desktop/RaPO-author/docs/acceptance/FRESH-PROCESS-GPU-MAPPING-V7-20260914/raw/acceptance_probe.stdout.json)，验收目录清单见 [HASHES.json](C:/Users/Administrator/Desktop/RaPO-author/docs/acceptance/FRESH-PROCESS-GPU-MAPPING-V7-20260914/HASHES.json)。

## Independent gate results

1. `test_gpu_mapping_v7.py` 返回 `PASS_V7_GPU_MAPPING_FIXTURES`。正例覆盖 Ray UUID/numeric、完整 host `nvidia-smi` 诊断文本与单设备 CUDA 映射；负例覆盖多 token CVD、重复物理 UUID、额外可见设备、未知 Ray id 与 PCI 错配。
2. `launcher_contract_probe_v6.py` 返回 `PASS_V6_LAUNCHER_C_AB_CONTRACT`；23 个候选 Python 文件 AST parse 通过。
3. `run_v6.py` 静态接线复核通过：导入 `gpu_preflight_v7`，preflight 位于 production `subprocess.Popen` 之前，preflight-only/result schema 仍为 6，生产 argv builder 与 v6 相同，且没有错误引用旧 `HASHES_v6.json`/`HASHES_v7.json` 作为运行时包验证。
4. 对 v7 真实 raw 的 `validate_worker_reports` 独立重放返回 `PASS_REPLAY_V7_RAW_MAPPING`；worker full-host SMI 文本被确认只是 diagnostic evidence，不参与可见性判断。

## Real mapping raw

原始目录：`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v7/raw/remote-v7-gpu-preflight-20260914-211/`。

- 选择顺序为 host index 2 / `GPU-f32f2674-753c-cd20-7606-34a0e5804687` / PCI `08:00.0`，以及 index 3 / `GPU-d4babf14-b743-2673-4344-311c2f561214` / PCI `09:00.0`；两张都是 RTX 3090、4 MiB、无 selected-GPU compute app。
- 两个 Ray worker 在同一 `node_id`，raw PID 为 `690039`、`690035`；每个 worker 一个 Ray UUID id、一个 CVD token、runtime `device_count=1`、driver `cuDeviceGetCount=1`、local ordinal `0`。
- 每个 worker 的 runtime UUID 与 driver UUID 相同，并分别与 host `nvidia-smi` 的 PCI `09:00.0` / `08:00.0` 相符；两张物理 UUID distinct 且恰好覆盖选择集合。
- worker 内的 `nvidia-smi` 文本确实列出全机 7 张卡，但 v7 结果明确记录 `diagnostic_only_not_a_worker_visibility_gate`，未把该文本当作 worker 可见性证明。
- `probe.exit.txt`、`release-check.exit.txt`、`final-check.exit.txt` 均为 `0`。release/final raw 保持所选卡 4 MiB，selected UUID 不在最终 APPS 列表，`USER_PROCESSES` 区段为空；没有遗留本次 Ray/probe/production 进程。raw command 只运行 no-model `gpu_preflight_v7.py`，没有 C/A/B、模型构造或训练。

因此，物理映射 raw 本身是 PASS；它不能覆盖下面的候选 gate 实现缺陷。

## Blocking finding FPP-V7-001

候选 [gpu_preflight_v7.py](C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v7/gpu_preflight_v7.py:216) 在 Ray actor 的 `report()` 中写入：

```python
"process_start": str(time.time_ns()),
```

这是每次报告的当前时间，不是该 PID 的 OS process-start identity。v6 原实现 [gpu_preflight_v6.py](C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v6/gpu_preflight_v6.py:64) 会读取 `/proc/<pid>/stat` 的真实 start-time 字段；v7 删除了这条路径，却仍在 [gpu_preflight_v7.py](C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v7/gpu_preflight_v7.py:265) 用 `(pid, process_start)` 集合做 worker identity gate。真实 v7 raw 中的 `1789393391...` 值也呈现为 epoch nanoseconds，而非 v6 的 OS start-time 形式。

影响是：若同一实际 worker 进程分时返回两份物理报告，两个报告时间戳仍可不同，identity guard 可能接受它们为两个 worker。故当前实现没有满足协议要求的真实、可重放、fail-closed 的“两 个 distinct Ray worker”证据。修复应恢复真实 process-start identity（Linux 可使用 `/proc/<pid>/stat` field 22），并在接受前拒绝缺失或非真实身份字段；同时补一个针对同 PID/非真实 start identity 的负例。

## r2 parser identity boundary

此项已单独复核，没有把 r2 的路径绑定结果冒充继承 v6 identity：

- v7 frozen inherited-v6 parser identity：`06cb3fe8c6f78b46a37c6f36703a48e65a87f838f7d66b8734a86cd81500a7a3`。
- r2 copied parser identity：`5e56258c21437b119968c1916f0edacb4a1ce761387b89939d103ff926adcfa7`。
- 两者的 production entry bytes/hash 相同（entry SHA256 `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3`），但 r2 使用 `/mnt/conda/zhenglifeng/t/r6g211r2/source`，其 effective config 的 source-bound paths 与之前 v6 parser raw 不同。因此本报告保留两份身份并明确不等同；后续 C/A/B 必须继续使用实际运行根的 identity ledger，不能把 r2 parser raw 静默复用为旧 v6 parser identity。

## Scope and remaining work

本轮没有 C/A/B、模型、训练、推理、trajectory、COCO AP 或 paper-faithful 结果；不能据此宣称科学复现通过。下一步应在修复并重新冻结的 v7 增量上重做独立映射验收；FPP-V7-001 关闭后，才可把 physical mapping gate 交给后续 bounded C/A/B 执行任务。
