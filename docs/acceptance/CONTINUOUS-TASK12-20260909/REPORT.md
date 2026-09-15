# 同进程连续 Task 1→Task 2 独立验收报告

更新：2026-09-09。角色：独立验收。对象：`cross-task-resume-20260909` 的冻结诊断描述、固定运行证据，以及 `codex/integrate-accepted-fixes` 的只读源码身份。

## 结论

独立判定为：`PASS_LIMITED_CONTINUOUS_RUNTIME_WITH_SCOPE_NOTES`。

冻结证据支持一个有界的同进程连续路径：同一个 production `PersistentRunner`、同一个 world-size-2 worker group 连续执行 Task 1 和 Task 2；Task 1 在 global step 2 结束，Task 2 从 step 2 延续到 step 4。actor、anchor、CTAN、EMA、optimizer/scheduler 和 checkpoint 观察门均通过。

这不是跨进程精确恢复证明，也不是 paper-scale training、COCO AP 或原始实验身份证明。`CAND-RESUME-CIL-001` 仍开放，阶段 5 的跨任务与恢复 gate 仍为 `NOT PASSED`。

## 验收边界与方法

本验收只读取冻结的诊断和运行证据，使用本目录的 [`independent_probe.py`](independent_probe.py) 进行标准库独立复核。探针不导入 production module，不启动 Ray/GPU，不执行训练，也不改写诊断或运行证据；它独立解析 raw task records、重判结果、production experiment log、checkpoint manifest、源码清单和 postflight 资源记录。

起止检查均通过：

- `cross-task-resume-20260909/HASHES.json` 声明的 12 个目标文件全部匹配，起止 manifest SHA-256 均为 `0814e7fe716c112aac078fae45f2b5962f838e53a1d2043b237627caddf0aae8`。
- `continuous-runtime-evidence-20260909/HASHES.json` 声明的 45 个运行证据文件全部匹配，起止 manifest SHA-256 均为 `21e57f9d6c0432fbad0a7c8d11080251353d8f2f1b8ee6dc2b2d9f452490465f`。
- 完整重判结果 `continuous-probe-result-rejudged.json` 的 SHA-256 为 `d9397499c7d7f66fadfd334be12c3fc340bab718c3f06e6d786e3f8c1832ef34`。

目标诊断和运行证据在验收期间均未发生漂移。起止细节见 [`hash-start-end-compare.json`](hash-start-end-compare.json)，完整机器可读判定见 [`independent-evidence.json`](independent-evidence.json)。

## 运行与源码身份

- Host：`gpu-211`；目标物理 GPU：4、6。
- worker rank 0/1 的 CUDA-visible device、Ray GPU ID 和 UUID 在采集快照中均与物理 GPU 4/6 的 preflight UUID 匹配。
- model：`Qwen2-VL-2B-Instruct-895c3a4`。
- source entry SHA-256：`8a13974e3dfa7756a076844ce25ef6d66c71c29751fd2dec2f00a52b49092f3d`。
- diagnostic config SHA-256：`6093d4d72cef88b07d3a1b16cc8f49ba7c51163fdd01e05daab9cd7236eef0ab`。
- input manifest SHA-256：`eccd0dfe6c159eaca002ad016bb3a7bfe36578b4212957321f3c4ee41975e2af`。
- 集成源码清单 SHA-256：`6514f4dca401ffc805ae57031d1926f742e531ce0fbb981448315538ade8b0b1`；清单中的 6 个算法文件和 4 个测试文件均与当前文件 hash 匹配。
- 远端运行根：`/mnt/conda/zhenglifeng/rapo-author-cross-task-resume-20260909-attempt3/2026-09-09-143138`。

静态链复核确认探针调用真实 `PersistentRunner`、production CIL entry、原始 `run_task`、原始 `trainer.fit()`、production actor update、RaPO advantage hook 和 checkpoint manager；探针的 reinit、anchor copy、advantage 观察均包裹原调用，没有直接以 `load_weights` 代替 production 同步。源码工作树的 Git 状态因 safe-directory ownership 被 Git 拒绝读取，但这不影响已固定的 integration manifest 和逐文件 hash 身份判断。

## 关键运行证据

| 检查 | 独立结果 |
| --- | --- |
| runner / worker group | 同一 runner PID、同一 worker group、world size 2 |
| Task boundary | Task 1 after=2；Task 2 before=2、after=4；Task 2 reinit 的 `last_global_step=2`；Task 2 的配置 checkpoint 指向 Task 1 `global_step_2`，reinit 未执行磁盘 reload |
| production weight actions | Task 1 不执行 copy/enable；Task 2 执行 actor→anchor copy 和 enable anchor |
| actor / anchor | 两个 task 的 actor 均更新；边界 actor 连续；copy 前后和 freeze 检查通过，但比较是 sampled equality，不是全参数逐值证明 |
| CTAN / advantages | 4 次 advantage call；每次两个 UID group、每组 4 条；raw reward finite 且有组内变化，advantages finite 且非零 |
| retention | Task 2 step 3：期望/实际 delta sum 均为 `4.0`；step 4：期望/实际均为 `3.837252140045166`；由 production `experiment_log.jsonl` 聚合精确复核 |
| EMA | Task 1 end `update_count=2`；Task 2 reinit=2 且 payload 匹配；Task 2 end 和 sidecar=4；4 次递推检查通过 |
| optimizer / scheduler | 两个 rank 的对象、边界状态和非空状态连续，step 均增长 |
| checkpoint | Task 1 `global_step_2`、Task 2 `global_step_4` 各 18 个文件、各 `18,157,120,496` bytes；model、optimizer、extra state、dataloader 和 tracker payload 均在清单中 |

## 限制与范围修正

1. 这是同一个进程内的 `PersistentRunner` Task 1→Task 2 连续运行，不是新进程启动 Task 2 的 exact resume。没有覆盖 production-supported task-boundary entry、任务游标/seen-class plan、anchor 重建、EMA 与 checkpoint 原子绑定，以及新进程配置和数据游标协议。
2. actor/anchor 证据来自采样参数记录；它证明采样点的变化/相等，不证明全模型逐参数 equality。
3. 运行证据没有归档 standalone shell exitcode、stdout、stderr 或明确的 Ray shutdown 结果。独立检查未在可用 stderr 中发现 error-like 行，postflight 记录显示选定 GPU 4/6 idle，因此日志清理门按 `limited` 接受，不能把它表述为完整执行器成功/无错误证明。
4. 可选的 pre-model mapping 属性没有被 colocated WorkerDict 保留；实际 CUDA-visible device、Ray GPU ID 和 UUID 在各快照中仍与 preflight 一致，因此当前 mapping gate 通过，但该属性缺失被保留为覆盖说明。
5. 原始 task record 没有直接暴露 retention tensor formula 所需的逐样本字段；本验收只接受 production log 的 exact aggregate reconciliation，并明确标为 limited basis。

## 阶段判定与下一 gate

本轮通过的是“有界同进程连续运行”证据，不关闭 `CAND-RESUME-CIL-001`，不宣布作者代码达到正式复现放行条件，也不启动正式训练。

解除下一 gate 的最小证据是：在保持 source/model/input/GPU 身份可审查的前提下，另行执行并独立验收跨进程 Task 1→Task 2 的真实恢复入口和完整状态协议，至少覆盖 checkpoint 选择、task cursor、anchor、EMA、optimizer/scheduler、RNG 和数据游标；不得用本轮同进程连续结果替代。

本验收没有修改 production code、输入、legacy root、既有 GPU 诊断或运行证据；新增内容仅在本目录。

