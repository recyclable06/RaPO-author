# PRIVATE-RAY-FINAL-SIGNAL-HARNESS-20260920

状态：`PREPARED_LOCAL_SYNTAX_STATIC_ONLY`

这是 `FINDING-A-FINAL-PHASE1-SIGNAL-COVERAGE-012` 的独立外置信号准备包。它
不修改 FINAL runtime、父 `SUPERVISOR-SUPPLEMENT`、兄弟 `ZEROGPU-SUPPLEMENT`、
root `test-results.json` 或任何生产代码。

`run_signal_harness.py` 在目标 Linux 主机上将同一份 FINAL
`private_ray_supervisor.py` 作为子进程启动两次。每个 case 都使用一份私有
fake `ray` CLI 和 fake launcher；它们产生真实的 head/launcher 进程以及各自
的 `start_new_session=True` 后代。harness 等到 fake head、fake launcher、
`RUNNING` record、supervisor PID 和四个 fake PID 的 `/proc` UID/starttime/
session 身份齐备后，分别对 supervisor 自身真实 PID 执行一次 `os.kill`：
`SIGINT` 和 `SIGTERM`。它没有导入 FINAL 模块，也没有直接调用
`_handle_interrupt`。

每个 case 的证据目录位于外部 `Output` 下，包含 supervisor 最终 record/result、
supervisor stdout/stderr、fake 进程身份和 case JSON。验证项包括：

- signal number、目标 supervisor PID、UID、Linux procfs starttime、session 和
  process group；
- head、launcher 及两个跨 session descendant 的 UID/starttime/parent/session；
- final record 为 `STOPPED`，result 保留受控中断，Ray/launcher owned lists 为空，
  private temp root 已删除；
- cleanup 只报告本次已记录的 PID/start identity，预算不超过 120 秒，没有全局
  Ray 或进程清理动作；
- FINAL `HASHES_FINAL.json` 中四个 runtime entry 的 bytes/SHA-256 在两个 case
  前后完全相同。

本地已执行标准库静态测试（Windows Python 3.13）：四个 Python 文件均可解析，
命令包含三个原 basename、两个真实 signal case、独立 `/tmp` 名称和 120 秒预算，
且 harness 源码没有全局清理命令或直接 handler 调用。结果保存在
`newoutput/static-tests.json`。本轮不执行 Linux signal case；静态测试本身不产生
Linux PID/session 或 cleanup 证据。

证据边界：Windows 本地不能把该 harness 的语法/静态检查写成真实 Linux signal
通过；真实 `/proc`、PID/session、SIGINT/SIGTERM 和后代清理结果必须由协调者在
目标 Linux 主机执行 `SIGNAL_HARNESS_COMMAND.md`，然后独立审查输出。
