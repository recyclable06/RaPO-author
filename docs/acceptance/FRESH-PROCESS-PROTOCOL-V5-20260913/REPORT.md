# R3.1 fresh-process resume v5 独立验收

日期：2026-09-13。角色：`independent acceptance`。

本轮只审查冻结的 v5 诊断候选包、其 declared raw evidence、目标 R3.1
源码身份以及 CPU/static 判定逻辑。不修改 v5 准备包、R3.1 production/test
或旧版 evidence；不启动 Ray、GPU、SSH、模型、训练、推理或依赖安装。

## Verdict

**`NEEDS_PROTOCOL_REVISION`（GPU resume not ready）**。

v5 的包身份、历史 raw 清单、AST、launcher contract 和已有进程关联
fixture 可以独立复核，但候选包当前不能进入远程 parser/zero-GPU 之后的
GPU 门：冻结输入与真实 loader 的两步配方不一致；且 valid actor/anchor
copy 会被自身 fingerprint 判定器当成不相等。除此之外，恢复 exactness、
轨迹比较和 child-install/writer gate 仍有可构造的 false-pass 路径。

本轮没有产生生产代码或测试的修改，也没有把 v5 局部证据解释为正式复现
或 paper-faithful reproduction。

## Frozen identity and independent checks

- v5 candidate：
  `C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v5/`。
  独立复算 `HASHES_V5.json`：36 files / 186,444 bytes，package manifest
  `dc8c703f3facf86d19ca40e80a56f45b7ad21a4cf4c8c007b22aaeb3da27168e`；
  raw 为 4 files / 19,141 bytes，manifest
  `768648a7650f5df39b3bd6af0f0cf4bba98e111d5879374f99ff0b21bd57c14c`。
- v3 bootstrap supplement historical raw 独立复算为 99 files / 744,350
  bytes，manifest `21e8c73a617795a062536a647effbf01b3b6a2b6fae003d733bbbdf1fc59926d`，
  与 v5 新清单逐项一致；旧的 `271e28…` 声明仍未被倒推为已验证。
- frozen R3.1 target entry 为 102,269 bytes，SHA256
  `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3`；
  test reference 为 24,215 bytes，SHA256
  `2bb64dccbce91409840d04344a30a58b76265ae77145ab33b4819a3613b4aadf`；
  runtime source manifest 为 91 files，SHA256
  `947de3842eadb716d241eb4bb4f2fff62f2cfe39305cf03ffd0fbe35abd052e1`。
  三项均与 `EXPECTED_IDENTITY_V5.json` 一致。
- 19 个 v5 Python 文件 AST parse 通过；`launcher_contract_probe_v5.py`
  返回 `PASS_V5_LAUNCHER_C_AB_CONTRACT`；`test_v5.py` 返回
  `PASS_V5_PROCESS_ASSOCIATION_FIXTURES`。
- 独立 acceptance probe 原始输出见
  [`raw/01_v5_acceptance_probe.stdout.json`](raw/01_v5_acceptance_probe.stdout.json)，
  exit code 为 0。该 probe 没有导入 production target、启动 Ray、构造模型
  或使用 GPU。
- 候选包自己的 local zero-GPU raw 记录为
  `BLOCKED_ZERO_GPU_RAY_UNAVAILABLE`（`ModuleNotFoundError: ray`），其
  `zero-gpu-local-judge.json` 为 0 events / `FAIL_V5_ZERO_GPU_PREP`。因此
  没有真实 child propagation 结果可复用；远程 parser/loader/zero-GPU
  任务仍需在其批准环境独立运行。

## Findings requiring revision

### FPP-V5-001：冻结输入不能产生声明的 Task-2 两步配方（硬阻塞）

v5 的 `INPUT_MANIFEST_V5.json` 为 Task 2 提供 2 个样本；模板
`PPO_CONFIG_TEMPLATE_V5.json` 设置 `mini_rollout_batch_size=2`。目标实际
`base._build_dataloader` 在训练路径设置 `batch_size` 为该值并设置
`drop_last=True`，所以完整 Task-2 loader 的长度是
`floor(2 / 2) = 1`，不是 `EXPECTED_IDENTITY_V5.json` 和
`DIAGNOSTIC_CONFIG_V5.json` 声明的 2。独立 probe 记录了
`actual_length_from_frozen_samples=1`、`candidate_expected_length=2`。

目标 production entry 会在 `image_cls_cil_rapo.py:1401-1404` 用
`total_epochs * len(train_dataloader)` 计算每任务步数；v5 候选又在
`argv_validate_v5.py:80-87` 要求这个乘积为 2。因此实际远程 parser 应拒绝
该候选（`total_epochs=1, loader_len=1, updates=1`），即使 parser 依赖可用，
也不能产生 v5 要求的 C/A/B 更新计数。Task 1 的同样两样本/同样 batch 配置
也不会给 A 的两次 update。

返修条件：按冻结输入和真实 builder 重新冻结合法的 `epochs × loader_len=2`
配方，并重新生成包 hash、parser raw 和负例；不能把 `max_steps=2` 当成
loader 证据，也不能通过手造 loader 结果绕过真实 builder。

### FPP-V5-002：actor/anchor 相同状态会被 fingerprint 判成不相等（硬阻塞）

