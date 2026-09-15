# R3.1 fresh-process resume v4 / v3 补证独立验收

日期：2026-09-13。角色：`independent acceptance`。本轮只复核已冻结的 v4 局部诊断和 v3 bootstrap supplement；不修准备包、不修改 R3.1 production/test，不执行 GPU、Ray、SSH、安装、模型构造、训练、推理、commit 或 push。

## Verdict

`LIMITED_ACCEPTANCE_NOT_GPU_READY`。

v4 的 parser contract 和 canonical production-module child observer 证据在其声明范围内可接受：v4 package/raw manifest 可独立复算，C/A/B parser-only 正负例、真实 canonical import、child wrapper identity、原函数一次调用和进程内序列检查均有一致原始证据。v3 supplement 也可复核其 99 个 raw 文件的数量/总字节以及 9 个具名 key file，但其 raw 聚合 digest 没有随包提供逐文件 manifest 或算法，不能独立复算。

本轮没有发现 v4 已声称的 parser/child 局部结果与 raw 互相矛盾；发现一个会削弱 fail-closed 语义的 v4 judge 覆盖缺口，以及一个 supplement 证据清单缺口。二者在作为 GPU 前置门之前应修订。v4 没有交付完整 launcher、native checkpoint/RNG/anchor/vLLM 状态观测、真实 FSDP worker 训练或三腿恢复，因此不能据此放行 GPU。

## Frozen identities and independent checks

- v4 准备包：`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v4/`；`HASHES_V4.json` self SHA256 `6e6d1673e057cee982410eced9ed0feba947a042a4fca463f75956ba0cade586`，声明 30 files / 218524 bytes；本探针逐项复核 30/30、package manifest 和 17 个 raw file / 143656 bytes raw manifest 均一致。
- v3 supplement：`.../v3-bootstrap-supplement/`；`HASHES_SUPPLEMENT.json` self SHA256 `2a71bbadf3d83645b641d01ec6076ea5b501877dda6808217cbecfd253738b91`；9/9 key files bytes/hash 一致；raw 实际 99 files / 744350 bytes，与声明一致。
- v3 冻结身份仍为 `HASHES_V3.json` SHA256 `85ecc63edfac12d151ec83c391a70eee932f610de128b14208c9c308bf27d6bd`；R3.1 target entry `examples/baselines/img_cls_cil/image_cls_cil_rapo.py` 为 102269 bytes，SHA256 `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3`。
- 本轮独立探针原始输出：`raw/01_v4_acceptance_probe.stdout.json`；退出码为 0。探针只读 v4/supplement/v3/target raw 和源码，并在临时目录执行 judge CPU synthetic negative；不启动 Ray。

## Accepted limited evidence

### Parser contract

`raw/parser-result-v2.json` 报告 C/A/B 三腿 parser-only 正例、缺 `--cil-cfg` 负例和冻结 config binding hash mismatch 负例均符合预期；A/B/C identity SHA256 均为 `8459ab72f1185ba4fa275455d9743b05cdac48bd97a54a45c60f260b1993aa13`。独立探针确认：

- actual author entry 被导入，但没有 model construction，也没有 Ray；
- v4 parser-only effective config 使用 `total_epochs=1`、`max_steps=2`，且作者 `TrainerConfig.total_epochs` 确实声明为 `int`；
- `image_cls_cil_rapo.py:1401-1404` 在实际 runner 中会用 `total_epochs * len(train_dataloader)` 覆盖每任务步数。

因此 v4 修复了 v3 的 `total_epochs=null` parser 类型不兼容，并证明了 parser/identity 入口；它没有证明每任务实际恰好两次更新。v5 必须在合法整数 epochs 下，用实际 frozen loader 长度验证乘积为 2；不能把 parser-only `total_epochs=1` 当成最终训练配置。

### Canonical child observer

v4 raw Ray 结果报告：zero-GPU、canonical import、63 events、12 process files、3 个目标 modules、11 个实际 method labels；每个事件的 writer identity/`writer_seq` 和每个 PID 内序列均通过独立复核。所有 observed wrapper after event 的 `original_call_count` 为 1，且保留 original callable module identity。

证据边界如下：

