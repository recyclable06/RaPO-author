# Fresh-process GPU协议首轮协调审读

2026-09-11。R3.1生产代码CPU gate仍为PASS_READY_FOR_GPU；本文件评审的是诊断准备材料，不重新裁决或修改生产代码。

准备目录：`C:/Users/Administrator/.codex/worktrees/14c8/RaPO-author/docs/diagnostics/fresh-process-resume-20260911/`，HASHES.json自hash `78b5491a51f8e90d639e5b19786e35c953133d90901039ef258b2d3ef5ec9368`。协调者19文件bytes/hash核对一致。

裁决：**NEEDS_PROTOCOL_REVISION，不执行GPU**。16项validate-config和AST parse不证明生产命令可执行或state-exact可判定。

1. COMMANDS.md只设PYTHONPATH/WANDB等，没有强制显式两卡CVD/UUID/Ray实际映射检查。PPO的n_gpus_per_node=2不能代替物理卡隔离；未指定两张现场空闲卡必须在模型构造前终止。现场211仅一张卡空闲、207 nvidia-smi超时；资源事实需在未来执行前再查。
2. 命令使用`--config PATH`，但生产剩余参数经OmegaConf.from_cli解析并读取`config`，应按实际dotlist接口验证，如`config=PATH`。必须通过真实解析逻辑验证完整argv和配置，不只检查JSON自声明；C/A/B有效配置与identity需对账。COMMANDS对fresh loader与native restore顺序的文字也应和源码一致。
3. 协议承认缺少pre-first-update完整native fingerprint，却未实现runtime sidecar生产者。判定器仅检查sidecar键存在和固定phase_order就可state_exact=true，空值/伪值也可能通过，且缺anchor本身的比较。必须真正捕获native checkpoint对应的完整状态，并与恢复后/首次更新前的实际值逐项比较；仅有字段名、boolean和同一个marker fingerprint不构成证据。允许诊断侧只读before/after wrapper，原生产方法恰好调用一次、无替换算法/状态；不改冻结生产文件，不用采样替代完整状态。
4. trajectory窗口声明2步，但judge只要求至少1步后zip，可能缩短窗口仍通过；retention字段缺失被条件跳过。必须要求确切窗口和必需观测，不足明确未证明/失败；检查实际group内奖励差异及真实参数更新，不能以全batch min/max和日志含grad_norm替代。
5. A/B需独立核对runner/所有rank worker身份、训练前后boundary根不变、模型/输入/配置身份以及完整rank与RNG集合。OS父进程树不一定覆盖Ray独立派生worker，不能仅据root PID不同声称新worker组。

下一版写原目录新的`v2/`，保留首轮原件；补实际launch/observer/judge、CPU可做的正负判定用例、完整state观测schema/比较方法、原始离线结果和新HASHES。缺失/空/伪fingerprint、丢rank、1步冒充2步、缺retention必须不能通过。CPU小fixture只测试诊断判定器，不作为GPU恢复证据。

轨迹阈值在GPU结果前冻结。首轮0.25/0.5/0.5目前只属于准备草案，下一版应说明其量纲、指标范围与判别能力，不能看到GPU结果后调整。空间预算按实际checkpoint高水位核算；88GB当前估计保留可审查，不能删除旧数据腾空间。

新协调任务为`01a08faa-ba41-73b2-b3d3-e468521682e0`。续派/回报不传model/thinking，完成回报即冻结点，不覆盖同名历史raw/manifest。

## v2 接收与独立审查

2026-09-11，v2 准备任务回报完成。目录为上述准备目录下 `v2/`，`HASHES_V2.json` 自排除 SHA256 为 `b71694e292d7e0d8c059d3ffe06f0194cf9bac389386254e776a609bde70beac`，16 文件、145020 bytes；协调者逐项核对全部一致。v1 的19文件及原清单仍一致，R3.1 生产文件、测试及 r3 清单也均保持冻结身份。

状态为 **FROZEN_PENDING_INDEPENDENT_REVIEW**，不等于 GPU 可运行或恢复验收通过。v2 新增实际启动器、参数验证器、GPU/Ray 前置检查、运行观测器和判定器；自测记录只证明准备者的判定器 fixture 结果，不证明生产调用线路或真实恢复。

