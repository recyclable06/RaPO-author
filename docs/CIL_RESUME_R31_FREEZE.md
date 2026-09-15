# CIL 恢复 R3.1 验收快照登记

登记日期：2026-09-11。角色：协调/身份确认，不修改生产代码。

上次R3交付回报后，整改任务继续调整source manifest的目录过滤规则并更新测试，覆盖了同一r3目录的raw/patch/HASHES。独立验收在身份门发现变化，未对变化后的代码运行CPU或GPU；旧交付不能被当成新快照通过。此处将后续版本登记为R3.1，以区别首次R3；磁盘交付目录及其内部round标签仍为r3，身份以本登记的确切hash为准。

## 当前唯一验收输入

- 工作树：`C:/Users/Administrator/.codex/worktrees/8ac5/RaPO-author`；分支 `codex/remediate-cil-resume-001`；base HEAD `da0c5ad521387bab75e74dc0bf0fd47dc13a3647`。
- image：`examples/baselines/img_cls_cil/image_cls_cil_rapo.py`，102269 bytes，SHA256 `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3`。
- test：`tests/author_fixes/test_cil_resume.py`，24215 bytes，SHA256 `2bb64dccbce91409840d04344a30a58b76265ae77145ab33b4819a3613b4aadf`。
- 清单：工作树 `docs/remediation/CAND-RESUME-CIL-001/r3/HASHES.json`，SHA256 `ce058c0a2e9485ba027c2a6c7356f02ef99a3b0d1a283674d8a2e418f4a75271`。17个唯一列出文件已由协调者核对bytes/hash一致；2026-09-11再次确认目标两文件和清单未变。
- 相对R2 patch：24914 bytes，SHA256 `87c633344492d0187043546c22b465e2f39048eb4f8ffdf15c69ba01250a3e18`；相对5ced累计patch：100701 bytes，SHA256 `1711e418bf1a7c5acc49fb1187432199a09cf1eaa71465c7458315fb89973b4a`。

原R3身份（image `37fe1e53...`、test `7559c897...`、manifest `85424f75...`）已撤回验收；部分同名证据被整改者覆盖，不宣称原R3完整raw仍被保存。原身份阻塞文件保留于 `docs/acceptance/CIL-RESUME-CPU-R3-20260910/`。R1/R2证据与R2输入副本保持。

## 冻结与继续

整改任务已明确停止写入并结束；工具确认其空闲/未加载。本次用户已恢复独立验收任务 `01a074b8-560b-7be1-8874-1f55a7e1ae10`，当前正在运行，沿用该任务即可，不重复派发。新验收输出放 `docs/acceptance/CIL-RESUME-CPU-R31-20260911/`，保留先前身份阻塞原件。

沿用CIL_RESUME_DECISION、R2_DECISION、R3_DECISION及R3验收委托的实质内容，仅更新快照身份。独立验收可继续必要CPU/static检查；source/test/manifest前后核对，CPU自测42项不算独立通过。仍不进行GPU/SSH/训练，不关闭fresh-process finding。

完成回报即冻结点。任何后续必要修改须先回报撤回的快照、隔离在途验收，并以新版本保存证据后再交付；不得继续覆盖已经交付的同名清单或raw。
