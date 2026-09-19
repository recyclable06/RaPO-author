# FINDING-A-PRIVATE-RAY-LIFECYCLE-004

Status: `CONTRACT_BOUND_PENDING_REAL_SUPERVISOR_LIFECYCLE`  
Severity: `P1 — blocks safe A dispatch`

## What R2 proves

The pre-`Popen` guard requires a `private-ray-supervisor-record-v1` record,
matches its address to `--ray-address`, rejects `shared_ray=true`, rejects
shared/default/existing address tokens, and checks the declared private cleanup
scope plus required identity fields. The shared-record negative case remains
`REJECTED_BEFORE_POPEN` with zero sentinel calls.

## What R2 does not prove

The validator only reads and checks JSON fields. An independent record with a
nonexistent temp root, `head_pid=999999999`, a fictional process-start value,
and `owner=forged-owner` was accepted. It does not query Ray, verify PID/start
identity or ownership, check temp-root existence/owner/mode, or perform
post-run teardown.

`PRIVATE_RAY_SUPERVISOR_CONTRACT.md` is explicitly marked “not executed”; R2
contains no executable supervisor, atomic record writer, or cleanup owner.

## Required closure

Run a dedicated per-run supervisor implementation that starts and verifies a
new private Ray head, atomically writes the record, and cleans only the same
PID/session/temp-root on normal and timeout paths. Recheck that real record
independently before A dispatch.
