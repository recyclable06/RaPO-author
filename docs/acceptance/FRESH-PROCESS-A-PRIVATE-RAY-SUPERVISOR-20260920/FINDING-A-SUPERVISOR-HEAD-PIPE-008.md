# FINDING-A-SUPERVISOR-HEAD-PIPE-008

Status: `OPEN`  
Severity: `P1 — blocks reliable head readiness/log capture`

The long-lived Ray head is started with stdout/stderr connected to PIPE, but
the supervisor does not drain either pipe while waiting for readiness. A full
pipe can block the head. Logs are read only with `communicate(timeout=0)` during
cleanup, which can return no complete output when descendants still inherit
the pipe.

Required closure: use supervisor-owned log files or continuous bounded readers,
then record whether both streams were completely drained.
