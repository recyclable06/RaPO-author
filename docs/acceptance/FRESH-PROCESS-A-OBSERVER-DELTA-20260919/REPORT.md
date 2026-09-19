# A observer delta — independent acceptance review

审查日期：2026-09-19（Asia/Shanghai）  
角色：独立只读验收；范围仅为 `FRESH-PROCESS-V9-R2-A-OBSERVER-DELTA-20260919`。

## 独立结论

结论为 `PARTIAL — NOT READY FOR A GATE`。

delta 的静态修复方向是合理的：在 `ray.remote` 建立 Ray ActorClass dispatch 之前，对真实 `PersistentRunner` raw class 的 `run_task` 打 wrapper；同时保留返回 ActorClass 的兜底检查。现有 CPU 检查证明了这个分支在 fake ActorClass 上能够得到 before/after 和 `driver_rng_expected`，但它没有执行真实 Ray，也没有使用真实 `capture_driver_rng`、真实 ActorClass 序列化或真实 worker。

本机可用 Python 均未安装 Ray；项目要求的版本为 `ray==2.46.0`。因此本轮没有真实 zero-GPU Ray dispatch 证据，不能把 delta 标为 READY，也不能把旧 A raw 的 marker driver RNG 当作 actual after-event。

另有独立的运行接线缺口：冻结 `run_v9.py` 将 v9 runtime 目录固定插入 `PYTHONPATH` 首位，`runtime_entry_v6.py` 也固定从自身 v9 目录导入 `child_bootstrap_v6`。当前 7-file delta 没有新的 runtime entry、bootstrap、sitecustomize、event writer、launcher 或 self-contained runtime identity；`run_v9` 的现有 `identity_sha256` 也不包含 observer 文件。仅把 delta 文件放在旁边、继续执行冻结 v9 manifest，不能证明新 observer 已被 driver 和 Ray worker 加载。

## 原件完整性与身份

- delta manifest 声明 7 个文件、53,631 bytes；逐文件 bytes/SHA256 核对通过。
- `child_observer_v6.py` SHA256：`e9c2f17115c44348d1e9e056ee8b3b0b691d2f4ce40e3af0f5ca483f4cd53bd1`。
- frozen v9 observer SHA256：`a7e239bca8bea99dd01e07c842efc9d0a45126cc4b43689a798937e67b9c43e1`。
- frozen production source SHA256：`3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3`。
- frozen v9 package manifest SHA256：`3767c12fd6bc90ef43479486a057ae92b557aaa4ec276c12d5713871597bae7a`。
- 共享 A evidence 的 delivery manifest、marker、driver/EMA/vLLM 文件身份沿用原件；本轮没有改写它们。

## 静态 diff 与真实生产顺序

delta 相对 frozen v9 `child_observer_v6.py` 只增加 `_RAY_REMOTE_PATCHED`、`_patch_remote_source_class`、`_patch_remote_result` 和 `ray.remote` wrapper；原有 `_patch` 的 before/after、异常 re-raise、kwargs 优先解析、event payload 和 capture 逻辑未改动。

frozen production source 中：

- `image_cls_cil_rapo.py:1259-1260` 使用 `@ray.remote(num_cpus=1)` 定义 `PersistentRunner`；
- `image_cls_cil_rapo.py:1290-1291` 在之后的 `PersistentRunner.init` 中直接调用 `ray.remote(PersistentRefFSDPWorker)` / `ray.remote(FSDPWorker)`；
- `image_cls_cil_rapo.py:1305-1309` 对 `ray.remote(AutoRewardManager).options(...)` 使用普通非目标类路径。

新 wrapper 对 `@ray.remote(options)`、`ray.remote(Class)` 两种目标形式分别在原始 decorator/build 前 patch raw class，并把原始参数交给 Ray；非目标函数/类和带其他参数的调用走原始 `ray.remote`。由于 `_LoaderWrapper.exec_module` 在完整 production module 执行完后才调用旧的 `install_for_module`，`PersistentRunner` 的 decorator 是唯一需要在 module execution 期间提前处理的目标；后续 FSDP 类在 `PersistentRunner.init` 运行前已经由旧 observer 装好 wrapper。这支持“实际新增时序效果集中在 PersistentRunner”的判断。

但 `_patch_remote_result` 会遍历 Ray 返回 ActorClass 的候选 class，并按 `TARGET_PLANS` 的所有目标方法尝试 patch；没有真实 Ray 运行，不能独立证明 Ray 2.46.0 的 modified class、dispatch table、序列化和 repeated wrapping 不会产生重复 after-event 或改变其他目标类的行为。因此 scope 仍需真实 zero-GPU 检查闭合。

## 已执行的本地检查及其边界

- `test_child_observer_v6_cpu.py`：`CPU observer regression: PASS`；测试使用 `FakeActorClass`、`fake_remote`，并将 `capture_driver_rng`、runtime/state capture 全部替换为 stub。它只证明局部分支，不证明真实 Ray dispatch、序列化、worker bootstrap 或真实 RNG。
- delta `child_observer_v6.py`：Python compile 通过。
- `python` 与 `C:\msys64\ucrt64\bin\python.exe` 的 `importlib.util.find_spec("ray")` 均为 `None`；conda 入口不可用。没有执行安装、SSH、GPU、模型或训练。

## 当前最小闭合路径

1. 先创建一个新的、可核验的 observer runtime identity：明确 frozen v9 base manifest、delta child SHA、继承的 `child_bootstrap_v6.py`/`event_writer_v6.py`/`runtime_entry_v6.py`/`sitecustomize.py` SHA、production source SHA、entry/PYTHONPATH precedence 和实际启动命令。不能覆盖 frozen v9 后继续沿用旧 manifest。
2. 在已有兼容 Ray 2.46.0 的环境执行 [ZERO_GPU_REAL_RAY_PLAN.md](ZERO_GPU_REAL_RAY_PLAN.md) 对应的真实 zero-GPU probe；只导入 canonical production module、创建/调用 `PersistentRunner` 到预期的 inert error，不调用 `init`、不加载 model/dataloader、不训练。
3. 只有在 driver 与 Ray worker 的 bootstrap event 都报告 delta observer SHA，且真实 `PersistentRunner.run_task` 产生同一 call_id 的 before/after 后，才可把“observer dispatch 修复”标为可进入 A-only fresh run。A gate 仍必须另有真实 production after-event，其中 `driver_rng_expected` 必须由该 after-event 捕获并由 `boundary_evidence_v6.py` 派生，不能用 marker 替代。

