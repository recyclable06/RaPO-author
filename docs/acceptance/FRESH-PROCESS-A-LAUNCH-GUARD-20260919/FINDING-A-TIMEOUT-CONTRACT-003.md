# FINDING-A-TIMEOUT-CONTRACT-003

Status: `OPEN`  
Severity: `P1 — blocks bounded A dispatch`

## Evidence

- `guard_support.py:350-352` returns `timeout_seconds=1920` alongside
  `production_timeout_seconds=1800` and `cleanup_grace_seconds=120`.
- `run_v9.py:354` uses `communicate(timeout=int(guard["a_only"]["timeout_seconds"]))`,
  so the actual production deadline is 1920 seconds.
- The timeout handler kills the child at `run_v9.py:357` and calls
  `process.communicate()` with no timeout at `run_v9.py:358`.

## Impact

The launcher can run 120 seconds past the declared production deadline, and
its post-kill collection can block indefinitely.  This violates the frozen
`1800s + at most 120s` and `no_auto_extension` contract.

## Required closure

Separate the production deadline from cleanup grace, bound the post-kill
collection to no more than 120 seconds, and emit a deterministic failure if
that cleanup deadline is reached.
