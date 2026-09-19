# FINDING-A-DRIVER-RNG-002

状态：`OPEN — observer-derived boundary proof incomplete`  
范围：Fresh-process R2 leg A。

## 判定

A 的 Task-1 marker 与 marker-linked subordinate artifacts 已进入共享包并通过 SHA256 核对；但 A 的 boundary-derived proof 仍不完整，不能关闭 finding。

## 证据

- `evidence/A-boundary/task1-complete.json`：状态 complete，`global_step=2`，`next_task=2`。
- marker 引用的 `driver_rng.json`、`ema_task1.json`、`vllm_rng_rank_0.json`、`vllm_rng_rank_1.json` 均存在且 SHA256 与 marker 一致。
- `evidence/A-root/boundary-expected.json`：`complete=false`，错误为 `A actual post-publication driver RNG capture is missing`。
- A observer 共 81 文件、435 条记录；实际 `PersistentRunner.run_task` wrapper call 为 0，未形成 post-publication driver RNG expected 记录。

## 解释

这次补充关闭了“marker-linked 文件没有随包提供”的交付缺口，但没有提供足够证据证明 A 的 post-publication driver RNG 观测已经发生。现有材料不支持把它直接升级为生产实现缺陷，也不支持把 A 标为完整通过。

## 最小下一步

补齐实际 `PersistentRunner.run_task` 调用与 post-publication driver RNG 观测，或提供同等强度、可由 frozen observer 代码独立核验的证据；在此之前保持 `OPEN`。

