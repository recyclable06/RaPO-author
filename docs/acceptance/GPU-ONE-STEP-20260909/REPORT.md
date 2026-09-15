# attempt-15 独立验收报告

更新：2026-09-09。角色：独立验收。对象：`effective-update-20260909/attempt-15` 的冻结诊断证据，以及整合工作树 `codex/integrate-accepted-fixes` 的只读源码身份。

## 结论

结论为：`PASS_LIMITED_EFFECTIVE_UPDATE_WITH_SCOPE_EXCEPTION`。

“一步有效更新”本身通过：attempt-15 走完了真实 world-size-2 `trainer.fit()`、CTAN/EMA、actor optimizer update、anchor copy、生产 vLLM sync 和 post-sync 图文生成；独立探针没有把 sampled equality 当作全参数 equality，也把 sampled delta 与 summary-stat delta 分开记录。

但“本轮不写 checkpoint”的诊断边界未通过，因此不能把整个诊断包写成无条件 PASS。原始 JSON 的 `no_checkpoint_write=true` 只是运行结果中的声明；`run.stdout` 第 575–576 行实际出现了两 rank 的 `Saving model to .../outputs/unused-checkpoint-path/global_step_1/...`。整合源码 `verl/trainer/ray_trainer.py:702-703` 在 `save_freq <= 0` 时无条件调用 `_save_checkpoint()`，而探针把 `save_freq` 设为 `-1`，正好触发该分支；`verl/utils/checkpoint/fsdp_checkpoint_manager.py:90-103` 随后执行 `torch.save(...)`。当前本地副本没有远端 `outputs` 内容，不能据此证明文件最终保留或大小，但保存调用已经被运行日志和生产保存实现共同证明。

因此，本报告接受“有限的一步生产更新证据”，不接受“无 checkpoint 写入的干净诊断契约”。这不是对生产算法的修复，也不关闭阶段 5；跨任务与恢复验证仍为 `NOT PASSED`。

## 独立核对结果

证据身份先通过：诊断 `HASHES.json` 声明的 53 个文件全部存在，字节数和 SHA-256 全部匹配；attempt-15 原始结果 SHA-256 为 `994ddb9c7795211e0c55187d7467a8f0bdbe9721141f99c1c7a3513e960fec4a`。独立探针与集成身份为：诊断探针 `947d367c7302e24df6a12bb222a7bec58530c2ceabb928796d1fd56e0b02e8f7`，集成清单 `6514f4dca401ffc805ae57031d1926f742e531ce0fbb981448315538ade8b0b1`，其中 6 个算法文件和 4 个测试文件的当前 hash 均与清单记录一致。

运行身份记录为：

- source：`/mnt/conda/zhenglifeng/rapo-author-diagnostic-20260908/source`
- model：`Qwen2-VL-2B-Instruct-895c3a4`
- inputs：`/mnt/conda/zhenglifeng/t/eu-p1-20260908/inputs`
- host：`gpu-211`；world size：2；物理 GPU：4、6；Ray/CUDA 映射与预期 UUID 一致
- Python 3.11.6、PyTorch 2.6.0+cu124、Ray 2.46.0、vLLM 0.8.1（由冻结运行记录提供）

生产链静态复核通过：诊断代码使用真实 `PersistentRunner`、原始 `trainer.fit()`、原始 actor update、原始 advantage hook 和原始 `_sync_weight_to_vllm`；同步包装器只在 `loaded=true` 的生产 wake/load 边界观察，并调用原方法。集成源码中 `_sync_weight_to_vllm()` 继续执行实际 `model.load_weights(...)`，`trainer.fit()` 继续调用 `update_actor`，RaPO trainer 的生产 `fit()` 继续安装 CTAN hook。没有发现直接用 `load_weights` 替代生产同步的诊断 shortcut。

有效更新证据如下：

- CTAN hook 调用 1 次；优势 1,536/1,536 finite，1,029 个非零；EMA `update_count` 为 `0 → 1`。
- 两个 actor rank 的 gradient norm 均为 `36.75`；actor log-prob delta 为 1,536/1,536 finite，955 个非零，最大绝对值 `1.8301353454589844`，平均绝对值 `0.02675141580402851`。
- 16 个 rank/flat actor sampled parameter records 均发生变化；独立计算得到 16,384 个记录 sample、269 个 sample 值变化，sample 最大 delta `1.9073486328125e-06`。这只证明记录的 sparse samples，不证明全模型逐值变化。
- 初始 actor/anchor 的 16,384 个记录 sample 相等；旧 anchor 在 actor update 前后保持相等；更新后的 actor 与旧 anchor 有差异；actor-to-anchor copy 后新 anchor 的 16,384 个记录 sample 与更新后的 actor 相等。上述 equality 均明确标为 sampled equality。
- 选定的 trainable common key 为 `visual.blocks.0.attn.proj.bias`。生产同步前，actor 与 vLLM 的 32 个记录 sample 有差异，sample 最大 delta `1.9073486328125e-06`；相应 exact summary statistics 的最大差异为 `4.76837158203125e-06`。生产同步后 sample delta 和 summary-stat delta 均为 `0`；这仍不是全参数逐值 equality，`summary_scope=exact` 只说明统计量覆盖该参数，记录的 value array 仍是抽样值。
- post-sync generation 为 batch 4、response tokens 384（`4 × 96`），response tokens 全部 finite；运行 stdout 同时出现 Qwen2-VL、`image_key: images`、输入路径和 batch-4 generation marker，支持这是实际图文数据路径而非空 mock。

## CUDA 与资源边界

attempt-15 的 `run.exitcode` 为 `0`，stderr 未发现 CUDA illegal-memory-access、Traceback、OOM 或 RuntimeError 记录；Ray shutdown 为 true。结束资源记录中任务使用的 GPU 4、6 无 compute app 且各剩余约 4 MiB。早期 attempt-9、11、13 的 CUDA illegal-memory-access 证据保留在原诊断目录，本验收不把它们改写成 attempt-15 的失败，也不把成功轮次扩展成多轮稳定性结论。

## 阶段判定与解除条件

阶段 3 的“有限一步有效更新”证据：`PASS`，附 checkpoint scope exception。

阶段 5 的跨任务与恢复 gate：`NOT PASSED`。当前证据没有证明 Task 1→Task 2 的连续 EMA、anchor、optimizer/scheduler、任务游标、随机状态和精确中断恢复。

要把本诊断包提升为干净验收，最小解除条件是重新执行一个保持同一源码、模型、输入和 GPU 身份的独立诊断，并在诊断层显式阻断训练器的最终 `_save_checkpoint()` 分支，同时保留可审查的“未调用/无输出”证据；或者明确把 checkpoint 输出纳入本轮授权和证据清单。当前角色只做验收，没有执行 GPU 重跑、源码修复、删除或远端操作。

详细机器可读证据见 [`independent-evidence.json`](independent-evidence.json)，起止 hash 对照见 [`hash-start-end-compare.json`](hash-start-end-compare.json)；独立探针源码见 [`independent_probe.py`](independent_probe.py)；原始 attempt-15 仍在其冻结诊断目录中，未被本验收改写。
