# A observer runtime candidate — independent incremental review

Date: 2026-09-19

## Verdict

`NOT_READY_FOR_BOUNDED_A_ONLY`.

The real-Ray zero-GPU dispatch result is independently corroborated, and the old reference probe's real-Ray gap is closed for this narrow wiring check. The candidate is not yet ready to launch the bounded A-only production run because `run_v9.py` does not fail-closed on, or bind, `RUNTIME_CANDIDATE_MANIFEST.json` before it starts the production subprocess. The zero-GPU probe launcher performs that check, but it is a different entrypoint and does not prove the production path.

The A scientific gate remains open. No actual A run or post-publication `driver_rng_expected` was produced here.

## Independent package and source checks

- `HASHES_RUNTIME.json`: 40 declared files, 646,309 bytes; all entries match independently. Its SHA256 is `72f53b1238624c9c9b160b856168505cca2ef5b6048fffa567546c1614a6d5b1`.
- The candidate directory also contains 109 non-canonical files: 13 `__pycache__` files and 96 `ray-temp` files. They are generated residue/ancillary Ray logs, are not required by the candidate import closure, and are not silently counted as canonical runtime bytes.
- `RUNTIME_CANDIDATE_MANIFEST.json` independently verifies with SHA256 `e3417329860bbfb4dd43298b4d760e24caff60e39a3f93539d02b5071de7e338`. Its 13 Python files have no missing local imports.
- The frozen v9 `HASHES_v9.json` matches the declared SHA256 `45f79cbf83d004b6fd05c4e1ef61fe2f5b296dba1771aae24e45e570b890ee39`; the declared frozen package manifest identity is preserved.
- Local diff against the frozen v9 package shows seven inherited modules differ only by trailing blank lines: `argv_validate_v9.py`, `boundary_evidence_v6.py`, `event_writer_v6.py`, `gpu_preflight_v9.py`, `identity_v6.py`, `sitecustomize.py`, and `state_fingerprint_v6.py`.
- The semantic changes are limited to the intended wiring: `child_bootstrap_v6.py` records runtime manifest identity; `child_observer_v6.py` adds Ray raw-class prepatch and returned-ActorClass safety-net wrapping; `runtime_entry_v6.py` makes the candidate runtime first; and `run_v9.py` places candidate/source/inherited-v9 paths in that order and records the candidate runtime root. The two zero-GPU probe scripts are new additions.

No hidden scientific change was found in the inherited modules beyond those listed categories. The candidate does not contain `PPO_CONFIG_TEMPLATE_v9.json` or `EXPECTED_IDENTITY_v9.json`; the production command must resolve both explicitly from the frozen v9 root.

## Independent real-Ray evidence review

The supplied raw event set was reparsed, not accepted from summary booleans:

- 118 valid events in 14 event files and 19 bootstrap records.
- Ray `2.46.0`, `num_gpus=0`, `num_cpus=3`; no model load or training path was invoked.
- Every bootstrap record carries the candidate observer SHA `e9c2f17115c44348d1e9e056ee8b3b0b691d2f4ce40e3af0f5ca483f4cd53bd1` and candidate manifest SHA `e3417329860bbfb4dd43298b4d760e24caff60e39a3f93539d02b5071de7e338`.
- The real production `PersistentRunner` actor is identified from its own target events: PID `3915086`, process start `3915086:67472233`, role `ray_runner`, with exactly one `run_task` `BEFORE` and one `AFTER`. They share call ID `3915086:1789807978239168413:f2f92994383f410f9859c9a959d13973` and the same PID/start identity.
- The `AFTER` error is exactly the expected inert `AttributeError: 'NoneType' object has no attribute '_task_id'`.
- The production actor's same PID/start event file also has two candidate-identity bootstrap records. Their role field remains `production_driver` because the probe inherited that environment value; actor identity is established by same PID/start plus `ray_runner` target events, not by the separate probe-actor report.
- The non-production `ProbeActor` is PID `3913646`, with the single `ray_worker:ray_actor_method` bootstrap. It is distinct from PID `3915086` and is not used as a substitute for production actor evidence.
- The prohibited labels (`PersistentRunner.init`, model/dataloader/checkpoint/fit paths, and related calls) occur zero times. The expected actor constructor `PersistentRunner.__init__` does occur as one `BEFORE`/`AFTER` pair; this is actor construction, not the prohibited production initialization method.
- Non-target checks independently match `direct_class_options=5`, `inherited_method=15`, `decorated_class=8`, `direct_function=10`, and original exception types `AssertionError`/`AttributeError`. The driver has one remote-wrapper install event, with no additional event from repeated installation. The raw result and candidate `finally` path record runner kill and `ray.shutdown`.

