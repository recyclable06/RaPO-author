# FINDING-A-RAY-LIFECYCLE-004

Status: `OPEN`  
Severity: `P1 — blocks safe A dispatch`

## Evidence

- `guard_support.py:326` checks only that `ray_address` is non-empty.
- `A_ONLY_LAUNCH_COMMAND.md:25` obtains the address from
  `FRESH_RAY_ADDRESS` described as a “fresh existing-Ray check”.
- The candidate launcher has no Ray start/stop or named supervisor ownership
  step.  `run_v9.py` only passes the address to GPU preflight and the child.
- The supplied path precheck proves that the candidate/output/Ray-temp paths
  were absent before the Python-only check; it does not prove that the Ray
  service itself is dedicated or that it will be torn down.

## Impact

The current contract permits connecting the A run to a shared or otherwise
unowned Ray service.  That can mix resources and lifecycle state with unrelated
work, and the launcher has no defined cleanup owner after normal completion or
timeout.

## Required closure

Name the dedicated lifecycle owner, establish a fresh Ray session/address with
verifiable ownership, bind that identity into the A evidence, and guarantee
teardown on normal and timeout paths.  The `existing-Ray` placeholder must not
be used for A dispatch.
