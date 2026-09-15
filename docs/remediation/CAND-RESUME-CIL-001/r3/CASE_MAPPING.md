# CAND-RESUME-CIL-001 R3 case mapping

本轮只处理 R2 独立验收指出的 CIL-CPU-002、CIL-CPU-004、CIL-CPU-005。测试通过 AST 提取并执行生产控制流或生产协议函数；不启动 Ray/GPU，不把 fixture 当作 GPU 恢复结论。R2 已通过的 full-rank checkpoint、EMA/RNG、restore-before-anchor 和 continuous 行为保持不变。

| Finding | R3 生产修复 | 新增/保留 CPU 判别例 |
| --- | --- | --- |
| CIL-CPU-002：protected boundary pruning 不能中止正常流程 | Task 当前目录、previous-task 目录、最终清理三处遇到 boundary 父/子路径时打印保留并 `continue`；非法 resume 输入/输出重叠检查不变 | `test_actual_production_pruning_skips_boundary_and_continues` 提取三个真实 `for entry` pruning loop，在 Task 1 多 checkpoint、publish 后进入 Task 2、最终清理三种路径执行；验证 protected 内容不变、调用后可继续、普通旧 checkpoint 按原策略删除 |
| CIL-CPU-004：boundary 身份必须绑定实际本地模型和 tokenizer/processor | `_model_identity` 拒绝远端 ID，即使带 40-hex revision；要求已有本地 model 路径和 tokenizer/processor 路径的完整流式 content manifest。`PersistentRunner.init` 的 tokenizer/processor 实际调用改为配置的 `tokenizer_path`；共享 native loader/revision 框架不变 | `test_model_identity_rejects_remote_id_even_with_immutable_revision`；`test_model_identity_binds_independent_tokenizer_content` 验证同大小 tokenizer 内容变化改变身份；`test_runner_consumes_configured_tokenizer_path` 检查两个实际生产调用的参数 |
| CIL-CPU-005：source identity 必须覆盖运行时闭包 | source manifest 动态覆盖完整 `verl` Python 树（含 `models` 和 package init）、完整 examples Python/runtime 配置、image scripts/runtime 配置及 `requirements.txt`/environment locks；过滤 cache/log/output；解析 YAML 中实际 `reward_function` 路径并绑定其内容 | `test_source_identity_covers_dynamic_production_roots_and_config` 检查 worker/model/reward/config/依赖；`test_source_identity_tracks_configured_reward_and_tree_add_delete_mutation` 使用非默认 reward 文件验证实际路径，并验证新增、删除、同路径同大小内容变化都会改变 manifest |

## 组合回归

使用既有 `rapo-b01` 环境、`-B`、`PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider` 和 verbose 输出执行：

```text
D:/anaconda3/envs/rapo-b01/python.exe -B -m pytest tests/author_fixes/test_cil_resume.py tests/author_fixes/test_ctan.py tests/author_fixes/test_coco.py -p no:cacheprovider -v --tb=short
```

结果：17 项 CIL + 25 项 CTAN/COCO = **42 passed**，exit code `0`，stderr 为空。既有 CTAN 测试产生 1 个 ResourceWarning，不影响 42 项结果；完整 stdout/stderr/exit/环境见 `raw/02_combined.*`。
