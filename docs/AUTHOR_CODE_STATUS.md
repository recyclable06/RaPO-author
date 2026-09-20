# 作者代码当前状态

更新：2026-09-20。根目录现已整合经过独立代码/CPU验收的修订，逐文件身份见 [INTEGRATION_HASHES.json](INTEGRATION_HASHES.json)。作者原始204文件及论文身份由 [BASELINE.json](BASELINE.json) 和标签 `author-drop-20260904` 保留。

**尚未完成论文复现。** 当前上传内容是作者基线、已验收的局部修复和研究过程证据，不包含正式复现结果或模型权重。

## 当前实现与验证范围

| 项目 | 根目录当前行为 | 已验证与待验证 |
|---|---|---|
| CTAN / AUTH-CTAN-001 | 从Task 1首个优势batch开启；EMA跨任务连续传递，避免边界覆盖；retention仍从Task 2开始 | 独立代码/CPU验收通过，真实GPU有效更新及同进程跨任务有有限证据 |
| COCO / AUTH-COCO-001 | 开启seen标签提示时，训练allowed_classes使用全部seen类别 | 提示与奖励GT局部修复通过；five-shot共现配额、监督时机及完整AP评估仍待验证 |
| 图像任务边界恢复 / CAND-RESUME-CIL-001 | R3.1支持完整任务结束后发布完整边界，并由新进程进入下一任务 | [42项独立CPU检查通过](acceptance/CIL-RESUME-CPU-R31-20260911/REPORT.md)；v9 R2连续C完成4/4更新，A完成2次并发布marker，但A主进程RNG观察缺失；B停在anchor初始化，尚未观测到checkpoint恢复/fit，最终exit-6；恢复验收未通过 |
| GPU链路 | 既有环境下完成有限有效更新和同进程Task 1→2 | 见[一步验收](acceptance/GPU-ONE-STEP-20260909/REPORT.md)与[连续任务验收](acceptance/CONTINUOUS-TASK12-20260909/REPORT.md)；不扩大为全参数、完整轨迹或论文规模通过 |

当前恢复诊断采用同机两张RTX3090，比较连续运行C与退出后恢复A/B，每任务两次真实更新。要求边界完整状态精确恢复，后续奖励、优势、retention指标按预先冻结容差比较；不要求后续随机轨迹逐张量相等。

v9及奖励身份补充已获独立组合结论 [READY_FOR_BOUNDED_GPU](acceptance/FRESH-PROCESS-V9-REWARD-IDENTITY-20260916/REPORT.md)。R2连续C四次更新、exit0及两份checkpoint内容清单已获独立认可。最新[共享原件独立复核](acceptance/FRESH-PROCESS-R2-SHARED-20260917/REPORT.md)纠正此前B“恢复超时且被监督SIGTERM”的摘要：实际已初始化模型/FSDP/vLLM/persistent workers，两个rank都进入init_anchor但无返回事件；未观测到run_task、native restore或fit。child最终exit-6，supervisor记录child_term_sent=0/child_kill_sent=0，无owner的聚合SIGTERM行不能归因给监督程序。内部abort根因尚未确定，只补取两相关worker日志，不重跑B。A的marker引用driver/EMA/vLLM文件已齐并校验一致，但run_task观察调用为0，仍缺实际post-publication driver RNG证据，本地定位观察器。生产源码和科学门不改，211现场资源释放仍UNCONFIRMED。历史记录与勘误见 [诊断评审记录](FRESH_PROCESS_PROTOCOL_REVIEW.md)，任务以 [协调台账](TASK_COORDINATION.md) 为准。

## 后续门槛

**当前卡点是启动管理脚本的Linux实际验证，尚未启动新的A训练。** 观察器真实Ray零GPU调用、A启动前文件校验、参数一致性及R2超时helper已获独立确认；FINAL集中修订的005–010亦已[静态复核](acceptance/FRESH-PROCESS-A-PRIVATE-RAY-FINAL-20260920/REPORT.md)。这些结论不等于实际进程生命周期通过。

211已执行外置direct-import的Linux纯Python检查，未覆盖冻结test-results，也未启动真实Ray。实际supervisor在head阶段报 `private Ray executable identity changed`，未写RUNNING record、未进入launcher。外层测试却返回PASS，因为它接受了任意FAIL后的空清理集合；该PASS不采纳。日志未保留前后两个executable值，启动exec切换只是待验证假说。head_returncode为null、owned列表为空，因此all_owned_processes_gone字段也不能单独证明进程已释放。原始日志正在封存并独立定位，原件不改，不无变化重跑。

真实SIGINT/SIGTERM外置harness已准备，仅语法/静态检查通过，尚未在Linux执行。它要求实际RUNNING及head/launcher/后代身份齐备后才发送信号，不会把提前失败算作通过。独立审查已确认最小修复范围，已派独立整改子任务在隔离分支另存新candidate：启动exec身份稳定后锚定且持续严格核验、head已启动时不得把空登记集合当清理成功、Linux测试必须证明实际ready/launcher/后代和预期timeout。训练源码/观察器/旧证据保持不变。修订增量验收后执行Linux检查和真实零GPURay生命周期，之后复核双卡并运行A两步。实际发布后driver RNG仍是A运行验收项；B内部abort未解决，C已接受结果不重跑。

2026-09-19 22:18:44资源快照中211/207均可访问，211七张3090各仅1MiB、无compute-app，/mnt/conda剩余约1.78TiB、211本地盘约285GiB；这是历史快照，实际GPU启动前重核。9月20日211 CLI检查确认应使用既有环境bin/ray，不能用python -m ray。新数据写个人/mnt/conda目录或节点本地盘，不删除旧权重/证据。

旧v9运行的[独立超时复核](acceptance/FRESH-PROCESS-V9-GPU-TIMEOUT-20260916/REPORT.md)已确认Task1两次更新；留存日志未见明确OOM或运行异常，检查点保存约4.4分钟。远端checkpoint目前只有文件名称/大小清单，没有内容完整性验收；新运行需补内容hash与完整结束日志。旧交付JSON格式缺陷已登记，原始证据保持不变。

1. 执行并独立验收有限GPU恢复对照；GPU映射与进程身份的增量就绪验收已完成。
2. 冻结ImageNet-R首轮单seed完整实验的数据、任务划分、模型、配置、评估和资源预算。
3. 在具体正式实验范围获确认后启动，再扩展多seed；检测任务另行核实COCO数据与AP口径。

论文对应的原实验commit、逐seed命令/原始结果和完整环境身份仍未齐备。任何已知论文与代码差异继续披露，不把“修订实现可运行”表述为原论文结果已复现。

## 证据入口

- [整合说明](INTEGRATION_HANDOFF.md)：本次根目录的代码来源、保留范围与验证。
- [原始到手审计](audit/2026-09-04-author-intake/REPORT.md)：只描述作者基线，历史结论不改写。
- [CTAN验收](acceptance/AUTH-CTAN-001/REPORT.md)、[COCO验收](acceptance/AUTH-COCO-001/REPORT.md)、[恢复R3.1接收](CIL_RESUME_R31_ACCEPTED.md)。
- [复现计划](REPRODUCTION_NEXT_STEPS.md)、[资料地图](PROJECT_MAP.md)。

历史报告中的本机/远端绝对路径是当时证据来源；它们不保证在另一台机器可访问。模型、checkpoint、原始媒体与服务器运行目录不随本仓库发布。
