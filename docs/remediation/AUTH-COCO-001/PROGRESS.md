# AUTH-COCO-001 整改进度

2026-09-06：COCO 提示/GT 冲突整改完成并自测，等待独立验收。

1. 在独立 `codex/auth-coco-001` 工作树确认 base HEAD 为 `da0c5ad521387bab75e74dc0bf0fd47dc13a3647`，作者 tag commit 为 `7fe2a73291f208ad9784a8333523825718881907`。
2. 从已验收 CTAN 工作树 `b7ae` 重算并核对 265 项清单及清单 hash `1c2365642756bb24c37e2e12fbd734e3d29d5d30863ce0dfe55a44cb7351c0ef`；精确复制 6 个 CTAN 生产文件、3 个 CTAN 测试文件和 CTAN 交接证据。最新版治理 `AGENTS.md` 单独复制并记录 hash，不计算法差分。
3. 在 COCO 修改前保存 [PRE_BATCH_HASHES.json](PRE_BATCH_HASHES.json)。随包 COCO 数据 hash、CTAN 继承差分、治理差分和本批差分分开记录。
4. 新增 `tests/author_fixes/test_coco.py`。第一次 AST 探测误识别 `.remote` 调用，输出保留在 `red-coco.*`；修正后正式红证据为 `red-confirmed.*`：未改 COCO 接线时 exit 1，静态和动态冲突各失败，reward 对照通过。
5. 按 allowlist 只修改 `image_det_cil_rapo.py` 的 `allowed_classes` 调用参数。生产差分见 `production.patch`。
6. 修正测试自身的 AST 属性读取后，COCO 最终测试 `green-final.*` 为 3 passed；与已验收 CTAN 22 项合并回归 `regression.*` 为 25 passed。
7. AST 语法、6 个 shell `bash -n`、`git diff --check`、白名单、数据和 CTAN 源快照保全均通过；原始命令输出与 hash 清单留在本目录。

当前结论仅为：**COCO 提示/GT 冲突整改完成并自测，等待独立验收。** 未提交、未推送，未更新根状态或原审计。
