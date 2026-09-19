# Private Ray supervisor and zero-GPU delta — independent narrow review

日期：2026-09-20

## 结论

组合结论仍为 `NOT_READY_FOR_BOUNDED_ZERO_GPU`。

zero-GPU sibling 已独立确认并闭合原 command contract 差额：head 使用
`CUDA_VISIBLE_DEVICES=''`、`--num-gpus=0`、`--num-cpus=3`，主生命周期命令
固定 120 秒，cleanup 命令固定 120 秒共享上限，Ray temp 使用一次性短的
`/tmp/zlf-s20a`，并在启动 cluster 前安排 `python -m ray` 的只读 help/version
preflight。但独立的目标环境入口证据已经显示该调用方式不可用：Ray 2.46.0
环境没有 `ray.__main__`，`python -m ray start/status --help` 都 exit 1；同一
环境的 `bin/ray start/status --help` 才 exit 0。因此当前命令在实际 head
启动前即被 CLI 入口阻断，没有执行真实 Ray CLI 或 Linux lifecycle。

父 supervisor 的以下缺口仍直接适用于 zero-GPU wrapper：

- 父 supervisor 未在启动 head 前校验自身 manifest/hash；
- supervisor 自身没有 SIGTERM/SIGINT/finally cleanup 保证；
- supervisor 超时只杀 launcher session，R2 production child 的独立
  session 可能逃逸；
- Ray head 的 stdout/stderr 使用未持续读取的 PIPE。

此外，zero-GPU wrapper 自己也只按路径加载父 supervisor，没有在 head 启动
前校验 zero-GPU manifest 或冻结父文件 hash。真实 `python -m ray` 2.46
CLI、Linux `/proc`、normal/failed/timeout/interrupted teardown 和 120 秒
实际 lifecycle 证据仍缺失，因此不能放行。

## 独立确认的身份与测试

- 父 supervisor supplement：10 文件、65,323 bytes 全匹配；
  `HASHES_SUPERVISOR.json` self SHA 为
  `f4914b91d91b1b31873457e195805762c930b89c656fe09115d25b9502ee98d9`，
  `SUPERVISOR_MANIFEST.json` SHA 为
  `cac9d08d0c3b68d47218183ca21d61cb944d647d15d15746ec01ed350a84c119`。
- zero-GPU sibling：9 个声明文件、34,234 bytes 全匹配；
  `HASHES_ZEROGPU.json` self SHA 为
  `3635a3afd975d35770a1e9c41841da62fe3051be37ff95d39ffeeb5d19e3a003`，
  `MANIFEST_ZEROGPU.json` SHA 为
  `eae681218644bd759152658d425777b7cc3c6e80869a681e1415b01da104c4ed`。
- 目标主机的独立只读 CLI preflight：30 文件、16,933 bytes 全匹配；
  `HASHES.json` self SHA 为
  `9c8bc7cac8c7c85fd795ab860f8a357c1e4c65461cbbfbff6870c6a72f868775`。
  该证据记录 Python 3.11.6 / Ray 2.46.0、`python -m ray` 两个 help 均
  exit 1（缺少 `ray.__main__`），而同环境 `bin/ray` 两个 help 均 exit 0。
- 父标准库测试独立通过：`PASS_PRIVATE_RAY_SUPERVISOR_STANDARD_LIBRARY_TESTS`。
- zero-GPU 标准库测试独立通过：
  `PASS_PRIVATE_RAY_ZERO_GPU_SUPERVISOR_STANDARD_LIBRARY_TESTS`。
- 两组测试均使用 fake child/head、注入 readiness，并以
  `strict_linux=False` 运行；zero-GPU lifecycle 测试还通过 `head_command`
  override 绕过了真实 head builder。因此它们不能证明真实 `python -m ray`
  argv、Linux procfs 身份或真实 Ray 清理。

静态上，父实现确实包含 Linux `/proc` 的 PID/start/session/PGID/UID/argv
identity、record 原子 `os.replace()` 与 read-back、真实模式的
`python -m ray start/status` 接线；zero-GPU wrapper 在 head 前设置资源与
环境、把 readiness 纳入主 deadline，并从共享 cleanup budget 中扣除
launcher cleanup 时间。这些是实现存在性，不是实机成功证据。

## 开放缺口

### `FINDING-A-SUPERVISOR-MANIFEST-GUARD-005`

