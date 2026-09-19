# B worker-log narrow review

Date: 2026-09-19

## Result

This is a read-only local review of the corrected B phase evidence and the worker-log supplement. The supplement is internally consistent, but it does not recover a concrete worker stdout/stderr path or the internal abort cause. The result is therefore `PARTIAL_EVIDENCE_SUPPLEMENT`, not a scientific reproduction pass.

The corrected phase remains: B completed model, FSDP, vLLM, and persistent-worker initialization. Rank 0/PID `1161595` and rank 1/PID `1162100` both stopped at `PersistentRefFSDPWorker.init_anchor` `BEFORE` with no matching `AFTER`. No `run_task`, native checkpoint restore, or `fit` call was observed.

## Supplement integrity and scope

- Delivery manifest SHA256: `4a0783da323cec6858fc8d3729db4909a1a845607d3182dc321b1461d9a902e6`.
- The manifest declares 20 files totaling 13,695 bytes; all entries, sizes, and hashes match.
- `EVIDENCE_INDEX.json` SHA256: `6d934e1d1930acf8f4fce71330f7b0b8d5f158e995294d9a5091d848b01eb690`.
- The index covers 19 artifact files totaling 9,803 bytes. It records zero worker-log files and zero copied worker-log bytes.
- No weights or tensors were accessed or hashed. This review performed no new SSH, rerun, training, cleanup, or host-211 handling.

## Worker-log search result

The supplied raw records contain three limited searches against the recorded Ray session on host `207`:

1. PID-based `.out`/`.err` filename enumeration under `session/logs`.
2. PID-based `.out`/`.err` filename enumeration under the full session root.
3. PID content correlation in session `*.out`, `*.err`, and `*.log` files.

All three recorded an outer exit value of `0`, with empty stdout and stderr. The correlation record reports zero matching paths, zero copied files, and no path/size/mtime records. The already-copied 13 Ray service/driver logs also contain no exact target-PID content.

This is bounded negative evidence only. The commands do not use `pipefail`, so the recorded outer exit value cannot independently prove that every `find`, `grep`, or `xargs` stage succeeded. The correct statement is: the specified searches found no target-PID path or content; they do not prove that worker logs never existed or are absent from every location.

## Existing inventory limitations

The original inventory stdout has the expected `B_VALID`, `B_SUPERVISOR`, and `RAY_LOG_CANDIDATES` section boundaries. Its Ray section contains 318 regular-file rows, including 56 `python-core-worker-*` rows and 112 `worker-*.out/.err` rows. The exact target PIDs occur only in the two already-copied B observer event paths; there are no exact target-PID hits in the Ray section.

The inventory is not a complete proof of absence:

- The inventory script exited `127` because its CRLF final line was interpreted as `bash: line 38: $'\\r': command not found`.
- Each `find` was wrapped in `timeout 15s ... || true`, so a per-section timeout or find failure was not recorded independently.
- The Ray scan used `find -P ... -type f`; symlink entries were not enumerated and symlink targets were not followed.
- The Ray scan was limited to `-maxdepth 4` and a fixed set of log-like extensions.

These are concrete collection gaps, not evidence that a worker log was rotated or that a symlink existed. No specific rotation path, deleted file, or symlink target was recovered from the supplied evidence.

## Finding and minimal next observation

Finding `B-WORKER-LOG-LIMITATION-001` remains open: the worker-log identity and internal abort cause are not recovered. The child exited with code `-6`; supervisor records show `child_term_sent=0` and `child_kill_sent=0`, so the SIGTERM text is not attributable to the supervisor from current evidence. Host-211 cleanup remains `UNCONFIRMED`.

If a future B observation is authorized, keep it narrow and capture, at worker bootstrap and for only the two target ranks: PID plus `/proc/<pid>/stat` start ticks, Ray worker ID, cwd, and the `/proc/<pid>/fd/1` and `/proc/<pid>/fd/2` symlink targets. Record the exact worker-log path, supervisor exit metadata, and independent exit status for each discovery stage; use `set -o pipefail` for pipelines. Retain only the target-rank tails and the corresponding supervisor/Ray metadata, with no full-tree scan and no weight/tensor access.

