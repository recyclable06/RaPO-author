# CAND-RESUME-CIL-001 R3.1 独立 CPU/static 验收

日期：2026-09-11。角色：independent acceptance。目标只读工作树：`C:/Users/Administrator/.codex/worktrees/8ac5/RaPO-author`，分支 `codex/remediate-cil-resume-001`。

## Verdict

`PASS_READY_FOR_GPU`

该 verdict 只表示当前 R3.1 源码通过独立静态/CPU gate，可以交给专用 GPU 验收；不表示 fresh-process resume、两卡 native restore、轨迹一致性或论文规模指标已经通过。`fresh_process_resume` 仍为 `not_accepted`，本轮没有运行 GPU、SSH、训练、推理、安装、commit 或 push。

## Frozen identity

- `examples/baselines/img_cls_cil/image_cls_cil_rapo.py`: 102269 bytes，SHA256 `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3`。
- `tests/author_fixes/test_cil_resume.py`: 24215 bytes，SHA256 `2bb64dccbce91409840d04344a30a58b76265ae77145ab33b4819a3613b4aadf`。
- R3 evidence manifest `docs/remediation/CAND-RESUME-CIL-001/r3/HASHES.json`: independently computed SHA256 `ce058c0a2e9485ba027c2a6c7356f02ef99a3b0d1a283674d8a2e418f4a75271`; all 15 listed artifacts match its declared bytes/hash.
- `hash-start.json` and `hash-end.json` agree for source, test and manifest; `hash-comparison.json` records all three as unchanged.

The coordination freeze note prints a 65-character value for the manifest hash (`...418ef4a75271`), which cannot be a SHA-256. The direct 64-character computation above is the value used by this acceptance evidence; the note should be corrected as documentation hygiene. This did not produce source/test drift, and the manifest contents plus all listed artifact hashes were verified.

## Independent checks

`raw/02_independent_probe.stdout.txt` is an independent standard-library probe; it reads and AST-compiles selected production helpers without importing the runtime. It passed:

- the exact three production pruning branches at lines 1962, 1979 and 2021: protected Task-1 boundary content is preserved, control returns normally, and an unprotected ordinary old checkpoint is deleted;
- local model and tokenizer/processor content binding, same-size model mutation identity change, and remote model identifier rejection;
- world-size-2 full checkpoint acceptance, missing `dataloader.pt` rejection and missing per-rank optimizer rejection;
- dynamic source identity coverage, including `verl/models/monkey_patch.py`, `examples/reward_function/cls.py` and `scripts/image/rapo_cfg.json` (91 manifest files);
- CLI reachability and ordering: native restore → vLLM RNG restore → actor-to-anchor copy → `fit`, validation/checkpoint refresh before boundary publication, and driver RNG restoration before the fresh Task-2 loader.

The relevant production control points are the model identity helper at lines 440–481, tokenizer/processor initialization at lines 1270–1287, native restore and anchor ordering at lines 1379–1483, boundary publication at lines 1500–1577, pruning at lines 1961–2033, and CLI flags at lines 2077–2097.

## CPU regression

The exact independent command was run once with `-B`, `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, and an acceptance-owned `--basetemp`:

```text
D:/anaconda3/envs/rapo-b01/python.exe -B -m pytest tests/author_fixes/test_cil_resume.py tests/author_fixes/test_ctan.py tests/author_fixes/test_coco.py -p no:cacheprovider -v --tb=short --basetemp C:/Users/Administrator/Desktop/RaPO-author/docs/acceptance/CIL-RESUME-CPU-R31-20260911/pytest-basetemp
```

Result: **42 passed in 23.58s**, exit code `0`, stdout 5006 bytes, stderr 0 bytes. Raw stdout, stderr and exit are under `raw/03_combined.*`; command and environment are in `RUN_METADATA.json`.

## Remaining GPU handoff

The next independent GPU task must still verify two OS-process Task-1 publication and fresh Task-2 resume, world-size-2 native actor/optimizer/scheduler and worker-RNG restoration, driver/vLLM RNG, anchor fingerprint, Task-2 first update, state-exact and trajectory-close comparison, and paper-scale/original-experiment identity. This report does not close `CAND-RESUME-CIL-001` or authorize GPU execution itself.
