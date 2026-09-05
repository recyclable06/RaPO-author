# 作者代码到手审查：论文一致性与后续复现入口

> **接口与管线补查：** 见 [pipeline/REPORT.md](pipeline/REPORT.md)。CTAN 已接入共享 fit/优势/loss 主链，CPU 调用轨迹证实 Task 2 分支执行；发现 Ray 算法环境变量未显式传递的条件性风险，列 deferred，未实跑 Ray/GPU。

日期：2026-09-04。角色：审查编排；单一对话独立阅读与复核，未派生 agent。输入为用户本轮 `/goal`。本报告不是整改交付、独立验收或 GPU 放行。

> **后续第一性原则复核：** 见 [recheck/REPORT.md](recheck/REPORT.md)。两项P1维持；新增非零方差/无guard的CTAN历史丢失对照，以及COCO标准提示与奖励GT冲突的具体样本。5-shot抽样配额与有效监督量须区分；当前builder不能被当作随包206张的已知生成来源。本报告原始审查过程和数值保留，解释边界以该补充为准。

## 1. 裁决

**不能确认这份作者整理包无问题，也不建议直接启动正式复现。** 已确认两项标准路径上的论文一致性问题：CTAN在任务边界丢失论文要求持续携带的EMA历史；COCO标准入口的seen类别提示与novel-only过滤GT/奖励目标冲突。两项均有论文、源码和本地CPU证据，裁决为 `corroborated / P1`。COCO的5-shot抽样配额解释仍待作者确认，不能只凭合并后有效图片计数判定采样程序错误。这里确认的是“收到的文件与论文或公开入口存在差异”，不能由此推断作者原始实验结果错误。

作者包是今后复现的首要实现资料，但“来自作者”不等于“已经验证”或“与发表实验完全相同”。应保留原包，先向作者核实这些差异及实际实验版本，再冻结派生实现与独立验证目标。旧个人工程转为参考资料，历史 CPU 放行仍只适用于当时的旧工程。

| 分类 | 结论 |
|---|---|
| blocking | `AUTH-CTAN-001` 阻断所有依赖该 CTAN 的论文一致性声明；`AUTH-COCO-001` 另外阻断 COCO 协议复现 |
| non-blocking P2 / observation | 可复现环境入口、数据短缺说明、完整预测留存、资源可见性与清理边界，见 §6 |
| deferred | 分布式运行、保存重载等价性、COCO 指标口径、实际论文运行身份；未证明通过或故障 |
| out-of-scope | 修复作者实现、旧工程重新验收、安装、SSH/GPU、训练/推理、删除/移动、提交/push |

## 2. 输入身份、可信边界与恢复快照

输入基线：`46e7e257d65716b127187a19c19890aa70aad0b6`，分支 `codex/rapo-b03-orchestration`。收到的作者目录尚未被该提交包含，不能用此 HEAD 指代作者代码。作者目录的身份以 ZIP 和逐文件 SHA256 清单为准。