已续派独立验收任务 `01a074b8-560b-7be1-8874-1f55a7e1ae10`，工具确认运行中。只读核实实际生产接口、完整状态观测的语义及副作用、两步窗口、进程释放和边界保护；不得修准备包、重跑已通过的42项生产CPU测试或使用GPU。独立输出目录为 `docs/acceptance/FRESH-PROCESS-PROTOCOL-V2-20260911/`。收到独立结论后决定有限GPU执行或最小返修，沿用既有两卡与个人远端目录授权；当前没有启动GPU。

## v2 独立结论与 v3 返修边界

独立结论为 **NEEDS_PROTOCOL_REVISION**。验收 [REPORT.md](acceptance/FRESH-PROCESS-PROTOCOL-V2-20260911/REPORT.md) 及其自排除清单 SHA256 `6ff164f0b52b23ff9cb77c4e8a994f03354c57cf39f90aba3375e856e47afef3` 已接收；协调者核对11工件bytes/hash全部一致，并核对对应准备源码。下列问题属于诊断准备门，不改变生产 R3.1 CPU 通过结论，也不新增论文算法 P1 finding。

- FPP-V2-001：命令部署到唯一新根，PPO prompt/reward 路径却固定在旧根，启动器没有重绑定。
- FPP-V2-002：模型、tokenizer和输入仅记录实际内容，没有与预先冻结的预期内容清单比较；缺输入清单装载。
- FPP-V2-003：根进程安装与PYTHONPATH传播不足以保证实际Ray runner/worker安装观测器；judge仅要求某条install事件，缺每个实际role/rank进程的证据。
- FPP-V2-004：raw奖励变化可通过，但effective奖励恒定的反例仍通过。协调决定本次有效更新诊断同时要求真实组内effective奖励存在非零变化，按实际样本重算差异并与sidecar字段对账；保留非零advantages与actor更新证据，不改变训练奖励或为通过而选取结果。

返修仅在准备目录新增同级 `v3/`，保留v1/v2及全部验收原件，禁止改8ac5生产代码/测试。按实际source root生成配置并在运行前校验prompt/reward文件及内容；绑定预先冻结的完整model/tokenizer/input内容清单与class order，缺失或不符即失败。清单可以复用已核对的旧证据；缺失项允许对既有指定远端文件做只读哈希盘点，不能将每次运行现场值自动登记成expected。

实现可靠child bootstrap，并要求实际root/runner/各rank在关键事件前提供安装、模块身份、PID/start及role/rank对应证据。可在既有环境做必要的无模型、零GPU Ray启动冒烟，使用新个人临时根与隔离实例、有限进程/CPU资源，只证明bootstrap/导入/事件链；不得连用或停止他人的Ray、构造模型、申请GPU、训练、推理、安装或删除旧资产。这项针对性诊断不能充当完整恢复证据。

新版本补针对上述缺口的正负验证与原始结果、前后身份和HASHES；不重复未改动的生产42项测试。回报即冻结，再交独立验收；目前不执行C/A/B GPU实验。

## v3 接收与未完成的传播验证

v3 已回报 `READY_FOR_INDEPENDENT_REVIEW`。协调者核对 `v3/HASHES_V3.json` 自排除 SHA256 `85ecc63edfac12d151ec83c391a70eee932f610de128b14208c9c308bf27d6bd`、24文件183476 bytes，全部一致。该状态仅表示提交审查；准备者“已关闭”四项的表述不作为独立结论。

`SMOKE_RESULTS_V3.json` 实际记录本地缺少Ray，传播验证尚未完成。协调者源码审读发现 `child_bootstrap_v3.bootstrap` 只计算源码文件身份并写 `installed=True`，没有安装observer；sitecustomize只调用此函数。运行观测器的child install记录又从已有wrapper内触发，尚不足以证明wrapper真的进入实际Ray子进程。原smoke的自定义actor手工调用bootstrap，不能代替对真实production类/方法和checkpoint manager的核查。

