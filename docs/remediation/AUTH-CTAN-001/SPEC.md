# AUTH-CTAN-001 冻结整改规格

日期：2026-09-05。角色：整改与自测。依据：用户已批准的“按论文公开算法复现”实现约定；不是作者原实验身份认证，也不是独立验收结论。

## 数值约定

标准 CTAN 从 Task 1 的首个优势计算 rollout batch 开始。每条回答总奖励为其 token_level_rewards 之和；按 uid 提示组求总奖励均值。全批总奖励的标准差采用样本估计：

```text
r_i = sum_t reward[i,t]
mu_g = sum_{i in g} r_i / |g|
sigma = sqrt(sum_i (r_i - mean(r))^2 / (B - 1))
s_1 = sigma_1
s_k = 0.999 * s_(k-1) + 0.001 * sigma_k  (k > 1)
A[i,t] = (r_i - mu_group(i)) / (s_k + 1e-6) * response_mask[i,t]
```

每批调用一次 EMA 更新，累计 update_count 加一；当批使用更新后的尺度。组内至少两条回答，沿用作者 rollout.n > 1 前提。零方差允许 s=0；极小方差不设额外下限；仅 epsilon 进入分母。返回 advantages 与 returns，padding 为零。

**“首批以当批 sigma 初始化”和“样本标准差”是本项目冻结的实现约定，不能说成论文明确规定。** 跨任务连续 EMA 与 beta=0.999 是本次按公开算法落实的目标；Task 1 激活采用用户本次冻结口径，保留与作者原配置 Task 2 激活的差异。

## 任务和配置

Task 1 不注入 retention；Task 2 起仍先注入 retention，再计算总奖励、组均值与 CTAN。previous-task anchor 仍从 Task 2 开始。

三份真实标准 JSON 的 CTAN 配置一致：enable=true、beta=.999、eps=1e-6、activate_from_task=1、bootstrap_steps=0、min_std=0、guard_abs_max=0、bias_correction=false、beta_warmup_steps=0。beta_warmup_init=.9 字段仍保留，但在 warmup_steps=0 时无作用。现有字段、CLI 名称与显式变体开关保留；用户主动启用的 warmup、bias correction、bootstrap、min_std、guard 等变体不在本次论文规格验收范围。

数值和激活时点默认值统一到 dataclass、环境回退、两个 CLI 和三份标准 JSON。沿用作者显式启用接口：裸 CLI / 无 EMA_ADV_ENABLED 环境 / dataclass 的 enabled 默认为 false；标准 JSON 通过 enable=true 开启。这一开关差别是原接口的 opt-in 行为，不将裸 CLI 当作标准 shell 配置运行。CTAN 关闭时继续调用原 GRPO，无 EMA 实例及更新。

## 跨任务状态

正常 Task 1→2→3 使用现有 runner 的 `_load_ema_state` → `reinit_for_task` → normalizer → `_save_ema_state` 链。保留现有 JSON 的 latest/task_history 结构、字段及累计计数。last_batch_reward_* 继续作为记录字段保存，但不再覆盖有效 EMA。

启用 CTAN 后，在 task_id > activate_from_task 的后续任务构造 normalizer 时，必须有有效历史：ema_std 为有限非负数，update_count 为正整数。缺文件、不可解析文件导致 loader 返回 None；构造器明确报错，不允许静默首批初始化。正常任务即使训练批数为零也不会伪造有效历史，下一任务会失败。

本次只验证新实现写出并重载的状态。不迁移旧算法状态，不实现状态来源自动认证；有效字段本身不能证明文件来自本实现。独立验收和后续运行应从本实现 Task 1 新建输出开始，不复用旧算法 EMA 或 checkpoint。完整 checkpoint / optimizer / task cursor 精确中断恢复不在范围内。

## 规格与测试映射

测试入口：`tests/author_fixes/test_ctan.py`。独立预期由 Python 标量求和、均值、样本方差和递推计算，不调用 normalizer 生成答案。浮点统一 rtol=1e-5、atol=1e-6；计数、配置和跨边界状态精确比较。

| 规格 | 定向测试 |
|---|---|
| Task 1 首批/多批、样本 std、更新后分母、一次计数 | test_task1_first_and_multiple_batches_default_config |
| Task 1→2→3 与不断开序列、标量公式对照 | test_task123_matches_uninterrupted_and_scalar_formula |
| 不同历史、同一非零末批保留不同 EMA | test_different_histories_same_nonzero_last_batch |
| 真实临时 JSON 保存/读取、历史、计数、下一批优势 | test_real_json_roundtrip_count_and_next_advantage |
| 零/极小方差、取消下限 | test_zero_and_tiny_variance_no_floor（2 项） |
| 超过旧 guard=5 的优势不回退 | test_old_guard_threshold_exceeded_without_fallback |
| Task 1/2/3 共享 hook、retention 先注入、Task 1 不注入 | test_shared_hook_task123_retention_before_ctan |
| 关闭 CTAN 时原 GRPO 精确数值及无 EMA | test_disabled_ctan_unchanged_original_grpo（3 项） |
| 必要历史缺失/无效明确失败 | test_later_task_requires_valid_history（6 项） |
| 图像和检测真实 reinit 状态传递及缺失失败 | test_actual_reinit_passes_state_and_fails_when_missing（2 项） |
| 三份真实配置解析、CLI/env 默认值及显式覆盖 | test_real_configs_cli_and_environment_defaults（3 项） |
| padding 为零 | 所有数值测试共用 check_output，同时核验 returns |

CPU 测试使用当前工作树未改写的 AST 函数/类，保留装饰器与函数体；最小 SimpleNamespace 仅提供张量容器/配置字段，不替换被测算法。底层 GRPO 使用当前作者源码注册与分派函数。逐文件源 hash 见 red-confirmed.json 与 green.json。

静态接线证据另存 verification.json：shell→真实 JSON、视频→图像入口、runner 状态读写与传递、fit 安装/恢复 hook、advantages→actor policy loss。静态连接不等于完整 CLI、DataLoader、Ray/RPC 或 GPU 已执行。
