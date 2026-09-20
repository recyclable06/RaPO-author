# FINDING-A-FINAL-PHASE1-FROZEN-OUTPUT-011

状态：OPEN / BLOCKING

`FINAL_COMMAND.md` 的 Phase 1 直接执行：

```text
python -B "$Final/run_supervisor_tests.py" --linux-process-check
```

但 `run_supervisor_tests.py:main()` 无论默认套件还是
`--linux-process-check`，都会把结果写回 `ROOT/test-results.json`。该文件是
`HASHES_FINAL.json` 声明的 4 个 runtime 文件之一，也是
`MANIFEST_FINAL.json` 的 runtime entry。Phase 1 成功后会改变冻结 runtime
字节，Phase 2 的 pre-head hash gate 随即拒绝同一目录。

最小安全调用：使用 `python -B -c` 或独立一次性 launcher 加载
`run_supervisor_tests.py`（不执行 `main`），直接调用
`run_linux_process_check()`，把返回 JSON 写入 final 目录之外的新 output
目录；调用前后复核 `HASHES_FINAL.json` 声明文件的 bytes/SHA 不变。具体契约
见 `PHASE1_DIRECT_CALL.md`。
