# 项目资料地图

更新：2026-09-14。当前根目录包含作者代码及已验收局部修订；原作者版本由 `author-drop-20260904` 标签保留。

| 路径 | 用途 |
|---|---|
| [README.md](../README.md) | 仓库入口与作者提供的使用说明 |
| [AUTHOR_CODE_STATUS.md](AUTHOR_CODE_STATUS.md) | 当前实现、实际验证范围和待完成事项 |
| [REPRODUCTION_NEXT_STEPS.md](REPRODUCTION_NEXT_STEPS.md) | 从当前诊断到正式实验的推进顺序 |
| [INTEGRATION_HANDOFF.md](INTEGRATION_HANDOFF.md)、[INTEGRATION_HASHES.json](INTEGRATION_HASHES.json) | 根目录整合来源与代码/测试逐字节身份 |
| `examples/`、`verl/`、`scripts/`、`data/` | 训练、奖励、数据构建和标准入口；实际数据说明见[data/DATASET.md](../data/DATASET.md) |
| `tests/author_fixes/` | CTAN、COCO和任务边界恢复的针对性代码测试 |
| [references/2605.09640v1.pdf](../references/2605.09640v1.pdf) | 唯一论文副本，hash见BASELINE |
| [BASELINE.json](BASELINE.json) | 作者drop、论文和原始来源身份 |
| `docs/audit/` | 不改写的作者基线审计与任务边界恢复审查 |
| `docs/remediation/`、`docs/acceptance/` | 已复制到根目录的整改与独立验收证据 |
| [FRESH_PROCESS_PROTOCOL_REVIEW.md](FRESH_PROCESS_PROTOCOL_REVIEW.md) | GPU恢复诊断各版本的协调裁决与勘误 |
| [TASK_COORDINATION.md](TASK_COORDINATION.md) | 本地任务/工作树索引，含机器相关路径，不是可移植运行配置 |
| [LEGACY_REFERENCE.md](LEGACY_REFERENCE.md) | 旧工程只读参考边界，不构成当前实现依赖 |

服务器上的数据、模型、checkpoint和运行缓存留在原位置。各工作树中的完整GPU诊断包及运行证据仍按其冻结路径保留；不为根目录上传移动或删除工作树，不把它们的默认HEAD当作已验收源码。

运行环境导出文件是作者提供的材料。当前验证使用的环境子集及差异应结合具体报告阅读，不宣称完整复刻论文环境。
