# FPP-V9-REWARD-IDENTITY 独立补充验收

日期：2026-09-16。角色：`independent acceptance`。

本轮只复核 v9 唯一未闭合的 reward source identity 证据：实际
`RewardConfig` 解析后的 callable、`ray.cloudpickle` 序列化 round-trip、
本地 `AutoRewardManager` loader、真实 zero-GPU Ray worker 是否各自从
loaded callable 定位源文件并独立计算同一 `source_sha256`。没有重跑 42 项
CPU、GPU、SSH、model、training 或 C/A/B，也没有修改候选或既有验收。

## Verdict

**组合结论：`READY_FOR_BOUNDED_GPU`。**

原 v9 验收的唯一 blocker
`BLOCKED_RAY_REWARD_SOURCE_HASH_IDENTITY` 已由本补充闭合。该结论只表示
可以进入既定的受控 bounded GPU C/A/B；不代表 fresh-process restore、
科学复现、COCO AP、paper-scale 或 paper-faithful 结果已经通过。

## Supplement integrity

- 补充候选：`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/acceptance/FRESH-PROCESS-INIT-COMPAT-V9-20260916/v9-reward-identity-supplement-20260916/`。
- supplement self-excluded package：14 files / 47,813 bytes；package
  manifest `2935c0c6ff3d34adc44d727c2356b71b22d73714becc28b360f443e445737c56`；
  `HASHES_SUPPLEMENT.json` self SHA256
  `da6ad19c30cf5cffc5ed47b5b1ef7983b9d9008c21e0ad57e7c350b739eb789a`。
- raw subset：8 files / 21,382 bytes；raw manifest
  `c978ac2c9910fed038b2f936fb5a78cc0be3b69fa8f627d6d526f2d2820a97ca`。
  本验收独立逐项重算 supplement file list、bytes、SHA-256 和两个 compact
  manifest，全部与 `HASHES_SUPPLEMENT.json` 一致。
- supplement 只包含 probe、配置/引用、报告和 raw；未复制
  `run_v9.py`、`PPO_CONFIG_TEMPLATE_v9.json`、`EXPECTED_IDENTITY_v9.json`
  或 `HASHES_v9.json`。

## Frozen v9 and previous acceptance binding

本补充独立重新读取并校验 v9 候选：`HASHES_v9.json` self SHA256
`45f79cbf83d004b6fd05c4e1ef61fe2f5b296dba1771aae24e45e570b890ee39`；
package 205 files / 4,658,581 bytes，manifest
`3767c12fd6bc90ef43479486a057ae92b557aaa4ec276c12d5713871597bae7a`；
raw 128 files / 4,185,383 bytes，manifest
`9d41841454ac9cc9dddd226f8d52613514675a5ab04b5188d2cd0b1f5736485c`。

原 v9 验收目录
`C:/Users/Administrator/Desktop/RaPO-author/docs/acceptance/FRESH-PROCESS-INIT-COMPAT-V9-20260916/`
的 self-excluded manifest、probe 输出和原 blocker 均未改变；原 v9 的其它
CPU/static、vLLM numeric、PCI GPU mapping、v8 inheritance 和 scientific
recipe 结论按原 hash 复用。本补充使用实际冻结 `run_v9.py` renderer/argv，
不是新的 launcher 版本。

## Independent probe-source review

`reward_identity_supplement_probe.py` 已 AST parse，并独立检查到：

- `actual_callable_identity()` 从 callable 本身经
  `inspect.getsourcefile`/`inspect.getfile` 得到真实源文件，再对
  `source_path.read_bytes()` 做 SHA-256；期望值只在实际计算后比较。
- stage record 先从实际 loaded `manager.reward_fn` 取得 identity，再真实调用
  `compute_score`；没有从 expected metadata 手填 stage hash。
- serialized stage 使用实际 `ray.cloudpickle.dumps/loads` 后再构造真实
  loader；Ray worker 也独立执行 source lookup 和 `hashlib.sha256`，不是回显
  driver 值。
- missing/mismatched `source_sha256` negative checks 均拒绝；`:main` 实际
  loader 也拒绝。probe 使用冻结 `run_v9.py` 的 renderer/argv，Ray 为
  `num_gpus=0`，并在 finally 中 kill actor、shutdown Ray。

## Raw reward identity evidence

原始目录：
`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/acceptance/FRESH-PROCESS-INIT-COMPAT-V9-20260916/v9-reward-identity-supplement-20260916/raw/reward-identity-20260916-211/`。

远端命令使用已安装 diagnostic runtime、空 `CUDA_VISIBLE_DEVICES`、
`CUDA_DEVICE_ORDER=PCI_BUS_ID` 和 private zero-GPU Ray namespace；exit 0，
Ray 已释放，`gpu_used=false`、`model_constructed=false`、
`training_started=false`。

有效链路的 `post_init` 次数为 1，输入 spec 是
`cls.py:compute_score`，原始 name 为 null。以下三阶段都从实际 loaded
callable 得到相同 identity：

| stage | callable | actual relative path | source SHA-256 | sample overall |
| --- | --- | --- | --- | --- |
| `serialized_reward_config` | `compute_score` | `examples/reward_function/cls.py` | `028b9c9721c0c1d80b0ae3652aec31c8fb458827ca4d079b1253b537099978a1` | `2.0` |
| `local_reward_loader` | `compute_score` | `examples/reward_function/cls.py` | `028b9c9721c0c1d80b0ae3652aec31c8fb458827ca4d079b1253b537099978a1` | `2.0` |
| `ray_worker_roundtrip.worker_report` | `compute_score` | `examples/reward_function/cls.py` | `028b9c9721c0c1d80b0ae3652aec31c8fb458827ca4d079b1253b537099978a1` | `2.0` |

实际 cloudpickle payload 为 272 bytes。missing hash 与全零 mismatch 两个负例
均 rejected；`:main` 派生 name mismatch 且真实 reward loader 抛出缺少
`main` callable 的错误。stdout summary、完整 `probe-result.json` 和 exit
marker 相互一致。

## Scope boundary and next gate

本轮只补齐 reward identity 证据，没有新增 GPU 或模型操作。组合后 v9 可
交给后续已授权的 bounded GPU C/A/B 任务；该任务仍须独立保存新鲜输出并
继续遵守原 v6 boundary、state、trajectory 和科学结果门槛。

完整本轮 probe 输出见
[raw/acceptance_probe.stdout.json](C:/Users/Administrator/Desktop/RaPO-author/docs/acceptance/FRESH-PROCESS-V9-REWARD-IDENTITY-20260916/raw/acceptance_probe.stdout.json)，
本轮目录清单见
[HASHES.json](C:/Users/Administrator/Desktop/RaPO-author/docs/acceptance/FRESH-PROCESS-V9-REWARD-IDENTITY-20260916/HASHES.json)。
