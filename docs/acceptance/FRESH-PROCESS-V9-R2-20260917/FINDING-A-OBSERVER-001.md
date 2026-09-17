# FINDING-A-OBSERVER-001：A-valid driver RNG 观察链不完整

## 判定

- 类型：diagnostic observation/collection gap
- 严重性：阻塞 A full boundary evidence，但当前不定性为 production publication defect
- 生产代码变更授权：无
- 科学结论：A-valid 的 Task 1 marker 已发布；完整 boundary 未证明

## 事实

R2 的 A-valid marker 已在本地交付并通过字节数、SHA256、schema/status/global-step 核验：`status=complete`、`completed_task=1`、`global_step=2`、`next_task=2`，marker SHA256 为 `c7b8c132de4346bba8c570d429bdcbef603c0bbeea6bfd8803fea84175d4f795`。

同一候选的 `boundary-expected.json` 为 `complete=false`，`driver=null`，并报告 `A actual post-publication driver RNG capture is missing`。A raw observer event 目录没有交付文件；marker 引用的 `boundary_state/driver_rng.json` 与两个 vLLM RNG 文件也没有交付。因此当前无法从原始 event 或 marker-referenced subordinate files 重建完整边界。

## 源码证据

生产源码 `examples/baselines/img_cls_cil/image_cls_cil_rapo.py`（SHA256 `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3`）显示：

- `_publish_task_boundary` 在第 881 行写入 `driver_rng_payload`；
- `PersistentRunner.run_task` 在第 1546 行进入 publication 分支；
- 第 1566 行采集 vLLM boundary RNG；
- 第 1573 行向 publication 函数传入 `_capture_driver_rng_state()`。

诊断 sidecar `child_observer_v6.py` 只在第 248、251–252 行同时满足 `PersistentRunner.run_task`、`publish_task_boundary` 为真、`task_id == 1` 且 `RAPO_DIAG_LEG == "A"` 时附加 `driver_rng_expected`。`boundary_evidence_v6.py` 第 126、133–134 行只从该 after-event 字段派生 driver record；没有该 event 就报告上述错误。sidecar 还在第 371–386 行尝试通过 Ray runtime_env 传播诊断环境，但本候选没有 raw events，无法证明触发条件、子进程传播或采集保存的具体失败点。

## 最小允许后续

只允许在诊断/验收范围内补足证据：

1. 保持冻结生产 source、publication 参数、阈值、reward/advantage/retention 容差不变；
2. 收集同一 run 的 raw `PersistentRunner.run_task` after events；
3. 收集 marker 引用的三个 `boundary_state` 文件并逐文件核对记录的 SHA256；
4. 如需修复，只在 `child_observer_v6.py`、`boundary_evidence_v6.py` 或交付收集逻辑内定位并记录修复，不把诊断补丁冒充生产修复；
5. 重新生成完整 boundary 后，才进入 B fresh-process acceptance。

不得通过手工生成或补写 RNG 结果来把 A 标成 complete。

