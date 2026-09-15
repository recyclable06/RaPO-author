# R3.1 fresh-process resume v6 独立验收

日期：2026-09-14。角色：`independent acceptance`。

本轮只审查冻结的 v6 诊断候选包、候选包声明的 raw evidence、冻结目标源码身份和 CPU/static 判定逻辑。未修改生产源码、生产测试、v6 候选或既有 evidence；未启动 GPU、Ray 训练、模型、推理、SSH 或依赖安装。

## Verdict

**`READY_FOR_BOUNDED_GPU`**。

v6 的包清单、raw 清单、冻结 R3.1 目标身份、解析器/loader 远程证据、真实零 GPU child observer 证据以及 CPU 正负判定均独立通过。它只获得进入受控双 GPU C/A/B 门的资格；本轮没有 GPU preflight、完整 C/A/B、native state/RNG exact restore 或 trajectory 结果，因此不能据此宣称 scientific acceptance、paper-scale 或 paper-faithful reproduction。

## Frozen identity and package integrity

- 候选目录：`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v6/`。
- 独立复算候选包为 59 files / 4,268,936 bytes，self-excluded package manifest SHA256：`60e5d5ee5b161f212466976af1f7689a632dbeffb0911615a27440115365ce54`。
- 独立复算 raw 为 26 files / 4,068,026 bytes，raw manifest SHA256：`0cf3c8256e0b0797fc48ba20fa7fa7eb7dc5296296a7091a14b8258c59229f1ef`。
- 冻结目标为 `C:/Users/Administrator/.codex/worktrees/8ac5/RaPO-author`：production entry 102,269 bytes / `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3`；test reference 24,215 bytes / `2bb64dccbce91409840d04344a30a58b76265ae77145ab33b4819a3613b4aadf`；runtime source manifest 91 files / `947de3842eadb716d241eb4bb4f2fff62f2cfe39305cf03ffd0fbe35abd052e1`。三项均与 v6 expected identity 一致。
- 候选包 20 个 Python 文件 AST parse 通过。

完整机器可读复核输出见 [`raw/acceptance_probe.stdout.json`](raw/acceptance_probe.stdout.json)；本验收目录的自排除清单见 [`HASHES.json`](HASHES.json)。

## Independent gate results

1. `test_v6.py` 返回 `PASS_V6_PROCESS_AND_DIGEST_FIXTURES`；完整 group 正例、重复序列/拆分 rank/不完整 before-after 负例、label-free equal digest 正例和 unequal content 负例均通过。
2. `launcher_contract_probe_v6.py` 返回 `PASS_V6_LAUNCHER_C_AB_CONTRACT`。
3. 保留的远程 parser raw 返回 `PASS_PARSER_CONFIG_LOADER_ONLY`，且 probe/result 完全一致：C/A/B identity hash 相同，Task 1/2 实际 loader length 均为 1，`total_epochs=2`，每任务 updates 均为 2，`batch_size=2`、`drop_last=true`；`model_constructed=false`、`ray_started=false`、`training_started=false`。
4. 远程 zero-GPU raw 的 `result.json`、原 judge 和 local recheck 都是 v6 pass；我重新从 12 个 event files 读取 129 个事件并调用冻结 v6 judge，独立结果仍为 `PASS_V6_ZERO_GPU_PREP`，`sequence_ok=true`、`process_association_ok=true`、`reasons=[]`。
5. 零 GPU 事件由两个真实 `ray_worker` OS process 产生；每个 worker 都有四个实际 target-module install reports 和 11 个目标 wrapper 调用，所有事件使用同一份 `event_writer_v6` bytes/hash。远程 install module 的四个 bytes/hash 逐项与冻结目标源码相符。
6. 额外 CPU 负例确认：install seq 晚于 call 会被拒绝；伪造 writer path/bytes/hash 会被拒绝；观察 label 不会改变相同内容 digest；改变内容会改变 digest。

这些检查覆盖了 v6 本轮声明的 loader 配方、真实 child-side 安装、install-before-call、writer identity、完整 before/after 关联、label-free state digest 和 zero-GPU fail-closed 准备门。边界 exact comparison、actual post-load state、两步 C/B trajectory 仍必须由后续 bounded GPU run 提供真实结果；本轮不预先替代这些结果。

## Observation

远程 worker 返回的 bootstrap 子报告内部仍写有 `schema_version=5`，但其外层事件由 v6 writer 写为 schema 6，事件级 schema/writer/judge 检查全部通过。该项记录为 metadata drift，不构成本轮进入 bounded GPU 的阻塞；若后续收紧 evidence schema，应在下一候选中统一为 6。

## Remaining scope

下一步仅是按候选 `COMMANDS_v6.md` 在获授权的 approved environment 中执行显式两张 3090 的 GPU preflight，再运行新鲜 C/A/B roots，并要求唯一完整诊断 pass `PASS_V6_FULL_C_AB`。在该结果出现前，不得把本验收 verdict 写成恢复 exactness 或论文复现结论。
