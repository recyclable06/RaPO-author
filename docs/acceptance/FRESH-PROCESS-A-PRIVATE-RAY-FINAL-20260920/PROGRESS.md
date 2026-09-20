# Progress

2026-09-20 — independent review of final combined runtime.

- Final executable bundle: 4 files / 86,564 bytes; all declared hashes and
  manifest entries match.
- Direct module import plus `run()` passed the portable standard-library suite;
  `main()` was not executed and the frozen `test-results.json` stayed unchanged.
- Static implementation review supports closure of 005–010, including pre-head
  snapshot validation, interrupt cleanup, launcher descendant tracking,
  file-backed logs and verified `bin/ray` entrypoint.
- Phase 1 as documented is unsafe: its `main()` overwrites a frozen runtime file.
  A direct-call, external-output contract is recorded in
  `PHASE1_DIRECT_CALL.md`.
- Phase 1's Linux function does not deliver real SIGINT/SIGTERM to the
  supervisor. Portable direct-handler calls are not signal evidence; a separate
  Linux signal harness remains required.
- No SSH, Ray, GPU, model, training or A-mode action was taken.
