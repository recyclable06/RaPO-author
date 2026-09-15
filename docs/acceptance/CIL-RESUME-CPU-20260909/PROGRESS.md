# CAND-RESUME-CIL-001 独立验收进度

更新：2026-09-09。

## 当前状态

`FAIL_NOT_READY_FOR_GPU`；`fresh_process_resume=not_accepted`。

## 已完成

- 读取主目录 `AGENTS.md`、`CIL_RESUME_DECISION.md`、`TASK_COORDINATION.md` 和 2d90 审查的 finding/spec/allowlist/cases。
- 核对 8ac5 target branch/base HEAD、目标 remediation `HASHES.json`、5ced integration manifest、整改补充 `SUPPLEMENT_HASHES.json` 和实际 finding-only patch 身份。
- 建立独立 AST/static probe：CLI、marker atomic-last、source/model/input/config/plan 字段、fresh loader cursor、native restore→anchor copy 顺序、continuous `None` 分支和 pruning 逻辑。
- 使用 production serializer/validator 节点生成并读取小型真实 fixture；有效 fixture 和缺 checkpoint 负例通过，缺 `dataloader.pt` 的 manifest 被错误接受。
- 独立运行 31 项 CPU 回归：31 passed，exit 0；退出清理阶段的 pytest Windows `PermissionError` 已原样归档。
- 起止 hash 证明 production source、new test、target `HASHES.json` 和 5ced integration manifest 未变。

## 阻断项

- `CIL-CPU-001`：publish marker 后没有 Task 1 stop/return，不能形成 FRESH-RESUME-01 的正常退出进程 A。
- `CIL-CPU-002`：publish 进程未设置 `resume_boundary`，默认 checkpoint pruning 可能删除 Task 1 boundary checkpoint。
- `CIL-CPU-003`：validator/publisher 未强制 `dataloader.pt` 出现在完整 native manifest。
- `CIL-CPU-004`：model identity 未强制 immutable revision 或完整 model content/weight manifest。
- `CIL-CPU-005`：source identity 只覆盖 6 个选定文件，不能作为完整 production source identity。

## Case coverage

- CPU-RESUME-01：pass。
- CPU-RESUME-02：model shard delete/append pass；其他 required artifact 类型未全部独立变异。
- CPU-RESUME-03：cursor/model-only pass；step/tracker/EMA/RNG/identity 负例未全部覆盖。
- CPU-RESUME-04：部分 static pass，但 publish stop/pruning gate fail。
- REG-RESUME-01：31 项组合运行 pass。
- REG-RESUME-02、FRESH-RESUME-01/02/03、STATE-EXACT-01、TRAJECTORY-CLOSE-01：留给修复后的专用 GPU/跨进程验收。

## 下一步

整改任务需先修复并重新归档 CIL-CPU-001～005，重新通过独立 CPU/static gate；在此之前不派 GPU fresh-process 运行，不关闭 `CAND-RESUME-CIL-001`，不改写既有 continuous runtime 判定。

