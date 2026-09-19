# FINDING-A-TWO-GPU-IDENTITY-002

Status: OPEN — two-GPU A identity and actual RNG evidence pending

## Evidence

The candidate manifest records `num_gpus=0` and `CUDA_VISIBLE_DEVICES=""`; those values describe the accepted zero-GPU probe. The candidate package and its real-Ray evidence do not establish two-GPU execution, GPU UUID mapping, or the actual A post-publication driver RNG after-state.

## Minimum closure

Run the candidate-bound A-only two-step sequence with two explicit devices and the existing v9 GPU preflight. Record the actual source/runtime/worker identities and derive complete `driver_rng_expected` from the new production `PersistentRunner.run_task` after-event. Keep B/C out of this run; this does not revisit unresolved B evidence.

