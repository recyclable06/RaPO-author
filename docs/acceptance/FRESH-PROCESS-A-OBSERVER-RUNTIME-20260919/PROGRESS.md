# Progress

Date: 2026-09-19

- Completed an independent read-only incremental review of the candidate runtime package and raw zero-GPU Ray evidence.
- Independently verified the 40-file/646,309-byte delivery hash set, 13-file candidate runtime manifest, frozen v9 hash identity, import closure, source diff classes, and 118-event/14-file raw event set.
- Rebound the real `PersistentRunner` actor by its own PID/start and `ray_runner` target events; the separate `ProbeActor` was not used as production evidence.
- Confirmed real Ray `2.46.0`, zero GPU, three CPU, exact inert `_task_id` error, zero prohibited calls, non-target pass-through, and release/shutdown evidence.
- Found the production-launcher gap: candidate `run_v9.py` does not verify/bind `RUNTIME_CANDIDATE_MANIFEST.json` before its subprocess.
- Verdict: `NOT_READY_FOR_BOUNDED_A_ONLY`.
- Next minimum scope: close the production manifest guard, then run the new candidate-bound A-only two-GPU sequence and derive actual post-publication `driver_rng_expected`. B/C were not rerun.

