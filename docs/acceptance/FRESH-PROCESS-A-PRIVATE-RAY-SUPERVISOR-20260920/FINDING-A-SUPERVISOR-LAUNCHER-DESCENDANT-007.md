# FINDING-A-SUPERVISOR-LAUNCHER-DESCENDANT-007

Status: `OPEN`  
Severity: `P1 — blocks timeout containment`

The supervisor starts the launcher in a new session and kills only that
launcher group. The frozen R2 launcher starts its production child in another
new session. Supervisor process discovery is limited to the Ray temp-root/head
tree, so a supervisor-level production timeout can kill the R2 launcher before
it cleans its own child, leaving the production session alive.

Required closure: make the supervisor own and verify the full launcher/
production process tree, or use one verifiable supervisor-owned session, and
clean all owned sessions within the shared 120-second budget.
