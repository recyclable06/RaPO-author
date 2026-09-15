# AUTH-CTAN-001 独立验收报告

日期：2026-09-06  
角色：独立验收；本报告不承担整改、不承担 COCO 验收。

## 结论

**通过：冻结实现满足本轮批准的 CTAN 本地代码行为规格。**

这里的“通过”只覆盖当前冻结工作树中的 CPU 可执行算法、JSON 状态、CLI/env/config 默认值、共享 hook 和静态接线；不表示 Ray/DataLoader/RPC/GPU、anchor 分片、COCO AP、完整 checkpoint 精确恢复、原论文数字或作者原实验身份已经通过。

没有发现足以阻断本批标准路径的新增问题。没有修改目标工作树、公开测试、原审计、根状态或清单；没有执行 `verify_scope.py`、`run_evidence.py`、launcher、训练、推理、Ray/GPU 或 COCO。

## 被验收快照与保全

| 项目 | 现场身份 |
|---|---|
| 验收对象 | `C:\Users\Administrator\.codex\worktrees\b7ae\RaPO-author` |
| 分支 | `codex/auth-ctan-001` |
| current/base HEAD | `da0c5ad521387bab75e74dc0bf0fd47dc13a3647` |
| 作者 baseline commit | `7fe2a73291f208ad9784a8333523825718881907` |
| 作者 tag | `author-drop-20260904`；annotated tag object `9022e7c1594e995c222205be049972e80e689fa6` |
| 冻结清单 | `docs/remediation/AUTH-CTAN-001/SHA256SUMS.json` |
| 清单声明/现场文件 | 265 / 265 |
| 清单自身 SHA-256（首轮/末轮） | `1c2365642756bb24c37e2e12fbd734e3d29d5d30863ce0dfe55a44cb7351c0ef` / 相同 |
| 首轮清单结果 | 0 missing、0 mismatch、0 extra、0 unlisted；PASS |
| 末轮清单结果 | 0 missing、0 mismatch、0 extra、0 unlisted；PASS |

首轮和末轮摘要分别保存在 `tmp/manifest-start.json` 与 `tmp/manifest-end.json`。目标树末态仍为预期的 6 个未提交生产修改、26 个允许前缀下的未跟踪文件；主工作树 `C:\Users\Administrator\Desktop\RaPO-author` 没有 tracked CTAN 差分，仅保留原未跟踪论文文件和本验收目录。

## 现场测试与执行环境

现场以子进程从目标树运行了用户指定命令，stdout/stderr/退出码未写入目标树：

```powershell
& 'D:/anaconda3/envs/rapo-b01/python.exe' -B -m pytest tests/author_fixes/test_ctan.py -p no:cacheprovider -v --tb=short
```

- cwd：`C:\Users\Administrator\.codex\worktrees\b7ae\RaPO-author`
- exit code：`0`
- 结果：`22 passed in 6.56s`
- stderr：空
- 环境覆盖：`PYTHONDONTWRITEBYTECODE=1`、`PYTHONIOENCODING=utf-8`
- Python 3.10.20、torch 2.5.1+cpu、numpy 1.26.4、pytest 8.4.2；Windows CPU 环境
- Ray、datasets、Transformers、vLLM 未安装；未安装任何依赖

原始输出和元数据：`public-test.stdout.txt`、`public-test.stderr.txt`、`tmp/public-test.json`。测试及 `source_loader.py` 已读核：测试的 `ROOT` 由当前目标树文件位置解析，选取目标树当前源码 AST 节点执行；没有导入旧工程、没有改写算法节点。真实 torch、JSON helper、原 GRPO、共享 hook 和两个真实 reinit 方法均在测试中执行；`SimpleNamespace` 只承载被测逻辑读取的字段。

## 规格逐项映射