`state_fingerprint_v5.py:122-123` 把传入的 `label` 放进 state-dict digest；
`capture_runtime` 对 actor 使用 `label="actor"`、对 anchor 使用
`label="anchor"`（`state_fingerprint_v5.py:204-208`）。child observer 随后
在 `child_observer_v5.py:235-242` 直接比较这两个 digest，作为
`state["equal"]`。所以两个内容完全相同的 state dict 也产生不同 SHA256。
独立 probe 用同一个 scalar state 验证了该结果：`equal_actor_anchor_hashes_rejected=true`。

full judge 在 `judge_v5.py:222-228` 要求 `equal is True`，因此真实有效的
actor→anchor copy 会被 v5 judge 拒绝。返修条件：用不包含角色 label 的同一
canonical content digest 比较，或显式比较 entry 内容/shape/dtype/bytes；
补一个等状态正例和不等状态负例后重新冻结。

### FPP-V5-003：native/RNG restore 只证明“有完整值”，没有证明恢复到 A 边界

v5 的 full judge 没有把 B 的 restore fingerprint 与 A boundary checkpoint
或 A 的同名 native fingerprint 对账。尤其是：

- `child_observer_v5.py:188-192` 对 `restore_boundary_vllm_rng` 记录的是传入
  的 `payload`，不是 restore 后 `rollout_sharding_manager` 的实际状态；
  `judge_v5.py:219-221` 只检查该值 `available/complete`。
- `state_fingerprint_v5.py:201-208` 在 worker 没有专用 `worker_rng_state`
  属性时，退回捕获当前进程 RNG；这不能证明 checkpoint 中的 RNG 已加载。
- native actor/optimizer/scheduler 和 driver RNG 也只做“完整 fingerprint”
  存在性检查，没有和 A 的 boundary 内容建立逐项 equality 或受控 restore
  对照。

这不改变目标源码已有 checkpoint manager 的实现事实；它说明 v5 acceptance
gate 尚未证明 exact resume。返修条件：在真实 wrapper 中捕获 restore 后的
native manager/worker/vLLM 状态，保存可审查的 A-side expected fingerprints，
并由 judge 对每个 rank、每个组件逐项比较；缺失或只存在输入 payload 时失败。

### FPP-V5-004：trajectory comparator 只比较每组均值，可通过不同轨迹

`trajectory_compare_v5.py:20-37` 只读取 `raw_rewards.mean` 和
`effective_advantages.mean`，没有要求 group fingerprint 完整，也没有比较
逐样本/逐 token 的 digest、组内排列或 update call identity。独立 probe 构造
了 C/B 两步均值相同但 `full_digest` 不同的证据，candidate comparator 仍
返回 `PASS`（`same_means_different_group_digests_trajectory_passed=true`）。

返修条件：先要求确切两步和完整 group evidence，再按冻结 update/call/rank
对齐比较全量 raw/effective tensors 或明确的完整 digest；均值只能作为附加
诊断，不能作为 strict trajectory pass 的唯一判据。

### FPP-V5-005：child install 顺序和 writer 身份不是 fail-closed

`judge_v5.validate_process_association` 将同一 `(pid, process_start)` 的
install report 汇总后检查，但没有要求 install event 的序号早于 wrapper
call。独立 probe 以 seq 1/2 先写 before/after、seq 3 才写 install，
`validate_event_sequences` 和 process association 都通过；这与
`PROTOCOL_V5.md` 明确拒绝 “event calls before installation” 相冲突。

同时 `judge_v5.py:54-59` 只检查 `writer.module` 和 SHA 字符串长度，没有把
writer `path/bytes/sha256` 与冻结的 `event_writer_v5.py` 内容对账。独立 probe
使用不存在的 writer path、1 byte 和任意 64 位 hash 仍通过。这使得
`test_v5.py` 中使用的 fixture writer 也不是实际 writer identity 证明。

返修条件：对每个进程要求 install event 的 seq 严格早于其 calls，并核对
writer 文件的冻结 bytes/hash；安装报告还应与被观测 target/module identity
绑定，不能只检查非空字段。

## Secondary gate observations

- `run_v5.py:183` 在 `run_preflight()` 之前调用 `validate_effective_argv()`，
  后者会 import production entry；而 `gpu_preflight_v5.py:152` 把结果标为
  `checked_before_production_import=true`。当前 import 尚未构造模型，但
  “显式 GPU/Ray gate 先于 production import”的声明与实际顺序不一致，应在
  下一版明确修复或缩窄声明。
- `gpu_preflight_v5.py:117-126` 只验证两个 worker 覆盖 requested physical
  UUID 集合，没有把 worker 的 logical id、`CUDA_VISIBLE_DEVICES` 顺序和
  physical UUID 建立逐 worker 的有序映射；这应在真实 GPU 前再收紧。

## Accepted / not accepted scope

可复用范围仅限：v5 包及历史 raw 的身份清单、目标源码身份、19 文件 AST、
纯 CPU launcher contract，以及其现有正负 fixture 的行为。不能复用为：真实
parser/loader 通过、Ray child observer 传播、GPU preflight 通过、C/A/B
production run、native state/RNG exact restore、两步 trajectory pass 或
paper-level reproduction。

## Required next step

先在 v5 原准备目录的新增版本修复 FPP-V5-001/002，并补齐
FPP-V5-003/004/005 的 fail-closed 判定与负例；保留 v1-v5 原件和本验收原件。
新候选重新冻结后，先由独立任务复核 parser/loader 和 zero-GPU raw，再决定
是否进入 GPU 三腿；在此之前不执行 C/A/B GPU resume。