已安排两项不修改冻结v3的独立工作：验收任务只读复核v3配置/身份/奖励判定及真实hook传播机制，输出 `docs/acceptance/FRESH-PROCESS-PROTOCOL-V3-20260911/`；专用诊断任务在已授权的既有远端环境补充无模型、零GPU、隔离Ray的运行核查，输出14c8准备目录下同级 `v3-bootstrap-supplement/`。后者应分别报告原smoke传播和实际child函数对象是否安装wrapper，缺失时记录 `NOT_INSTALLED`，不得临时安装绕过问题或把日志字段当证明。保持v1/v2/v3及生产/测试原件不变，收到补证后按其冻结身份增量复核。目前仍不启动GPU实验。

## v3 独立结论与下一版范围

独立 [v3 REPORT.md](acceptance/FRESH-PROCESS-PROTOCOL-V3-20260911/REPORT.md) 结论 **NEEDS_REVISION**；自排除验收清单 SHA256 `f2e04b79e53fe385280c1e1f7eb43b9b6bb2f34c5f9176ae0b12c521af102959`，6工件37380 bytes，协调者逐项核对一致。协调者还核对了命令模板、验证函数签名/调用以及bootstrap源码，接受以下限定问题：

1. FPP-V3-001：COMMANDS 中 run_leg 漏传 required `--cil-cfg`，正常命令退出2。
2. FPP-V3-002：`_verify_frozen_content` 使用未定义的 `known`，调用者没有传入，正常路径发生NameError；验收探针注入known所得正例仅用于定位，不是生产通过证据。
3. FPP-V3-003：实际child wrapper安装未得到保证，且没有wrapper report的hash-only child event可通过安装门。根进程patch的部分序列化可能性不等于完整checkpoint/worker hooks已传播。
4. FPP-V3-004：bootstrap和observer各自的序号写进同一PID事件文件，实际出现 `[1,1,2]`。下一版统一为进程内共享事件序号并明确writer/进程身份，judge校验重复、缺必要安装记录及关键先后关系；跨进程不按本地序号建立全局次序。

在途v3补证继续按原范围完成、保全并冻结；不因审查失败重写它或伪造安装。之后专用诊断任务可在同级 `v4/` 修复以上问题，保留所有旧版及其原始证据。新版本需要实际完整命令解析/内容验证的正例，不能仅做源码token或手工注入全局变量的检查；可在既有远端环境无模型执行真实parser/config/identity路径。bootstrap需针对实际child的真实目标类/函数安装并验证wrapper对象，原函数恰好调用一次、幂等且不改算法或RNG。无模型、零GPU的真实传播核查继续沿用既定隔离实例和个人目录边界。其他已通过且未改变的行为复用证据；仍不运行生产GPU三腿，不改8ac5生产/test。v4回报后再独立验收。

## 2026-09-13：接收 v4 局部结果并整合完整运行候选

用户要求继续推进。现场任务已结束且v4存在，不能继续把它记为在途。协调者核对v4清单 `HASHES_V4.json` 自身 SHA256 `6e6d1673e057cee982410eced9ed0feba947a042a4fca463f75956ba0cade586`，30工件218524 bytes，全部bytes/hash一致；v3仍24文件且冻结身份未变。v3补证 `HASHES_SUPPLEMENT.json` 自身 `2a71bbadf3d83645b641d01ec6076ea5b501877dda6808217cbecfd253738b91`，9个具名key_files全部核对一致，99个raw文件的聚合覆盖需独立验收进一步核实。

v3真实远端补证结论为 `NOT_INSTALLED_FRESH_RAY_CHILD`，同时保留探针动态模块名导致部分路径无法执行的限制。v4在211既有Python 3.11.6 / Ray 2.46.0上取得parser与canonical child import的有限结果：C/A/B参数解析、缺参和内容错配拒绝；63事件、11个方法label和两个rank标签。它是待独立复核的局部诊断证据：`run_v4.py`只有参数构造，`child_observer_v4.py`记录调用，没有接回完整native状态观测或三腿launcher。因此不能据v4自测启动GPU实验。

另发现必须在真实运行配置中处理的差异：v3的 `total_epochs=null` 不符合实际 `TrainerConfig.total_epochs: int`；v4仅以parser专用 `total_epochs=1`通过解析。实际image runner在源码1401–1404以 `total_epochs * len(train_dataloader)` 覆盖每任务步数，不能仅看max_steps=2就认定两步。下一版保留每任务恰好2次真实更新的既定诊断预算；按冻结输入及实际loader长度选择合法整数epochs并验证乘积为2，不改生产逻辑或把parser专用值冒充最终配置。

