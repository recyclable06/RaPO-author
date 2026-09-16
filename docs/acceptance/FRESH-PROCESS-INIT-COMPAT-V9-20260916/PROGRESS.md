# v9 independent acceptance progress

日期：2026-09-16。角色：`independent acceptance`。

已完成：

- 独立复算 v9/v8 package 与 raw manifest；v9 205/4,658,581、raw 128/4,185,383；
  v9/v8 共同 150 路径逐项 byte-exact。
- 独立核对 8ac5 entry/test/runtime/reward source identity、model/input
  manifest、v6 recipe 和 v9 template 最小 delta。
- 正确 cwd 下运行 v9 CPU fixture、C/A/B launcher contract、AST/import probe。
- 独立解析 vLLM numeric no-model、reward init、numeric PCI GPU preflight
  raw；失败尝试保留且未计入通过。

当前 verdict：`BLOCKED_RAY_REWARD_SOURCE_HASH_IDENTITY`。

剩余最小工作：候选需让 serialized/local/real-Ray worker 观测各自独立
暴露并核验 `source_sha256`，然后只重跑受影响的 reward-init raw 与本验收。
在此之前不进入 bounded GPU C/A/B。
