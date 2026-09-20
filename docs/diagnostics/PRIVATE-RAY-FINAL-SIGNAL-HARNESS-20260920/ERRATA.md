# Errata — runtime hash transcription

日期：2026-09-20

已冻结的外置信号 harness 文件保持原样。本说明只记录三处文档元数据转录错误；不把原文件表述为已修正，也不重新生成整套 harness。

以下三个位置把 FINAL runtime `HASHES_FINAL.json` 的 SHA-256 少写了一个 `a`：

- `MANIFEST.json` 的 `source_runtime_identity.runtime_hashes_sha256`
- `RUN_METADATA.json` 的 `identity.runtime_hashes_sha256`
- `SIGNAL_HARNESS_COMMAND.md` 中的 FINAL runtime identity

错误转录为：

```text
3b9f055da492741754f80b63e2255716e118fe546bca429267c542877136f67
```

正确的完整 64 位 SHA-256 为：

```text
3b9f055da492741754f80b63e2255716e118fea546bca429267c542877136f67
```

`run_signal_harness.py` 中实际使用的 `RUNTIME_HASHES_SHA256` 常量已经是上述正确值，代码未受该文档转录错误影响。FINAL runtime、父/兄弟 snapshot、`HASHES.json` 及本地静态测试结果均未修改；真实 Linux signal harness 仍未运行。