并行安排：独立验收只读复核冻结v4及v3补证，输出主目录 `docs/acceptance/FRESH-PROCESS-PROTOCOL-V4-20260913/`，给出有限通过/失败与可复用范围；专用诊断任务在同级新 `v5/` 整合完整可执行候选，保持全部旧版及生产/test原样。v5范围仅为既定C/A/B launcher、实际配置/身份校验、真实child安装与完整native/driver/vLLM/anchor/更新观测及总判定器接通；复用已证明方法，不能只再交局部smoke。先完成无模型的全命令/真实parser/loader步数及零GPU child wiring验证，冻结完整包，再接受独立就绪审查。现阶段不启动GPU、不构造神经网络模型、不训练/推理、不安装依赖或删除旧资产。既有必要远端只读身份与隔离零GPU诊断授权继续有效。

### v4 独立有限接收及 v5 增量

独立结论 [LIMITED_ACCEPTANCE_NOT_GPU_READY](acceptance/FRESH-PROCESS-PROTOCOL-V4-20260913/REPORT.md) 已接收。验收清单自身1649 bytes、SHA256 `15e8d7dfea05398e83dba0d4acd7e31b844eaf8c443a8930e8b8d80b02f19164`；协调者6工件38488 bytes全部核对一致。v4 package/raw聚合已独立复算；可复用parser、canonical import/真实方法安装、一次调用及进程内序列的有限证据。两个rank是RawChildProbe的inert调用，真实PersistentRunner也只覆盖早期错误返回路径，不能当作FSDP训练或恢复通过。

独立发现并已传给在途v5：FPP-V4-001，judge将不同PID/rank的方法label并集作为完整覆盖，split-rank反例仍通过；v5按实际role/rank/(PID,start)绑定该进程安装、required labels、唯一call_id的before/after和原函数一次调用，增加对应负例。FPP-V4-002，v3 supplement缺99项raw清单和聚合算法；数量/字节及9个key_files成立，但历史聚合 `271e28...` 尚未独立复算，不推断篡改。允许在v5新增只读生成的全量清单及明确规范，若能从原脚本恢复算法则对账；否则保留旧聚合未验证状态，不覆盖旧文件或把当前清单倒推为历史保全证明。无需为该清单问题重跑Ray。完整v5继续推进，不重新派发或等待用户重复授权。

### v5 冻结接收与实际环境补证

v5准备者回报完成，协调者核对 `HASHES_V5.json` 自身 SHA256 `3eaa31d79c5201830372ab642579122e83ec7732567414764b880ae217eb650c`，36工件186444 bytes逐项一致。包内本地zero-GPU结果仍是缺少Ray而未完成；完整parser/config/loader也未在真实依赖环境执行。`READY_FOR_INDEPENDENT_REVIEW` 只表示提交审查，不构成运行就绪。

v5选择 `total_epochs=1` 并宣称Task2 loader长度为2，但模板的 `mini_rollout_batch_size=2`、每Task两个冻结样本需要实际验证；真实builder按该batch size且drop_last构建，不能凭声明接受两步预算。其长度probe还传入None tokenizer/processor，需以实际接口结果裁决。不得通过手改冻结包或补造loader证明来获得通过。

已续派独立验收只读审查完整v5，输出 `docs/acceptance/FRESH-PROCESS-PROTOCOL-V5-20260913/`。另新建本项目专用执行任务，在既有211/207环境完成实际无模型parser、安全dry-run、零GPU Ray wiring及判定，并在自己的worktree保全原始结果；它不修改v5，独立支路失败后继续其他可安全执行的probe。新任务按规则创建为Luna Max，既有任务模型/推理设置均不更改。创建返回待准备工作区的client id，须在取得真实thread id并核实状态后更新台账，不将创建请求误记为运行完成。当前不执行GPU恢复三腿。

### v5 独立阻断与 v6 限定决定

独立v5 [REPORT.md](acceptance/FRESH-PROCESS-PROTOCOL-V5-20260913/REPORT.md) 为 `NEEDS_PROTOCOL_REVISION`。验收清单自身 SHA256 `21e0f10b68f912106e6da27c4c53e5fe8bee1d1e40c68ea081cbee85fb2da442`，6工件26009 bytes，协调者核对全部一致。历史99项raw清单及当前摘要现已独立核对，旧未复现摘要仍保持原有历史地位。

