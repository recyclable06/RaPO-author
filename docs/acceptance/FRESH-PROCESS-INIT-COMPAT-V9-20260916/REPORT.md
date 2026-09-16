# FPP-V8-INIT-COMPAT v9 独立增量验收

日期：2026-09-16。角色：`independent acceptance`。

本轮只验收 v9 对 FPP-V8-INIT-001/002 的初始化兼容增量：numeric
`CUDA_VISIBLE_DEVICES` 的 PCI-ordered mapping，以及 production
`RewardConfig` callable 初始化/序列化/loader/Ray round-trip。未修改候选、
生产源码、生产测试或既有验收；本轮没有启动新的 SSH/GPU/model/training，
也没有重跑未改变的 42 项 CPU 或 C/A/B。

## Verdict

**`BLOCKED_RAY_REWARD_SOURCE_HASH_IDENTITY`**。

v9 的 callable 名称链路已通过：真实 `RewardConfig.post_init` 派生
`compute_score`，序列化结果保留该 name，本地 loader 和真实 zero-GPU Ray
worker 都实际加载并调用 `compute_score`，错误的 `:main` 同时被 validator
和真实 loader 拒绝。production validator 也记录并核验了冻结的 reward
source hash。

但本轮的严格验收条件要求 post-init/序列化/local loader/真实 Ray worker
各阶段都能证明同一 callable 及同一 `source_sha256`。现有 v9 raw 和 probe
只在 `effective_reward_config` 与 `production_validator.reward_identity`
中暴露 `source_sha256=028b9c9721c0c1d80b0ae3652aec31c8fb458827ca4d079b1253b537099978a1`；
`serialized_reward_config`、`local_reward_loader` 和
`ray_worker_roundtrip.worker_report` 均没有该字段，也没有 worker 端的独立
重算记录。因此不能把“同一 source hash 已贯穿实际序列化及 Ray worker”
当作已证明，v9 暂不具备 `READY_FOR_BOUNDED_GPU` 资格。

最小解除条件：在序列化、本地 loader 和真实 Ray worker 观测中加入独立重算
的 `source_sha256`，逐项与冻结 reward source hash 比较；只重跑受影响的
reward-init evidence 和本验收 probe 即可。不得用手填的派生 name 或单次
文件 hash 替代 worker 端证据。

## Package and inheritance integrity

- v9 候选：`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v9`。
- v9 self-excluded package：205 files / 4,658,581 bytes；package manifest
  `3767c12fd6bc90ef43479486a057ae92b557aaa4ec276c12d5713871597bae7a`；
  `HASHES_v9.json` self SHA256
  `45f79cbf83d004b6fd05c4e1ef61fe2f5b296dba1771aae24e45e570b890ee39`。
- v9 raw subset：128 files / 4,185,383 bytes；raw manifest
  `9d41841454ac9cc9dddd226f8d52613514675a5ab04b5188d2cd0b1f5736485c`。
  声明与独立复算逐项一致。
- v9 与 v8 的 150 个共同路径逐项 byte-exact；新增 55 个路径中只有
  15 个 non-raw init-compat delta，另 40 个是新增/保存的 raw evidence。
- v8 inherited package：150 files / 4,471,333 bytes；package manifest
  `7dbfe1ea8666fed036ae9d59d0b1697ec0d0f2b265d4869e643859bde494b34b`；
  raw 88 files / 4,125,939 bytes，raw manifest
  `8b1dd4f3bc0fd81dee612c78aaff6b4dee50f3830c4149657dc574dde9025358`；
  `HASHES_v8.json` self SHA256
  `abd4ccad8d3f2159cd636505b3c78bcafb14e4890e31d1cc81656d97ddc41420`。
- `FROZEN_V8_REFERENCE_v9.json` 中的 v8 package、v8 GPU acceptance delivery
  manifest 和 `modified=false` 引用均未改变；v8 physical/process evidence
  按冻结边界复用，没有在本轮改写或重跑。

## CPU and static results

