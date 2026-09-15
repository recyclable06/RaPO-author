# RaPO Author-Code Reproduction Rules

This repository is the active workspace for reproducing RaPO from the author-provided code.

## Sources and identity

- The paper at `references/2605.09640v1.pdf` defines the published algorithm and experiment specification.
- Tag `author-drop-20260904` is the immutable 204-file author-code baseline. Its identity is recorded in `docs/BASELINE.json`.
- Paper and author code are both first-hand sources. Preserve and report conflicts; author provenance does not imply verification.
- `docs/AUTHOR_CODE_STATUS.md` is the current status entry. Detailed evidence is under `docs/audit/2026-09-04-author-intake/`.
- `C:/Users/Administrator/Desktop/RaPO` is the legacy Visual-RFT/DeepSpeed project and evidence archive. It is reference-only for this repository.

## Current gate

- `AUTH-CTAN-001` and `AUTH-COCO-001` are corroborated findings in the author baseline. Their approved local corrections have passed bounded independent code/CPU acceptance and are integrated in the root checkout; this does not close the scientific reproduction gate.
- The root production/test bytes now match the R3.1 snapshot recorded in `docs/INTEGRATION_HASHES.json`. Historical diagnostic runs still bind their original source paths and hashes; do not silently substitute a new checkout path in a frozen run identity.
- Limited effective-update and same-process Task 1→2 GPU evidence exists. Fresh-process GPU restore, COCO AP, full experiments and original experiment identity remain pending. Current status is in `docs/AUTHOR_CODE_STATUS.md`; operational coordination is in `docs/TASK_COORDINATION.md`.
- Do not inherit legacy checkpoints, Task 1-6 artifacts, patches, manifests, tests or CPU release decisions.

## Roles and changes

- Code audit, remediation and independent acceptance use separate conversations. GPU diagnostics use another dedicated conversation.
- User-requested documentation, rule and Skill maintenance is a governance role: it may edit the requested instructions and supporting documentation without switching to code remediation or closing a finding.
- Audit work does not edit production code. Remediation changes only an approved finding and allowlist. Acceptance does not repair code.
- Preserve the baseline tag. Make every code change on a separate branch and review it against `author-drop-20260904`.
- Do not use skip, mocks of the subject, deleted tests or weakened assertions to pass a gate.
- Dependency installation, SSH/GPU use, training, inference, deletion, moves, commits and pushes require authorization covering that action. Relevant authorization earlier in the same conversation remains valid for the same scope and consequences; do not request it again merely because the task advanced.
- In an authorized editing task, routine edits and removal of this task's disposable temporary files are allowed. This does not authorize removing pre-existing files, scientific evidence, checkpoints or unintegrated work.
- Never import legacy code merely because it already has tests.

## Model allocation and usage

- User preference (2026-09-06): planning, decisions and creation/coordination of worktree tasks use GPT-6 Astra with High reasoning (`gpt-6-astra`, `high`).
- Implementation, test execution and independent acceptance tasks use GPT-5.6 Luna with Max reasoning (`gpt-5.6-luna`, `max`); role separation still applies.
- Set model and reasoning explicitly only when creating a new task, according to the role choices above. User correction (2026-09-11): never change any existing task's model or reasoning setting during continuation, dispatch or callback. Omit `model` and `thinking` from every `send_message_to_thread` call, including child-to-coordinator reports; never copy the child's Luna settings onto the receiving task. Preserve each existing task's current settings unless the user explicitly requests a change.
- Pass the frozen scope and evidence links instead of repeating the full conversation. Reuse completed independent evidence after verifying snapshot identity; repeat relevant checks when code, inputs or unresolved concerns change. Prefer compact progress snapshots over repeated full task reads.

## Project-local coordination authorization

- User authorization (2026-09-09): the coordinator may create as many tasks as needed inside the current `RaPO-author` project, or continue existing tasks whose project and context are suitable. Do not dispatch work to legacy `RaPO` project tasks or fork their conversation history into this project.
- New tasks receive a concise role, frozen source/evidence identities, allowed outputs, completion criteria and a callback to the coordinator. Preserve separate audit, remediation, acceptance and GPU-diagnostic roles. A new worktree is an output workspace, not automatically the integrated implementation under review.
- Each task must send its completion, concrete blocker or required user decision back to the coordinator using `send_message_to_thread`, including the verdict, artifact paths, hashes and remaining scope. The current coordinator is `01a08faa-ba41-73b2-b3d3-e468521682e0`; the prior coordinator `01a070af-8ee0-7641-b712-0cf59648e6ca` is superseded and must not be resumed by automatic callbacks. Callback arguments contain only `threadId`, `prompt`, and optionally `hostId`; omit `model` and `thinking`. The coordinator verifies the result and dispatches the next authorized step without waiting for the user to repeat “continue”.
- Use event-driven callbacks for automatic continuation. The user disabled timed heartbeat checks on 2026-09-09; do not recreate or resume them without a new request. Do not duplicate active work or repeatedly rerun unchanged checks. Keep routine monitoring quiet; notify only on meaningful progress, failure or a required decision. User pauses and stops take precedence over automated continuation.
- This delegation authorization does not waive action-specific boundaries for destructive cleanup, external communications, spending, commits/pushes or scientific decisions. Ordinary reversible implementation choices within a verified finding and a frozen allowlist can be resolved by the coordinator; stop only the branch requiring missing authorization or a material user decision.

## New-session recovery

1. Run `git status --short --branch` and `git log -5 --oneline --decorate`.
2. Read this file, `docs/AUTHOR_CODE_STATUS.md`, `docs/PROJECT_MAP.md`, and the current audit REPORT/PROGRESS/BLOCKED.
3. Re-run checks appropriate to the current risk. Treat old runtime logs as recorded evidence unless approved evidence-reuse conditions are met.
4. Declare the role matching the request. If a remaining action requires a formal role switch, hand it to a suitable separate task under the project-local coordination authorization above; stop only actions still lacking authorization. Do not treat the role boundary as a reason to pause unrelated authorized work.