协调者接受FPP-V5-001/002/003/005的具体阻断：两样本/batch2/drop_last给loader长度1，epochs1只能一步；fingerprint将角色label纳入内容hash，使相同actor/anchor不等；恢复判定缺少A边界expected与B实际post-state逐项比较，vLLM仅回显payload；安装可晚于调用且writer只检查字符串格式。v6分别采用实际验证的 `epochs=2 × loader_len=1`（Task1/2各两步），以无角色label的完整canonical内容摘要比较，逐rank/组件绑定A实际持久化边界与B真实恢复后状态，按进程序列及冻结writer/module bytes/hash校验安装和调用。

对FPP-V5-004只采纳缺少完整group证据、精确窗口/调用对齐与retention比较的部分；不将“不同digest但均值相同”本身定为失败。既有协议是 `state-exact` 加冻结指标的 `trajectory-close`，并未要求后续随机轨迹逐tensor完全相等。保持raw reward均值绝对差0.25、advantages均值0.5、retention contribution均值0.5，须从完整、有限、数量/UID/mask/调用来源明确的真实数据重算并绑定各rank和两步窗口；完整摘要用于内容身份/完整性，不自动要求C/B摘要相等。额外分布或逐元素差异可如实报告，不新增为未经冻结的硬门。输出明确为精确恢复状态与冻结指标接近，不能升级为完整轨迹相同。缺retention或错位/缺失group均失败。

v6仅新增同级目录，保留v1-v5、全部独立验收及原始证据，不改生产/test。将以上最小修复与实际无模型验证做完再冻结；import前GPU gate的声明须与真实顺序一致（只读parser路径可不分配GPU，但模型构造前必须完成实际两卡映射门），逐worker验证Ray分配/CVD/physical UUID映射，不能把worker-local logical 0在两进程重复当成物理卡冲突。仍不运行C/A/B GPU实验。当时未确认的新执行任务，现已核实为71a6工作区任务，见下方更新。

### 2026-09-14：v6冻结接收，恢复独立就绪复核

用户明确继续推进。协调者以协调角色核对14c8准备目录 `v6/HASHES_v6.json`：自身SHA256 `e0c671e00f481efbffb0097cc361673aca1e504914356ebe603a2f1d75c3c820`，59文件4268936 bytes逐项一致；清单记录package manifest `60e5d5ee5b161f212466976af1f7689a632dbeffb0911615a27440115365ce54`、raw manifest `0cf3c8256e0b0797fc48ba20fa7fa7eb7dc5296296a709a14b8258c59229f1ef`，聚合交独立复算。8ac5生产入口和测试再次核对符合R3.1冻结身份。

实际原始结果 `v6/raw/remote-parser-20260913-211/probe-result.json` 记录Task1/2各两个样本、loader长度1、epochs2、每任务两次更新，C/A/B identity均为 `06cb3fe8c6f78b46a37c6f36703a48e65a87f838f7d66b8734a86cd81500a7a3`；没有模型构造、Ray启动或训练。`v6/raw/remote-zero-20260913-211/judge.json` 记录129事件、sequence及process association通过、PASS_V6_ZERO_GPU_PREP。它们是待独立复核的无模型证据，不能代替真实恢复与训练通过。

已续派独立验收 `01a074b8-560b-7be1-8874-1f55a7e1ae10` 并确认active，输出主目录 `docs/acceptance/FRESH-PROCESS-PROTOCOL-V6-20260914/`。只读完整v6，增量检验实际配置、label-free完整状态、A持久化边界与B实际恢复后状态、安装时序/writer身份，以及真实group/mask/UID/retention两步证据。零GPU预期inert raised的例外只适用该probe，完整GPU调用仍须正常返回。继续严格遵守上节state-exact与trajectory-close的范围决定；不增加后续逐tensor轨迹相等硬门。复用未变的42项生产CPU证据，禁止验收者修包或启动GPU。