1. 候选 cwd 下 `python -B test_init_compat_v9.py` 返回
   `PASS_V9_INIT_COMPAT_FIXTURES`；numeric CVD 逆序 PCI fixture、重复/UUID/
   错误 `CUDA_DEVICE_ORDER` 负例及 reward template 约束均通过。
2. 候选 cwd 下 `python -B launcher_contract_probe_v6.py` 返回
   `PASS_V6_LAUNCHER_C_AB_CONTRACT`；C/A/B boundary 参数契约未改。
3. 候选顶层 35 个 Python 文件 AST parse、6 个 v9 初始化相关模块导入均
   通过，未生成 `__pycache__`。
4. `run_v9.py` 的 gate 顺序独立确认是
   CVD/order 设置 → template identity/render → v9 effective-argv validator
   → v9 GPU preflight → production `Popen`；child environment 继续传播
   numeric CVD 与 `PCI_BUS_ID`。production argv builder 与 v8 除 launcher
   文件名外 byte-equivalent，科学 recipe/config/trajectory/threshold 未改。
5. 8ac5 source identity 仍为 entry 102,269 bytes、test 24,215 bytes、
   runtime manifest 91 files；entry/test/runtime/reward hash 与 v9 expected
   identity 逐项一致。model/input manifest hash 也未变。

## Initialization evidence

### vLLM numeric CVD

原始证据目录：`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v9/raw/remote-vllm-numeric-20260916-211/`。

已安装 vLLM 0.8.1 的真实 converter 将 numeric CVD `2,3` 转为 `[2,3]`；
UUID token 触发已知的 `ValueError: invalid literal for int()`，且
`model_constructed=false`、`engine_initialized=false`、exit 0。v9 没有修改
vLLM。

### Reward callable

原始证据目录：`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v9/raw/remote-reward-init-20260916-211/`。

- `post_init` 调用次数为 1，输入 spec 为 `cls.py:compute_score`，原始
  `reward_function_name` 为 null；派生 name 为 `compute_score`。
- 序列化后的 RewardConfig、local `AutoRewardManager` 和真实 zero-GPU Ray
  worker 均加载/调用 `compute_score`，样例 score 一致；模型未构造、训练未开始。
- `:main` 负例在 validator 和真实 reward loader 两处均拒绝。
- strict source-hash stage 结果：effective config 与 production validator
  为 true；serialized config、local loader、Ray worker 为 false（字段缺失）。
  这正是本验收 blocker，而不是把 callable-only raw 误报为完整通过。

### Numeric PCI GPU preflight raw

原始证据目录：`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v9/raw/remote-gpu-numeric-20260916-211-r2/`。

已对既有 raw 做独立解析：numeric CVD `4,5` 在 `PCI_BUS_ID` host order
中解析为 `84:00.0` / `85:00.0` 两张 RTX 3090，对应 UUID
`GPU-4bd5a062-f6e3-e8bf-83d1-a44675314850` 与
`GPU-ad2d5d4b-c278-e728-c742-6913c7a3437d`；两个真实 Ray worker 同节点、
PID/worker ID distinct，runtime/driver UUID+PCI 和 `/proc/<pid>/stat`
field 22 均可重算，selected GPU release check 为 PASS。第一次选择被外部
作业占用的 GPU-2/3 以 exit 1 的拒绝记录保留，未计为通过。

## Scope boundary

本轮没有执行 C/A/B、模型构造、训练、推理、fresh-process restore、COCO AP
或 paper-faithful reproduction；没有安装依赖、SSH 或重跑新的 GPU。完整
独立 probe 输出见
[raw/acceptance_probe.stdout.json](C:/Users/Administrator/Desktop/RaPO-author/docs/acceptance/FRESH-PROCESS-INIT-COMPAT-V9-20260916/raw/acceptance_probe.stdout.json)，
验收目录清单见
[HASHES.json](C:/Users/Administrator/Desktop/RaPO-author/docs/acceptance/FRESH-PROCESS-INIT-COMPAT-V9-20260916/HASHES.json)。
