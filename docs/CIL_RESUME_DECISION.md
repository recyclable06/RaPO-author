# CIL Task 1→Task 2 恢复整改冻结决定

日期：2026-09-09。角色：协调/范围冻结；不修改生产代码。按用户项目内持续授权，批准独立整改 `CAND-RESUME-CIL-001`，严重度为 P2 operational gap；不是新的论文算法 P1。

## 已核实输入

- 独立审查任务：`01a08575-504b-7492-85ab-2fef30c1f5a9`，工作树 `C:/Users/Administrator/.codex/worktrees/2d90/RaPO-author`。
- 审查目录：上述树 `docs/audit/2026-09-09-cil-resume/`；`HASHES.json` SHA256 `6aa2a18152e293dc84c8d90dc60f8cf5e39917562b6dc5a87c630bdee8bcdcbb`。
- 协调者重新核对其中 12 个目标源码、4 个既有测试、6 个引用证据文件、6 个审查文档：28/28 SHA256 一致。该核对是身份检查，不是重新执行旧 GPU 实验。
- 待整改源码是 `C:/Users/Administrator/.codex/worktrees/5ced/RaPO-author` 的未提交整合快照，不能以新工作树默认 HEAD 替代；整合 manifest SHA256 `6514f4dca401ffc805ae57031d1926f742e531ce0fbb981448315538ade8b0b1`。

## 批准范围与澄清

遵循审查目录的 FINDING、SPEC_DRAFT、ALLOWLIST、ACCEPTANCE_CASES，并以本决定澄清范围：

1. 唯一生产修改文件为 `examples/baselines/img_cls_cil/image_cls_cil_rapo.py`；唯一新增测试为 `tests/author_fixes/test_cil_resume.py`。允许另写本整改目录的说明、差异和证据。开始时允许将 5ced 的已验收生产/测试字节原样置入新工作树，单独记录为整合快照初始化，不能把它当成本 finding 的新增修改。
2. 仅支持 image CIL 完成 Task 1 后的 fresh-process Task 2 入口。`ACCEPTANCE_CASES.md` 中 FRESH-RESUME-04 要求 Task 2 再发布 task2-complete，与最小范围不一致：本轮改为验证 Task 2 正常完成/保存，且原 Task 1 boundary 不变；不要求 Task 3 恢复协议或 task2-complete marker。其余关闭条件保持。
3. CPU-RESUME-01 的测试工件可使用小型真实文件 fixture，并由生产 serializer/validator 处理；原生大模型 checkpoint 不可能由 CPU metadata helper 生成。此类 fixture 只验证协议，不能当作训练恢复证据。
4. 正常 continuous 分支保持内存续跑语义。新增边界发布必须有显式启用方式，使用 `save_model_only=false` 才能发布；未启用时不能让原有默认 model-only 工作流报错。恢复入口缺状态/错身份必须 fail closed。
5. Task 1 marker 在所有 post-training validation 后发布，完整绑定 native checkpoint、EMA、driver/per-rank vLLM RNG、计划、输入、配置和模型身份。新进程 native restore 必须早于 actor→anchor copy；Task 2 loader 从新任务 cursor 0 开始。
6. 不改论文算法、共享 trainer/checkpoint/sharding 或检测/视频路径。发现范围内无法实现时回报具体符号和必要 allowlist 差额，由协调者判断；不要求用户重复批准已授权的常规局部实施。

## 交付与后续

整改任务先完成实现、CPU 协议正负例、既有 25 项 CTAN/COCO 回归、相对 5ced 与 author-drop 双重差异和前后 hash。允许使用既有本地运行环境，不授权新安装、SSH/GPU、训练/推理、commit/push、旧数据删除。

整改完成后由独立验收检查冻结快照，再交专用 GPU 任务准备并执行既有授权范围内的同栈两卡 continuous 与两个 OS process 对照。GPU 运行前冻结具体命令、输出根、输入身份、状态字段与轨迹容差；整改者不自签验收。只有真实跨进程证据通过才关闭 finding。
