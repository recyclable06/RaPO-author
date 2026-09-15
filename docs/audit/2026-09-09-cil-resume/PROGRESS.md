# CIL 任务边界恢复审查进度

更新：2026-09-09。角色：独立代码审查；未修改生产源码，未执行 SSH/GPU/安装/训练/推理，未下载 checkpoint 权重。

## 已完成

- 锁定目标整合树 `C:/Users/Administrator/.codex/worktrees/5ced/RaPO-author`、branch `codex/integrate-accepted-fixes`、HEAD `da0c5ad...`、author baseline `7fe2a73...`。
- 阅读主目录与目标树 `AGENTS.md`、`docs/PROJECT_MAP.md`、`docs/AUTHOR_CODE_STATUS.md`、`docs/INTEGRATION_HANDOFF.md`、`docs/INTEGRATION_HASHES.json`；确认整合台账自身 hash 为 `6514f4dca401ffc805ae57031d1926f742e531ce0fbb981448315538ade8b0b1`。
- 阅读当前 image CIL `main/_run_cil/run_task/reinit/_load_checkpoint`、base CIL loader、generic trainer、FSDP checkpoint manager、worker 和 vLLM sharding manager；静态确认 normal Task2 `load_checkpoint_path=None` 是同进程设计。
- 复核 14c8 static result 与 2026-09-09 continuous GPU/independent acceptance：同进程连续 Task1→Task2 通过限定范围；fresh-process entry、anchor/EMA/cursor/config/RNG 原子协议仍未证明。
- 确认 Task 1 fit 内部 checkpoint 早于 `run_task` extra validation；extra validation 会经过 vLLM generation，当前 gen RNG 不在 native checkpoint；EMA sidecar/tracker 非原子且缺完整 manifest。
- 形成 `confirmed operational gap / P2` 裁决、单一 finding、图像侧最小生产 allowlist、failclosed spec 和 CPU/2GPU/fresh-process acceptance cases。

## 当前结论

`CAND-RESUME-CIL-001` 仍开放。它阻断 fresh-process exact-resume 声明，不阻断 continuous runtime 或将其升级为论文 P1。Task 2 的新 dataloader 必须按原语义构建并从 cursor 0 开始，不能机械加载 Task 1 exhausted cursor；anchor 可由恢复 actor 经生产 copy 重建，避免重复完整权重。

## 尚未完成

- 未实现 `--resume_task_boundary` 或完成 marker；未运行真正两个 OS process 的 Task1→Task2。
- 未取得服务器/GPU 侧 fresh-process 运行证据；不得用已有同进程运行根作为替代。
- 未验证具体 model revision、完整输入 manifest 或真实 paper-scale/AP/原始实验身份；这些不在本 finding 的扩大范围。

## 下一动作

由独立整改任务仅按 `ALLOWLIST.md` 修改 image CIL 入口和新增协议测试；整改后由独立 acceptance 任务执行 `ACCEPTANCE_CASES.md`。若实现要求修改共享 trainer/checkpoint/sharding 文件，先提交具体影响和 allowlist 差异，不自动扩大范围。
