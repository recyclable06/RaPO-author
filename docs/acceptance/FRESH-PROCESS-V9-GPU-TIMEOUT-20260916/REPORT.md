# FRESH-PROCESS-V9-GPU-TIMEOUT-20260916

## 结论

独立复核确认候选运行的结论应保持 `BLOCKED_C_TIMEOUT_AFTER_TASK1`，不能升级为 PASS 或科学复现验收。C 确实走过模型构造、rollout/reward、Task 1 实际训练和 checkpoint 保存；但在 Task 2 的 dataloader/reinit 过渡后，900 秒 outer timeout 到期，未观察到任何 Task 2 actor update。

保留的 structured production、observer 和 Ray 日志没有发现 OOM、实际 traceback、CUDA/NCCL/fatal runtime marker。这个结果不等价于“完整运行无异常”，因为完整 production stdout/stderr 和 wrapper 的 process-end 边界并未保留。

## 逐项证据

Observer 目录包含 81 个 JSONL 文件、426 行，独立解析错误为 0。`target_wrapper_call_before` 和 `target_wrapper_call_after` 各 27 个；其中 `FSDPWorker.update_actor` 有 4 个成对调用，覆盖 rank 0/1 各两次，且每个 after 都是 `returned`、`complete=true`。因此观测计数为：Task 1 `2/2`，Task 2 `0/2`，总计 `2/4`。

`experiment_log.jsonl` 有 3 条合法 JSON 记录：2 条训练记录（step 1、2）和 1 条 step 2 validation 记录。两条训练记录的 reward overall 都是 `0.375`；没有 Task 2 训练记录。CIL metrics summary 和 `task_metrics.log` 也只发布了 Task 1 指标（`last_acc=50.0`）。

## 时间线（observer Unix time）

| 事件 | 证据时间 |
|---|---:|
| Driver `PersistentCILTrainer.fit` entered | 1789562631.241786 |
| Task 1 update 1：rank 1 before → after | 1789562701.3523324 → 1789562772.8940294 |
| Task 1 update 1：rank 0 before → after | 1789562702.0888612 → 1789562773.2478416 |
| Task 1 update 2：rank 1 before → after | 1789562848.818342 → 1789562919.0210385 |
| Task 1 update 2：rank 0 before → after | 1789562849.169566 → 1789562919.4673393 |
| Driver `_save_checkpoint` entered → returned | 1789562928.307839 → 1789563191.6737876 |
| Driver `fit` returned | 1789563191.726094 |
| Post-checkpoint dataloader returns | 1789563191.9336312; 1789563200.9202654; 1789563201.0536625 |
| Post-checkpoint `reinit_for_task` returned | 1789563201.1704686 |
| After that point | No `FSDPWorker.update_actor` event; timeout boundary followed |

Checkpoint worker/manager events also returned for both ranks. The original remote inventory lists the six expected world-size-2 actor files with concrete sizes, but no file hashes or remote bytes are present in this acceptance workspace. The independent classification is therefore `remote_inventory_structural_listing_only`, not content-integrity verification. The locally retained `model_world_size_2_rank_1.pt` is only 1,804,271,616 bytes versus the listed remote size 2,442,685,994 bytes and is explicitly excluded from judgment.

## 异常与日志边界

The lexical scan found 92 matches in Ray service logs, all classified as expected lifecycle/teardown messages (37), zero/status counters (54), or one pre-run cluster cleanup line. There were 0 high-risk runtime markers. The pre-run cleanup line is the GCS message at 20:39:50, before the production path timestamp 20:39:57. Observer events had 0 matches. The retained runtime evidence had only explanatory boundary text matches and 0 high-risk runtime markers; it is not complete stdout.

The C leg used a 900-second outer timeout with SIGTERM on expiry and returned SSH exit code 1. The candidate tree has no `run-result.json`, `process-end.json`, `process.stdout.log` or `process.stderr.log`. `C-ssh.stdout.txt` is explicitly a normalized console excerpt, not complete raw production stdout. A/B and trajectory judge were not run.

## 交付层限制

The candidate delivery manifest self-hash independently recomputes to `f8ea1a5562aa05f03b741808c64346ef08d7525bc7342738bf7c0bf692da8463`. Its 439 entry lines sum to the declared 1,831,106,053 bytes. However, the manifest as a whole is not valid JSON: `generated_at` contains a literal line break (`Invalid control character at line 7 column 20`). This is a delivery-manifest defect, not evidence of a production exception; the raw evidence files were reviewed separately.

The candidate's final release check records that private diagnostic processes were absent, GPUs 4–6 were idle, and other users' GPU processes on GPUs 0–3 remained untouched. No release action was performed during this review.

## 后续边界

C remains blocked. Any continuation requires a separately authorized, still-bounded follow-up with the same frozen v9 identity and numeric PCI-ordered visibility, or a focused Task 2 transition diagnostic. The current R2 experiment in the root workspace is separate and is not replaced or judged here.
