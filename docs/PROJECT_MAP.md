# 项目资料地图

更新：2026-09-05。本仓库只承载作者代码基线、基于该基线的后续工作和对应审计证据。

| 路径 | 作用 | 边界 |
|---|---|---|
| `examples/`, `verl/`, `scripts/`, `data/` | 作者实现与标准入口 | 基线身份由 `author-drop-20260904` 冻结；后续修改必须可与其比较 |
| `references/2605.09640v1.pdf` | 论文原件 | SHA256见 `BASELINE.json` |
| `docs/AUTHOR_CODE_STATUS.md` | 当前状态入口 | P1、已接通主链、pending和下一放行点 |
| `docs/audit/2026-09-04-author-intake/` | 详细审计证据 | 报告、探针、原始输出、hash和待作者问题 |
| `docs/BASELINE.json` | 仓库基线身份 | 作者drop、论文、旧仓库和源ZIP身份 |
| `docs/LEGACY_REFERENCE.md` | 旧工程指针 | 只引用，不把旧实现作为本仓库依赖 |
| `C:/Users/Administrator/Desktop/RaPO` | 旧个人Visual-RFT/DeepSpeed仓库 | 历史实现、实验与整改记录；不作为作者实现规格或运行入口 |

数据集构建输出、模型、checkpoint、日志和缓存不进入Git。正式运行目录由后续批准目标冻结，不复用旧工程artifact。
