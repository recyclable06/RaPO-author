# CIL 任务边界恢复第二轮整改

日期：2026-09-09。角色：协调/范围冻结。承接 [CIL_RESUME_DECISION.md](CIL_RESUME_DECISION.md)，不扩大 finding、算法或生产文件 allowlist。

独立验收 `docs/acceptance/CIL-RESUME-CPU-20260909/REPORT.md` 裁决 `FAIL_NOT_READY_FOR_GPU`；验收 HASHES.json 自 hash `f20fbcd2eaa200eeb2e6aea099d908ee7a2fb764e1525119d33e0216c94f24a6`，协调者重新核对11工件bytes/hash均一致，并读取具名生产调用确认五项缺口。31项CPU测试通过不替代生产协议完整性。验收中的 P1-gate 仅表示本恢复阶段阻断，不升级为论文算法 P1；主 finding 仍为 P2 operational gap。

## 修复范围

- `CIL-CPU-001`：提供明确的生产模式，在 Task 1 全部验证和 marker 发布成功后正常结束进程 A，不进入 Task 2。可以让显式发布选项直接表示发布后停止，或增加显式停止参数；必须有可复现的完整CLI组合，正常未启用边界模式仍按原 continuous 流程。退出前完成必要清理，输出不能虚称所有任务已完成。
- `CIL-CPU-002`：已发布/作为恢复输入的 boundary checkpoint 必须免于本次 pruning。保护逻辑不依赖 `resume_boundary` 非空，并覆盖删除父路径的情况。marker成功发布后保护其所需的工件；正常未发布目录的既有策略不扩展。`save_task_ckpt=none` 仍不能发布。
- `CIL-CPU-003`：publisher 与 validator 均要求真实 native full checkpoint 工件集合。必须绑定 `dataloader.pt`（仅保留 Task 1 状态，不将其游标加载给 Task 2），以及匹配 world-size/rank 的 actor/optimizer/extra-state和tracker；不能只判断任意一个optimizer文件存在。严格核对实际源码定义的文件布局，缺任一必要rank或文件 fail closed。
- `CIL-CPU-004`：模型身份必须绑定实际加载的本地权重、索引、必要config/tokenizer等完整内容，或能够验证这些内容对应的不可变身份。路径、任意 revision 字符串或几个metadata文件不够。采用流式hash避免将权重读入内存；本轮CPU测试用小型真实文件检验同路径同大小权重变化也会失败，不下载或安装模型。
- `CIL-CPU-005`：source identity 覆盖实际执行的完整 production 源码/配置范围，包含 native manager、worker、actor、sharding、loader、奖励/共享实现等。采用确定且可解释的源码文件集合/manifest，遗漏、增加、同路径内容变化可检测；排除可变日志、文档、缓存、输出等非生产工件。不得通过弱化 identity 合同解决。

以上只可修改 `examples/baselines/img_cls_cil/image_cls_cil_rapo.py` 和 `tests/author_fixes/test_cil_resume.py`。其他生产/配置/既有CTAN/COCO测试均只读。如必须修改共享实现，先回报必要符号与差额，不自行扩大。

## 保存与交付

在8ac5原整改分支继续；编辑前将首轮冻结 image/test 的原字节保存到新 `docs/remediation/CAND-RESUME-CIL-001/r2/inputs/` 并记录原hash。保留首轮报告、HASHES、SUPPLEMENT、patch/raw及独立验收原件，不覆盖历史证据。新实现、raw日志、差异、case mapping、前后hash和报告写r2目录。补丁至少包含本轮相对首轮的修改与相对5ced的finding累计修改，不将所有旧审计文档作为本轮代码差异。

新增有实际判别能力的CPU正负例覆盖上述五项及对应生产函数/控制流，保留既有断言强度。使用既有环境执行相称验证，直接保存stdout/stderr/exit/命令/环境；禁用bytecode并将临时测试目录放在本任务可写目录，避免先前验收的退出清理权限错误。成功后不无变化重复测试。

整改完成回报独立验收；验收不修复代码。GPU/SSH/训练继续等待代码/CPU重新通过。旧boundary/checkpoint、baseline tag、原始科学证据保持，不进行安装、commit/push或无关删除。
