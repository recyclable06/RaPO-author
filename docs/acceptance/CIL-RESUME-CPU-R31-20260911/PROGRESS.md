# R3.1 验收进度

1. 读取 `docs/CIL_RESUME_R31_FREEZE.md`，确认 R3.1 唯一输入和输出目录；保留 `CIL-RESUME-CPU-R3-20260910` 的旧身份漂移文件。
2. 起始身份核对通过：目标 source/test 与冻结 bytes/hash 一致；R3 evidence manifest 的 15 个列出文件逐项一致。
3. 独立 probe 通过：真实 pruning 三分支、完整 checkpoint fail-closed、model/tokenizer 内容身份、动态 source/reward 依赖、CLI 可达性和 restore/loader/anchor/publish 顺序。
4. 冻结 CPU 组合回归一次通过：42 passed，exit 0，stderr 0。
5. 结束身份核对通过：source、test、manifest 均未改变。

当前状态：`PASS_READY_FOR_GPU`（仅代码 CPU/static gate）；`fresh_process_resume=not_accepted`。剩余项是专用 GPU 的跨 OS process 两卡 restore、RNG/anchor/Task-2 first update、state-exact/trajectory-close 和论文规模指标。
