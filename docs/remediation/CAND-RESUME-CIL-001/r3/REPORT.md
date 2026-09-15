# CAND-RESUME-CIL-001 R3 整改报告

日期：2026-09-09。角色：independent remediation。对象：`C:/Users/Administrator/.codex/worktrees/8ac5/RaPO-author`，分支 `codex/remediate-cil-resume-001`。

## Verdict

`ready_for_independent_acceptance`

这是 R3 CPU/static 整改交付状态，不是 GPU fresh-process 验收结论。R2 独立验收指出的三个阻塞项已在允许的 image production/test 文件内修复，并以真实生产控制流和负例验证；下一步由独立验收重新读取源码和本目录证据后决定 GPU 边界。

## 修复内容

1. CIL-CPU-002：三处常规 checkpoint pruning 对 protected boundary 父/子路径执行保留并继续，不再将正常保留抛成异常。Task 1 多 checkpoint 可到达 stop-after 的正常 `break`；不 stop 进入 Task 2 时，已发布 Task 1 根保持不变；普通未保护旧 checkpoint 仍按原策略删除。
2. CIL-CPU-004：boundary 发布/恢复的模型身份限定为已存在的本地 model 路径和实际 tokenizer/processor 路径，分别绑定完整递归 content manifest。远端 ID（含 40-hex revision）fail closed；PersistentRunner 的 tokenizer/processor 初始化实际使用 `tokenizer_path`，没有修改共享 native loader/revision 框架。
3. CIL-CPU-005：source identity 改为动态枚举完整 `verl`、examples 和 image runtime 配置树，包含 package initialization、models、动态 reward 和项目依赖锁，排除 cache/log/output；从运行配置解析实际动态 reward 文件并绑定其内容。

## CPU/static evidence

先执行了目标文件 AST parse，exit code `0`，stderr 为空；原始证据为 `raw/01_ast.*`。随后执行组合回归：

```text
D:/anaconda3/envs/rapo-b01/python.exe -B -m pytest tests/author_fixes/test_cil_resume.py tests/author_fixes/test_ctan.py tests/author_fixes/test_coco.py -p no:cacheprovider -v --tb=short
```

结果为 **42 passed**（17 CIL + 25 CTAN/COCO），exit code `0`，stderr `0` bytes，完整证据为 `raw/02_combined.stdout.txt`、`raw/02_combined.stderr.txt`、`raw/02_combined.exit.txt` 和 `raw/02_combined.meta.json`。既有 CTAN 测试报告 1 个 ResourceWarning；没有失败或 error。

## Patch and identity evidence

- R3 相对 R2 的实际 patch：`CAND-RESUME-CIL-001-r3-vs-r2.patch`，bytes 和 SHA-256 见 `HASHES.json`。
- R3 相对 5ced 的累计实际 patch：`CAND-RESUME-CIL-001-r3-vs-5ced.patch`，仅包含当前 allowlist 内 image source 和新增/更新的 CIL test，bytes 和 SHA-256 见 `HASHES.json`。
- R2 冻结输入：image `ba8a5da9341785178bd444112c4fc78dd352b52fe359b768218f4a4a6f5f7863`、test `331e62782cc63ef9a2fb4d2de1afe921593f629309f263c6728a7de5299e3f64`，逐字副本保存在 `inputs/`。
- R3 输出：image `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3`（102,269 bytes）、test `2bb64dccbce91409840d04344a30a58b76265ae77145ab33b4819a3613b4aadf`（24,215 bytes）。
- 逐文件 bytes/hash、自排除说明和验证命令见 `HASHES.json`。

## Scope remaining

未执行 GPU、SSH、训练、推理、依赖安装、commit 或 push。两个 OS process 的 native world-size-2 restore、driver/vLLM RNG、anchor fingerprint、Task 2 首个真实 update、state-exact/trajectory-close 和 paper-scale metrics 仍留给独立 GPU 验收；本报告不把 CPU fixture 当作这些结果，也不关闭原 finding。
