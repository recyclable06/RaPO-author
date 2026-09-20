# Private Ray FINAL Linux Phase 1 failure audit

Date: 2026-09-20  
Role: independent read-only audit  
Verdict: `FAIL_EARLY_HEAD_IDENTITY_NOT_PHASE1_PASS`

The bounded Linux/procfs call did start the synthetic head, but the supervisor
failed during live executable identity verification:

`SupervisorError: private Ray executable identity changed`

The failure occurred before readiness, the running record, and launcher start.
The wrapper itself exited `0` and returned
`PASS_PRIVATE_RAY_ZERO_GPU_CLI_FINAL_SUPERVISOR_LINUX_STANDARD_LIBRARY_CHECK`
because `run_linux_process_check()` intentionally expects a controlled
`FAIL_ZERO_GPU_SUPERVISOR_LIFECYCLE` and then asserts only a few cleanup
booleans. That wrapper result is therefore a test false positive, not a Phase 1
lifecycle pass. No real Ray service, GPU, model, training, or A-mode run was
started.

## Frozen scope and evidence

The reviewed runtime is the FINAL four-file bundle:

- `HASHES_FINAL.json` SHA-256:
  `3b9f055da492741754f80b63e2255716e118fea546bca429267c542877136f67`
- `MANIFEST_FINAL.json` SHA-256:
  `fc97026c8e51f137d3106d0f918ff3577d8a2886b230f443023e2579d08de0b0`
- `private_ray_supervisor.py` SHA-256:
  `fc37f34dd4459fb3050fe7ffee79cfc8d5da1bd69da022ae721fe827486eb302`

The raw execution bundle is
`docs/diagnostics/PRIVATE-RAY-FINAL-LINUX-PHASE1-20260920/`. Its frozen
`HASHES.json` identity is `f1f9573c831ce802f40e8975a110452c749cfbf1d2e2893bdf53e931ffbba2ef`
(34 files, 608549 bytes). The raw `supervisor-result.json` is 5155 bytes with
SHA-256 `70dfa9018d5536efa0c51fb2a66088f0a3a2d07b92b860030c1fae6f1d2ef1c7`.

The recorded result has `head_spawned=true`, PID `299497`, and
`head_returncode=null`. `ray-head.stdout.log` contains 250019 bytes and
`ray-head.stderr.log` is empty. `launcher-and-record-absence.txt` and
`supervisor-root-listing.json` establish that the failure preceded
`_write_running_record()` and `_wait_launcher()`; no launcher log or running
record was produced.

The cleanup result reports `all_owned_processes_gone=true`,
`launcher_process_tree_verified=true`, `temp_root_removed=true`, and
`cleanup_unowned_action_used=false`, but all four owned-process collections are
empty, `head_returncode` is null, and no saved post-cleanup `/proc` query or
head PID/start/UID after snapshot exists. Resource release is therefore
`UNKNOWN` for this run. An empty collection cannot establish that the head or
launcher was registered, signalled, reaped, or absent after cleanup.

## Finding A — early head executable identity failure

See `FINDING-A-FINAL-LINUX-PHASE1-IDENTITY-013.md`.

This is a blocking lifecycle failure and an identity evidence gap. The raw
bundle does not preserve the first and subsequent `/proc/<pid>/exe` values, so
an `/usr/bin/env` to Python transition is only a hypothesis. The synthetic CLI
does use `#!/usr/bin/env python3` (`run_supervisor_tests.py:269`), while the
211 CLI preflight records the actual `bin/ray` shebang as an absolute Python
path (`RAY-CLI-ENTRY-PREFLIGHT-20260920/raw/06-ray-script-shebang.stdout.txt`).
The fake shebang behavior must not be projected onto the real Ray executable
without a separate run.

