# FINDING-DELTA-REAL-RAY-002

状态：`OPEN — real Ray dispatch unverified`

## 事实

本机未发现兼容 Ray：`C:\Program Files\Python313\python.exe` 与 `C:\msys64\ucrt64\bin\python.exe` 的 `import ray` spec 均为 `None`，conda 入口不可用。项目 requirement 记录的是 `ray[default]==2.46.0`。

`test_child_observer_v6_cpu.py` 的 `FakeActorClass`/`fake_remote` 在装饰前看到 `_rapo_v6_observer=true`，并用 stub `capture_driver_rng` 产生 `cpu-test-driver`。这只能验证 delta 的局部控制流，不能证明：

- Ray 2.46.0 的真实 ActorClass dispatch table 使用了 raw class wrapper；
- wrapper 随 ActorClass 序列化并在真实 worker 执行；
- worker bootstrap 从 delta 路径加载 observer；
- `_patch_remote_result` 不造成重复包装或其他 actor 方法的行为变化；
- actual production `run_task` after-event 具有真实 RNG capture。

## 最小解除条件

在不安装、不用 GPU、不加载 model、不调用 training 的已有 Ray 2.46.0 环境执行真实 zero-GPU probe。至少收集 driver/worker bootstrap identity、`ray_remote_wrapper_install`、canonical production source identity，以及真实 `PersistentRunner.run_task` before/after 的同一 call_id。预期 inert error 可以是 `PersistentCILTrainer` 尚未初始化导致的异常；这不构成 A gate PASS。

