# FINDING-DELTA-SCOPE-003

状态：`STATIC-PARTIAL — scope needs real-Ray closure`

## 静态判断

delta 的 `observed_remote` 对 `@ray.remote(options)` 和 `ray.remote(Class)` 保留原始参数；非目标类/函数及原始异常路径继续交给原始 `ray.remote`。`_patch` 的 `_rapo_v6_observer` 标记也保留 repeated wrapping 的复用路径。

但新增 helper 使用整个 `TARGET_PLANS` 识别 raw class，并对 Ray 返回 ActorClass 的所有候选 class 尝试 patch，而不是代码层面只写死 `PersistentRunner`。按 production import 顺序，其他目标 FSDP classes 在 `install_for_module` 发生后才进入 `PersistentRunner.init` 的 remote 调用，通常会走 `reused=true`；这只是基于源码顺序的静态推断。

## 最小闭合证据

真实 Ray 2.46.0 zero-GPU probe 必须覆盖：

1. `@ray.remote(num_cpus=1)` 的 `PersistentRunner` target raw-class prepatch；
2. direct `ray.remote(Class)` 与 `.options(...)` 的非目标路径参数透传；
3. inherited method、原始 decorator/remote 异常、重复 install 不增加重复 after-event；
4. driver 与 worker 的 observer identity 一致；
5. actual `PersistentRunner.run_task` before/after 一对一匹配。

在这些证据出现前，不把 scope review 写成无条件 PASS。