独立执行任务实际ID为 `01a098f2-b412-7453-9957-3f88c17fe6f0`，工作区71a6，标题“执行 v5 零 GPU 集成验证”；此前list_threads漏项导致“准备中”记录错误。其v5原报告已读：实际epochs1×loader1只产生一步；117事件probe通过但judge拒绝15个inert raised调用，结论BLOCKED_V5_PARSER_RECIPE_AND_ZERO_GPU_JUDGE。原目录未见顶层完整交付清单，已派其仅在同级新supplement补全量文件身份，不重跑远端、不改原件；补证只绑定当前读取状态，不能倒推历史保全。v6独立就绪通过后，再由该专用执行任务推进已授权的同机最多两张空闲3090有限C/A/B实验，旧资产继续保留。
### 2026-09-14：v5历史运行交付补证接收

71a6执行任务已完成同级 `FRESH-PROCESS-V5-ZERO-GPU-20260913-supplement/`。协调者核对 `ORIGINAL_ARTIFACT_MANIFEST.json` 自身SHA256 `a2d64ed282dd4beee16f24908fa45e57f667901064c1b4c208249827643e5f53`；原目录134文件2837689 bytes，逐项bytes/hash与全量文件数一致。按清单声明的排序及canonical JSON算法复算entries聚合为 `6de449d3ef83d9ac70bb632b69008b8d8fc079a7bf5a9b27e54e5e83f925fca0`，一致。补证只绑定本日读取状态，v5阻断结论不变；没有重跑远端实验。v6独立就绪验收仍在进行。
### 2026-09-14：v6独立就绪通过，派发有限GPU运行

独立验收 [REPORT.md](acceptance/FRESH-PROCESS-PROTOCOL-V6-20260914/REPORT.md) 为 `READY_FOR_BOUNDED_GPU`。协调者核对其自排除清单5文件35029 bytes全部一致，`HASHES.json`自身SHA256 `0b54a5d9c125988911bae811911f723a3f288c4706eefde4e096efbbb8b7ee95`。独立复算候选59文件及raw 26文件聚合，重判129事件，实际parser/loader与CPU正负检验均通过；仍没有GPU或exact restore实际结果。

勘误：独立REPORT手写raw摘要含 `...6a7091a14...`，其机器原始输出、候选清单与回报正确值均为 `0cf3c8256e0b0797fc48ba20fa7fa7eb7dc5296296a709a14b8258c59229f1ef`。保留已冻结报告原件，以机器复算值作为身份。bootstrap子报告schema_version=5是已披露的非阻断元数据差异，外层v6事件检查通过。

已向71a6专用执行任务 `01a098f2-b412-7453-9957-3f88c17fe6f0` 派发冻结v6有限C/A/B。沿用既有211/207、同机最多两张现场空闲RTX3090、个人短唯一根及既有环境/模型/输入授权；先核实空间、身份及物理卡映射，再构造模型。C每任务两次更新，A Task1两次后发布完整边界并退出，B新OS进程恢复Task2两次；保持state-exact与冻结指标trajectory-close。新输出为其工作树 `docs/diagnostics/FRESH-PROCESS-V6-GPU-20260914/`，保全全部命令/退出码/raw/全量清单。禁止现场修冻结包、生产或测试，失败交协调者另派准备角色处理；无可用资源则回报事实，旧资产全部保留。真实结果到达后再独立验收，不将派发等同于运行完成。
### 2026-09-14：现场双卡资源阻塞，C/A/B未启动

执行任务回报 `BLOCKED_GPU_PREFLIGHT_RESOURCES_BUSY`。协调者读取保存的211（20:01:43 +08:00）与207（20:02:00 +08:00）原始输出：211七张卡均不满足空闲条件；207仅index2为4 MiB且未列入该次compute-apps输出，其余六卡均超1024 MiB。因此两台都无同机双卡组合，资源阻断成立。磁盘约2.07 TB可用，本次并非空间阻塞。

执行报告声称207 index2也有指定compute app，但保存的raw不支持这一细节；协调者不采纳“所有14卡均有进程”的表述。保留原报告并在此勘误，不因不影响结论的文字错误重跑现场。preflight脚本未调用，模型/Ray/远端根未创建，C/A/B更新数均为0，两个后置判定未运行。

