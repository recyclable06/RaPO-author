# 作者代码接口定位与 CTAN 调用链复核

2026-09-04；用户要求定位既有两项问题，并检查 CTAN 是否实现后未接入流程。本对话继续承担审查编排，仅追加本地审计工件，不修改作者代码、不运行 Ray/GPU、不承担整改或独立验收。

## 结论

**CTAN 已接入训练代码主链，不是只有定义而没有调用。** 三份标准配置均能被真实参数解析函数读成 enabled=True；共享 Trainer 在 fit 中替换优势计算入口，Task 2 起调用 CTAN，产出的 advantages 在源码中继续传至 actor policy loss。CPU 探针执行原作者 hook/算法函数体，确认 Task 1、Task 2 和关闭 CTAN 三条分支有不同调用轨迹。

这不等于真实 Ray 训练已经验证通过。另发现一个需实测的进程间配置缺口：父进程设置 EMA_ADV_* / RETENTION_*，远程 PersistentRunner 再从自身环境读取，但 ray.init 的 runtime_env 没有显式传递这些字段。新建本地 Ray 的环境继承可能使其正常工作；复用已有 Ray 集群时可能读到缺失或旧配置。此项作为 D-PIPE-ENV-01 / deferred observation 留存，不在缺少真实 Ray 证据时升级为新的 corroborated P1。

## 两项既有问题的阅读位置

以下路径均相对 `RaPO_作者整理代码/`；行号对应到手包204文件，与原 ZIP 哈希一致。

| 问题 | 接口与行号 | 应关注的代码行为 |
|---|---|---|
| AUTH-CTAN-001 核心 | `examples/baselines/_rapo_components.py::EMAAdvNormalizer.__init__`，253–274 | 254–255 加载历史 EMA；267–274 在 task>=2 且有末批统计时，用末批统计覆盖。最直接的两行是273、274。 |
| CTAN 标准调用方 | `examples/baselines/img_cls_cil/image_cls_cil_rapo.py::PersistentCILTrainer.reinit_for_task`，277–282；检测对应 `image_det_cil_rapo.py`，215–221 | 每个任务创建新 normalizer 并传入读回的状态，因此覆盖并非闲置分支。 |
| CTAN 其他默认差异 | `_rapo_components.py::_effective_beta`，318–327；`_apply_guard_rail`，365–387 | 每任务重新 warmup beta；极端优势整组回退 GRPO。它们属于原 finding 的语义差异，不能被误称为整个模块没启用。 |
| AUTH-COCO-001 任务归属 | `examples/baselines/cil_det/image_det_cil.py::_infer_example_task_id_from_answer`，663–678 | 第678行按图片所有类别中的最晚任务分配图片。单独这一条实现了单任务分配，不单独判错。 |
| COCO 调用方 | `examples/baselines/cil_det/image_det_cil_rapo.py::_run_cil`，846–852、882–898 | prompt 使用 seen 类别；889将当前任务 novel 类别作为 allowed_classes 传入，893另传 prompt_label_list。 |
| COCO 实际删标注 | `examples/baselines/cil_det/image_det_cil.py::_build_dataloader`，764–775；`_filter_annotations_by_classes`，655–660 | 765–766 改写训练 answer；659只留下 allowed 类别。777–782只设置提示类别列表，不恢复已删除的答案。 |

检测问题应将三处合在一起看：一图分配给最晚任务、答案只保留该任务类别、提示却要求全部已见类别。上一轮实际奖励函数对照中，同一标准样本“输出全部8框”得到1.25，“只输出保留的car框”得到3.0。该数值来自 [上一轮现场结果](../recheck/results.json)，本轮未重复奖励实验，标记 recorded-but-not-rerun；本轮重新亲读并定位了调用方和过滤接口。不能仅凭超过5张的计数断言当前 builder 错误生成了随包206张，解释边界仍见 [第一性原则复核](../recheck/REPORT.md)。

## CTAN 从配置到 loss 的线路

1. **配置。** 六个 `scripts/{image,video,det}/*.sh` 均传 `--cil_cfg`；三个 `rapo_cfg.json` 都启用 ctan、retention，activate_from_task=2。图像 `_parse_args:879–938` 和检测 `_parse_args:1051–1114` 在 parse 前应用 JSON defaults。未单独写 `--ctan_enable` 不代表漏开；本轮执行原解析函数，三份配置都得到 True。
2. **实例。** 图像 `_set_env:940–955` 设置环境；远程 `PersistentRunner.init:361–378` 读配置、构造 `PersistentCILTrainer`。检测对应 `_set_env:1117–1131`、`init:496–513`。共享 `_rapo_components.py:516–521` 在 enabled 时创建 normalizer。视频包装器 `video_cls_cil_rapo.py:38–39` 复用图像 main。
3. **继承链。** 图像 `run_task:466`、检测 `run_task:606` 调用 trainer.fit；两个 Persistent Trainer 都继承共享 RaPO Trainer，未另写 fit 覆盖。共享类继承 `RayPPOContinualTrainer`，后者也未覆盖 fit，因此不会绕过共享 hook。
4. **实际接线。** 共享 `_rapo_components.py:593` 将 `verl.trainer.ray_trainer.compute_advantage` 替换为实例 hook，595调用父类 fit，597在 finally 恢复。底层 `verl/trainer/ray_trainer.py:643–648` 每步调用的正是该模块全局函数。优势计算在 PersistentRunner 内的 Trainer 控制流程进行，不要求各 GPU worker 再安装同一 hook。
5. **算法分支。** `_compute_advantage_with_hooks:580` 先添加 retention；584–588按 GRPO、normalizer 和 task 门槛选择算法；586调用 CTAN。Task 1 记录末批统计并用普通 GRPO，是默认激活时点。`AdvantageEstimator` 为 str Enum（`core_algos.py:89`），字符串 grpo 可通过判断；本轮动态走过该比较。
6. **送入 loss。** CTAN `compute_grpo_advantage:391–416` 在414–415写 advantages/returns；`ray_trainer.py:661` 将 batch 送至 update_actor；`fsdp_workers.py:566` 转入 actor.update_policy；`dp_actor.py:254–262` 读取 advantages 并传入 compute_policy_loss，288执行 backward。此间未发现重新运行普通 GRPO或优势白化的主路径代码。actor 部分仅亲读，未实际反向传播。
7. **状态存取。** 图像 `run_task:443–455,469–472`、检测 `run_task:581–592,609–611` 读取/传入/保存 EMA。共享 `:607–610` 指向各 task 的共同父目录下 ema_online_stats.json。问题发生在读回后的构造器覆盖，不能归因于没有保存或加载。

