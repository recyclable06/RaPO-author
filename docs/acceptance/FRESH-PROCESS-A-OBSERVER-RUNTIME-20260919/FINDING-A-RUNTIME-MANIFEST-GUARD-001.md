# FINDING-A-RUNTIME-MANIFEST-GUARD-001

Status: OPEN — production launch guard missing

## Evidence

The candidate-only zero-GPU launcher verifies the candidate file manifest, frozen v9 hash identity, and production source identity before starting its probe. The production `run_v9.py` candidate does not reference `RUNTIME_CANDIDATE_MANIFEST.json` or `RAPO_DIAG_RUNTIME_MANIFEST`; it sets `RAPO_DIAG_RUNTIME_ROOT` and `PYTHONPATH`, then launches `runtime_entry_v6.py`.

`child_bootstrap_v6.py` records a manifest only when the environment variable is already present. Recording a supplied path/hash is not a fail-closed verification of the candidate files.

## Impact

The real-Ray zero-GPU result proves candidate dispatch wiring, but it does not prove that the production A launcher cannot silently run with an inherited or old observer when the caller omits or misbinds the candidate manifest.

## Minimum closure

Before the production subprocess is spawned, verify the candidate manifest entries, frozen v9 hash/package identity, and production source identity; set `RAPO_DIAG_RUNTIME_ROOT`, `RAPO_DIAG_RUNTIME_MANIFEST`, `RAPO_DIAG_V9_ROOT`, and the candidate-first `PYTHONPATH` in that same subprocess environment. Fail closed on any mismatch.

