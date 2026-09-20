# PRIVATE-RAY-FINAL-LINUX-PHASE1-20260920

Status: `BLOCKED_EARLY_HEAD_IDENTITY`.

This was one bounded Linux/procfs standard-library diagnostic on host `211`.
The final bundle was loaded with `importlib` and
`run_linux_process_check()` was called directly. `run_supervisor_tests.py:main()`
was not invoked, so the frozen final `test-results.json` was not overwritten.
The run used the exact source basenames as sibling directories, the existing
diagnostic Python 3.11.6 environment, `PATH` prefixed with that environment's
`bin`, empty `CUDA_VISIBLE_DEVICES`, `PYTHONDONTWRITEBYTECODE=1`, and `python -B`.

The wrapper process exited `0` and the function returned
`PASS_PRIVATE_RAY_ZERO_GPU_CLI_FINAL_SUPERVISOR_LINUX_STANDARD_LIBRARY_CHECK`.
That function result cannot be used as a complete Phase 1 pass: its test
intentionally asserts that the synthetic lifecycle returns
`FAIL_ZERO_GPU_SUPERVISOR_LIFECYCLE` and then checks cleanup. The actual
supervisor result failed before the launcher and running record:

`SupervisorError: private Ray executable identity changed`

The supervisor started the fake head and completed runtime validation, then
failed during the live executable identity check. The recorded head command
used a fake CLI with shebang `#!/usr/bin/env python3`, `--num-gpus=0`,
`--num-cpus=3`, and private temp root `/tmp/zlf-s20l`. The record does not retain
both executable values, so an exec-transition race is only a hypothesis and is
not asserted as the finding. Because the failure happened before
`_write_running_record()` and `_wait_launcher()`, there is no launcher log or
private supervisor record; `raw/launcher-and-record-absence.txt` and
`raw/supervisor-root-listing.json` preserve that fact.

The early failure did produce a bounded head log and entered the supervisor's
cleanup path. The head stdout log is 250019 bytes and file-backed; head stderr
is empty. The supervisor result reports `all_owned_processes_gone=true`, an
empty final owned-process list, `temp_root_removed=true`,
`cleanup_unowned_action_used=false`, and no global `pkill` or `ray stop`.
However, `head_returncode` is null, the result contains no post-cleanup
`/proc` snapshot, and no independently saved post-run process query exists.
Those fields therefore do not prove that the started head was fully released;
resource release remains unverified in this phase. The supervisor root listing
contains only this run's validation, head logs, and supervisor result. No real
Ray service, GPU, model, or training was started, and SIGINT/SIGTERM delivery
was outside this phase.

The final runtime and both frozen sibling snapshots were checked before and
after the call. Every listed file matched its expected bytes and SHA-256;
`runtime-unchanged.json` is true. Fixed identities were:

- final `HASHES_FINAL.json`: `3b9f055da492741754f80b63e2255716e118fea546bca429267c542877136f67`; `MANIFEST_FINAL.json`: `fc97026c8e51f137d3106d0f918ff3577d8a2886b230f443023e2579d08de0b0`;
- parent `HASHES_SUPERVISOR.json`: `f4914b91d91b1b31873457e195805762c930b89c656fe09115d25b9502ee98d9`; manifest: `cac9d08d0c3b68d47218183ca21d61cb944d647d15d15746ec01ed350a84c119`;
- zero-GPU `HASHES_ZEROGPU.json`: `3635a3afd975d35770a1e9c41841da62fe3051be37ff95d39ffeeb5d19e3a003`; manifest: `eae681218644bd759152658d425777b7cc3c6e80869a681e1415b01da104c4ed`.

The first attempted call used short deployment aliases and stopped at the
fixed sibling lookup with `FileNotFoundError`, before any child process. It was
not blindly rerun: the deployment was corrected to the three exact basenames,
then the single recorded direct call above was made. The detailed raw command
stdout/stderr/exit, invocation history, runtime identities, validation, logs,
procfs summary and result are under `raw/`.

The recursive transfer also left a byte-identical nested copy of the remote
output under `raw/rapo-author-a-private-ray-supervisor-phase1-output-20260920-fullbasename/`.
It is retained as collected evidence; `HASHES.json` includes both copies and
reports 34 files; the largest file is 250019 bytes.
