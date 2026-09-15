# CAND-RESUME-CIL-001 最小整改规格草案

状态：供整改任务直接实现；本轮只冻结范围和验收契约，不改生产源码。

## 1. 目标与非目标

目标是支持且只支持以下边界：

> 图像 CIL 的 Task 1 已完成全部训练和 post-training validation，native checkpoint、EMA、计划、配置、输入和随机状态已发布为完整 `task1-complete`；进程结束；新进程从 Task 2 的第一个新 dataloader batch 开始。

非目标：中间 batch 精确抢占、通用 fault tolerance、Task 1 内部重启、视频/检测任务、改变论文算法、另存一份完整 anchor 权重、逐 token bitwise 复现保证。

## 2. 入口契约

在图像 CIL 模块新增显式 boundary resume 参数，例如 `--resume_task_boundary PATH`。没有该参数时，标准 `_run_cil` 和当前 continuous `PersistentRunner` 路径保持原语义：Task 2 仍使用内存 actor/optimizer/scheduler，仍可传 `load_checkpoint_path=None`。

有该参数时，入口必须在创建训练任务前完成：

1. 读取 `PATH`，要求 `status=complete`、`completed_task=1`、`next_task=2`；禁止把普通 `checkpoint_tracker.json`、model-only 目录或任意 `global_step_*` 路径当作 boundary record。
2. 校验 record 自身引用的所有文件存在、bytes 和 SHA-256 一致；校验 checkpoint 目录名的 step、tracker 的 `last_global_step`、record 的 `global_step` 三者一致。
3. 校验 source manifest、base/reference model identity、input manifest、immutable config 和 classplan；只允许当前输出根与任务输出目录变化。source、model revision、输入、配置、类别顺序、Task 1/2 划分任一缺失或不一致都 failclosed。
4. 从 record 直接取得 `class_splits`、`seen_class_names`、Task 2 `current_classes` 和 expected loader recipe；不得重新以新的 global NumPy RNG 或 CLI seed 随机生成另一份 plan。

参数名可由实现选择，但必须形成清晰的“正常 continuous”与“fresh boundary restore”两条分支；不能以隐式检测 `load_checkpoint_path` 或目录存在性猜测。

## 3. Task 1 完成记录 schema

完成记录建议为 `task_1/task1-complete.json`，以同目录 temp 文件写入、flush/fsync 后 `os.replace`，并在 marker 发布前完成目录 fsync。marker 是最后一个可见的提交点；没有它的 checkpoint 一律不可恢复。

最小字段：

| 字段 | 要求 |
| --- | --- |
| `schema_version`, `status` | 固定版本；`status` 必须为 `complete` |
| `completed_task`, `next_task`, `global_step` | `1`, `2` 和 Task 1 最终 step；与目录/原生 tracker 交叉校验 |
| `checkpoint` | 绝对或 boundary-root 相对路径、`save_model_only=false`、完整文件 manifest、manifest hash；必须有 model/optimizer/extra_state/dataloader/tracker 所需内容 |
| `ema` | EMA state 的 canonical JSON hash 与已校验 payload/path；不得只依赖未校验的 root sidecar |
| `plan` | full class order、class splits、Task 1 seen、Task 2 current/seen、classplan hash |
| `config` | canonical effective config hash；明确允许变化字段仅为 output root/task save path/resume flag |
| `source` | branch/HEAD 或等价的每个 production source SHA-256；必须与当前 source 相同 |
| `model` | base model/reference identity：canonical path 加不可变 revision/content identity；anchor provenance 标为 `reconstructed_from_task1_actor` |
| `input` | train/val manifest 路径、bytes/hash、数据类别目录或 JSONL identity；不能只记录人类可读路径 |
| `rng` | driver state artifact hash；每 rank native extra-state RNG 校验结果；vLLM sharding RNG artifact/hash |
| `loader_policy` | `new_task_dataloader`、`cursor=0`、sampler type、`config.seed`、shuffle/drop_last/batch recipe、Task 2 dataset fingerprint |
| `state_fingerprint` | actor checkpoint manifest fingerprint、EMA update count、anchor reconstruction rule、计划/config/input 汇总 fingerprint |

无需把完整 anchor 权重再写入 record：只要 native actor 完整恢复，并且生产 copy 能对所有必要参数/状态建立 actor→anchor fingerprint，即以 record 记录 provenance 和 fingerprint。

## 4. 发布顺序

在 `run_task()` 的逻辑边界完成后按如下顺序发布：

1. 训练和所有 post-training validation 完成。注意当前 `trainer.fit()` 内部的 final validation/checkpoint 早于 `run_task()` 的 `extra_val_splits`；必须在全部 validation 后再用 native manager 刷新同一最终 global-step checkpoint，或保存等价、可校验的 post-validation active RNG sidecar。不得引用仍早于 extra validation 的 RNG 作为最终边界状态。
2. 保持 `save_model_only=false`，让现有 `FSDPCheckpointManager` 生成 actor、optimizer、scheduler 和 worker CPU/CUDA/NumPy/Python RNG。对每个 rank 做文件 manifest；缺少 optimizer 或 extra state 直接失败。
3. 保存/校验 EMA。可继续维护现有 continuous root sidecar，但 boundary record 必须绑定一份 immutable payload/path/hash；写入必须是同目录 temp + fsync + replace。
4. 在 vLLM 已 offload、`loaded=false` 的安全点，通过图像 worker 的生产 API 捕获各 rank `gen_random_states` 和 `torch_random_states`；通过 driver sidecar 捕获 driver `torch`/NumPy/Python state 及 loader seed recipe。sidecar 逐文件 hash。
5. 生成 plan/config/source/model/input manifest，重新计算所有 hash 和 state fingerprint。
6. 只有所有检查通过后，原子发布 `task1-complete.json`；tracker 不能取代该 marker。异常、进程终止或 marker 未发布都只能得到“不可恢复的未完成边界”。