- 两个 rank-labelled `ray_worker` 是 v4 `RawChildProbe` actors；它们对真实 canonical module/class 做 import-hook patch，然后用 `object.__new__` dummy receiver 调用 8 个 inert labels。它们不是 `FSDPWorker` 训练、FSDP state 或真实 worker 初始化证据。
- 真实 `PersistentRunner` actor 只执行 `run_task(None, ...)`，在 trainer 为 `None` 的早期路径抛出预期 `AttributeError`；这证明真实 runner class 的 wrapper/原函数路径，不证明 dataloader、model、worker、checkpoint、vLLM 或 anchor 状态。
- v3 supplement 的 fresh-child raw 仍显示 4 个真实目标方法没有 v3 observer marker，状态 `NOT_INSTALLED_FRESH_RAY_CHILD`；其后 v4 的 canonical import-hook 结果是新的 v4 局部证据，不应倒推 v3 runtime_observer 已被修复。

## Findings requiring revision before relying on the gate

### FPP-V4-001：judge 将 wrapper labels 跨 PID/rank 全局拼接（P2）

`judge_v4.py:_check_calls()` 将 `(pid, process_start, label)` 的记录汇入一个全局 `observed` label 集合，然后只检查 `REQUIRED_LABELS - observed`；它没有要求每个指定 role/rank 自己覆盖 required calls，也没有把 wrapper call 与对应 child install report 在同一进程绑定。独立 CPU synthetic negative 将 required labels 拆到两个 worker rank（每个 rank 缺一部分），但 `judge_v4.evaluate()` 仍返回 `PASS_V4_REAL_CHILD_OBSERVER` 且 `reasons=[]`。

当前 v4 raw 恰好显示两个 `RawChildProbe` rank 都各自记录了同一组 8 个 inert labels，故这不是对本次 raw 的篡改或现成 false pass；它是判定器的 fail-closed 覆盖缺口。返修条件：按明确的 role/rank/process scope 分组检查 required labels、install report、before/after pair 和原函数一次调用，并区分 `RawChildProbe` 诊断角色与真实 FSDP worker 角色。修订前只能复用 v4 的“canonical child observer 局部证据”，不能把 judge PASS 当成所有 rank 的生产 hook gate。

### FPP-V4-002：v3 supplement 的 99-file raw aggregate 不可独立复算（P2，证据清单）

`HASHES_SUPPLEMENT.json` 只提供 9 个 `key_files` 的逐文件 bytes/hash，以及 `raw_file_count=99`、`raw_total_bytes=744350` 和一个 `raw_manifest_sha256`；没有 99 项逐文件 manifest，也没有说明聚合输入的路径格式、排序、字段顺序或 canonicalization。独立复核确认 99 files/744350 bytes 和 9/9 key files 一致，但按 v4 已可复算的 compact `[path, bytes, sha256]` manifest（含 `raw/` 前缀）得到 `21e8c73a617795a062536a647effbf01b3b6a2b6fae003d733bbbdf1fc59926d`，不是声明的 `271e28a876cbe6734463aabd5738cd44f549da8cbe463e507b3ee3db6cadbc78`。

这不能单独证明 raw 被篡改；它证明的是当前包不足以让另一验收者从目录复算该 aggregate。返修条件：附上 99 项逐文件 manifest 并冻结 canonical hash 算法，或提供可重复的生成命令和其原始 manifest 输出。补齐前，supplement 的结论可作为 key-file/raw-count 证据使用，不能把 aggregate digest 当作已独立验证的全量身份。

## Deferred integration boundary (not a v4 failure)

以下是 v4 明确未交付、应由 v5 完整集成，不作为本轮额外 failure：

- 完整 C/A/B launcher 调用 `main()`、实际 output/boundary marker、driver/Ray runner/每个真实 FSDP worker 的 role/rank 对账；
- native actor/optimizer/checkpoint manager、driver RNG、worker RNG、anchor、vLLM stream 的完整 before/after fingerprint 和恢复前后逐项比较；
- 实际每任务恰好两次 update 的 loader-size 证明；
- GPU/FSDP、模型构造、训练、推理、COCO AP、exact resume 和论文级结果。

这些缺失不能被解释成“v4 失败”，但也不能被 v4 的局部 PASS 代替。v5 应复用 v4 已核实的 parser/identity 方法和 canonical child import 机制，并把完整状态观测、launcher 和逐 rank 判定接通后再重新独立验收。

## Execution boundary

本轮没有启动 GPU、Ray、SSH、安装、模型构造、训练或推理；没有修改 v4、v3 supplement、v3、production 或 tests。验收只新增本目录工件。
