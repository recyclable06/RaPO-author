# A launch guard — independent incremental review

Date: 2026-09-19

## Verdict

`NOT_READY_FOR_BOUNDED_A_ONLY`.

The frozen `14c8` candidate independently passes the identity-bound launch
guard checks, including the previously open production manifest binding.  The
candidate is still not ready for the bounded A dispatch because its launcher
does not implement the declared `1800s + at most 120s` process budget, and the
Ray address contract does not establish a dedicated Ray lifecycle owner.

No A production run, Ray session, GPU preflight, model load, or training was
started in this review.  The actual post-publication `driver_rng_expected`
gate therefore remains open.

## Independent checks

- `HASHES_LAUNCH_GUARD.json` independently verifies 14 declared files and
  74,540 bytes with no mismatches.  Its self SHA256 is
  `0bbc37a4a04ef7f2031d9ace2a70444d4271a983e41d9cba7a0cdadbb7fee98d`.
- The standard-library fixture probe passed.  The positive guard passed and
  missing manifest, corrupt manifest, production-source drift, and frozen-v9
  drift were all rejected before the `Popen` sentinel; negative `Popen` calls
  were `0`.  The fixture did not import Ray, torch, OmegaConf, or a model.
- The supplied 211 evidence is a bounded existing-Python guard check only:
  `PASS_LAUNCH_GUARD`, 205 frozen-v9 package files, and the declared production
  source SHA.  Its raw record says `ray_started=false`, `model_loaded=false`,
  and `training_started=false`; it is not evidence of a production `Popen` or
  A run.
- The A-only recipe and paths remain aligned with frozen v9: world size 2,
  rollout `n=4`, `total_epochs=2`, `max_steps=2`, two updates per task,
  `save_model_only=false`, Task-1 publish/stop boundary, the frozen model and
  input roots, and `scripts/image/rapo_cfg.json`.  The candidate and frozen-v9
  A argv builders match after normalizing only the launcher-file path.
- Parent observer manifest, frozen-v9 `HASHES_v9.json`, and the production
  entry SHA all match their declared identities.  This independently supports
  closure of `FINDING-A-RUNTIME-MANIFEST-GUARD-001` for this frozen candidate,
  but does not promote the candidate to a scientific A result.

## Open findings

### `FINDING-A-TIMEOUT-CONTRACT-003`

`guard_support.py:350-352` returns `timeout_seconds=1920` while separately
declaring `production_timeout_seconds=1800` and `cleanup_grace_seconds=120`.
`run_v9.py:354` passes the combined 1920 seconds to
`process.communicate(timeout=...)`.  On timeout it calls `process.kill()` at
line 357 and then calls `process.communicate()` without a timeout at line 358.
Thus the launcher neither enforces the 1800-second production deadline nor
provides a bounded 120-second cleanup deadline; the cleanup can block without
limit.  The contract's `no_auto_extension` text does not repair this runtime
behavior.

Minimum closure: use the declared 1800-second production deadline, then apply
an explicitly bounded cleanup grace of at most 120 seconds after termination;
record which deadline/cleanup path was used and fail closed if cleanup itself
exceeds the grace.

### `FINDING-A-RAY-LIFECYCLE-004`

`guard_support.py:326` only rejects an empty Ray address.  The launch command
still requires `FRESH_RAY_ADDRESS` described as coming from a “fresh
existing-Ray check” (`A_ONLY_LAUNCH_COMMAND.md:25`), and the candidate has no
launcher/supervisor step that starts, identifies as dedicated, owns, and tears
down the Ray session.  `run_v9.py` passes the address to GPU preflight and to
the production child, but does not establish its ownership or cleanup.

Minimum closure: freeze a dedicated-Ray lifecycle owner (the launcher or a
named dedicated supervisor), require a fresh address/session identity that
cannot be the shared Ray service, and record/perform teardown on both normal
completion and timeout.  Do not execute the A command with the current
`existing-Ray` placeholder.

## Evidence boundary and scope

This is a read-only independent acceptance review of the `14c8` candidate.
The production source, frozen v9 package, parent observer snapshot, prior raw
evidence, and GPU/model state were not modified or used.  The next action is a
small candidate correction review for findings 003/004; a full re-run is not
needed merely to recheck unchanged identity evidence.