同一主链的 retention anchor 接口也有接线：ActorRolloutRef 实际映射至各自 `PersistentRefFSDPWorker`；anchor 初始化、后续任务 actor→anchor 复制、compute_anchor_log_probs RPC 及加奖励接口均有调用和注册。没有发现仅定义未引用的简单缺口；真实 FSDP 分片复制、RPC 分发和模型数值仍属于原 D-GPU-01 的 pending evidence。

## 本轮 CPU 实测与限度

成功命令（exit_code=0）：

```powershell
& 'D:\anaconda3\envs\rapo-b01\python.exe' docs/audit/2026-09-04-author-intake/pipeline/pipeline_probe.py
```

Python3.10.20、torch2.5.1+cpu。探针 [pipeline_probe.py](pipeline_probe.py) 用 AST 选取并执行原函数/类，保留函数体和行号；以最小张量数据载体提供 batch 字段，用 sys.setprofile 记录调用。未导入旧个人实现，未替换被测 CTAN/GRPO/retention 数值算法。共8组，每组8条 rollout。

| 控制条件 | 实际调用 | EMA 更新次数 | 正优势示例 |
|---|---|---:|---:|
| Task 1，开关开启 | observe_batch_without_ema → 原 GRPO | 0 | 0.935413 |
| Task 2，开关开启 | retention → compute_grpo_advantage → EMA 更新 | 1 | 0.992155 |
| Task 2，CTAN 关闭 | retention → 原 GRPO | 无 normalizer | 0.935413 |

后两组使用相同输入奖励及相同 retention 设置，差异来自 CTAN 分支。实际轨迹、源文件 SHA256、三套解析结果见 [results.json](results.json)。

**边界：** 没有执行完整 CLI、Ray actor、完整 DataProto/RPC、模型 forward/backward 或保存重载。探针预先提供 anchor_log_probs，不验证 anchor RPC。它证明原 hook 的分支和张量效果；完整训练链其余连接由源码阅读支持。不能将两类证据合写成端到端训练已通过。

## D-PIPE-ENV-01：远程进程是否获得配置

本轮确认的 repo/live fact：

- 父进程 `_set_env` 设置 EMA_ADV_* / RETENTION_*；远程 Runner.init 调用 from_env，没有显式接收这两个配置对象。
- 图像基类 `_ensure_ray:502–515`、检测基类 `_ensure_ray:1196–1209` 的 runtime_env.env_vars 只列 tokenizer/NCCL/vLLM/CUDA七项，没有算法字段；ray.init 未固定 address="local"。
- 在探针自身进程移除相关字段后，实际 EMAAdvConfig.from_env 和 RetentionRewardConfig.from_env 均返回 enabled=False。这是缺失环境的默认行为对照，不是一次 Ray 失败复现。
- init 若将 ema_adv 置为 None，后续 reinit_for_task 只在其非 None 时重建；Task 2 不会自行从 JSON 重新开启。进程间开关丢失可能持续整条链。

随包 requirements 固定 Ray2.46.0。其 [环境文档](https://raw.githubusercontent.com/ray-project/ray/ray-2.46.0/doc/source/ray-core/handling-dependencies.rst) 说明集群基础环境及 runtime_env；[init 源码](https://raw.githubusercontent.com/ray-project/ray/ray-2.46.0/python/ray/_private/worker.py) 支持默认连接已有实例；[进程启动源码](https://raw.githubusercontent.com/ray-project/ray/ray-2.46.0/python/ray/_private/services.py) 为新 Ray 子进程复制当前环境。结合作者代码可作以下有条件推断：

- **新建本地 Ray：** 在 _set_env 后启动的服务可能通过进程继承拿到变量。不能仅据 runtime_env 缺项断言正常脚本必然关闭 CTAN。
- **复用环境不同的既有 Ray：** Runner 可能看不到父进程刚设置的值，或读取旧值；CTAN及retention均有风险。尚未在真实 Ray2.46.0 中重现，不据此断言作者历史训练关闭了它们。

下一次在获批作者环境检查时，应核对 Runner 进程实际 EMAAdvConfig/RetentionRewardConfig、Task 2 normalizer 非空且 update_count 随 step 增长，并记录 Ray 是新建还是复用。父进程 cil_cfg.json 只能说明意图；仅有 EMA 文件也不能证明采用论文的连续统计。这里仅记录待核实项，没有安装依赖、部署探针或下发远程命令。

## 保全与当前裁决

原 AUTH-CTAN-001 / AUTH-COCO-001 裁决保持；未整改、关闭 finding 或自称独立验收。作者204文件逐个重算 SHA256，与 intake-snapshot.json 完全一致。新增 pipeline 工件及审查报告/PROGRESS/BLOCKED 入口；旧业务代码、作者代码、测试和配置保持原样。作者澄清论文/实现差异、真实进程边界和分布式执行仍未完成。
