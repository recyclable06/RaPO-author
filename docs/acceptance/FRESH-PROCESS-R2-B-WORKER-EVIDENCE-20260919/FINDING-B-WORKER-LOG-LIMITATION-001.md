# B-WORKER-LOG-LIMITATION-001

Status: OPEN / NOT RECOVERED

## Statement

The corrected B evidence establishes the phase boundary at `PersistentRefFSDPWorker.init_anchor` `BEFORE` on both ranks, but the supplied local evidence does not identify the corresponding worker stdout/stderr files or the internal cause of the child exit `-6`.

## Evidence

- Target PIDs: `1161595` and `1162100`.
- Three recorded searches returned no matching filename or content; each has empty stdout/stderr and an outer exit record of `0`.
- The supplement copied zero worker-log files and zero worker-log bytes.
- The original Ray inventory contains 318 regular-file rows, but no exact target-PID hit in its Ray section.

## Collection gaps

The original inventory has a CRLF-induced exit `127`, masks each `find` status with `timeout 15s ... || true`, uses `find -P ... -type f` so symlink entries are not enumerated, limits the Ray scan to depth 4, and checks only selected extensions. The new search pipelines omit `pipefail`. These facts limit absence claims; they do not establish rotation, deletion, or symlink use.

## Required next observation

For a future authorized B run, capture the two target ranks at bootstrap with PID/start-tick identity, Ray worker ID, cwd, stdout/stderr fd symlink targets, exact log path, and per-stage command status. Preserve only those narrow tails and supervisor/Ray metadata. Do not access weights or tensors.