The minimum implementation change is limited to the FINAL supervisor identity
capture and its Linux test/evidence contract. After `Popen`, it must wait for a
stable post-exec identity and retain before/stable/after records for PID,
procfs start time, UID, session, process group, executable, argv, and argv
digest. It must continue enforcing the existing PID/start/UID/session/group
and command identity checks after the stable identity is selected. If stable
identity cannot be obtained, the run must fail closed with explicit evidence;
it must not silently relax those checks.

## Finding B — empty cleanup collections make the Linux test pass falsely

See `FINDING-A-FINAL-LINUX-PHASE1-CLEANUP-TEST-014.md`.

The current Linux test asserts only that the supervisor status is `FAIL`, the
launcher tree is marked verified, all owned processes are gone, and the temp
root was removed (`run_supervisor_tests.py:312-316`). Since the observed failure
happens before launcher start and before owned-process capture, an arbitrary
early failure can satisfy those assertions with empty lists. The wrapper's
`PASS_*` result consequently does not prove head readiness, launcher startup,
descendant tracking, timeout handling, or cleanup.

The minimum implementation and test change is limited to the FINAL supervisor,
`run_supervisor_tests.py`, and the external-result documentation. Once a head
has spawned, cleanup must either retain and verify its identity and every
observed descendant, or report `cleanup_unknown`/failure. An empty discovery
result must not permit `all_owned_processes_gone=true` or temp-root deletion
unless the captured PID/start/UID set has an independently recorded post-check
showing that each process is gone. The test must prove head readiness, launcher
start, a launcher child in a new session, and the expected production timeout
before accepting cleanup. A generic expected `FAIL_ZERO_GPU_SUPERVISOR_LIFECYCLE`
is insufficient.

## Minimum repair allowlist

The independent remediation may touch only:

1. `private_ray_supervisor.py` in the FINAL runtime, limited to post-exec
   identity stabilization, early head ownership capture, cleanup unknown/fail
   handling, reaping/post-check recording, and related result fields.
2. `run_supervisor_tests.py` in the FINAL runtime, limited to the Linux fake
   process check, its assertions, stable-identity/shebang regression coverage,
   and external output handling.
3. The associated FINAL command/phase documentation and raw recorder needed to
   describe the corrected invocation and evidence.

The remediation must not modify training code, observer code, scientific
parameters, GPU selection, the 0-GPU resource budget, the existing parent or
zero-GPU snapshot identities, or the separate SIGINT/SIGTERM harness scope.

## Acceptance standard

A corrected fake Linux check is acceptable only when its frozen raw evidence
shows all of the following:

- final runtime bytes and hashes are unchanged before and after the call;
- the synthetic head is spawned and reaches an explicit readiness marker;
- stable post-exec identity records include the same PID, procfs start time,
  owner UID, session, process group, executable, argv, and argv digest across
  the required samples;
- the launcher starts, its new-session descendant is observed with its own
  PID/start/UID identity, and both head and launcher ownership collections are
  non-empty before timeout cleanup;
- the bounded production timeout is the triggering condition, rather than an
  arbitrary early failure;
- cleanup records the signals/actions, reaps owned processes, and stores a
  post-cleanup procfs check proving every captured PID/start identity is gone;
- temp-root removal occurs only after that proof, and any missing or uncertain
  identity yields an explicit failed/unknown result;
- the returned Phase 1 status is derived from these lifecycle facts and cannot
  be `PASS_*` merely because an expected failure was observed.

The separate Linux signal harness must still send real SIGINT and SIGTERM to a
controlled supervisor PID and verify its cleanup; direct handler calls and
descendant cleanup signals do not close that existing evidence gap. A real
Ray 2.46.0 zero-GPU lifecycle using the verified absolute `bin/ray` entrypoint
must be run separately before any A-mode dispatch. This fake-process result
cannot substitute for it.

## Scope boundary

This audit is read-only. It did not modify the FINAL subject, production code,
raw execution evidence, or runtime snapshots; it did not SSH, start Ray, use a
GPU, load a model, train, or rerun the diagnostic.
