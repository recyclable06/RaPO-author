# AUTH-COCO-001 独立验收报告

日期：2026-09-06。角色：独立验收；只裁决已批准的 COCO 提示/奖励 GT 一致性整改，不修代码、不推进 GPU 或其他 finding。

## 裁决

**通过（限定为 COCO 提示/GT 冲突的 CPU 局部代码行为）。**

目标工作树中，标准 `--prompt_seen_labels` 路径已把训练 `allowed_classes` 接到当前 `seen_class_names`；未开启时仍使用当前任务 `ordered_task_class_names`。任务图片过滤仍先于标签过滤，真实未改 helper 对 `answer` 与 `answer_seg` 的类别、对象字段和顺序保持原有行为。没有发现本批批准范围内的反例。

这不是完整 COCO 协议、训练、GPU 或论文复现放行，也不关闭整个 COCO 门禁。

## 冻结身份与范围

- 被验收实现：`C:/Users/Administrator/.codex/worktrees/1449/RaPO-author`，branch `codex/auth-coco-001`，base HEAD `da0c5ad521387bab75e74dc0bf0fd47dc13a3647`。
- 作者基线：tag `author-drop-20260904`，commit `7fe2a73291f208ad9784a8333523825718881907`。
- CTAN 只读源：`C:/Users/Administrator/.codex/worktrees/b7ae/RaPO-author`，branch `codex/auth-ctan-001`，HEAD 与 base 相同。
- COCO `HASHES.json`：38 项全部匹配；清单自身 SHA256 为 `e6f54e82a577822f8d6ba8ac887b29c5017c6f8894488cf17851b62ff69d148f`，起始/结束重算一致。
- CTAN `SHA256SUMS.json`：265 项全部匹配；清单自身 SHA256 为 `1c2365642756bb24c37e2e12fbd734e3d29d5d30863ce0dfe55a44cb7351c0ef`。

相对 CTAN 源逐字节比较得到 263 项相同，且仅有预期的两项差异：最新版 `AGENTS.md` 治理输入，以及 `examples/baselines/cil_det/image_det_cil_rapo.py` 的一行 COCO 修改。目标相对 CTAN 的新增文件仅为 `docs/remediation/AUTH-COCO-001/` 交接/自测材料和 `tests/author_fixes/test_coco.py`。随包数据、`image_det_cil.py`、检测奖励函数和继承的 3 个 CTAN 测试与作者基线的保全检查均通过。

## 现场证据

### 1. 公开回归

从目标工作树直接执行，设置 `PYTHONDONTWRITEBYTECODE=1`，未调用包装 runner：

```text
D:/anaconda3/envs/rapo-b01/python.exe -B -m pytest tests/author_fixes/test_coco.py tests/author_fixes/test_ctan.py -p no:cacheprovider -v --tb=short
```

结果：exit code `0`，`25 passed`（COCO 3 项、继承 CTAN 22 项）。独立捕获的命令、环境、stdout、stderr 在本验收目录的 `public-regression.meta.json`、`public-regression.stdout.txt`、`public-regression.stderr.txt`。

### 2. 独立静态接线与动态局部检查

`independent_probe.py` 从真实源码 AST 读取 `_run_cil` 的唯一 `runner.run_task.remote` 调用和未改写的 `image_det_cil.py` helper，未 import Ray/datasets/Transformers/vLLM，也没有改写被测函数：

- 实际表达式为 `seen_class_names if known_args.prompt_seen_labels else ordered_task_class_names`；`task_id_filter` 为 `task_idx`，`class_to_task` 为真实 `class_to_task`。
- `_build_dataloader` 的真实 AST 中，`task_id_filter` 分支在 `allowed_classes` 分支之前；后者对 `answer`、存在的 `answer_seg` 各调用一次真实 `_filter_annotations_by_classes`。
- 以类别顺序和真实 helper 遍历 5-task seeds `136/377/639` 与 10-task seeds `277/305/738`，共核 45 个任务行。206 条随包训练记录保持一图一行、图像唯一、任务归属和顺序；任务图数分别为：
  - 5-task：`[16,19,11,64,96]`、`[16,17,27,58,88]`、`[22,19,22,56,87]`；
  - 10-task：`[13,14,10,16,13,16,20,20,41,43]`、`[11,10,21,10,14,15,10,23,39,53]`、`[10,12,13,13,11,14,23,23,45,42]`。
- 独立合成的单任务、跨任务共现 `answer`/`answer_seg` 输入确认：先按最晚类别任务选择图像；seen 路径保留原对象字典、坐标/实例字段及顺序，novel-only 路径只移除非 novel 类别。
- 随包 `train2017/000000018783.jpg` 的真实作者 SciPy/Hungarian reward：完整 8 框答案 `overall=3.0`，仅 car `overall=1.25`，差 `1.75`；即使加 `0.5` retention 上限也不能反转。

独立探针 JSON 为 `independent-probe-start.json` 和 `independent-probe-final.json`；起始/结束 hash 对照在 `hash-start-end-compare.json`。

### 3. 语法与结构保全

- 8 个相关 Python 文件 AST parse 全部 exit `0`。
- 六个 shell 入口用本机 Git Bash 执行 `bash -n` 全部 exit `0`。
- 目标工作树 `git diff --check` exit `0`。
- 结构证据在 `structural-checks.json`，目标状态快照在 `target-status.txt`。

## 红/绿测试历史核对

交接中保留的红/绿 stdout 不是同一份测试源码的完整快照，因此不能声称各阶段文件字节相同。证据能确认的演进如下：

1. `red-coco.stdout.txt` 的首轮失败为 AST 没有定位到 `.remote` 调用（`0 == 1`），不是被测生产路径通过；随后 `red-confirmed.stdout.txt` 使用修正后的定位后，在未改生产接线的基线下得到静态和动态两项失败、奖励对照通过。
2. `green-coco.stdout.txt` 和 `green-confirmed.stdout.txt` 的失败来自测试自身对 AST 属性/分支访问的假设，分别是属性节点识别和 task 分支查找；最终 `green-final.stdout.txt` 为 3 passed。
3. 我亲读最终 `test_coco.py`、继承的 `source_loader.py` 和 `test_ctan.py`，并用独立探针复做了关键生产接线、过滤顺序、字段保全和奖励检查。最终测试没有 skip、mock 被测算法、删除断言或弱化为只测静态字符串；但中间修订源文件未单独保全，所以对历史每一版的逐字节变化仅按上述 stdout 证据报告。

## 结论边界

本次通过只覆盖：

- 标准提示 seen 类别与训练奖励 GT 允许类别一致；
- 未开启 seen 提示时保留 novel-only 行为；
- 任务图片分配、过滤顺序、`answer`/`answer_seg` 局部行为和指定奖励反例已核对；
- 本批差分、CTAN 前置清单、作者 tag 和随包数据无意外漂移。

仍待另行协议确认或运行：五样本配额解释、有效监督量/监督出现时机、验证集及 per-task AP、crowd/空图口径、真实 DataLoader/Ray/RPC、分布式/GPU、完整 resume、模型训练/推理及论文数字。继承 CTAN 的 22 项仅作为本次回归，不在本报告重新关闭或重裁决 CTAN finding。