The old acceptance record was `NOT_RUN_BLOCKED_NO_LOCAL_RAY` with `delta_dispatch_ready=false`; the new raw run is a real-Ray `PASS_REAL_RAY_ZERO_GPU_DISPATCH`. This closes the old local-Ray/worker-bootstrap gap only for the zero-GPU wiring scope.

## Open findings

### `FINDING-A-RUNTIME-MANIFEST-GUARD-001`

The candidate's zero-GPU launcher and probe call a manifest verifier and set `RAPO_DIAG_RUNTIME_MANIFEST`. The production `run_v9.py` path does neither: `_set_environment` sets `RAPO_DIAG_RUNTIME_ROOT` and `PYTHONPATH`, then `subprocess.Popen` launches `runtime_entry_v6.py`; no candidate manifest verification or manifest environment binding occurs before that launch. `child_bootstrap_v6.py` only records the manifest if an environment variable was supplied; it does not verify its contents.

Minimum closure: make the production launcher fail closed after verifying the candidate manifest, frozen v9 identity, and production source identity, and set `RAPO_DIAG_RUNTIME_MANIFEST` in the same environment that starts `runtime_entry_v6.py`.

### `FINDING-A-TWO-GPU-IDENTITY-002`

The candidate manifest's runtime fields explicitly describe the zero-GPU probe (`num_gpus=0`, `CUDA_VISIBLE_DEVICES=""`, `num_cpus=3`, model/training false). That identity cannot be promoted to a two-GPU A identity. A future A-only run must use two explicit GPU devices, pass the existing v9 GPU preflight, record the actual driver/worker identities, and keep the candidate code/manifest identity separate from the zero-GPU probe metadata.

The actual post-publication A after-event and `driver_rng_expected` are still missing and must be generated by the new A two-step run. This is an A-gate requirement, not evidence that the zero-GPU dispatch was a model/training run.

## A-only command contract

The following is the bounded contract to use after `FINDING-A-RUNTIME-MANIFEST-GUARD-001` is closed. It is a contract, not an executed command in this review. Values in angle brackets must come from the frozen manifests or GPU preflight; they must not be guessed.

```bash
set -euo pipefail
Candidate=/mnt/conda/zhenglifeng/t/rapo-author-a-observer-runtime-candidate-20260919-r1
V9=/mnt/conda/zhenglifeng/t/r9r211d16b/v9
Source=/mnt/conda/zhenglifeng/t/r9r211d16b/source
Out=/mnt/conda/zhenglifeng/t/fresh-process-a-only-20260919
export RAPO_DIAG_RUNTIME_ROOT="$Candidate"
export RAPO_DIAG_RUNTIME_MANIFEST="$Candidate/RUNTIME_CANDIDATE_MANIFEST.json"
export RAPO_DIAG_V9_ROOT="$V9"
export PYTHONPATH="$Candidate:$V9:$Source"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_VISIBLE_DEVICES="<numeric-device-0>,<numeric-device-1>"

python3.11 -B "$Candidate/run_v9.py" \
  --leg A \
  --source-root "$Source" \
  --entry "$Source/examples/baselines/img_cls_cil/image_cls_cil_rapo.py" \
  --config-template "$V9/PPO_CONFIG_TEMPLATE_v9.json" \
  --expected "$V9/EXPECTED_IDENTITY_v9.json" \
  --model-root "<frozen-model-root-from-EXPECTED_IDENTITY_v9>" \
  --input-root "<frozen-input-root-from-EXPECTED_IDENTITY_v9>" \
  --cil-cfg "$Source/scripts/image/rapo_cfg.json" \
  --output-root "$Out" \
  --gpu-uuids "<physical-uuid-0>,<physical-uuid-1>" \
  --cuda-visible-devices "$CUDA_VISIBLE_DEVICES" \
  --ray-address "<existing-ray-address>"
```

The production launcher must verify the candidate manifest before this subprocess, must use the frozen v9 config/expected files explicitly, and must produce only the A leg (`--publish_task_boundary --stop_after_task_boundary` is derived from `--leg A`). Acceptance then requires the actual after-event's complete `driver_rng_expected`; neither this zero-GPU run nor a boundary marker may substitute for it.

