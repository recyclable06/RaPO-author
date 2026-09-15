# Progress — fresh-process resume v5 independent acceptance

日期：2026-09-13。状态：`NEEDS_PROTOCOL_REVISION`。

已完成：

- 独立复算 v5 package/raw manifest：36/36 文件、186,444 bytes 和 4/4 raw
  文件、19,141 bytes 均一致。
- 独立复算 v3 bootstrap supplement historical raw：99 files / 744,350
  bytes，逐文件清单与 `21e8c73a…` aggregate 一致。
- 独立核对 R3.1 production entry、test reference、91-file runtime manifest。
- 独立 AST parse 19 个 v5 Python 文件；运行 launcher contract 和 v5 CPU
  process-association fixtures，均返回 0。
- 发现冻结输入的真实 loader 配方为 2 samples / batch 2 / drop_last，长度
  1，不能满足候选声明的 `total_epochs=1 × loader_len=2`。
- 用同内容 actor/anchor state、call-before-install、伪 writer、均值相同但
  digest 不同的轨迹构造判定器反例，记录 FPP-V5-002 至 FPP-V5-005。

未完成且本轮明确不执行：远程真实 parser/config/loader、零 GPU Ray child
probe、GPU preflight、C/A/B、模型构造、训练、推理、SSH、安装、commit/push。

证据入口：`REPORT.md`、`acceptance_probe.py`、`raw/01_v5_acceptance_probe.stdout.json`。