| 资料 | 身份与证据地位 |
|---|---|
| 本地 `2605.09640v1.pdf`，23 页 | `paper fact`；SHA256 `fc48b658fd3d96980f4733cbd9672aa21be2f3b04e73958de54bf4e0e15965e0`；题名与 [arXiv v1](https://arxiv.org/abs/2605.09640v1) 相符 |
| `RaPO_作者整理代码.zip` | 用户交付的作者整理包；SHA256 `97ac812aff1f1ff0aa049d04b43d726b714f0f8bfddd5e45cfe8027c5094c3d8` |
| `RaPO_作者整理代码/` | 204 个文件与 ZIP 的 204 个文件逐字节一致；无作者原始 Git commit 或论文运行 artifact 可供本轮验证 |
| 作者 README、配置与代码 | 作者实现的一手材料；README 关于论文运行环境的陈述仍须区分于现场运行证据 |
| `实验室服务器使用规范.md` | 用户指定前半部分为一手操作规范；以 `RaPO 私有操作补充（2026-08-03）` 为界，之前含管理员署名的正文为规范，之后为历史操作备注；整文件和分段 hash 见快照，不转载访问资料 |
| 原个人代码、2026-07-31 审查、batch1–4 与 handoff | 旧独立实现及历史过程证据；不能裁决作者代码的正确性；旧运行结果均为 `recorded-but-not-rerun` |

作者“主要内容初步检查、尚未深入检查与原版一致性”的提示来自本轮用户转述；未将它伪装成包内已找到的原文。论文和作者代码冲突时明确保留冲突，不用个人实现或作者 README 自动覆盖论文。

标准路径冻结为：作者 README 的六个 `scripts/{image,video,det}/*.sh` 入口、随包配置、公开数据构建入口、随包正常 JSONL/类别列表与作者公开 seeds；从指定 base model 新建输出目录开始，正常跨任务训练及评估。手改 JSON、非标准 Python API、恶意输入不是本轮阻断依据。图片/视频本体未在本轮下载或读取验证。

起始工作区已有七个 tracked dirty 文件：`AGENTS.md`、`README.md`、`docs/remediation/batch2/BLOCKED.md`、`docs/remediation/batch3/PROGRESS.md`、`docs/remediation/batch3/decisions.md`、`docs/reproduction_spec.md`、`docs/smoke_test.md`；另有未跟踪作者目录、ZIP 和 batch4 文档。它们不是本轮新增代码差分。完整起始 tracked 文件 hash、status、作者 hash、ZIP 对照见 [intake-snapshot.json](intake-snapshot.json)。

## 3. 论文—实现对照

页码均为本地 PDF 的物理页码（从 1 开始）。源码路径相对作者目录；“静态相符”不表示已经运行训练。

| 论文内容 | 作者实现与本轮结论 |
|---|---|
| p4–5 Eq.2–4：生成 token 上先求 drift 均值，再取正部，指数奖励并 stop-gradient | `_rapo_components.py::_apply_retention_reward` 静态相符；CPU 检查不同长度、padding、负 drift、梯度分离，数值相符 |
| p4：上一任务终点作为冻结 anchor，当前任务继续训练 | `image_cls_cil_rapo.py::copy_actor_to_anchor/run_task` 在后续任务开始复制 actor 到独立 frozen anchor；主训练 worker 持续存在。FSDP 分片复制和数值一致性尚未实跑 |
| p5 Eq.5–6：EMA 跨任务持续、装载上一任务最终 EMA，不重置尺度 | `EMAAdvNormalizer.__init__` 先读 EMA 再用上批统计覆盖；每任务 warmup beta、极值回退均在默认配置启用；**AUTH-CTAN-001** |
| p6：8 rollouts、alpha=20、lambda=0.5、beta=0.999，task2 起启用 | 六个 launcher / 三个 `rapo_cfg.json` 的主要参数相符；实际前两步 beta 为 0.9/0.9495，见 CTAN finding |
| p7：图像 200 类、10/20 tasks、每类 5-shot、三种顺序 | README seeds 为 1990/1993/1996；CUB、IN-R、Tiny 的列表均 200×5；IN-A 实际 985 张/199 个非空类，见 §6 |
| p7：所有 seen classes 联合测试、A 与历史最佳遗忘 F | 图像 trainer 联合推理一次，再拆任务指标；A 为样本微平均，F 排除当前任务、比较历史最佳。静态未见与该口径冲突，未运行模型预测 |
| p8：图像每任务 2 epochs | 图像 launcher 为 2；训练 `drop_last=True`、batch8，因此每任务 100 张只消费 96 张/epoch，50 张只消费 48 张/epoch；此为实际 loader 语义，不擅自改成旧工程严格预算 |
| p8：COCO 80 类、5/10 tasks、每类最多 5 张、无跨任务图片重用 | 图片身份无重复/交叉；重新分任务后seen提示与novel-only过滤GT/奖励冲突；合并后的shot计数需作者解释，不能单独判错；**AUTH-COCO-001** |
| p8：COCO 7B、5 epochs、标准 COCO mAP | launcher 模型/epoch 相符；val JSONL 为 4952 张，框转换与 per-task 筛选另需确认，不能把未跑 pycocotools 写成 mAP 通过 |
| Appendix B p12–13：分类准确+格式奖励、检测 Hungarian/IoU/类别/格式奖励 | 阅读 `examples/reward_function/{cls,det}.py`，主要公式结构相符；本轮未对整个 reward 模块逐分支实跑，额外解析/占位检查属于作者实现细节 |
| p9：视频及 DIL 扩展 | 包内 UCF101 split01 505=101×5 的列表与入口存在；未找到 Kinetics-200、DomainNet、OfficeHome、Pascal VOC 的完整实验入口；包的 README 仅声明 CIL 三类范围，不据此指控实现 bug |
| 表格三 seed mean±std 与多 baseline | README 给 seeds；没有可核对的完整论文逐 seed 原始结果，也未提供覆盖全部表格的方法编排/汇总链；旧个人 orchestration 不能直接填补 |
| p6：8×H100 | 图像入口默认 4 卡，视频/检测默认 8 卡；这是包与论文运行配置差异，需核实真实使用的命令；本轮没有现场硬件结论 |

实现另包含固定 base reference 的 loss-level KL（launcher 系数 0.002），与 previous-task retention anchor 是两个对象；不能把个人工程的 previous-anchor KL=0.04 直接迁入。优化器/梯度裁剪/dual-clip/rollout token 截断/worker 调用顺序已沿主路径阅读，但这些数值实现细节尚无作者逐次运行证据可据以证明论文等价。

## 4. AUTH-CTAN-001 — 跨任务 EMA 被最后一批统计覆盖

**裁决：corroborated / P1。** 影响 image、video、detection 三条 RaPO 标准路径的训练优势与论文 Eq.5–6 一致性；不据此宣称会改变结果多少。

证据链：

1. `paper fact`：p5 §3.2.3 明确上一任务最终 EMA 在下一任务作为初始值继续使用；Eq.5 是 beta 加权的持续更新。
2. `repo fact`：`examples/baselines/_rapo_components.py:253–274` 装载 `ema_std` 后，在 task≥2 又被 `last_batch_reward_std` 覆盖；`:318–327` 每任务重新 warmup beta；`:365–387` 极值时整组回退 GRPO。三份默认配置启用 beta=.999、warmup2/.9、guard5。图像 runner `:443–472` 正常读写 EMA JSON，`:277–287` 构造新 normalizer；视频复用该 runner，检测亦使用同一组件。
3. `live-read artifact/command`：[cpu_probes.py](cpu_probes.py) 从原作者文件 AST 选取并执行未改写的 normalizer，使用真实 CPU PyTorch、8 prompt×8 rollout 的正常标量奖励。task1 observe → task2 两批 → JSON roundtrip → task3，未修改配置来制造故障。源文件 SHA256 `73aac97f816c124e4fbf06ab3ac0e270045fc79a91c62dc534e8d5d39f99243c`。

| 数值 | 现场结果 |
|---|---:|
| task2 两次更新实际 beta | 0.9、0.9495 |
| task2 保存的最终 EMA std | 0.95700603 |
| task2 最后一批 std | 0 |
| task3 刚读入后 std | 0 |
| task3 下一批实际更新后 std | 0.10079052 |
| 按论文从保存值继续更新应得 std | 0.95705693 |
| 该批触发 GRPO fallback 的组数 | 8/8 |
| 正优势：实际 / 按论文局部对照 | 0.93541354 / 1.04486883 |

局部对照以作者已保存的 EMA 为共同起点，仅检验跨边界连续性，不伪称整段训练已按论文重跑。全组相同奖励是准确/格式等离散奖励的正常可能结果；即使最后一批 std 不为零，只要不等于 EMA，也发生覆盖。没有证明这种特定数值序列在某次真实 GPU 训练中出现，但触发覆盖的条件本身是公开跨任务路径。

现有 JSON 保存、warmup、min_std、guard 能提供数值保护，不能保住论文所述的连续 EMA；因此不能把它当普通错误输入问题降为 P2。覆盖、warmup 和 fallback 统一作为 CTAN 实现口径问题，不按参数变体拆 finding。待作者确认这是整理失误还是论文未写明的真实稳定化策略；审查者没有自行选择/实施修复。

## 5. AUTH-COCO-001 — 标准任务分配改变训练GT并与seen提示冲突

**裁决：corroborated / P1。** 影响 COCO 的训练样本/标签和实验比较口径；不阻断与 COCO 无关的数据工作。

证据链：

1. `paper fact`：p8 的 COCO 协议给出每图只分到一个任务、无跨任务训练样本重用、每类最多 5 张训练图。
2. `repo fact`：`data/create_object_det_cil_dataset.py::fewshot_sample` 会累计共现类别，不能保证每类图数上限。公开 launcher 使用随包 206 行 `train_5shots.jsonl`。`image_det_cil.py:663–678,733–740` 根据当前类别顺序把每图分到所含类别的最晚任务；`:765–772` 再过滤为当前任务标签。`image_det_cil_rapo.py:889–896` 标准传入 novel classes 与 task_id，因而这不是手动改 JSON 的旁路。
3. `live-read artifact/command`：探针调用原作者 `_build_class_order`、`_chunk_classes`、`_build_class_to_task_map`、`_infer_example_task_id_from_answer` 和 `_filter_annotations_by_classes`，遍历 README 全部六个 COCO seeds。实际数据与函数均未更改。

| Tasks / seed | 各任务图片数（batch 截断前） | 没有训练正标注的类别数 | 单类有效训练图片最大数 |
|---|---|---:|---:|
| 5 / 136 | 16,19,11,64,96 | 25 | 53 |
| 5 / 377 | 16,17,27,58,88 | 14 | 19 |
| 5 / 639 | 22,19,22,56,87 | 14 | 19 |
| 10 / 277 | 13,14,10,16,13,16,20,20,41,43 | 12 | 12 |
| 10 / 305 | 11,10,21,10,14,15,10,23,39,53 | 16 | 17 |
| 10 / 738 | 10,12,13,13,11,14,23,23,45,42 | 16 | 24 |

例如 5-task seed136，`bicycle`、`dog`、`chair` 等 25 类没有保留下来的训练正标注；`person` 有 53 张、`car` 24 张、`book` 13 张。这里数的是不同图片中的保留标签，既非实例数也非多 epoch 重复次数。完整类别计数与归属见 [cpu-probes.json](cpu-probes.json)。`person` 所在 Task4 共64张、`car` 所在 Task5 共96张，均为batch8的整倍数，因此这些具体超额案例不会被 `drop_last` 去掉；它也不能恢复已被过滤的类别标注。

包内 train/val 的路径身份交集为 0，206 张图都恰好分到一个任务，六个顺序均无零 batch 任务。因此“所有任务会因样本不足立即起不来”被排除；当前已确认的问题是管线可正常运行，但seen-class提示与novel-only训练GT/奖励目标不一致。合并后某类图片数超过5张以及部分旧类零正标注仍是需作者解释的数据协议事实，不能脱离抽样配额定义单独判定采样程序错误。路径去重和task_id不消除提示/评分冲突。

需要作者提供各任务数/seed 实际使用的 few-shot 清单、类别顺序和多标签分配规则，确认“最多 5 张”是否包含共现标签、早期类别是否在后续图像保留标注。不能未经确认改成随机另抽 5 张或迁用旧个人划分，因为两者都可能偏离原实验。

## 6. 其他观察与尚未解决的证据缺口

以下没有被本轮升级为已确认 P1；新发现若要阻断不同范围，仍须按标准路径影响单独裁决。

| ID / 状态 | 现场所见、限制与后续核实 |
|---|---|
| OBS-DATA-01 / non-blocking P2 | IN-A 清单 985 张，199 个非空类；192 类5张、5类4张、1类3张、1类2张。不能用 200×5 的表述覆盖实际清单，也不能将缺数据解释成算法 bug；需确认论文实际是否同一清单 |
| OBS-ENV-01 / non-blocking P2 | README 有宽范围 requirements 安装与环境 lock 两条入口；作者声明 Python3.11.6/torch2.6.0+cu124/vLLM0.8.1/Ray2.46.0。未来以作者确认的环境锁为起点，保留版本实测；本机 CPU 环境不是这个环境 |
| OBS-TRACE-01 / non-blocking P2 | 默认 `--save_task_ckpt latest` 会清理较早任务检查点，不能指望结束后任意复跑旧任务；完整预测与逐 seed 表格证据不足。旧目录未在本轮被清理 |
| OBS-RESOURCE-01 / non-blocking P2 | 检测 runner `image_det_cil_rapo.py:427–431` 会移除 Ray 为零GPU actor 设置的空 `CUDA_VISIBLE_DEVICES`；共享服务器部署前需核实 driver/SAM 的设备授权。未观测实际越界占卡。成功路径才 `ray.kill(runner)`，中断清理也须检查 |
| D-EVAL-01 / deferred | 检测 per-task mAP 构造在 `image_det_cil_rapo.py:646–665` 丢弃不含该任务 GT 的图片，其上该类假阳性也不参与；这与在整个 seen 验证集合按类别计分不同。包内 val4952、crowd/空图处理也需对照实际原始协议。没有 pycocotools/原始评估输入，不捏造 COCO AP 反例或量化 F 偏移 |
| D-RESUME-01 / deferred | 持续运行中的跨任务 worker 保留状态，与进程中断后 resume 是两回事。每步 FSDP checkpoint 不等于整条 CIL 链的 EMA/anchor/task cursor 原子快照；外层启动新时间戳目录并从首任务循环。未执行中断/重载，不宣布断点恢复等价 |
| D-GPU-01 / deferred | FSDP anchor shard 复制、vLLM 权重同步与 rollout/actor token 对齐、BF16/FA2、NCCL、优化器非有限梯度跳步后 scheduler/EMA 的关系均未实跑。阅读 [vLLM 0.8.1 executor 源码](https://github.com/vllm-project/vllm/blob/v0.8.1/vllm/v1/executor/abstract.py) 已排除“external_launcher 根本不支持 V1”的简单断言；实际 V0/V1 和权重同步仍待指定环境验证 |
| D-PROVENANCE-01 / deferred | 包无可核对的原始提交、每个表格逐 seed 命令/输出/模型版本 manifest；README 的“paper runs”陈述不能替代这些资料。模型用名称加载，后续必须记录实际 revision |
| D-SCOPE-01 / out-of-scope | 未交付的 DIL/Kinetics/完整 baselines 不在本包 README 承诺范围；要复现这些表格需额外资料，不把旧工程冒充作者实现 |

第一手实验室规范仍约束后续操作：先核实占用、显式限定获准设备、使用个人目录、遵守后台任务与退出清理要求。后半段历史 SSH 注记不代表今天的资源状态或启动授权。本轮未连接服务器，也未安装任何依赖。

## 7. 现场验证及其边界

| 检查 | 结果与证据 |
|---|---|
| ZIP—目录完整性、源码身份 | 204/204 一致；最终再核查作者目录/ZIP/PDF/私有规范均未改动 |
| 作者 Python 语法 | 83 个文件，Python3.10.20 与首次清点的3.12.14均无 AST/compile 语法错误；不产生作者目录 pycache；不代表可 import 所有依赖 |
| 六个 shell launcher | Git Bash `bash -n` 全部 exit0；没有执行 launcher |
| CTAN 反例 | 已复现论文差异；stdout 留存 8/8 guard 回退。探针 exit0 表示断言成功复现差异，**不是 CTAN 通过** |
| Retention Eq.2–4 | 实际奖励和手算对照分别约 `[0.18393968,0.5,0.5]` / `[0.18393973,0.5,0.5]`，误差≤1e-6；梯度分离符合预期 |
| 图像与视频列表 | CUB/Tiny/IN-R 各1000；IN-A985；UCF505。IN-R24000train/6000test、IN-A5981train/1519test 的列表集合无交叉，few-shot 均为 train 子集；未核图像像素内容 |
| COCO 清单与标准筛选 | 206train/4952val、80类、无路径重复/交叉；六种顺序结果见 §5 |
| 旧测试 | 仅现场收集113项，见 `legacy-test-collection.txt`；没有重跑旧测试，更没有把它们当成作者测试 |
| git diff/check 与白名单 | 最终结果见 `verification.json`；仅本文相关文档治理和新 audit 工件，作者及旧业务代码/测试/配置/patch无变更 |

CPU 探针在 `D:\anaconda3\envs\rapo-b01\python.exe`、torch2.5.1+cpu、numpy1.26.4 运行。因缺 Ray/vLLM/Transformers/datasets/pycocotools 等依赖，采用 AST 选取未改写的作者数值类/纯函数进行隔离验证；输入容器仅供应这些函数实际读取的字段，没有 mock 被测算法。它不能覆盖真实 DataLoader、Ray 分发或模型运行。环境清点见 [runtime-environment.json](runtime-environment.json)。

重跑本轮可重复检查（不执行训练、不安装）：

```powershell
& 'D:\anaconda3\envs\rapo-b01\python.exe' docs/audit/2026-09-04-author-intake/verify_intake.py
```

该命令检查 hash/语法、调用 CPU 探针、写同目录结果；初始快照 `intake-snapshot.json` 不覆盖。完整命令、exit code、stdout/stderr 在 [verification.json](verification.json) 与 [cpu-probes-stdout.txt](cpu-probes-stdout.txt)。本轮没有继承为 `carried-forward-unchanged` 的旧训练或验收门禁。

## 8. 整理结果、权限与下一放行点

已创建 [项目资料索引](../../PROJECT_MAP.md)，在根 README/AGENTS 与旧常用说明入口标明作者资料优先、旧工程参考范围；旧代码、实验记录、正式 finding、七个已有 dirty 文件的原有内容与历史裁决保留。未移动或删除文件、未 commit/push、未写 agent memory。作者204文件与旧工程业务文件的最终 hash 保全结果见 verification。

文档收口授权来自同一 `/goal` 中“将已有工程产出整理清楚避免干扰”的明确请求，按 `neat-freak` 的知识整理方式执行。此有限例外仅更新索引、资料权威与状态入口，不切换成整改或验收角色，不修改作者/旧业务代码或以整理动作关闭 finding。

后续顺序：作者澄清并补齐运行身份 → 用户冻结论文口径与作者实现差异的处理决定 → 独立整改对话在保留原包的派生目录实施最小修改 → 新独立验收 → 另行批准作者技术栈的 GPU 门禁 → 从 pinned base 的 Task1 开始正式链。此次“以后以作者代码为核心”不等于已经批准安装、GPU 训练或把原包自动改成个人实现。

旧 batch4 的 Visual-RFT/ZeRO-3 短门禁不再是当前默认下一步；其历史决策未撤销或改写，但不能替作者 FSDP 路径发证。作者答复前仍可阅读和设计核实工作，不能宣称作者代码已无问题。
