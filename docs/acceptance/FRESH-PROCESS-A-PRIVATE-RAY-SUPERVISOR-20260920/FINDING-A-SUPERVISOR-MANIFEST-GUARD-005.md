# FINDING-A-SUPERVISOR-MANIFEST-GUARD-005

Status: `OPEN`  
Severity: `P1 — blocks trusted supervisor launch`

`SUPERVISOR_MANIFEST.json` and `HASHES_SUPERVISOR.json` describe the frozen
supervisor files, but neither `private_ray_supervisor.py` nor
`SUPERVISOR_COMMAND.md` validates them before starting the Ray head. The
supervisor can therefore be changed after review without a fail-closed launch.

Required closure: validate the supervisor runtime file set/hash before any Ray
start and record the verified identity in the session record/result.
