# FRESH-PROCESS-V9-R2-20260917 独立验收审查

## 结论

本次是只读、独立的 R2 结果审查；未修改候选工作树、生产源码或远端状态，也未进行 SSH/GPU/模型/依赖/训练/重跑操作。

总判定保持为：**`BLOCKED_B_RESTORE_TIMEOUT`**。C 的连续生产证据可复用；A 证明了 Task 1 marker 已发布，但完整 boundary evidence 未成立；B 未产生 Task 2 更新，未证明 fresh-process exact resume。B-only 重跑不足以直接接受，且当前远端收尾状态仍未确认。

## 输入身份与审查边界

- R2 候选：`C:\Users\Administrator\.codex\worktrees\71a6\RaPO-author\docs\diagnostics\FRESH-PROCESS-V9-GPU-20260916-R2`
- R2 delivery manifest：73 项、2,840,712 bytes，SHA256 `7bc2d84c752ccd87982cb53ba8055dff0e25e5d23244541ba54067e0ee549244`
- closeout：`C:\Users\Administrator\.codex\worktrees\71a6\RaPO-author\docs\diagnostics\FRESH-PROCESS-V9-GPU-20260917-CLOSEOUT`
- production source：`C:\Users\Administrator\.codex\worktrees\8ac5\RaPO-author\examples\baselines\img_cls_cil\image_cls_cil_rapo.py`，SHA256 `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3`
- diagnostic sidecar：`C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\diagnostics\fresh-process-resume-20260911\v9`

## 分腿结果

### C：`PASS_C_PRODUCTION`，证据可复用

C 完成了连续 Task 1 → Task 2 生产路径：4 个 training updates，global steps `1,2,3,4`，进程和 launcher 均为 exit 0，stdout/stderr/process-end/run-result 边界齐全。

- Task 1：steps 1–2，overall reward `0.375, 0.500`；最后准确率 `50.0`。
- Task 2：steps 3–4，overall reward `0.500, 0.625`；step 4 retention drift `0.004269292578101158`，retention reward `0.9256303310394287`。
- checkpoint inventory：36 个文件、总字节 `36,314,240,992`，每文件 SHA256 清单 SHA256 `72dbe33d171cc2f9d1c6243d76aa75d7836395bbc6d4462c40db829c487fe7cd`。这是远端逐文件 size/hash inventory，不等同于本机重新读取 checkpoint 内容。
- 完成结果高风险扫描未发现 OOM、traceback、CUDA error 或 NCCL failure。末尾 Ray worker shutdown 信息发生在生产 exit 0 之后，属于清理阶段，不能倒推为训练失败。

C 可支持连续生产更新、指标、launcher/child 结束边界及 checkpoint inventory；不能单独支持 fresh-process resume、A 完整 boundary 或 B restore。

### A-invalid：`BLOCKED_GPU_PREFLIGHT`，无科学效应

数值 CVD 未解析到冻结的 ordered UUID，模型未构造、训练未开始；该腿不产生科学结果，也不应被当作训练失败样本。

### A-valid：`PASS_TASK1_MARKER_BUT_BOUNDARY_INCOMPLETE`

A-valid 进程 exit 0，模型已构造并完成 Task 1 的 2 个 training updates，随后停止在 Task 2 之前。marker 本地字节数 `40,138`，SHA256 `c7b8c132de4346bba8c570d429bdcbef603c0bbeea6bfd8803fea84175d4f795`，`status=complete`、`completed_task=1`、`global_step=2`、`next_task=2`，marker 内的 Task 1 checkpoint manifest 也存在。

但 `boundary-expected.json` 为 `complete=false`，`driver=null`，错误为 `A actual post-publication driver RNG capture is missing`。候选中没有 raw observer event 文件；marker 引用的三个 `boundary_state` 文件也没有随候选交付，因此不能独立证明这些引用文件的内容：

- `boundary_state/driver_rng.json`：未交付；marker 记录 SHA256 `46982e7ff065f5ddcbe754919de364a214becbcd93b88f0d88d36e0e5e348fa3`
- `boundary_state/vllm_rng_rank_0.json`：未交付；marker 记录 SHA256 `f6bb080f94c2267d2bf784ab45bba0a8d8f40bef2c5fdab20bef291ad8899418`
- `boundary_state/vllm_rng_rank_1.json`：未交付；marker 记录 SHA256 `56046e84a0716523ea7a23e0ae9dab7aa7514124a20681603225131aaac00c13`

源码核对显示，生产 `image_cls_cil_rapo.py` 的 `_publish_task_boundary` 在第 881 行写入 `driver_rng_payload`，`PersistentRunner.run_task` 在第 1546、1566、1573 行进入发布路径、采集 vLLM RNG 并传入 `_capture_driver_rng_state()`；marker 是最后写入。因此当前证据足以确认“诊断观察/采集链不充分”，不足以把问题定性为生产 publication defect。具体 finding 见 [FINDING-A-OBSERVER-001.md](FINDING-A-OBSERVER-001.md)。

### B-valid：`INCOMPLETE_RESTORE_TIMEOUT`

B 保留的是 `raw/B-timeout-observations.txt` 摘要，不是完整 raw stdout/stderr/process-end/run-result/Ray/event 证据。摘要记录：

- child 身份和 restore-stage 位置曾被验证；最后成功远端检查时没有 Task 2 update。
- child 曾处于 `D`/disk sleep，伴随高 `rchar`；这与 restore I/O 相容，但不能证明 I/O 是根因。
- deadline 后只对已重新核验身份的 child 发送 SIGTERM；私有 Ray 清理过程中 child 输出管道导致 launcher 未完成最终化，SSH evidence stream 随后中断。
- 因而没有 B exit code、完整输出、最终 Ray/launcher/child/GPU release state。B 只能复用为“未建立 Task 2/exact resume”的负证据，不能复用为 restore pass、退出判定或资源释放结论。

## Closeout 状态

closeout 只执行了 1 次 strict-hostkey、只读连接探针；host 211 返回 SSH exit 255，stderr 为 `Timeout, server 192.168.1.211 not responding.`。本次没有执行清理命令、全局 Ray stop、pkill、训练或 B 重跑；远端身份未重新核验，最终 cleanup/release **`UNCONFIRMED_HOST_UNREACHABLE`**。

因此不得声称远端已释放。最小解除条件是恢复 host 211 访问后，重新执行同一受限只读 identity probe；只有在 PID、start ticks、cmd、cwd、env 与冻结 run-root/session 精确匹配后，才可讨论定向收尾。

## 复用与下一步

当前可复用范围是 C 的连续生产证据，以及 A 的 Task 1 marker/更新负载证据。A 完整 boundary 和 B 的任何正向 resume/cleanup 结论均不可复用。

最小恢复路径：先隔离或修复 Ray child-pipe/restore-stage 失败，并在诊断侧收集 raw A observer events 与 marker 引用的全部 `boundary_state` 文件；不要伪造 RNG。A boundary 完整后，再以 fresh process、完整 stdout/stderr/process-end/run-result 及 observer/Ray 证据单独执行已授权的 B acceptance leg；保持原 reward/advantage/retention 容差不变，并验证 B Task 2 updates 与 boundary 对比。

本审查不关闭 paper-faithful reproduction、COCO AP、完整实验或 `AUTH-CTAN-001`/`AUTH-COCO-001` 科学门禁。

