# Real zero-GPU Ray probe plan

这不是 A gate 的重跑，也不是 fake/mock 测试。它只在已有、兼容项目的 `ray==2.46.0` 环境中执行，不安装依赖、不使用 GPU、不加载 model、不调用 training。

## 入口

```text
python -B zero_gpu_real_ray_probe.py \
  --source-root C:/Users/Administrator/.codex/worktrees/8ac5/RaPO-author \
  --v9-root C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/v9 \
  --run-root <fresh-zero-gpu-output> \
  --result <fresh-zero-gpu-output>/result.json
```

入口会把 delta observer 目录放在 v9 support 目录之前，但不覆盖 v9 文件；worker 的 `PYTHONPATH` 由真实 `ray.init(runtime_env=...)` 传播。结果必须同时记录 delta observer SHA、v9 inherited bootstrap/event-writer SHA、frozen production SHA 和 fresh output root。

## Probe 行为

1. 导入真实 Ray，若不存在则写 `BLOCKED_REAL_RAY_UNAVAILABLE`，不生成 PASS。
2. 使用 `ray.init(address="local", num_gpus=0, include_dashboard=False, log_to_driver=False)`。
3. 通过 delta observer 导入 canonical production module，并校验 production source SHA；只创建 `PersistentRunner` actor。
4. 调用 `runner.run_task.remote(config=None, task_id=1, ..., publish_task_boundary=True)`；由于没有调用 `runner.init`，预期在 trainer 尚未初始化处抛出 inert error。这个调用仅验证真实 actor dispatch，不构造 model、不建 dataloader、不训练。
5. 再创建一个 `num_gpus=0` 的小型 probe actor，让其通过 inherited v9 `child_bootstrap_v6` 重新报告实际 worker observer path/SHA，并导入 canonical production module；该 actor 不属于生产对象，不作为生产 gate 证据。
6. 读取真实 event JSONL，核对 driver/worker 的 bootstrap identity、`ray_remote_wrapper_install`、`PersistentRunner.run_task` before/after 的同一 `call_id`，并确认没有 model/training 调用。

## 通过条件与边界

只有以下条件全部满足，才可把 delta 的“真实 dispatch 接线”标为 PASS：

- `ray==2.46.0` 真实运行且 `num_gpus=0`；
- driver 与 Ray worker 的 `child_bootstrap_install.observer.sha256` 都等于 `e9c2f17115c44348d1e9e056ee8b3b0b691d2f4ce40e3af0f5ca483f4cd53bd1`；
- `ray_remote_wrapper_install.installed=true`，且 runtime identity 中明确 delta 优先级；
- 真实 `PersistentRunner.run_task` 有一条 before 与一条 after，call_id 相同；after 可为预期 inert exception，但不能是缺少 after 的静默返回；
- canonical production source SHA 与 frozen identity 一致，未执行 `PersistentRunner.init`、model load、dataloader build 或 training。

此 probe 仍不能关闭 A gate。A gate 还必须用同一新 runtime identity 进行 A-only fresh run，并从真实 post-publication `PersistentRunner.run_task` after-event 派生完整 `driver_rng_expected`；不得用 marker 或 probe stub 替代。

