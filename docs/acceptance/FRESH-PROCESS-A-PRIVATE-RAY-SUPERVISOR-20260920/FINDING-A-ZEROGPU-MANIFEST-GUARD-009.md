# FINDING-A-ZEROGPU-MANIFEST-GUARD-009

状态：OPEN

`zero_gpu_supervisor.py` 的 `_load_frozen_supervisor()` 只检查传入路径是
regular file 且不是 symlink，然后直接 import；它没有校验
`MANIFEST_ZEROGPU.json`/`HASHES_ZEROGPU.json`，也没有校验父
`HASHES_SUPERVISOR.json` 中冻结的 `f4914b...` identity。两个 manifest 目前
只是外部证据。修改 wrapper 或被传入的父 supervisor 后，命令仍可在
启动 Ray head 前继续执行。

最小修正：在 head 启动前以固定、受校验的 launcher 验证 zero-GPU wrapper
及父 supervisor 的 manifest/hash，并把实际校验结果写入 result/record；校验
失败必须 fail closed。标准库测试没有覆盖该路径。
