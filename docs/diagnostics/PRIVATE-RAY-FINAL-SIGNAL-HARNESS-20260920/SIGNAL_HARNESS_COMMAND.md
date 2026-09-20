# 012 Linux real-signal harness command

This is the external evidence command for `FINDING-A-FINAL-PHASE1-SIGNAL-COVERAGE-012`.
It starts the exact four-file FINAL runtime as a child process twice, waits until
the fake CLI, fake launcher, `RUNNING` record, and `/proc` identities are ready,
then sends one real OS signal to the supervisor PID in each isolated case:
`os.kill(supervisor_pid, SIGINT)` and `os.kill(supervisor_pid, SIGTERM)`.

The harness does not import the FINAL supervisor or call its handler. It uses
only fake CLI/launcher processes, so this command does not start Ray, allocate a
GPU, load a model, or train. The result directory is outside `Final`; the
frozen `Final/test-results.json` is read and hashed but never written.

Deploy the harness directory and the three frozen sibling directories on the
same Linux host. The sibling basenames are part of the deployment contract:

```text
FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-ZEROGPU-CLI-FINAL-SUPPLEMENT
FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-SUPERVISOR-SUPPLEMENT
FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-ZEROGPU-SUPPLEMENT
```

The FINAL runtime identity is `HASHES_FINAL.json` SHA-256
`3b9f055da492741754f80b63e2255716e118fe546bca429267c542877136f67` and
`MANIFEST_FINAL.json` SHA-256
`fc97026c8e51f137d3106d0f918ff3577d8a2886b230f443023e2579d08de0b0`.
The harness also passes and checks the frozen parent identities
`f4914b91d91b1b31873457e195805762c930b89c656fe09115d25b9502ee98d9` /
`cac9d08d0c3b68d47218183ca21d61cb944d647d15d15746ec01ed350a84c119` and
the frozen ZeroGPU identities
`3635a3afd975d35770a1e9c41841da62fe3051be37ff95d39ffeeb5d19e3a003` /
`eae681218644bd759152658d425777b7cc3c6e80869a681e1415b01da104c4ed`.

Run exactly once with fresh output and fresh short `/tmp` temp roots:

```bash
set -euo pipefail

Harness=/mnt/conda/zhenglifeng/t/PRIVATE-RAY-FINAL-SIGNAL-HARNESS-20260920
Final=/mnt/conda/zhenglifeng/t/FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-ZEROGPU-CLI-FINAL-SUPPLEMENT
Parent=/mnt/conda/zhenglifeng/t/FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-SUPERVISOR-SUPPLEMENT
ZeroGpu=/mnt/conda/zhenglifeng/t/FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-ZEROGPU-SUPPLEMENT
Python=/mnt/conda/zhenglifeng/rapo-author-diagnostic-20260908/env/rapo-author/bin/python
Output=/mnt/conda/zhenglifeng/t/rapo-author-a-private-ray-final-signal-output-20260920
SigintSupervisorRoot="$Output/sigint-supervisor-root"
SigtermSupervisorRoot="$Output/sigterm-supervisor-root"
SigintRayTmp=/tmp/zlf-s20i
SigtermRayTmp=/tmp/zlf-s20t

test "$(basename "$Final")" = 'FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-ZEROGPU-CLI-FINAL-SUPPLEMENT'
test "$(basename "$Parent")" = 'FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-SUPERVISOR-SUPPLEMENT'
test "$(basename "$ZeroGpu")" = 'FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-ZEROGPU-SUPPLEMENT'
test "$(dirname "$Final")" = "$(dirname "$Parent")"
test "$(dirname "$Final")" = "$(dirname "$ZeroGpu")"
test ! -e "$Output"
test ! -e "$SigintRayTmp"
test ! -e "$SigtermRayTmp"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
exec "$Python" -B "$Harness/run_signal_harness.py" \
  --final "$Final" \
  --parent "$Parent" \
  --zero-gpu "$ZeroGpu" \
  --output "$Output" \
  --sigint-supervisor-root "$SigintSupervisorRoot" \
  --sigint-ray-tmp "$SigintRayTmp" \
  --sigterm-supervisor-root "$SigtermSupervisorRoot" \
  --sigterm-ray-tmp "$SigtermRayTmp" \
  --python-executable "$Python"
```

The two signal cases have separate supervisor roots and separate direct `/tmp`
Ray roots. The harness passes `--lifecycle-timeout-seconds 120` and
`--cleanup-budget-seconds 120` to the FINAL supervisor for both cases. It
records each supervisor PID, UID, Linux procfs starttime, session, process
group, fake head/launcher identities, and the two new-session descendants.

Each case is successful only when the final record is `STOPPED`, the final
result retains the expected signal number and controlled interruption, all
owned and launcher processes are gone, the private Ray temp root is removed,
cleanup remains scoped and within 120 seconds, and every FINAL runtime file
has the exact same bytes/SHA-256 before and after. The intentional supervisor
result status for a signal case is `FAIL_ZERO_GPU_SUPERVISOR_LIFECYCLE`; the
outer harness status is `PASS_REAL_LINUX_SIGNAL_HARNESS` only after both
cases satisfy the cleanup evidence.

Write all returned JSON and logs under `$Output`. Do not run the old
`run_supervisor_tests.py` main, and do not write `$Final/test-results.json`.
