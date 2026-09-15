# AUTH-COCO-001 COCO 提示/GT 一致性整改规格

日期：2026-09-06。角色：整改与自测；不承担独立验收，不关闭 finding。

## 冻结范围

- 保留随包 `train_5shots.jsonl` 的 206 张图片、原始框、类别顺序、六个 seeds，以及按图片最晚类别所属任务分配图片的规则。
- 任务过滤仍先于标签过滤；使用作者现有 `_infer_example_task_id_from_answer` 和 `_filter_annotations_by_classes` 行为。
- `--prompt_seen_labels` 开启时，训练 `allowed_classes` 必须使用当前 `seen_class_names`，使提示类别集合与奖励 GT 允许类别集合一致。
- 未开启 `--prompt_seen_labels` 时，继续使用 `ordered_task_class_names`，保留 novel-only 行为。
- `answer` 与存在的 `answer_seg` 使用同一允许类别范围过滤；不改变类别、框、实例或分割字段。

## 已证实冲突与最小修复

修复前，`_run_cil` 的真实 `runner.run_task` 调用把当前任务 novel 类别传给 `allowed_classes`，同时 `prompt_seen_labels` 把全部 seen 类别传给提示。`_build_dataloader` 先按图片任务归属筛选，再按 `allowed_classes` 改写 `answer` 和 `answer_seg`，因此标准提示要求的早期类别会从奖励 GT 消失。

本批仅把该调用参数改为：

```python
allowed_classes=seen_class_names if known_args.prompt_seen_labels else ordered_task_class_names
```

没有改奖励函数、评估器、builder、样本清单、数据文件或既有 CTAN 逻辑。

## 自测映射

- 静态接线：从真实 `_run_cil` AST 读取 `runner.run_task.remote` 参数；确认 `seen_class_names`/novel-only 条件、`task_id_filter`、`class_to_task` 均保留。
- 动态局部：从作者 `image_det_cil.py` AST 读取未改写 helper，遍历 seeds 136/377/639（5-task）和 277/305/738（10-task）。任务计数分别为：
  - 5-task：`[16,19,11,64,96]`、`[16,17,27,58,88]`、`[22,19,22,56,87]`。
  - 10-task：`[13,14,10,16,13,16,20,20,41,43]`、`[11,10,21,10,14,15,10,23,39,53]`、`[10,12,13,13,11,14,23,23,45,42]`。
- 以上是 `drop_last` 前的逐图统计，不是五样本配额证明，也不是各类首任务监督时机证明。
- 逐图检查 206 张图片的顺序、唯一性、任务归属、seen 路径完整 `answer/answer_seg` 框保留和非 seen 路径 novel-only 对照；覆盖单类图与跨任务共现图。
- 使用随包 `000000018783.jpg` 的完整 8 框 GT 和作者 SciPy/Hungarian reward：完整同格式答案 `3.0`，仅 car `1.25`，差距 `1.75`；加入最大 `0.5` retention 后仍不能反转。
- 合并回归复跑既有 22 项 CTAN 测试；不修改既有 CTAN 测试文件。

## 非范围

本批不判定五样本配额、监督出现时机、COCO AP/per-task AP、Ray/DataLoader/RPC、分布式/GPU、训练/推理或原始论文实验身份；这些仍需独立协议确认。
