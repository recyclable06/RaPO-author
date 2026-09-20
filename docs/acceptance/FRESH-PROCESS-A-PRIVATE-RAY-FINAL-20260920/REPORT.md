# Final combined supervisor — independent narrow review

日期：2026-09-20

## 结论

当前裁决：`NOT_READY_FOR_BOUNDED_LINUX_STDLIB_AS_WRITTEN`。

新 standalone runtime 对 005–010 的实现已基本完成静态闭合：manifest/snapshot
guard、SIGINT/SIGTERM cleanup、launcher descendant tracking、file-backed logs
和 `bin/ray` 接线均存在，且 portable standard-library suite 独立通过。但
冻结的 Phase 1 命令不能直接运行：它会覆盖被 HASHES_FINAL 冻结的
`test-results.json`；同时 `run_linux_process_check()` 没有向 supervisor 进程
实际发送 SIGINT/SIGTERM，不能支撑命令文档对信号覆盖的表述。

因此可以在修正调用方式后运行 Linux/procfs fake-child 检查，但当前命令不应
直接执行，也不能把它标为完整的 signal-verified Phase 1。具体安全调用契约
见 `PHASE1_DIRECT_CALL.md`。

## 身份与已执行的本地检查

- final runtime：4 文件、86,564 bytes；`HASHES_FINAL.json` self SHA
  `3b9f055da492741754f80b63e2255716e118fea546bca429267c542877136f67`；
  `MANIFEST_FINAL.json` SHA
  `fc97026c8e51f137d3106d0f918ff3577d8a2886b230f443023e2579d08de0b0`；
  runtime entries 全部匹配。
- parent/zero-GPU frozen snapshot 的 hash 与 manifest identity 与上一轮一致：
  parent `f4914b91...` / `cac9d08d...`，zero-GPU `3635a3af...` /
  `eae68121...`。
- 目标主机 CLI preflight 证据已核对：30 文件、16,933 bytes，self SHA
  `9c8bc7cac8c7c85fd795ab860f8a357c1e4c65461cbbfbff6870c6a72f868775`；
  Ray 2.46.0 的 `bin/ray start/status --help` 均成功，`python -m ray`
  不可用。
- 通过导入测试模块并直接调用 `run()`，没有执行其 `main()`，得到
  `PASS_PRIVATE_RAY_ZERO_GPU_CLI_FINAL_SUPERVISOR_STANDARD_LIBRARY_TESTS`。
  final runtime 文件字节和哈希在调用前后保持不变。

本轮未在目标 Linux 上运行 `run_linux_process_check()`，未 SSH、未启动 Ray、
GPU、模型或训练。

## 005–010 实现复核

- 005：组合 runtime、父 snapshot、zero-GPU snapshot 在 head `Popen` 前校验，
  并原子写入 validation；portable corruption test 确认 head spawn 为 0。
- 006：实现安装 SIGINT/SIGTERM handlers，`execute()` 捕获 `BaseException`，
  统一 cleanup 并在 `finally` 恢复 handler。当前仍缺真实 Linux signal delivery
  证据，见 012。
- 007：Linux monitor 记录 launcher descendants 的 PID/start/UID/parent chain，
  保留已见 identity，cleanup 后复核无遗留；portable tests 不能替代 Linux
  procfs 运行。
- 008：head/launcher 使用 supervisor-owned file-backed logs；250 KiB fake
  head 输出测试通过，无长生命周期 unread PIPE。
- 009：final runtime 在 head 前校验父和 zero-GPU frozen snapshot 的 hash 与
  manifest，且校验结果进入 record/result。
- 010：head/readiness 使用传入的目标环境 `bin/ray`，不再调用
  `python -m ray`；CLI help 选项与 2.46.0 入口证据一致。

这些是代码和 portable 测试结论，不是 Linux/procfs 或真实 Ray lifecycle
成功证据。

## 当前具体缺口

### `FINDING-A-FINAL-PHASE1-FROZEN-OUTPUT-011`

`FINAL_COMMAND.md` 的 Phase 1 调用脚本会进入 `main()`，而 `main()` 把结果写
回 `ROOT/test-results.json`。该文件属于 4 个冻结 runtime 文件，Phase 1 后
会使 Phase 2 的 pre-head hash gate 拒绝目录。

最小处理：加载模块但不执行 `main()`，直接调用
`run_linux_process_check()`，将返回 JSON 写到 Final 目录之外，并前后复核
runtime bytes/SHA 不变。

### `FINDING-A-FINAL-PHASE1-SIGNAL-COVERAGE-012`

`run_linux_process_check()` 只启动 fake CLI/launcher descendants，并在 timeout
cleanup 中向 descendants 发送信号；它没有向 supervisor 自身发送 SIGINT 或
SIGTERM。portable `run()` 里的 handler 测试只是直接调用
`_handle_interrupt(...)`，不是实际进程信号。

最小处理：另用 Linux-only harness 启动受控 supervisor/test process，向其真实
PID 发送 SIGINT、SIGTERM，收集最终 record/result、cleanup budget 和无遗留
进程证据。不能扩大当前 Phase 1 测试报告。

## 下一步边界

修正 Phase 1 调用后，可先运行 Linux/procfs fake-child 检查；其结果仍不能替代
真实 Ray 2.46.0 zero-GPU lifecycle。Phase 2 应继续使用已验证的 `bin/ray`、
空 CVD、0 GPU、3 CPU、120 秒主预算和共享 120 秒 cleanup。A mode 仍是独立的
两 GPU / 1800 秒分支，不能用 zero-GPU 证据替代。
