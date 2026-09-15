# CIL 任务边界恢复第三轮整改

2026-09-09，协调决定。范围沿用 CIL_RESUME_DECISION.md 与 CIL_RESUME_R2_DECISION.md，仅原image生产文件与test_cil_resume.py；不扩大共享代码或科研协议。

R2独立验收仍为 FAIL_NOT_READY_FOR_GPU。验收目录 `docs/acceptance/CIL-RESUME-CPU-R2-20260909/`，HASHES.json 自hash `d65d544bd4f734cb68bf99baf036b4dfc3426df5e6a57ffaf99add5c708c8c6f`，12工件协调者核对一致。CIL-CPU-003已通过；CIL-CPU-001的stop分支被002实际pruning异常阻断。按独立生产代码复现修复剩余三项：

1. **CIL-CPU-002**：三处常规pruning遇到protected boundary父/子路径时跳过删除并继续流程，不能把正常保留当成异常。仍拒绝非法恢复输入/输出重叠。测试实际生产pruning控制流：Task1多checkpoint+默认latest可到达正常stop；publish后不stop的Task2也能完成；两种情形boundary内容不变，不受保护的旧checkpoint按原策略处理。这是运行逻辑中的跳过删除，不是跳过测试或被测主体。
2. **CIL-CPU-004**：本finding的边界发布/恢复限定为已经存在、实际加载且完整content manifest绑定的本地模型和tokenizer/processor路径。拒绝远端ID，即使带40-hex revision；不在本轮新增下载或共享loader的revision传递框架。正常未启用boundary的旧远端模型工作流仍保持原语义。local actor/base reference与实际tokenizer路径必须对应，不可只hash未被实际消费的路径。原有本地完整hash正例保留，新增remote/伪revision拒绝及独立tokenizer路径变化负例。
3. **CIL-CPU-005**：source identity完整覆盖本项目生产Python与运行配置，至少包含完整 `verl` 树（含models及包初始化）、image/CIL相关examples、动态reward及其项目内依赖。可使用确定的完整 `verl`/`examples` Python树及已解析配置manifest，排除docs/log/cache/output。配置可指定的动态reward文件还须绑定实际所读文件内容，不能仅hash默认cls.py或配置中的路径字符串。没有必要追逐一份不断补文件名的固定短名单；对增加、删除、同路径内容改变有可执行检验。

整改前将R2 image/test原字节另存 `8ac5/docs/remediation/CAND-RESUME-CIL-001/r3/inputs/` 并hash。R1/R2代码副本、验收、报告、raw、manifest、patch全部保留。新r3证据包括实际相对R2和5ced patch、逐项case映射、前后hash与一次完整相称CPU测试raw。已有full-rank/checkpoint/EMA/RNG/restore-before-anchor与continuous行为必须保留。

先形成通过真实失败路径的修复与负例，再送独立验收；不以旧probe的字符串/AST存在性PASS替代实际控制流。继续使用既有环境，无GPU/SSH/安装/训练/commit/push或旧资产删除。完成回报由协调者复核，再派独立验收。
