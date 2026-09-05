# RaPO Author-Code Reproduction Rules

This repository is the active workspace for reproducing RaPO from the author-provided code.

## Sources and identity

- The paper at `references/2605.09640v1.pdf` defines the published algorithm and experiment specification.
- Tag `author-drop-20260904` is the immutable 204-file author-code baseline. Its identity is recorded in `docs/BASELINE.json`.
- Paper and author code are both first-hand sources. Preserve and report conflicts; author provenance does not imply verification.
- `docs/AUTHOR_CODE_STATUS.md` is the current status entry. Detailed evidence is under `docs/audit/2026-09-04-author-intake/`.
- `C:/Users/Administrator/Desktop/RaPO` is the legacy Visual-RFT/DeepSpeed project and evidence archive. It is reference-only for this repository.

## Current gate

- `AUTH-CTAN-001` and `AUTH-COCO-001` are corroborated P1 findings. Do not claim paper-faithful reproduction while either remains unresolved.
- CTAN is connected to the training path. Its confirmed issue is cross-task EMA continuity, not an unused implementation.
- Ray environment propagation, distributed execution, exact resume, COCO AP and original experiment identity remain pending.
- Do not inherit legacy checkpoints, Task 1-6 artifacts, patches, manifests, tests or CPU release decisions.

## Roles and changes

- Audit, remediation and independent acceptance use separate conversations. GPU diagnostics use another dedicated conversation.
- Audit work does not edit production code. Remediation changes only an approved finding and allowlist. Acceptance does not repair code.
- Preserve the baseline tag. Make every code change on a separate branch and review it against `author-drop-20260904`.
- Do not use skip, mocks of the subject, deleted tests or weakened assertions to pass a gate.
- Do not install dependencies, use SSH/GPU, train, infer, delete, move, commit or push unless the current request authorizes that action.
- Never import legacy code merely because it already has tests.

## New-session recovery

1. Run `git status --short --branch` and `git log -5 --oneline --decorate`.
2. Read this file, `docs/AUTHOR_CODE_STATUS.md`, `docs/PROJECT_MAP.md`, and the current audit REPORT/PROGRESS/BLOCKED.
3. Re-run checks appropriate to the current risk. Treat old runtime logs as recorded evidence unless approved evidence-reuse conditions are met.
4. Declare one role for the conversation and stop if the requested work requires a formal role switch.