协调者生成当前读取身份接收清单 [FRESH_PROCESS_V6_GPU_BLOCKED_RECEIPT_20260914.json](FRESH_PROCESS_V6_GPU_BLOCKED_RECEIPT_20260914.json)，覆盖执行目录13文件15271 bytes；清单自身SHA256 `aac2face91566b2633d9b7d860b93c601d3fe70ca300dce15863b7b067ab4845`。它只绑定本次读到的原件，不倒推历史保全。v6的READY_FOR_BOUNDED_GPU继续有效；待同一授权主机有两张合格空闲卡，再以新输出根重验现场并执行，不重复CPU验收、不恢复用户禁用的定时轮询。
### 2026-09-14：用户报告211资源释放，恢复有限执行

用户明确表示“211现在有三张空闲卡，继续推进”。协调者已恢复71a6专用执行任务，先重新检查211当前GPU/compute-apps/UUID与空间、身份，再从合格空闲卡中选两张执行冻结v6 preflight及C/A/B，最多占用两张。原资源阻塞证据保留，不能用旧快照否定新资源信息；用户报告亦不代替实际启动前检查。新本地输出为 `docs/diagnostics/FRESH-PROCESS-V6-GPU-20260914-r2/` 或唯一后缀，远端使用新的短唯一个人根。候选与R3.1生产、状态和指标协议不变，未变CPU/零GPU证据复用。完成或具体阻断后回报完整原始结果及全量文件清单，再安排独立实际结果验收。
### 2026-09-14：r2真实映射失败与FPP-V6-GPU-MAP局部修复

211现场确认index2/3/4三张卡空闲，执行仅选2/3。两次无模型preflight分别失败于Ray返回UUID字符串被强制转成int，以及无过滤nvidia-smi枚举全机7卡却被当成worker CUDA可见设备。协调者阅读 `gpu_preflight_v6.py` 与r2两份stdout确认上述诊断断言错误；不采纳执行报告“需要找每worker nvidia-smi只显示一张卡的环境”作为解决前提。Ray官方get_gpu_ids接口允许List[int]或List[str]，CUDA可见设备/ordinal须由CUDA实际接口核实，而非全机管理列表推断。参考 https://docs.ray.io/en/latest/ray-core/api/doc/ray.get_gpu_ids.html 和 https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/environment-variables.html ；现场具体版本仍以Ray2.46实现在新版中核实。

r2 `DELIVERY_MANIFEST-r2.json` 自身SHA256 `3d3ab9f61a9dbce1c416267c99acfd66a56bf0df84330b6977b28a98f3d3095e`，37文件56608 bytes协调者逐项核对一致。C/A/B均未开始，执行方报告两私有Ray已停止、所选卡释放；新远端根 `/mnt/conda/zhenglifeng/t/r6g211r2` 和全部原件保留。此次parser身份 `5e56258c21437b119968c1916f0edacb4a1ce761387b89939d103ff926adcfa7` 与原准备轮次不同，需在后续交接明确路径绑定差异，不能只凭PASS推断身份等同。

已续派14c8准备角色最小新版：限定GPU mapping、必要launcher接线/身份清单及相关正负验证，不改生产/test或已冻结v6，不机械重写无关模块。真实CUDA local ordinal的UUID（或PCI bus id与物理身份交叉核对）必须证明每worker恰好一张可见卡、同机两个不同worker覆盖所选两张；兼容Ray UUID/numeric，保留型号/空闲/两卡上限。允许既有授权范围内无模型CUDA/Ray实际映射probe，不启动C/A/B。交付冻结后独立增量验收，随后71a6执行恢复；已验收且未变CPU/零GPU范围复用，训练和指标协议不变。
### 2026-09-14：v7映射增量冻结并交独立复核

准备者提交14c8准备目录v7，协调者逐项核对116文件4393404 bytes一致，`HASHES_v7.json`自身SHA256 `6e17de365bd2905fb821f37c88a4c441e4d2440d92437fdbf0d6729c962c2e38`。声明package manifest `4606990ad442783ae08ff2149ac6d71a46236a660630bbaf8d2d41c60acf9fbb`，raw65文件4117257 bytes、manifest `57945f80de9a53d5e137ce83bc299a08c0122b82696def0c724af1bf2a2919b3`，交独立复算。