为了避免无必要的重复大权重，若第二次 native save 只是对同一 global-step 目录刷新 post-validation 状态，应覆盖同一 checkpoint 目录而不是再保留第二份任务权重；anchor 仍只在 worker 内存中重建。

## 5. 新进程恢复顺序

1. 在任何 rollout 前校验 boundary record、source/model/input/config/plan 与全量 checkpoint manifest。
2. 用当前标准 `PersistentRunner.init()` 建立新 worker group 和 base reference/初始 anchor module；此时不能把 base anchor 作为 previous-task anchor 使用。
3. 按 record 构建 Task 2 train/val loader。Task 2 的 train loader 是新的 `StatefulDataLoader`，current classes 精确为增量类，prompt/seen classes 精确为累计 seen 类，cursor 必须为 0。不要加载 Task 1 的 `dataloader.pt`；该文件是 Task 1 游标，不是 Task 2 游标。
4. 调用 CIL trainer 的明确 disk-restore 分支：把 Task 1 checkpoint path 交给现有 native `_load_checkpoint()`，恢复 actor、optimizer、scheduler 和 worker extra-state RNG。该分支必须适用于 `task_id=2`，不可再次被当前 continuous 的 `task_id == 1` 条件清空。
5. native restore 成功后恢复 driver/vLLM RNG sidecar；确认每 rank 状态 hash、global step 和 scheduler/optimizer step 与 record 相同。
6. 恢复的 actor fingerprint 通过后，调用现有生产 `copy_actor_to_anchor()`，再检查 anchor 与恢复 actor 的完整/可审查 state fingerprint；严禁 copy 发生在 disk restore 之前。
7. EMA 以已校验 payload 传入 Task 2 reinit；`update_count`、beta/eps/activation config 与 record 一致。缺 EMA 或历史不连续立即停止。
8. Task 2 首步前写入一条结构化 restore event，包含 `checkpoint_path`、`completed_task=1`、`next_task=2`、global step、current/seen classes 和 fingerprint；首步后再验证 actor update、EMA increment 和 retention anchor 输入。

实现上可在 `PersistentCILTrainer` 增加“显式先 restore、再 copy anchor”的小方法：restore 后把已恢复 step 置入受控 preset，使 `fit()` 不重复磁盘加载；正常 continuous 分支仍使用现有 preset-only 内存路径。这样不会把 Task 2 的 `None` 误用于 fresh mode。

## 6. RNG 与数据语义

现有 native manager 已覆盖每 worker 当前 torch CPU/CUDA、NumPy、Python RNG；新增协议必须明确它没有覆盖 vLLM manager 的独立 `gen_random_states`，也没有覆盖 driver 状态。每 rank sidecar/API 应在 vLLM offload 后抓取，restore 必须在首个 Task 2 `generate_sequences()` 前完成。

Task 2 的 `RandomSampler` 使用新建 local `torch.Generator.manual_seed(config.seed)`；这是新任务的采样起点，不应继承 Task 1 的 exhausted sampler state。DataLoader worker seed 受 driver 状态和 loader 创建/iterator 时机影响，因此 driver RNG 必须在构建/迭代 Task 2 loader 前恢复，或将等价 seed recipe 明确写入并验证。不得以 `skip_dataloader_state` 这个当前无消费者的动态属性声称协议已实现。

## 7. Fail-closed

以下任何一项都必须在 rollout/actor update 前终止并保留证据：marker 缺失/状态非 complete；checkpoint/tracker/marker step 不一致；任一文件缺失、bytes/hash 不匹配；`save_model_only=true`；optimizer/scheduler/worker RNG/EMA/driver/vLLM RNG 缺失；source/model/input/config/classplan 不匹配；Task 2 current/seen classes 错位；anchor copy 来源不是刚恢复的 actor；Task 2 loader cursor 非 0；新进程仍走 `load_checkpoint_path=None`；旧 boundary 根被 pruning；必须依赖 legacy artifact、mock、跳过 assertion 或安装/下载才能继续。

`save_task_ckpt=none` 不能发布可恢复 boundary；`latest` 只有在 Task 1 marker 发布时 checkpoint 仍存在且新进程不会删除旧 boundary 根才可用。输出根可以改变，但 source boundary 根是只读输入，不能在 fresh resume 的 pruning 逻辑中被删除或移动。

## 8. 可接受的复现声明

验收报告须分开写：

- `state-exact`：record、source/model/input/config/classplan、global step、actor/optimizer/scheduler、EMA、worker/native RNG、driver/vLLM RNG、fresh-loader policy 和 anchor provenance/fingerprint 与边界一致。
- `trajectory-close`：在 BF16、FlashAttention、异步分布式归约或 vLLM sampling 的非确定性下，比较 Task 2 首步/短窗口的有限指标、奖励/优势分布和任务指标，使用预先冻结的容差与 seed 复现；不得承诺逐 token 或逐参数 bitwise 相同。

只有真正跨 OS process 的 Task 1→Task 2 acceptance 通过，才可写 `fresh_process_resume=accepted`；同进程连续证据只能写 `continuous_runtime=accepted_limited`。
