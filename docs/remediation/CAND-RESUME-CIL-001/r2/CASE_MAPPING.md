# CAND-RESUME-CIL-001 r2 case mapping

本轮测试只验证生产 boundary protocol 和控制流，不启动 Ray/GPU，不替代后续两进程 GPU 验收。旧 CTAN/COCO 测试保持原断言并作为回归集合运行。

| 冻结缺口 | r2 生产覆盖 | 新增 CPU 判别例 |
| --- | --- | --- |
| CIL-CPU-001 发布后正常退出 | `--publish_task_boundary --stop_after_task_boundary` 必须成对启用；Task 1 marker 成功后 loop `break`，清理后输出明确“Task 2 was not run”，连续模式不启用时不变 | `test_source_guards_preserve_continuous_path_and_restore_order` 检查显式 CLI、stop 分支和 continuous `load_checkpoint_path=None` 语义 |
| CIL-CPU-002 发布/恢复源 boundary 不得 pruning | `protected_boundary_roots` 同时登记恢复源与新发布 marker 根；`_path_overlaps_roots` 对 boundary 子路径和父路径均保护 | `test_pruning_guard_protects_boundary_children_and_parent` 正例/反例；源码断言检查三处 pruning 调用均使用保护判断 |
| CIL-CPU-003 native full checkpoint | publisher 与 validator 共同要求 `dataloader.pt`、单一 world-size 的完整 rank 集合及每 rank 的 model/optim/extra-state；tracker 与 global step 继续绑定 | `test_multi_rank_native_checkpoint_fixture_is_accepted` 正例；`test_missing_dataloader_fails_closed_even_with_refreshed_manifest`、`test_missing_native_rank_state_fails_closed_even_with_refreshed_manifest` 负例 |
| CIL-CPU-004 模型 content identity | 本地 model path 绑定完整递归流式 content manifest；远程引用仅接受 40-hex immutable revision | `test_model_identity_binds_all_local_model_content` 改变同大小权重后 hash 必须变化 |
| CIL-CPU-005 完整 source/config identity | 对 production Python roots 动态枚举 `.py`，排除 `__pycache__`/日志/文档，另绑定 image config、base config、shared components、protocol；增加文件、删除文件或内容变化都会改变 manifest | `test_source_identity_covers_dynamic_production_roots_and_config` 检查 manager/worker/actor/sharding/loader/reward/config 均在 manifest |

## 组合执行

使用既有 `rapo-b01` 环境、`-B`、`PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider` 和 r2 可写临时目录执行：

```text
D:/anaconda3/envs/rapo-b01/python.exe -B -m pytest tests/author_fixes/test_cil_resume.py tests/author_fixes/test_coco.py tests/author_fixes/test_ctan.py -p no:cacheprovider -v --tb=short
```

结果：新增 CIL 12 项 + CTAN/COCO 25 项 = **37 passed**，exit code `0`；完整 stdout/stderr/环境/命令见 `raw/01_combined.*`。

## 发布进程的可复现入口

在现有 image CIL 启动命令的基础上，Task 1 发布进程必须显式追加两个选项：

```text
python -m examples.baselines.img_cls_cil.image_cls_cil_rapo --base_classes 20 --incremental_classes 20 --class_order_seed 1993 --save_task_ckpt latest --save_dir <output-root> --prompt_seen_labels --cil_cfg scripts/image/rapo_cfg.json --publish_task_boundary --stop_after_task_boundary config=examples/config.yaml data.train_files=<train-dir> data.val_files=<val-dir> worker.actor.model.model_path=<local-model-dir> trainer.total_epochs=2
```

`--stop_after_task_boundary` 没有 `--publish_task_boundary` 时 fail closed；未启用这两个 boundary 选项的既有 continuous workflow 不走 stop 分支。Task 2 fresh resume 仍使用独立 output root、新 loader、cursor `0`，不加载 Task 1 `dataloader.pt` 游标。
