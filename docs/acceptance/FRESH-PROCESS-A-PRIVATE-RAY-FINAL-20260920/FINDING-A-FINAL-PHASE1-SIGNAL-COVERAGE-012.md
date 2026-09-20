# FINDING-A-FINAL-PHASE1-SIGNAL-COVERAGE-012

状态：OPEN / EVIDENCE GAP

最终 supervisor 实现静态上已安装 SIGINT/SIGTERM handler，并在
`execute()` 中以 `BaseException` + cleanup/finally 路径承接中断。可是
`run_linux_process_check()` 本身只启动 fake Ray/launcher descendants，等待
production timeout，然后让 supervisor 的 cleanup 向这些 descendants 发
SIGTERM/SIGKILL；它没有向 supervisor 自己发送 SIGINT 或 SIGTERM，也没有
调用 `_handle_interrupt()`。默认 `run()` 的 signal 检查只是当前 Windows
进程内直接调用 `_handle_interrupt(signal.SIGINT/SIGTERM, None)`，不是真实
进程信号。

因此 `FINAL_COMMAND.md` 对 Phase 1“验证 SIGTERM/SIGINT”的描述扩大了实际
覆盖范围。最小补充是另一个 Linux-only harness：启动 final supervisor/或
受控 test process，向其真实 PID 发送 SIGINT 和 SIGTERM，分别收集最终
record/result、cleanup budget、child 无遗留和 signal identity；不能把当前
portable direct-handler 结果或 descendant cleanup 信号当作该证据。
