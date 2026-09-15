# 作者代码当前状态

更新：2026-09-14。根目录现已整合经过独立代码/CPU验收的修订，逐文件身份见 [INTEGRATION_HASHES.json](INTEGRATION_HASHES.json)。作者原始204文件及论文身份由 [BASELINE.json](BASELINE.json) 和标签 `author-drop-20260904` 保留。

**尚未完成论文复现。** 当前上传内容是作者基线、已验收的局部修复和研究过程证据，不包含正式复现结果或模型权重。

## 当前实现与验证范围

| 项目 | 根目录当前行为 | 已验证与待验证 |
|---|---|---|
| CTAN / AUTH-CTAN-001 | 从Task 1首个优势batch开启；EMA跨任务连续传递，避免边界覆盖；retention仍从Task 2开始 | 独立代码/CPU验收通过，真实GPU有效更新及同进程跨任务有有限证据 |
| COCO / AUTH-COCO-001 | 开启seen标签提示时，训练allowed_classes使用全部seen类别 | 提示与奖励GT局部修复通过；five-shot共现配额、监督时机及完整AP评估仍待验证 |
| 图像任务边界恢复 / CAND-RESUME-CIL-001 | R3.1支持完整任务结束后发布完整边界，并由新进程进入下一任务 | [42项独立CPU检查通过](acceptance/CIL-RESUME-CPU-R31-20260911/REPORT.md)；真实GPU新进程恢复对照尚未开始训练 |
| GPU链路 | 既有环境下完成有限有效更新和同进程Task 1→2 | 见[一步验收](acceptance/GPU-ONE-STEP-20260909/REPORT.md)与[连续任务验收](acceptance/CONTINUOUS-TASK12-20260909/REPORT.md)；不扩大为全参数、完整轨迹或论文规模通过 |

当前恢复诊断采用同机两张RTX3090，比较连续运行C与退出后恢复A/B，每任务两次真实更新。要求边界完整状态精确恢复，后续奖励、优势、retention指标按预先冻结容差比较；不要求后续随机轨迹逐张量相等。

v6运行准备曾获独立就绪结论，实际启动前暴露GPU映射检查错误。v7已修正物理映射并取得真实无模型证据，但独立复核发现进程启动身份取值错误；目前仅修这一诊断增量。历次失败与限制见 [诊断评审记录](FRESH_PROCESS_PROTOCOL_REVIEW.md)，当前任务以 [协调台账](TASK_COORDINATION.md) 为准。诊断代码与科学训练代码分开维护。

## 后续门槛

1. 完成进程身份修复的增量验收，再执行并独立验收有限GPU恢复对照。
2. 冻结ImageNet-R首轮单seed完整实验的数据、任务划分、模型、配置、评估和资源预算。
3. 在具体正式实验范围获确认后启动，再扩展多seed；检测任务另行核实COCO数据与AP口径。

论文对应的原实验commit、逐seed命令/原始结果和完整环境身份仍未齐备。任何已知论文与代码差异继续披露，不把“修订实现可运行”表述为原论文结果已复现。

## 证据入口

- [整合说明](INTEGRATION_HANDOFF.md)：本次根目录的代码来源、保留范围与验证。
- [原始到手审计](audit/2026-09-04-author-intake/REPORT.md)：只描述作者基线，历史结论不改写。
- [CTAN验收](acceptance/AUTH-CTAN-001/REPORT.md)、[COCO验收](acceptance/AUTH-COCO-001/REPORT.md)、[恢复R3.1接收](CIL_RESUME_R31_ACCEPTED.md)。
- [复现计划](REPRODUCTION_NEXT_STEPS.md)、[资料地图](PROJECT_MAP.md)。

历史报告中的本机/远端绝对路径是当时证据来源；它们不保证在另一台机器可访问。模型、checkpoint、原始媒体与服务器运行目录不随本仓库发布。
