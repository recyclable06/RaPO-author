# FINDING-A-SUPERVISOR-INTERRUPT-CLEANUP-006

Status: `OPEN`  
Severity: `P1 — blocks owned cleanup on interruption`

`PrivateRaySupervisor.execute()` has `try/except Exception` but no `finally`
and no SIGTERM/SIGINT handlers. SIGTERM uses the default process termination;
SIGINT raises `KeyboardInterrupt`, which is not caught by `Exception`. Either
path can leave the private Ray session and temp root without a final record.

Required closure: install idempotent interruption handling and route every
interrupt through the same bounded, owner-checked cleanup routine.
