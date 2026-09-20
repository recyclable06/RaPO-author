# FINDING-A-FINAL-LINUX-PHASE1-IDENTITY-013

Status: `OPEN / BLOCKING`

## Observed failure

The strict Linux/procfs direct call spawned the synthetic head, then failed
with `SupervisorError: private Ray executable identity changed` during the
live head identity check. It failed before readiness, `_write_running_record()`,
and launcher start. The raw result records `head_spawned=true`, PID `299497`,
and `head_returncode=null`; the head log contains 250019 bytes.

The raw evidence does not retain the first and later executable values. The
fake CLI source uses `#!/usr/bin/env python3`, so an exec-transition race is a
plausible mechanism, but it is not established. The real host `bin/ray`
preflight records an absolute Python shebang, and no actual Ray start was
performed; the fake behavior must not be generalized to that entrypoint.

## Impact

The result is an early supervisor failure, not a verified Linux Phase 1 pass.
Readiness, launcher startup, descendant tracking, timeout behavior, and actual
Ray lifecycle remain unobserved.

## Minimum repair allowlist

Change only the FINAL `private_ray_supervisor.py` identity startup path and the
corresponding `run_supervisor_tests.py`/raw evidence contract. After `Popen`,
capture and persist the initial identity, poll until the executable/argv
identity is stable after exec, and persist the stable and post-readiness
identity. Continue to enforce PID, procfs start time, owner UID, session,
process group, and command identity. A failure to obtain a stable identity
must remain an explicit fail-closed result.

Use a stable absolute-interpreter synthetic CLI for the normal Linux lifecycle
test, and retain a separate regression test for a shebang exec transition.
Verify the real absolute `bin/ray` entrypoint in a separate zero-GPU lifecycle;
do not treat fake CLI evidence as real Ray evidence.

## Acceptance

The raw result must contain before/stable/after identity records with the same
PID/start/UID/session/group and the expected executable/argv digest, followed
by explicit head readiness and launcher startup. Any mismatch must identify the
actual values and fail without claiming lifecycle success.
