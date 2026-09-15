# CAND-RESUME-CIL-001 验收用例

这些用例用于独立验收，不在本轮执行 GPU/SSH/安装/训练。结论必须分别报告 `state-exact` 与 `trajectory-close`，不得用同进程连续结果代替 fresh process。

## CPU / static 协议用例

### CPU-RESUME-01：有效完成记录正例

使用生产图像 CIL 的 boundary serialization/validation helper 写入一个真实 schema 的小型 metadata/artifact fixture（文件均由生产 helper 生成，不能手写绕过校验）。验证：

- `status=complete`、`completed_task=1`、`next_task=2`、checkpoint suffix、tracker 和 global step 一致；
- 每个引用文件的 bytes/SHA-256、EMA payload hash、source/config/input/classplan hash 均通过；
- `save_model_only=false`、EMA update count 合法、Task 2 current/seen classes 合法；
- 输出根可不同，但 source boundary 根不进入 pruning；
- 解析结果明确要求新 Task 2 loader cursor=0。

预期：返回可恢复 boundary object，未启动 rollout。

### CPU-RESUME-02：缺件/错 hash 负例

逐项删除或改变 checkpoint shard、optimizer/extra state、EMA、driver RNG、vLLM RNG、input manifest 或 classplan 文件/内容，保留 marker 不变。

预期：每一项在首个 rollout 前 failclosed；不回退 base actor、不调用 Task 2 actor update、不把目录存在当作通过。

### CPU-RESUME-03：语义不一致负例

分别构造以下 marker：step 与目录不一致、tracker 指向另一 step、`save_model_only=true`、`next_task=1`、Task 2 current class 与 plan 不同、seen 类顺序不同、配置/model/source/input hash 不同、EMA update count 回退、loader cursor 非 0。

预期：全部 failclosed，并在结构化错误中指出具体不一致字段。

### CPU-RESUME-04：入口分支保护

对源代码做 AST/static 检查并调用纯 helper：

- 没有 boundary 参数时，连续 `_run_cil` 仍构造一个 `PersistentRunner`，Task 2 仍使用 preset global step/in-memory path；
- 有 boundary 参数时，Task 2 reinit 接受显式 checkpoint path，且 restore 发生在 actor→anchor copy 之前；
- `skip_dataloader_state` 不被当作恢复协议唯一实现；Task 2 fresh loader 明确 cursor=0。

预期：既有 CTAN/COCO 测试行为不变，静态断言不依赖 mock subject。

## 既有正常路径保护

### REG-RESUME-01：25 项局部回归

在目标整合源码上运行现有 `tests/author_fixes/test_coco.py tests/author_fixes/test_ctan.py`。当前基线证据为 `25 passed in 11.51s`；整改后必须仍通过，不能改写 4 个既有测试以绕过恢复逻辑。

### REG-RESUME-02：同栈 2GPU continuous

复用同一 source/model/input/GPU 身份，走标准生产 `_run_cil`，同一个 `PersistentRunner` 和同一个 world-size-2 worker group 连续 Task 1→Task 2。确认：Task 2 的 `load_checkpoint_path=None` 仍是正常 in-memory branch；actor、optimizer/scheduler、anchor、CTAN/EMA、retention 和 Task 2 step 延续不退化。

这只能得到 `continuous_runtime=accepted_limited`，不能关闭 fresh-process finding。

## 真正 fresh-process 用例

### FRESH-RESUME-01：Task 1 完成 marker

进程 A 使用生产入口完成 Task 1，并在全部 post-training validation 后发布 `task1-complete`。独立检查 marker 最后发布、完整 native checkpoint manifest、EMA/driver/vLLM RNG、plan/config/input/source/model identity 全部存在并有 hash。进程 A 正常退出，不保留其 in-memory worker 作为 Task 2 证据。

### FRESH-RESUME-02：进程 B 从 Task 2 起点恢复

全新 OS process B 使用 boundary CLI 和允许变化的新 output root；要求新 runner PID、worker group identity 与进程 A 不同。首个 rollout 前记录并验证：

- 实际加载 `task_1/global_step_N`，不是 `None`、base actor 或 preset-only step；
- actor fingerprint 与 Task 1 completion record 相符；optimizer/scheduler step/LR 状态、global step、worker RNG 与 native checkpoint 相符；
- EMA payload/update count 与 Task 1 末值相符；vLLM `gen_random_states` / `torch_random_states` 和 driver RNG 已恢复；
- Task 2 current classes 是下一增量 split，prompt seen classes 是累计 seen split；新 train loader cursor=0，未读取 Task 1 dataloader cursor；
- actor 恢复后才调用生产 `copy_actor_to_anchor()`，anchor fingerprint 与恢复 actor 相符且 Task 2 update 后保持冻结；base reference identity 未变化。

### FRESH-RESUME-03：首个真实 Task 2 update

进程 B 执行至少一个真实 Task 2 update，记录 actor update、optimizer/scheduler 增长、CTAN group/advantage、retention anchor input、EMA increment、dataloader cursor 和新 checkpoint。不得用伪造 rollout、`n=1` 绕过 GRPO、直接 `load_weights` 替代生产同步或 probe 旁路。

### FRESH-RESUME-04：恢复后的边界再次可发布

进程 B 在 Task 2 完成边界发布新的 `task2-complete`；manifest/marker 与新 output root 匹配，旧 Task 1 boundary 根保持不变。`save_task_ckpt=none` 必须拒绝发布可恢复 marker。

## 状态精度与轨迹声明

### STATE-EXACT-01：存储状态

独立验收必须逐项报告 source/model/input/config/classplan、checkpoint file manifest、global step、actor/optimizer/scheduler、EMA、worker native RNG、driver RNG、vLLM RNG、fresh Task 2 loader policy 和 anchor provenance/fingerprint。任一字段没有持久化或 hash 绑定，都不能写 state-exact pass。

### TRAJECTORY-CLOSE-01：非确定 kernel 边界

固定 source/model/input/GPU/config 后比较 fresh process 与同栈连续路径的 Task 2 短窗口：raw reward/retention reward、EMA update、优势分布、optimizer/scheduler step 和有限 metrics，使用验收前冻结的数值容差。BF16、FlashAttention、异步归约和 vLLM sampling 可能使逐值轨迹不同；只要状态契约通过，不要求逐 token、逐参数或全轨迹 bitwise equality。

### FAILCLOSED-01：资源/身份异常

在不启动 rollout 的前提下，使用错误 source/model/input/config hash、旧 output root、被 pruning 的 boundary、缺少 vLLM/driver RNG 或新进程仍传 `None` 的条件运行负例。预期是保留错误证据并终止，不能通过“从头重跑 Task 1”冒充恢复成功。

## 关闭门槛

只有 `CPU-*`、`REG-*`、`FRESH-*`、`STATE-EXACT-01` 和 `TRAJECTORY-CLOSE-01` 均有独立原始证据，且报告明确区分两个进程，才可关闭 `CAND-RESUME-CIL-001`。在此之前只能写 `fresh_process_resume=not_accepted`，不影响已有限定的 continuous runtime 结论。
