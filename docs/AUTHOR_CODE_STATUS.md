# 作者代码当前状态

更新：2026-09-05。本仓库是今后以作者代码为核心的唯一活跃工程。Tag `author-drop-20260904` 保存收到的204文件原始基线；身份见 [`BASELINE.json`](BASELINE.json)。论文规定公开算法与实验规格，作者基线记录收到的实现；两者冲突时保留差异，不用旧个人实现替代。

## 当前裁决

**尚未达到“作者代码无问题”或正式复现放行条件。** 当前有两个 `corroborated / P1`：

| Finding | 已确认行为 | 影响 |
|---|---|---|
| `AUTH-CTAN-001` | Task边界加载保存EMA后，又用上一任务最后一批统计覆盖；默认逐任务重新warmup beta并可能回退普通GRPO | 跨任务归一化尺度不再是论文描述的持续EMA，并改变进入actor loss的优势值 |
| `AUTH-COCO-001` | 检测图片分配给最晚类别的任务，训练GT只保留当前novel类别；标准提示可列出全部seen类别 | 提示要求的旧类别从奖励GT消失，完整输出可能比只输出novel类别得分低；部分类别无训练正标注 |

COCO“每类最多5张”可能描述按类别抽样后取并集。合并后计数不能单独证明采样程序错误；当前P1最稳固的依据是seen提示、novel-only GT和奖励目标冲突。作者是否有意采用这些策略仍待澄清，现有证据不用于断言原论文结果无效。

## 已确认接通的主链

- 六个标准shell入口均使用对应 `scripts/{image,video,det}/rapo_cfg.json`；三份配置从Task 2开启CTAN和retention。
- 图像、视频、检测入口进入共享RaPO Trainer。共享 `fit()` 安装优势计算hook；CPU调用轨迹证实Task 2进入CTAN，advantages随后沿worker接口送入actor policy loss。
- EMA读取、传入、更新和保存接口存在。CTAN P1发生在状态读回后的normalizer构造过程。
- Retention的anchor初始化、actor到anchor复制、anchor log-prob RPC和奖励注入有静态调用链；CPU局部算术与论文相符。

这些是源码与CPU局部行为证据，不代表Ray/FSDP/vLLM、RPC、GPU或完整训练通过。

## Pending / deferred

- `D-PIPE-ENV-01`：算法开关依赖父进程环境，Ray runtime_env未显式携带。新建本地Ray可能继承成功；复用既有Ray可能缺失或读取旧值。尚未实跑，不是第三个P1。
- `D-RESUME-01`：checkpoint、EMA/anchor与任务游标的准确中断恢复未验证。
- `D-EVAL-01`：COCO per-task AP、验证图片筛选、crowd/空图及完整seen集合口径待确认。
- `D-GPU-01`：FSDP anchor分片复制、vLLM同步、BF16/FlashAttention-2、CUDA/NCCL和实际rank未运行。
- 原论文实验commit、逐seed命令、解析配置、base model revision、环境lock、checkpoint和原始指标/日志未取得。

## 证据入口

1. [`audit/2026-09-04-author-intake/REPORT.md`](audit/2026-09-04-author-intake/REPORT.md) — 完整到手审查。
2. [`recheck/REPORT.md`](audit/2026-09-04-author-intake/recheck/REPORT.md) — 两项P1的第一性原则复核。
3. [`pipeline/REPORT.md`](audit/2026-09-04-author-intake/pipeline/REPORT.md) — 接口行号、CTAN调用链和Ray环境观察。
4. [`AUTHOR_QUESTIONS.md`](audit/2026-09-04-author-intake/AUTHOR_QUESTIONS.md) — 待作者核实问题。
5. [`PROJECT_MAP.md`](PROJECT_MAP.md) — 本仓库资料边界。

下一顺序：作者澄清真实实现与实验身份 → 用户冻结P1处理口径 → 独立整改 → 独立验收 → 另行批准作者技术栈GPU诊断 → 从冻结base model的Task 1启动正式实验。
