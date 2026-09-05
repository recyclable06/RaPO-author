# 作者复现基线的阻断与缺口

> 后续第一性原则复核见 [recheck/REPORT.md](recheck/REPORT.md)：CTAN在非零方差且不触发guard时仍丢失跨任务历史；COCO除计数事实外，已复核标准提示要求全部seen类别而GT仅保留novel类别的评分冲突。两项阻断维持；few-shot抽样配额解释及原始实验身份仍待作者确认。

本轮到手审查已交付，以下阻止的是“作者代码无问题/可正式复现”的声明，并非隐藏未完成的审查命令。

## blocking

- `AUTH-CTAN-001`：跨任务统计重置、warmup/fallback 与论文持续 EMA 不一致；全体 RaPO 入口可达。等待作者解释/修订及用户冻结处理口径。
- `AUTH-COCO-001`：随包正常输入经公开入口产生类别正标注缺失及超过 five-shot 的计数；阻断 COCO 协议复现。等待实际逐顺序数据/标注口径。

## pending evidence

- D-PIPE-ENV-01 / deferred：CTAN/retention 参数通过父进程环境设置，Ray runtime_env 未显式携带；复用已有 Ray 时远程 Runner 可能读到缺失/旧值。尚未做真实 Ray 进程对照，不升级为已确认 P1，也不宣称所有标准启动均受影响。调用链及 CPU 证据见 [pipeline/REPORT.md](pipeline/REPORT.md)。

- 本地现有环境仅 CPU 数值核查；作者依赖栈与 GPU 路径、checkpoint/resume、COCO AP 未运行。
- 没有与整理包绑定的原始作者 commit、逐 seed 命令/配置/结果和模型 revision。
- IN-A 的985清单、COCO4952验证集及 per-task AP 口径需要作者核实；不能在缺证据时自行填补原实验。

## non-blocking P2 / out-of-scope

见 [REPORT.md §6](REPORT.md#6-其他观察与尚未解决的证据缺口)。没有以额外 schema、防恶意输入或未交付 DIL 扩大当前 P1 面。

没有权限/自动审批拒绝阻碍本轮资料审查；`.pytest_cache` 只读清点遇到访问拒绝，已记为未知，未改权限。未尝试未获授权的远程动作。