| 批准规格 | 现场证据 | 结论 |
|---|---|---|
| Task 1 首个优势 batch 生效；按回答求和、按 UID 组均值、全批样本 std | `test_task1_first_and_multiple_batches_default_config`；独立探针用字符串 UID、非连续组和 6 行输入，独立标量样本 std `2.588435821108957` | 通过 |
| 首批用当前 std 初始化；之后 `0.999*old+0.001*current`；用更新后尺度；每批一次计数 | Task 1 多批、Task1→2→3 标量递推；独立探针零历史续算后 `ema_std=0.0026299555301666283`、`update_count=8` | 通过 |
| Task1→2→3 跨任务连续，不被末批统计覆盖；不同历史在相同非零末批后仍有差异 | `test_task123_matches_uninterrupted_and_scalar_formula`、`test_different_histories_same_nonzero_last_batch` | 通过 |
| 任务边界恢复有效 EMA 与累计 `update_count`；启用 CTAN 的后续任务缺历史明确失败 | 真实 JSON roundtrip 测试、6 个无效历史参数化测试、两个图像/检测真实 `reinit_for_task` 测试；独立缺失 JSON loader 返回 `None` 后 Task 2 构造明确抛 history 错误 | 通过 |
| 关闭 warmup、bias correction、bootstrap、额外 min-std 和整组 GRPO fallback；保留 epsilon | 三份真实 JSON 精确解析；`bootstrap_steps=0`、`beta_warmup_steps=0`、`bias_correction=false`、`min_std=0.0`、`guard_abs_max=0.0`、`eps=1e-6`；零/极小方差和旧 guard 阈值测试 | 通过 |
| padding 输出为零，返回 `advantages` 与 `returns` | 测试公共 `check_output`；独立字符串 UID/padding/全零响应行 probe | 通过 |
| Task 2 先 retention，再 CTAN；Task 1 不注入 retention；Task 2/3 共享 hook 可达 | `test_shared_hook_task123_retention_before_ctan`：任务1/2/3均执行，任务2/3 metrics 存在；独立静态顺序为 retention 行 585、CTAN 行 591 | 通过 |
| CTAN 关闭保持原 GRPO 数值 | `test_disabled_ctan_unchanged_original_grpo` 的 Task1/2/3 三个参数化实例 | 通过 |
| 三份配置、CLI 和 env 默认值统一；原字段/CLI 保留，标准裸 CLI 仍 opt-in 关闭 | `test_real_configs_cli_and_environment_defaults` 的 image/video/det 三个入口；独立 JSON 精确检查三份文件同 hash `9853b9…e11861`，配置值全部匹配 | 通过 |
| JSON 结构沿用，新实现保存/重载；不宣称旧状态迁移或完整准确 resume | `test_real_json_roundtrip_count_and_next_advantage`；静态检查 runner 的 load→pass→save | 通过（限于本批范围） |
| 优势进入 actor loss 的标准接线仍可达 | 独立静态 probe：hook retention→CTAN，fit 安装/恢复 hook，driver `compute_advantage`→`update_actor`，worker→actor，actor 读取 `advantages`→`compute_policy_loss` | 通过静态接线；不等于 Ray/GPU 端到端通过 |

独立 probe 的完整 JSON 在 `tmp/independent-probe.json`，探针代码在 `acceptance_probe.py`；没有把被测 normalizer 当作标量预期生成器。

## 语法、范围与差分核验

- 7 个受影响/本批新增 Python 文件 AST parse：exit 0。
- 6 个标准 shell 入口 `bash -n`：全部 exit 0；未执行 launcher。
- 目标树 `git diff --check`：exit 0。
- 相对治理 HEAD，tracked 差分恰为以下 6 个白名单生产文件：共享 `_rapo_components.py`、图像/检测入口各 1 个、image/video/det 三份 JSON。
- 未跟踪文件共 26 个，全部位于 `tests/author_fixes/` 或 `docs/remediation/AUTH-CTAN-001/`；无白名单外文件。
- 相对作者 tag 的 tracked 差分共 44 项：6 个是本批生产差分，其余是治理 HEAD 已有的 `.gitattributes`、`.gitignore`、`AGENTS.md`、README、论文/基线/原审计和治理文档差异；未把这些治理差异计为本批整改。
- `production.patch` 与从作者 tag 现场重生成的 6 文件 diff 在规范化换行后完全一致。
- `data/`、`verl/`、`examples/reward_function/`、原审计目录、`AGENTS.md`、`docs/AUTHOR_CODE_STATUS.md` 相对治理 HEAD 无差异；随包数据、verl、奖励函数和原审计字节保全通过。

范围/静态原始结果分别在 `tmp/scope-check.json`、`tmp/static-flow.json`、`tmp/config-check.json`；生产 diff 原始副本在 `tmp/production-diff-against-tag.patch`。

## 阻断、非阻断遗留与范围外

### 本批阻断

无。没有发现批准的 CTAN 标准路径可达且会实质改变本批算法/状态结果的新增失败。

### 非阻断遗留

- 现场是 CPU 局部代码验证；Ray runtime_env 环境传播、真实 DataLoader/RPC、分布式/FSDP、vLLM、anchor 分片复制、CUDA/NCCL、模型 forward/backward 未运行。
- 完整 checkpoint/optimizer/task cursor 精确中断恢复、COCO AP、论文数字、base model revision、逐 seed 原始实验身份仍未验证。
- 缺少 Ray/datasets/Transformers/vLLM 是环境边界，不是本批 CTAN 本地验收失败；未擅自安装。

### 范围外

- 本轮不验收、不修复 `AUTH-COCO-001`，不启动 COCO。
- 用户明确排除的显式 warmup/bias-correction/bootstrap/min-std/guard 算法变体、旧算法状态迁移和完整 resume 不被扩展为本批要求。
- 不把通过结论扩展为作者全包、GPU-ready 或论文结果复现通过。

## 证据入口

- 进度：`PROGRESS.md`
- 阻断/遗留：`BLOCKED.md`
- 命令：`COMMANDS.md`
- 环境：`ENVIRONMENT.json`
- 验收工件 hash：`HASHES.json`
- 冻结清单首/末轮：`tmp/manifest-start.json`、`tmp/manifest-end.json`
