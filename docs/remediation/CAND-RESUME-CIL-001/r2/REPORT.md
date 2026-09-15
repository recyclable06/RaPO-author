# CAND-RESUME-CIL-001 第二轮整改报告

日期：2026-09-09。角色：independent remediation。对象：8ac5 工作树 `codex/remediate-cil-resume-001`。

## Verdict

`ready_for_independent_acceptance`

这是第二轮 CPU/static 交付状态，不是 GPU fresh-process 验收结论。独立验收仍需重新读取 r2 源码和测试，随后才可决定是否进入 GPU/SSH 任务。

## 修复内容

1. CIL-CPU-001：新增 `--stop_after_task_boundary`，必须与 `--publish_task_boundary` 同时使用。Task 1 完成全部 post-training validation、刷新 full checkpoint、写入 EMA/RNG 和 atomic-last marker 后，主循环只完成当前任务指标与清理，显式 `break`，正常结束并明确输出 Task 2 未运行。未启用 boundary 选项的 continuous workflow 不走该分支。
2. CIL-CPU-002：恢复输入 boundary 根与新发布 marker 根都登记到 `protected_boundary_roots`。`_path_overlaps_roots` 同时保护 boundary 的子路径和父路径，三处 pruning 均 fail closed；发布进程不再依赖 `resume_boundary` 是否非空。
3. CIL-CPU-003：publisher 与 validator 通过同一 checkpoint manifest 合同要求 `dataloader.pt`、单一 world-size 的完整 rank 集合，并对每个 rank 要求 `model_world_size_*`、`optim_world_size_*`、`extra_state_world_size_*`；tracker、global step、完整文件 hash 继续校验。Task 2 仍只建新 loader、cursor=0，不加载 Task 1 dataloader 游标。
4. CIL-CPU-004：本地 model directory/file 绑定递归完整 content manifest，所有权重、index、config、tokenizer 等文件使用流式 SHA-256；非本地引用只有 40-hex immutable revision 才可作为替代身份。路径或少量 metadata 不再足够。
5. CIL-CPU-005：source identity 对 6 个 production Python roots 动态枚举 `.py`，排除 `__pycache__`、日志、文档和输出；另加入 shared components、`verl/protocol.py`、`examples/config.yaml` 和 image config。当前 manifest 为 65 个条目（63 个 Python + 2 个配置文件），新增/删除/同路径内容变化均会改变身份。

## CPU/static evidence

使用既有 `D:/anaconda3/envs/rapo-b01/python.exe`（Python 3.10.20，pytest 8.4.2），命令禁用 bytecode 和 pytest cache，并将临时目录置于当前任务的 r2 目录：

```text
D:/anaconda3/envs/rapo-b01/python.exe -B -m pytest tests/author_fixes/test_cil_resume.py tests/author_fixes/test_coco.py tests/author_fixes/test_ctan.py -p no:cacheprovider -v --tb=short
```

结果：新增 CIL 12 项 + CTAN/COCO 25 项，共 **37 passed**，exit code `0`，stderr 为空。完整原始流、meta、环境和 exit 证据：`r2/raw/01_combined.*`。

新增判别例包括：

- multi-rank full checkpoint 正例；缺 `dataloader.pt`、缺 rank optimizer 的 fail-closed 负例；
- 同大小本地 model weight 内容变化导致 identity hash 变化；
- source manifest 覆盖 worker/actor/sharding/loader/reward/shared/config；
- boundary pruning 的父/子路径保护正例与 unrelated path 反例；
- stop-after-boundary CLI、正常退出文本、continuous path 和 restore-before-anchor 静态控制流断言。

## Patch and identity evidence

- r2 相对首轮实际 patch：`CAND-RESUME-CIL-001-r2-vs-first-round.patch`，25,717 bytes，SHA-256 `8a8262ecb35dfbb104f9da757dab9e071fbb133d88f6db786bc8307d9a717cf6`。
- r2 相对 5ced 的累计实际 patch：`CAND-RESUME-CIL-001-r2-vs-5ced.patch`，84,665 bytes，SHA-256 `47424dd2a6038761b0790335b2e7efe6ba933ebbf146304176a53bb2a4e0eb1c`。
- 编辑前输入：image `23cbb3c01f69704eb304c2b9c884d8165a9783a913422d6e679e63bb42d71928`，test `a8b17b247eac0526108fbd7388af9b98946752bb8214d24229f00121bd200896`。
- r2 输出：image `ba8a5da9341785178bd444112c4fc78dd352b52fe359b768218f4a4a6f5f7863`（99,349 bytes），test `331e62782cc63ef9a2fb4d2de1afe921593f629309f263c6728a7de5299e3f64`（14,217 bytes）。
- 完整 r2 文件清单和自排除 manifest：`HASHES.json`。

## Scope remaining

未执行 GPU、SSH、训练、推理、依赖安装、commit 或 push。native two-process restore、world-size-2 FSDP/vLLM RNG、anchor 数值 fingerprint、Task 2 首个真实 update、state-exact/trajectory-close 和 paper-scale metrics 仍留待独立 GPU 验收；本报告不把 CPU fixture 当作这些结果。
