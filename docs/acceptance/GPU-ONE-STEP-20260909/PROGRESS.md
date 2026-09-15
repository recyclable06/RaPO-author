# 独立验收进度

更新：2026-09-09。

- 已完成：验证诊断 `HASHES.json` 的 53 个声明文件；起始读取的 attempt-15 结果与诊断清单身份一致。
- 已完成：独立解析 raw JSON，重算 phase、worker mapping、CTAN/EMA、gradient、actor sampled delta、anchor sampled equality、mapped vLLM stale/sync delta、log-prob 和 post-sync generation。
- 已完成：静态核对诊断 wrapper 与生产 `trainer.fit()`、actor update、CTAN hook、wake → `_sync_weight_to_vllm` → `model.load_weights` 链；10 个集成 key file hash 一致。
- 已完成：核对 attempt-15 的 source/model/input identity、GPU 4/6 释放和 CUDA error boundary；早期非法内存访问证据保持原样。
- 已发现：`no_checkpoint_write=true` 与 `run.stdout` 第 575–576 行的实际 `Saving model to ...global_step_1...` 冲突；源码最终保存分支解释了冲突。
- 当前裁决：有限一步有效更新通过；整体验收带 scope exception；阶段 5 未通过。

下一步只应在获得对应 GPU 重跑/诊断修改授权后，针对 checkpoint 写入边界补一轮独立验证；本进度不授权修改生产源码或启动跨任务恢复实验。
