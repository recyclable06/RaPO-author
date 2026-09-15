# CAND-RESUME-CIL-001 整改报告

日期：2026-09-09。角色：独立整改执行者。

## Verdict

`ready_for_independent_acceptance`

这是整改交付状态，不是 fresh-process GPU 验收结论，不关闭 `CAND-RESUME-CIL-001`。

## 实现范围

唯一生产文件为 `examples/baselines/img_cls_cil/image_cls_cil_rapo.py`；唯一新增测试为 `tests/author_fixes/test_cil_resume.py`。整合输入中的既有 CTAN/COCO 生产与测试字节保持不变。

实现了：

1. 显式 boundary 发布/恢复入口。默认 continuous 工作流不启用发布，也不因 `save_model_only` 默认配置失败；发布必须显式 `--publish_task_boundary`，且要求 `save_model_only=false`、`save_task_ckpt!=none`。
2. `task1-complete.json` 原子最后发布。marker 绑定 `global_step_N` 目录完整文件 manifest、tracker、full optimizer/worker extra-state、EMA sidecar、driver RNG、每 rank vLLM RNG、source、model、input、effective config、class plan、Task 2 loader policy 和 state fingerprint。缺件、错 hash、错 step、model-only、错误 plan 或非零 Task 2 cursor 均 fail closed。
3. fresh-process Task 2 入口使用 marker 的 class plan 和 current/seen classes，不重新随机生成计划；输出根必须与只读 Task 1 boundary 根分离，pruning 逻辑拒绝触碰 source boundary。
4. fresh restore 顺序为：恢复 driver RNG（loader 创建前）→新 Task 2 loader → native actor/optimizer/scheduler/worker RNG restore → per-rank vLLM RNG restore →生产 actor→anchor copy→restore event→Task 2 fit。Task 2 不读取 Task 1 `dataloader.pt`，loader policy 明确 `cursor=0`。
5. post-training extra validation 完成后用 native manager 刷新同一最终 step 的完整 checkpoint，再写 EMA/RNG sidecar 和最后 marker；不额外保存完整 anchor。

## 证据与身份

- 输入/初始化身份：[`PRE_HASHES.md`](PRE_HASHES.md)
- CPU/语法/回归原始证据：[`TEST_EVIDENCE.md`](TEST_EVIDENCE.md)
- 文件 hash 汇总：[`HASHES.json`](HASHES.json)
- 5ced source image CIL hash：`8a13974e3dfa7756a076844ce25ef6d66c71c29751fd2dec2f00a52b49092f3d`
- 整改后 image CIL hash：`23cbb3c01f69704eb304c2b9c884d8165a9783a913422d6e679e63bb42d71928`
- 整改后新增测试 hash：`a8b17b247eac0526108fbd7388af9b98946752bb8214d24229f00121bd200896`
- 相对 5ced image CIL 的 finding-only diff：`1,029 insertions / 29 deletions`（当前文件 93,286 bytes）。

## 验证结果

- `python -m py_compile examples/baselines/img_cls_cil/image_cls_cil_rapo.py tests/author_fixes/test_cil_resume.py`：PASS。
- 项目既有环境 `D:/anaconda3/envs/rapo-b01/python.exe`，Python 3.10.20 / pytest 8.4.2：新增协议 6 passed；`test_coco.py test_ctan.py` 25 passed；合计 31 passed。
- `git diff --check`：PASS。
- 未安装依赖、未使用 SSH/GPU，未训练/推理，未 commit/push。

## 未验证项

真实 native checkpoint、两进程 worker group、GPU/FSDP/vLLM RNG、anchor 数值 fingerprint、Task 2 首个真实 update、trajectory-close 和 paper-scale 指标均未在本任务执行。独立验收必须分别报告 `state-exact` 与 `trajectory-close`，不能用本报告或同进程连续证据替代。
