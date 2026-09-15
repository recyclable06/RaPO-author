# AUTH-COCO-001 独立验收交接

**COCO 提示/GT 冲突整改完成并自测，等待独立验收。** 本任务不承担独立验收，不更新根状态，不提交或推送。

## 身份与前置快照

- Worktree：`C:/Users/Administrator/.codex/worktrees/1449/RaPO-author`
- Branch：`codex/auth-coco-001`
- Base HEAD：`da0c5ad521387bab75e74dc0bf0fd47dc13a3647`
- 作者 commit：`7fe2a73291f208ad9784a8333523825718881907`
- CTAN 源：`C:/Users/Administrator/.codex/worktrees/b7ae/RaPO-author`，branch `codex/auth-ctan-001`，HEAD `da0c5ad521387bab75e74dc0bf0fd47dc13a3647`
- CTAN 冻结清单：265 项，`docs/remediation/AUTH-CTAN-001/SHA256SUMS.json` hash 为 `1c2365642756bb24c37e2e12fbd734e3d29d5d30863ce0dfe55a44cb7351c0ef`。本树除授权覆盖的最新版 `AGENTS.md` 和本批 COCO 单行生产差分外，源快照 263 项逐字节匹配。
- 前置生产/测试/数据 hash：见 [PRE_BATCH_HASHES.json](PRE_BATCH_HASHES.json)。最终全量 hash：见 [HASHES.json](HASHES.json)。

## 精确差分

- 继承 CTAN：6 个生产文件、3 个 CTAN 测试文件及 `docs/remediation/AUTH-CTAN-001/` 证据，均来自只读 b7ae 源，hash 见 `PRE_BATCH_HASHES.json`。
- 治理输入：`AGENTS.md` 来自 `C:/Users/Administrator/Desktop/RaPO-author/AGENTS.md`，source/target hash 均为 `ea219982348cf89432058fc6be6c3cd78d93b5a47c39c6eb24e6f84c6f0ce411`，不计算法差分。
- 本批生产：`examples/baselines/cil_det/image_det_cil_rapo.py` 的 `runner.run_task` 调用仅将 `allowed_classes` 改为 prompt seen 时使用 `seen_class_names`、否则使用 `ordered_task_class_names`。精确补丁见 [production.patch](production.patch)。
- 本批测试：新增 [test_coco.py](../../../tests/author_fixes/test_coco.py)，不改已有 3 个 CTAN 测试文件；完整新增差分见 [tests.patch](tests.patch)。
- 未改：奖励函数、评估器、`image_det_cil.py` builder/filter 实现、数据文件、类别/框/实例、样本清单和 CTAN 逻辑。

## 命令与结果

环境：`D:/anaconda3/envs/rapo-b01/python.exe -B`，Python 3.10.20、torch 2.5.1+cpu、numpy 1.26.4、pytest 8.4.2；已有 scipy。以下均为 CPU 局部验证。

| 阶段 | 命令 | 结果 | 原始证据 |
|---|---|---:|---|
| COCO 红 | `D:/anaconda3/envs/rapo-b01/python.exe -B -m pytest tests/author_fixes/test_coco.py -p no:cacheprovider -v --tb=short` | exit 1；2 failed/1 passed | `red-confirmed.stdout.txt`, `red-confirmed.stderr.txt` |
| COCO 绿 | 同上 | exit 0；3 passed | `green-final.stdout.txt`, `green-final.stderr.txt` |
| COCO + CTAN 回归 | `D:/anaconda3/envs/rapo-b01/python.exe -B -m pytest tests/author_fixes/test_coco.py tests/author_fixes/test_ctan.py -p no:cacheprovider -v --tb=short` | exit 0；25 passed | `regression.stdout.txt`, `regression.stderr.txt` |
| 语法/范围 | AST parse、6 个 `bash -n`、`git diff --check`、源快照/白名单核对 | exit 0 | `syntax-check.json`, `scope-check.json` |

红测的失败直接来自修复前真实 `allowed_classes` 表达式及 seen/novel GT 冲突；不是依赖缺失或路径错误。`000000018783.jpg` 的作者 reward 对照为完整答案 3.0、仅 car 1.25，差距 1.75；最大 0.5 retention 不足以颠倒该差距。

## 验收边界

测试执行了真实源码 AST 节点和真实数据/奖励函数的 CPU 局部行为；静态接线与动态过滤证据分开。没有执行完整模块 import、Ray、真实 DataLoader/RPC、分布式/GPU、模型 forward/backward、COCO AP 或论文实验。因此本交接不等于独立验收、GPU-ready 或论文结果复现通过。