父 `private_ray_supervisor.py` 与 `SUPERVISOR_COMMAND.md` 不引用并校验
`SUPERVISOR_MANIFEST.json`/`HASHES_SUPERVISOR.json`。修改父 supervisor 后
仍可直接启动 head。

最小修正：在创建 Ray head 之前由受校验的启动器校验父 runtime manifest/hash，
并把校验结果写入 record/result；失败必须 fail closed。

### `FINDING-A-SUPERVISOR-INTERRUPT-CLEANUP-006`

父 `execute()` 只有 `except Exception`，没有 SIGTERM/SIGINT handler 或
`finally`。SIGTERM 默认终止，SIGINT 的 `KeyboardInterrupt` 也不会进入该
分支，可能留下 head、后代和 temp root。

最小修正：将 SIGTERM/SIGINT 转为受控退出，并让同一幂等、bounded cleanup
路径覆盖所有异常退出及最终 record。

### `FINDING-A-SUPERVISOR-LAUNCHER-DESCENDANT-007`

父 supervisor 为 launcher 建立新 session，R2 `run_v9.py` 又为 production
child 建立新 session；supervisor 的 discovery 只覆盖 Ray temp-root/head
ancestor tree。supervisor-level timeout 先发生时，production session 可能
在 launcher 被杀后继续存在。

最小修正：让 supervisor 拥有并验证 launcher→production 的完整 session/tree，
并在同一 cleanup budget 内按 PID/start/UID 清理及复核所有后代。

### `FINDING-A-SUPERVISOR-HEAD-PIPE-008`

父 `_start_head()` 将长生命周期 head 的 stdout/stderr 接到 PIPE，readiness
期间没有 reader；日志只在 cleanup 后以 `communicate(timeout=0)` 读取，可能
阻塞 head 或得到不完整日志。

最小修正：使用 supervisor-owned file-backed logs 或持续 drain reader，并记录
日志 drain 完整性。

### `FINDING-A-ZEROGPU-MANIFEST-GUARD-009`

zero-GPU wrapper 的 `_load_frozen_supervisor()` 只检查路径是 regular file 且
不是 symlink，然后直接 import；它不校验 `MANIFEST_ZEROGPU.json`、
`HASHES_ZEROGPU.json` 或冻结父 hash `f4914b...`。两个 manifest 只是外部
证据，不能阻止被替换的 wrapper/父 supervisor 在 head 前运行。

最小修正：在 head 启动前校验 zero-GPU wrapper 及父 supervisor 的固定
manifest/hash，把结果写入 record/result，失败即停止。

### `FINDING-A-ZEROGPU-CLI-ENTRYPOINT-010`

目标环境的只读 preflight 已证明 Ray 2.46.0 没有 `ray.__main__`：
`python -m ray start/status --help` 均 exit 1，stderr 为
`No module named ray.__main__; 'ray' is a package and cannot be directly executed`。
只有同环境的 `bin/ray start/status --help` exit 0。当前父 supervisor 和
zero-GPU command 都硬编码 `python_executable -m ray`，所以真实 head/readiness
尚未有可用入口。

最小修正：统一改用已验证的同环境 `bin/ray`（或等价可验证 CLI executable）
执行 head、readiness 和 help preflight，并记录 executable、shebang、Ray
version 与实际 argv；修正后重新执行 bounded zero-GPU lifecycle。

## zero-GPU 与 A-mode 边界

zero-GPU delta 已将零 GPU 的命令资源和短路径约束写入
`ZERO_GPU_COMMAND.md`；其命令显式传入 120 秒主预算和 120 秒共享 cleanup
预算。wrapper 本身允许 CLI 参数被调用者覆盖，因此“bounded”目前依赖按该
冻结命令调用，而不是代码内的 120 秒上限。A-mode 仍是独立的两 GPU、1800 秒
production 分支，不能用 zero-GPU fake/准备证据替代 A 的真实验证。

本机 `C:\Program Files\Python313\python.exe` 没有 `ray` module；本轮未安装
依赖、未重复 SSH、未启动 Ray/GPU、未加载模型、未训练、未启动 production
launcher。目标主机的只读 CLI preflight 已执行但明确失败于 `python -m ray`
入口；修正为已验证的 `bin/ray` 后，仍需执行真实 private zero-GPU lifecycle，
并保存 procfs identity、readiness、record、normal/failed/timeout/interrupted
teardown 和无遗留进程证据。
