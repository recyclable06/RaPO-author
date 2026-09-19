# FINDING-DELTA-WIRING-001

状态：`OPEN — runtime identity/deployment not bound`

## 事实

冻结 v9 的 `run_v9.py:147-163` 将 v9 目录写入 `PYTHONPATH`；`runtime_entry_v6.py:29-35` 又把自身 v9 目录插入 `sys.path` 首位，并从该目录导入 `child_bootstrap_v6`。该 bootstrap 再从 import path 导入 `child_observer_v6`。

当前 delta 只提供 `child_observer_v6.py`、审计脚本、CPU fake test、报告和引用文件；没有新的 `runtime_entry_v6.py`、`child_bootstrap_v6.py`、`sitecustomize.py`、`event_writer_v6.py`、`run_v9.py` 或新 runtime manifest/identity。

`run_v9` 的 `identity_sha256` 由 `argv_validate_v9.py:218-232` 的 production/config/model/input/runtime-source identity 组成，不含 observer 文件 SHA。因而旁置 delta 文件或直接覆盖 frozen v9 observer 后照旧执行，均不足以形成可核验的新 observer identity。

## 最小解除条件

提供一个新的 acceptance-only runtime root 或等价的新 entry wrapper，明确：

- frozen v9 base manifest 及其 self-excluded SHA；
- delta `child_observer_v6.py` SHA `e9c2f17115c44348d1e9e056ee8b3b0b691d2f4ce40e3af0f5ca483f4cd53bd1`；
- inherited bootstrap/event-writer/runtime-entry/sitecustomize 的路径与 SHA；
- delta 优先于 frozen v9 的 `PYTHONPATH`/`sys.path` 顺序；
- unchanged production source SHA `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3`；
- 实际启动入口和 fresh output root。

该 identity 绑定完成前，不把 delta 标成 READY，也不启动 A fresh run。

