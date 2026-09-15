# AUTH-COCO-001 独立验收进度

2026-09-06：独立验收完成，限定裁决为 COCO 提示/GT 冲突的 CPU 局部代码行为通过。

1. 确认当前工作树为独立证据树 `C:/Users/Administrator/.codex/worktrees/0b06/RaPO-author`；未把它或 base HEAD 当作被验收实现。被验收实现固定为 `C:/Users/Administrator/.codex/worktrees/1449/RaPO-author` 的 `codex/auth-coco-001`。
2. 亲读目标 AGENTS、main 最新 AGENTS、AUTHOR_CODE_STATUS、PROJECT_MAP、BASELINE、COCO 交接/规格/进度/限制，以及原审计 REPORT/PROGRESS/BLOCKED、recheck 和 pipeline 的 COCO 部分。
3. 重新核对 COCO 38 项 hash、COCO 清单自身、CTAN 265 项清单及清单自身；起始/结束重算无漂移。
4. 独立比较目标与 CTAN 源：263 项逐字节相同；只剩 AGENTS 治理覆盖和本批 `allowed_classes` 一行差分；COCO 新增范围仅为本批交接材料和 `test_coco.py`。
5. 直接在目标 cwd 执行公开命令，独立保存命令/环境/退出码/stdout/stderr：25 passed。
6. 独立探针从真实调用点读取条件表达式，遍历六个 seed 的 45 个任务行；实跑未改 helper 的任务归属/过滤与合成 `answer_seg` 字段保全；真实 reward witness 通过。
7. Python AST、六个 shell `bash -n`、`git diff --check` 全部通过。

交付文件见同目录 `REPORT.md`、`BLOCKED.md` 及命令/探针/结构/hash 证据。未修改目标、CTAN 源、main 根目录、生产代码、公开测试或旧证据；未安装依赖、SSH/GPU、训练/推理、commit/push 或派生 agent。
