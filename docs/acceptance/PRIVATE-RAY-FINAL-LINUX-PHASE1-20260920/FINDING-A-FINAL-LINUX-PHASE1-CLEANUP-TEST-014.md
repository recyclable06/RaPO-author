# FINDING-A-FINAL-LINUX-PHASE1-CLEANUP-TEST-014

Status: `OPEN / BLOCKING`

## Observed false positive

The direct wrapper returned
`PASS_PRIVATE_RAY_ZERO_GPU_CLI_FINAL_SUPERVISOR_LINUX_STANDARD_LIBRARY_CHECK`,
but the actual supervisor result was `FAIL_ZERO_GPU_SUPERVISOR_LIFECYCLE` before
the launcher. The test then accepted that controlled failure after asserting
only `launcher_process_tree_verified`, `all_owned_processes_gone`, and
`temp_root_removed` (`run_supervisor_tests.py:312-316`).

The supervisor result has empty head and launcher owned-process collections,
`head_returncode=null`, and no saved post-cleanup `/proc` snapshot, while
reporting all of those success booleans. The synthetic child PID and its exit
identity were not retained. An empty set therefore satisfies the test without
proving that any process was observed or cleaned up; a child that exits on its
own cannot be attributed to supervisor cleanup.

## Impact

The Linux check can return `PASS_*` for a pre-launch or early identity failure.
It does not currently establish head readiness, launcher startup, expected
timeout, process ownership, signal delivery, reaping, or residual absence.

## Minimum repair allowlist

Change only the FINAL supervisor cleanup/result fields, the Linux fake check,
and the external evidence contract. Once a head has spawned, retain a verified
head identity and every observed descendant. If discovery or post-cleanup
verification is unavailable, report `cleanup_unknown`/failure and do not set
`all_owned_processes_gone=true` or remove the temp root. Record signal actions,
reaping, and a post-check for each captured PID/start/UID identity.

The normal Linux check must use a controlled head-ready marker, a launcher
ready marker, a launcher child created with `start_new_session=True`, and a
bounded production timeout. It must assert non-empty ownership observations
before cleanup and prove all captured identities are gone afterward. A separate
early-failure test may assert fail-closed behavior, but must not be converted
into the lifecycle PASS path.

## Acceptance

`PASS_*` is valid only when head readiness, launcher start, expected timeout,
non-empty ownership records, signal/kill/reap actions, final procfs absence,
and conditional temp-root removal are all evidenced. Any missing identity or
empty collection after a spawned head is an explicit failure/unknown result.
