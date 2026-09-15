# AUTH-CTAN-001 整改进度

2026-09-05：整改完成并自测，等待独立验收。

1. 恢复确认：隔离 worktree 起始干净，HEAD 为 da0c5ad521387bab75e74dc0bf0fd47dc13a3647；作者 tag 指向 7fe2a73291f208ad9784a8333523825718881907。创建 codex/auth-ctan-001 分支。分支写入共用 Git 元数据需要沙箱提升，自动审核已允许，无未决权限阻碍。
2. 阅读根规则、当前状态、资料地图、基线身份及原审计 REPORT/PROGRESS/BLOCKED/recheck/pipeline 报告。未把旧探针或旧工程当实现/测试依赖。
3. 在生产改动前创建 22 项定向测试。最初准备运行包含检测类名选择错误和预期张量 dtype 错误，原始输出保留在 red.txt；这两项工具问题已修正，不作为目标红测试依据。
4. 正式红测试 red-confirmed：19 failed / 3 passed，exit 1。失败全部是目标行为差异；测试及被测源文件 hash 已记录。
5. 最小生产修改：共享 normalizer 保留历史，首批初始化，增加必要历史校验；统一配置与 CLI/env 默认值。runner 原有状态传递、真实 JSON 读写及 hook 注入顺序足够，无需重复实现。
6. 正式绿测试 green：同一测试源文件 22 passed，exit 0；没有删测试、skip、mock 被测算法、弱化断言或放宽容差。仅运行 CPU 函数，没有模型训练/推理。
7. 语法、静态接线和范围保全另做检查。证据脚本准备时修正两个检查假设：作者 tag 与治理 HEAD 的差别包含既有 .gitignore/README；actor 实际从 model_inputs 读取 advantages。增加主工作树 PDF 对照后，补充 UTF-8 读取 BASELINE.json，避免 Windows 默认 GBK 解码失败；该准备阶段输出保留在 verification-preparation.*。均未因此修改生产代码。
8. 交接入口 HANDOFF.md；精确生产/测试差分、原始命令输出与 SHA256 清单均保存在本目录。现役根状态、原审计证据、AGENTS 未收口或宣称通过。

本任务停止在 CTAN 整改交接。由另一个独立任务验收，通过后才考虑 COCO。
