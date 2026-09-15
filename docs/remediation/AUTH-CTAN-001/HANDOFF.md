# AUTH-CTAN-001 独立验收交接

**整改完成并自测，等待独立验收。** 本任务只承担 AUTH-CTAN-001 整改，不承担审计或独立验收；不推进 COCO。所有修改未提交、未推送。

## 实际位置与身份

- Worktree：`C:/Users/Administrator/.codex/worktrees/b7ae/RaPO-author`
- Branch：`codex/auth-ctan-001`
- Base HEAD / 当前 HEAD：`da0c5ad521387bab75e74dc0bf0fd47dc13a3647`
- 作者 commit：`7fe2a73291f208ad9784a8333523825718881907`
- 保留 tag：`author-drop-20260904`；annotated tag 对象为 `9022e7c1594e995c222205be049972e80e689fa6`，其 peeled commit 为上述作者 commit。
- 原主工作树：`C:/Users/Administrator/Desktop/RaPO-author`，最终 `main` 无 tracked 差分，仅保留未跟踪 `2605.09640v1.pdf`；该 PDF SHA256 与 docs/BASELINE.json 的 `fc48b658fd3d96980f4733cbd9672aa21be2f3b04e73958de54bf4e0e15965e0` 一致。

## 实现与精确差分

规格及测试映射见 [SPEC.md](SPEC.md)。生产共 6 个白名单文件，63 行新增 / 58 行删除：

| 路径 | 修改 |
|---|---|
| examples/baselines/_rapo_components.py | 删除任务边界末批覆盖；首个活跃批初始化；必要历史有效性检查；CTAN 默认值统一；更新算法说明 |
| examples/baselines/img_cls_cil/image_cls_cil_rapo.py | 仅 5 个 CTAN CLI 默认值 |
| examples/baselines/cil_det/image_det_cil_rapo.py | 仅 5 个 CTAN CLI 默认值，无 COCO 筛选/奖励变更 |
| scripts/{image,video,det}/rapo_cfg.json | 各 5 个 CTAN 默认值 |

runner 原有 load→reinit→normalizer→save 状态传递足够，保留原函数。历史缺失检查集中在共享构造器，两条真实 reinit 均已定向调用验证。retention/hook 原有注入顺序不需要修改。无其他生产修改。

- [production.patch](production.patch)：针对作者 tag 的精确生产差分；治理 HEAD 的这些生产路径与作者 tag 相同。
- [tests.patch](tests.patch)：3 个新增测试/最小加载及运行辅助文件的完整新增差分。
- [SHA256SUMS.json](SHA256SUMS.json)：冻结当前全部 tracked 文件及本批新增文件，包含生产、测试、文档、补丁、原始输出；仅排除清单自身，避免自引用。交接的事实身份以字节 hash 为准，不依赖未提交 diff 的视觉摘要。
- [verification.json](verification.json)：作者原始 204 个文件 SHA256、白名单对照、7 个 Python 文件编译、6 个 shell 语法、静态连接位置、Git 原始输出及主工作树保全。

196/204 作者文件仍逐字节相同；`.gitignore` 和 `README.md` 的差别来自 base HEAD 的既有治理提交，本次未变；余下 6 个为本批生产修改。相对 base HEAD 的所有 tracked 差分恰为上述 6 个。data、verl、奖励函数、论文、原审计证据、AGENTS 和现役状态文档均保持 base HEAD 字节。

## 自测证据与复跑

环境：Windows，`D:/anaconda3/envs/rapo-b01/python.exe`，Python 3.10.20、torch 2.5.1+cpu、numpy 1.26.4、pytest 8.4.2。已有 scipy/jinja2；缺 Ray/datasets/Transformers/vLLM。环境具体值与命令完整参数见 red-confirmed.json、green.json。

| 阶段 | 结果 | 命令记录和原始输出 |
|---|---|---|
| 正式红测试（生产改动前） | exit 1；19 failed / 3 passed | red-confirmed.json、red-confirmed.stdout.txt、red-confirmed.stderr.txt |
| 正式绿测试 | exit 0；22 passed | green.json、green.stdout.txt、green.stderr.txt |
| 语法/范围/静态接线 | exit 0 | verification-run.json、verification.stdout.txt、verification.stderr.txt、verification.json |

正式红/绿测试文件 SHA256 完全相同，且红测试的生产源 hash 与作者基线一致。最初工具准备输出 red.txt 包含已修正的类名/dtype 问题，不作为红测试依据，详见 PROGRESS.md。预期公式独立用标量计算，rtol=1e-5、atol=1e-6，计数/配置精确比较，无 skip、被测算法 mock 或弱化断言。

在上述 worktree 中，独立任务可直接运行测试，避免覆盖冻结证据：

```powershell
& 'D:/anaconda3/envs/rapo-b01/python.exe' -B -m pytest tests/author_fixes/test_ctan.py -p no:cacheprovider -v --tb=short
```

本次记录运行使用 `tests/author_fixes/run_evidence.py red-confirmed` 和 `... green` 包装上述命令，包装器将命令、环境、被测源 hash、exit code 和 stdout/stderr 保存到本目录；同名证据存在时会拒绝覆盖。

`verify_scope.py` 是本批证据工具，其执行会重写本目录 verification.json 和两份 patch。独立验收如需复跑，应将新输出另存独立验收目录，或先保留本冻结清单；不要把重跑后的证据当成本次原件。

## 证据边界与验收下一步

CPU 实测执行当前工作树中原样选取的 normalizer、真实 JSON 函数、原 GRPO、真实 hook、reinit、CLI/env 函数。SimpleNamespace 仅提供张量容器/字段。共享 hook 的 Task 1/2/3 路径和 retention 算术已实测；静态 fit/runner/worker/loss 连接分开列在 verification.json。

没有执行完整模块 import、完整 CLI、DataLoader、Ray/RPC、GPU、anchor 权重复制、模型 forward/backward、训练/推理或完整 checkpoint 恢复。Ray 环境传播、COCO AP、原始实验身份仍待验证。本结论不是 GPU-ready 或论文复现完成。新实现状态保存重载通过，不表示旧算法状态可迁移；正式后续运行应从新 Task 1 开始。

独立验收任务先核对 worktree、branch、HEAD 和 SHA256 清单，再独立审阅生产差分/规格并执行自有验证；验收不修代码。当前根状态与两项 finding 裁决未修改。只有该独立任务验收通过后才可推进 COCO。其余遗留见 [BLOCKED.md](BLOCKED.md)。