新版保留v6科学状态/指标模块名称及字节，新增gpu_preflight_v7并最小修改run_v6映射接线。211真实无模型probe报告两个worker runtime/driver各1可见设备、local0对应所选index2/3不同UUID且PCI匹配，完整SMI七卡列表仅作诊断；报告probe退出后释放。尚无C/A/B结果。已派独立验收新目录 `docs/acceptance/FRESH-PROCESS-GPU-MAPPING-V7-20260914/`，核对真实raw、正负映射、沿用范围以及完整launcher是否正确验证新清单/处理探针释放，复用未变CPU/零GPU证据。通过后再续派71a6执行，不因准备者自测通过跳过独立增量复核。
### 2026-09-14：v7仅进程身份阻断，限定增量修复

独立v7验收为NEEDS_PROTOCOL_REVISION/FPP-V7-001，协调者5文件35270 bytes逐项核实，验收HASHES.json自身 `6f3e0f1a11aff3dd06f8a2f741df8d54940532cb20384c55de907e9d83a88749`。真实物理映射、UUID/PCI/count、fixture、launcher与资源释放均已独立通过，可复用。阻断限于gpu_preflight_v7.py用当前time_ns填process_start，却以(pid,process_start)集合证明不同worker；同PID不同报告时间可绕过。协调者已读源码确认。

已派14c8准备者在新v8或自包含supplement仅恢复Linux真实OS start采集并拒绝读取失败、缺失/损坏身份及同PID伪不同时间，要求同机不同PID与worker身份；保留可复算原始/proc字段，不能靠数字长度或来源标签代替真实性。优先零GPU实际Linux进程增量probe，复用未变物理映射及其他已验收范围，不重复全GPU/全parser/42CPU。原v7与验收原件不改，交付冻结后独立增量复核，再恢复71a6执行；科学配置/指标不变。
### 2026-09-15：v8进程身份修复冻结并交独立增量复核

协调者核对14c8准备目录v8的150文件4471333 bytes全部一致，HASHES_v8.json自身SHA256 `abd4ccad8d3f2159cd636505b3c78bcafb14e4890e31d1cc81656d97ddc41420`；package manifest `7dbfe1ea8666fed036ae9d59d0b1697ec0d0f2b265d4869e643859bde494b34b`，raw88文件4125939 bytes、manifest `8b1dd4f3bc0fd81dee612c78aaff6b4dee50f3830c4149657dc574dde9025358`交独立复算。原v7保持冻结。

准备者报告实际/proc字段采集稳定、真实子进程不同PID，零GPU Ray两个worker的原始启动tick和worker ID完整，已退出释放；未重跑GPU映射或C/A/B。新gpu_preflight_v8与run_v6必要接线仅修FPP-V7-001，其余v7映射证据复用。已派独立验收到主目录 `docs/acceptance/FRESH-PROCESS-PROC-IDENTITY-V8-20260915/`，检查原始proc重算/拒绝缺失与伪时间/真实身份/负例以及入口接线。根目录GitHub整合不改变8ac5冻结运行身份。独立就绪通过后71a6继续有限GPU对照。
### 2026-09-15：v8独立就绪接收，续派有限GPU执行

独立[v8 REPORT](acceptance/FRESH-PROCESS-PROC-IDENTITY-V8-20260915/REPORT.md)为READY_FOR_BOUNDED_GPU。协调者核对验收清单5文件31351 bytes一致，HASHES.json自身SHA256 `65482518dfa90e27bdfaaefe54ec71083c61dc0e093ff3c112c27a4a8e924949`。真实/proc direct与零GPU Ray身份、负例、28项AST及launcher接线通过；v7物理映射按冻结字节复用，不再以当前时间填进程启动身份。

已续派71a6执行者在新本地 `docs/diagnostics/FRESH-PROCESS-V8-GPU-20260915/` 及新短唯一个人远端根，现场选同机两张空闲3090，部署冻结v8并运行继承run_v6入口（实际gpu_preflight_v8）。C/A/B预算、8ac5生产、模型/输入和状态/指标协议不变。必须记录本次路径绑定身份、各腿真实更新与A边界前后清单、全部日志/退出/释放及完整交付hash；失败不现场修包。当前只确认已派发，未声称实际训练或恢复完成。
