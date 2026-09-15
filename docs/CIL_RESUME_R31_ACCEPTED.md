# R3.1 CPU验收接收及GPU准备交接

2026-09-11。协调角色：核实独立验收、冻结下一步范围，不修改生产代码。

独立验收 `docs/acceptance/CIL-RESUME-CPU-R31-20260911/REPORT.md` 的裁决为 `PASS_READY_FOR_GPU`，仅限代码/CPU/static。42项测试一次通过、exit 0、stderr为空；目标源/test/manifest前后不变。协调者核对19个验收工件及3个目标文件，22/22 bytes/hash一致；验收HASHES.json自hash `7c595a7d3d5744307fab722750f75308843d04c1a36fb128f594bbc2ae1fc12c`。不重跑已通过且身份未变的CPU测试。

目标仍为8ac5工作树的R3.1（磁盘证据目录r3）：image `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3` / 102269 bytes；test `2bb64dccbce91409840d04344a30a58b76265ae77145ab33b4819a3613b4aadf` / 24215 bytes；r3/HASHES.json `ce058c0a2e9485ba027c2a6c7356f02ef99a3b0d1a283674d8a2e418f4a75271`。工作树默认HEAD不能替代这些未提交字节。

## 报告文字勘误

独立报告称协调冻结文档的manifest hash有65字符。协调者直接读取该文档，以正则提取实际值并计数，结果为64字符，且等于上述文件计算值。文档自身hash仍为验收输入记录的 `8c8296d484ec6b9d8d078de7ece3b3621ff5a2dd7285d26601c3faa0d01cef61`，说明并非验收后改过文字。这条报告提示不成立；保留独立报告原件及其HASHES，在此记录勘误，不改已冻结验收工件或生产代码。

## 下一步

复用当前项目的专用GPU诊断任务 `01a07606-d888-7a83-853f-83cf7c65ddf3`，先准备新的双进程恢复协议与诊断工件，并执行既有授权范围内的只读SSH/资源/空间/路径身份核实。本次准备不启动GPU训练/推理；协议和实际运行范围经协调者检查后再下发执行，属于内部交接，不要求用户重复批准同范围动作。

协议覆盖同栈两卡continuous保护、进程A Task1全部验证后发布marker并正常退出、进程B新runner/workers从Task2恢复、native完整状态/RNG/anchor来源/新loader起点、至少一个真实Task2更新。分开给state-exact与trajectory-close，轨迹容差须在运行前冻结；无法完整观测的状态不得用采样冒充全量通过。

沿用211/207选择同节点两张空闲3090、个人路径 `/mnt/conda/zhenglifeng/`、既有环境与模型/输入，严核CVD/Ray/物理UUID；旧checkpoint/outputs全部保留。空间预算按新方案实际checkpoint数量与既有约18.16GB/份计算，加余量，不能仅套用过去60GB阈值。无空闲卡时继续独立准备，不开定时监控；不新增安装、正式训练、下载大checkpoint或旧资产删除。

所有后续派发/回报保留目标任务已有模型：`send_message_to_thread`不传`model`或`thinking`。新任务创建才按原Astra High/Luna Max角色规则选模型。新协调任务为 `01a08faa-ba41-73b2-b3d3-e468521682e0`，不要再回报旧主任务。fresh_process_resume仍为not_accepted，paper-scale/AP/原实验身份均不由此关闭。
