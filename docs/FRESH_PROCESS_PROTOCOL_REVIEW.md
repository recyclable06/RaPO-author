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
### 2026-09-15：v8执行前资源阻塞

71a6执行任务回报BLOCKED_GPU_PREFLIGHT_RESOURCES_BUSY。协调者核对 `FRESH-PROCESS-V8-GPU-20260915/DELIVERY_MANIFEST-r8.json` 自身SHA256 `b5ea0681a12759d504ee2f6b8e9337867892fd58369400beb1b94c131772e80e`，18文件15390 bytes全部一致，并读取两台主机的原始资源输出。211在08:28:40（+08:00）没有合格空闲3090，207在08:29:00只有index2一张（5 MiB）；无同机双卡组合。两台可用磁盘约1.70 TB。

本轮仅检查现场资源、路径/所有权及本地冻结身份；未部署、未做远端模型/输入全量hash、未创建新远端根、未启动Ray/模型/训练。C/A/B更新数均为0，trajectory/judge未运行。v8独立就绪仍有效，资源变化后重新检查并用新根执行；不新增修复、不重跑未变验收，也不恢复用户禁用的定时轮询。
### 2026-09-16：v8 GPU门通过、C初始化失败与v9最小兼容范围

协调者核对71a6 `FRESH-PROCESS-V8-GPU-20260916/DELIVERY_MANIFEST-v8-gpu-20260916.json` 自身SHA256 `0f080e2e55116a770565b81533041aa28b70d4d0c60542991d74918c945bbcfb`，239文件2512119 bytes全部一致。REPORT末尾2511961 bytes为旧汇总笔误，以清单与复算值为准，报告原件保留。211选物理GPU4/5；v8 preflight PASS，source entry/test/runtime均匹配8ac5冻结值，C路径绑定identity为 `f8402b07c42aee8775e21b0918a2e1c58921140bebdc9213281aa540bd50b8b9`。C生产初始化exit1、0/4更新，A/B未启动；执行方保全全stdout/stderr及10:31:52释放检查，私有Ray结束，未停止其他用户进程。

已读原始调用栈和配置，限定两个诊断兼容问题：FPP-V8-INIT-001，vLLM0.8.1的device_id_to_physical_device_id把CVD token转int，UUID触发ValueError，随后出现模型架构inspection失败；FPP-V8-INIT-002，诊断模板reward_function只有cls.py路径，手填derived reward_function_name会被生产RewardConfig.post_init覆盖为main，而真实模块定义compute_score。源函数和奖励算法不是本次修改对象。

已派14c8准备者新v9最小修复：物理选择及验收仍以UUID为准，但允许经过真实CUDA/PCI/UUID验证的一致numeric CVD贯穿head/driver/worker/vLLM，不能只把SMI编号当作CUDA编号；保留同机两卡与真实进程身份门。奖励模板改为生产支持的cls.py:compute_score声明，并通过实际parser/RewardConfig/加载器确认callable及内容身份，不手填派生字段冒充有效配置。仅必要launcher/preflight/config/identity与正负例、文档/清单，不改R3.1、依赖、C/A/B步数或指标。既有环境真实无模型兼容检查后冻结，独立增量复核再交71a6执行；不重跑未变42CPU或全部传播检查。新远端根r8g211d16和全部旧证据保留。
### 2026-09-16：v9冻结接收并交独立初始化兼容复核

协调者核对14c8准备目录v9的205文件4658581 bytes全部一致，HASHES_v9.json自身SHA256 `45f79cbf83d004b6fd05c4e1ef61fe2f5b296dba1771aae24e45e570b890ee39`；声明package manifest `3767c12fd6bc90ef43479486a057ae92b557aaa4ec276c12d5713871597bae7a`，raw128文件4185383 bytes、manifest `9d41841454ac9cc9dddd226f8d52613514675a5ab04b5188d2cd0b1f5736485c`交独立复算。v8全部150路径声明保持原字节，新v9模块单独提供初始化兼容修复。

准备者报告安装版vLLM0.8.1数字编号转换、实际production parser/RewardConfig/AutoRewardManager在本地及零GPU Ray加载compute_score、非法main拒绝均通过。最终numeric GPU probe在211现场选4/5，经PCI_BUS_ID与实际CUDA/runtime/driver/UUID核对两worker及释放，报告exit0。早期错误源（45529字节）、Ray环境传播错误与历史2/3被占用的失败原件保留；不把历史示例卡当固定授权，已明确可现场任选同机两张合格3090。

已派独立验收到主目录 `docs/acceptance/FRESH-PROCESS-INIT-COMPAT-V9-20260916/`，重点核实真实原始结果、全量8ac5源身份、reward callable身份及run_v9实际全路径接线，复用未变v8范围。新source路径对应的运行身份需如实绑定，不能只凭entry hash接受整个旧远端树。v9就绪验收后再由71a6执行C/A/B；本轮准备没有模型构造或训练。

### 2026-09-16：v9独立结论与奖励源码身份最小补充

独立[验收报告](acceptance/FRESH-PROCESS-INIT-COMPAT-V9-20260916/REPORT.md)结论为BLOCKED_RAY_REWARD_SOURCE_HASH_IDENTITY。协调者复算5文件57690bytes全部一致，HASHES.json自身SHA256 `74fdd89b1f297d1b7ae75d74783bde2a6a69c4906fdc3d19ca530d63e712cae4`。验收独立复算v9及继承v8身份，通过numeric真实映射、安装版vLLM转换、奖励callable实际调用、源码与launcher接线；不推翻这些通过范围。

唯一缺口是serialized_reward_config、local_reward_loader和真实Ray worker report缺少各自独立计算的source_sha256，现有上游hash不能证明worker实际加载文件相同。已续派14c8新建v9-reward-identity-supplement-20260916，仅扩展诊断probe并重跑受影响的零GPU奖励加载证据：由实际反序列化配置或已加载callable定位文件，在对应进程内计算hash并与冻结reward身份比较，保留真实调用及非法main拒绝。原v9包、run_v9及所有失败记录保持冻结；无需新launcher版本、重复GPU映射或42CPU。补充交付后只独立复核该缺口，再续派71a6执行已授权双卡C/A/B。

补充已交付至14c8的 `docs/acceptance/FRESH-PROCESS-INIT-COMPAT-V9-20260916/v9-reward-identity-supplement-20260916/`。协调者核对14文件47813bytes全部一致，HASHES_SUPPLEMENT.json自身SHA256 `da6ad19c30cf5cffc5ed47b5b1ef7983b9d9008c21e0ad57e7c350b739eb789a`；package manifest `2935c0c6ff3d34adc44d727c2356b71b22d73714becc28b360f443e445737c56`，raw8文件21382bytes。真实211零GPUprobe报告post_init一次、三个阶段从实际callable独立定位文件并重算相同冻结reward hash、样例调用及负例通过、私有Ray已释放。已派独立增量复核到新目录 `docs/acceptance/FRESH-PROCESS-V9-REWARD-IDENTITY-20260916/`；当前仅接收证据，不提前宣告就绪或恢复通过。

### 2026-09-16：v9组合独立就绪，续派双卡C/A/B

独立[补充验收](acceptance/FRESH-PROCESS-V9-REWARD-IDENTITY-20260916/REPORT.md)给出READY_FOR_BOUNDED_GPU，原唯一reward source hash缺口闭合。协调者核对5文件32402bytes一致，HASHES.json自身SHA256 `da1f7ba51c903ca8e93cb870e10b2b07bc01e0bb701bc54eea47aa00b0939b21`；package manifest `2f973333b0487cdc9cfee5c134bd6b8372d6924938022f8fb51299c9b3716133`。独立确认三个阶段实际callable文件读取/哈希、cloudpickle往返、真实零GPU worker、实际调用和负例；未变范围复用，旧验收不改写。

已续派71a6，在新本地FRESH-PROCESS-V9-GPU-20260916与新短个人远端根中，现场检查211优先/207备用，任选同机两张合格空闲3090，以run_v9.py和v9 template/expected运行C/A/B。实际numeric CVD经PCI/CUDA/UUID映射确认，R3.1源码与世界大小2、n4、每任务两次更新、完整边界及冻结指标容差不变。保存每腿完整日志、真实更新、退出恢复、路径身份及资源释放；失败不现场改包。目前是执行派发，尚无该次模型初始化、训练更新或fresh-process restore结论。

### 2026-09-16：v9真实Task1训练完成，外层超时与同预算重跑

71a6交付BLOCKED_C_TIMEOUT_AFTER_TASK1。协调者逐项核对439文件1831106053bytes一致，DELIVERY_MANIFEST-v9-gpu-20260916.json自身SHA256 `f8ea1a5562aa05f03b741808c64346ef08d7525bc7342738bf7c0bf692da8463`。211选GPU4/5，numeric/PCI/UUID门PASS，C运行identity `462588adcf411ed68d7ec6e171b4fe88d4b374576d5304558819f6581185b23e`。真实Task1完成2/2更新，step约141.716/146.201秒，checkpoint保存及fit返回后Task2 reinit于1789563201.17047返回；尚无Task2 actor update即被900秒外层时限中断。C为2/4，A/B未开始，judge未运行；未证明生产异常。

外层timeout杀死wrapper导致run-result/process-end和完整production stdout/stderr未落盘；console文件是摘要而非完整原始输出。结构化日志、observer与Ray日志保留，独立复核任务将检查是否存在遗漏异常及checkpoint完整性证据边界。远端 `/mnt/conda/zhenglifeng/t/r9g211d16/` 约17GiB保留；本地1804271616bytes的部分模型传输明确无效，不作为恢复或判定输入，也不上传GitHub。现场释放检查记录21:06:39私有进程退出，GPU4–6空闲，其他用户0–3不动。

同一有限诊断授权内已续派新唯一R2从头运行C，不能用旧Task1 checkpoint拼接连续对照。科学更新数/配置不变，墙钟上限C2700秒、A/B各1800秒，生产合计最多6300秒；额外有限日志收尾与释放。超时监督在冻结包外实施：核验本次child PID/start/命令/目录后终止child，留launcher120秒排空communicate管道并保存结果，再只清理自身私有Ray；若无法安全实施或必须改包则回报准备角色，不现场改冻结源码。优先远端完整内容清单和判定所需raw，避免再次下载整份权重。失败或无进展到上限后停止并回报，不自动继续加时。

### 2026-09-16：超时证据独立复核接收与交付限制

独立[超时复核](acceptance/FRESH-PROCESS-V9-GPU-TIMEOUT-20260916/REPORT.md)保持BLOCKED_C_TIMEOUT_AFTER_TASK1。协调者核对5文件71818bytes一致，HASHES.json自身SHA256 `5f260585371a687916699bf5abbf305b36bfaebd2f2eaaca9cdf26255690d1cb`。81个observer文件426行无解析错误，每rank两次完整update_actor前后事件；experiment log有两次训练及一次validation，Task2无更新。checkpoint保存本身约263.37秒。留存Ray/observer日志未发现实际OOM/traceback/CUDA/NCCL高风险标记，但缺失完整stdout/stderr，不能推导整段运行无异常。

checkpoint的六文件清单只证明列示名称与大小，未提供远端内容hash；此前“完整checkpoint”执行方表述不能升级为内容完整或恢复可用验收。本地partial继续排除。旧delivery manifest含generated_at字符串字面换行，严格JSON解析失败；协调者此前PowerShell宽松解析后439文件逐项hash/bytes核对事实仍成立，但不应把它称为有效JSON清单。原件不覆盖，已要求执行者在R2收尾保留勘误或另存明确派生的修正版，并对新清单做严格JSON回读，不影响正在进行的GPU任务。

独立报告末尾的“separately authorized”不构成新的用户批准门：用户持续授权与协调者已明确下发的R2范围/预算覆盖本次有限重跑。R2任务继续，独立旧记录不替代或提前判定R2结果。

### 2026-09-17：R2连续C完成，A边界观察缺口与B恢复超时

协调者逐项核对71a6 `FRESH-PROCESS-V9-GPU-20260916-R2/` 73条目2840712bytes一致，DELIVERY_MANIFEST-R2.json自身SHA256 `7bc2d84c752ccd87982cb53ba8055dff0e25e5d23244541ba54067e0ee549244`。C的process-end exit0与run-result PASS_PRODUCTION_EXIT可读取，Task1/2各两次更新，远端checkpoint逐文件hash清单列36文件36314240992bytes；实际证据的独立接受范围仍待审查。

A-invalid因命令中错误UUID被preflight拒绝，无训练。A-valid完成Task1两次更新并发布marker，SHA256 `c7b8c132de4346bba8c570d429bdcbef603c0bbeea6bfd8803fea84175d4f795`；boundary-expected明确complete=false、driver=null，缺少A actual post-publication driver RNG capture。不能仅凭marker或native worker状态宣称完整边界已验收，也不能仅重跑B补回A时点的实际随机状态。

B-valid新进程恢复阶段超时，无Task2更新。执行方观察摘要记录D状态/folio_wait_bit_common、较大读取计数与定向child SIGTERM；这些不能单独确证I/O根因。Ray orphan持有管道使launcher未完成，私有Ray清理过程中SSH reset；2026-09-17 10:21:56后续只读SSH亦超时，远端释放和最终日志未确认。已续派一次有界连接核查，连接恢复时只按PID/start/cmd/cwd/env与本次session核验自身残留后处理，收集现有小文件及A内容hash，冻结到新CLOSEOUT目录；禁止全局进程清理、新训练及盲重试。

独立任务新建 `docs/acceptance/FRESH-PROCESS-V9-R2-20260917/`，检查C复用范围、A实际发布方法与observer触发点是否匹配、B现有证据局限，先给最小finding/allowlist再由对应角色修复。R2保持BLOCKED_B_RESTORE_TIMEOUT，完整恢复、trajectory judge与论文复现均未通过。原R2目录冻结，后续材料单独补充。

### 2026-09-17：一次收尾连接超时，远端释放仍未确认

71a6 `FRESH-PROCESS-V9-GPU-20260917-CLOSEOUT/` 已冻结，协调者核对10文件7791bytes一致，DELIVERY_MANIFEST-CLOSEOUT.json自身SHA256 `54339973bbc58084d981c7442de516ea44fcc55549faf6631ddd4465af221f74`，绑定R2清单。known_hosts匹配后，以StrictHostKeyChecking=yes、BatchMode、ConnectTimeout=12、ConnectionAttempts=1做唯一一次只读连接检查；2026-09-17 10:28:54.1392960开始，10:29:07.0813817结束，exit255，stdout为空，stderr为“Timeout, server 192.168.1.211 not responding.”。

未建立远端会话、未取得PID/start/cmd/cwd/env身份，未发送kill/stop/pkill，也未新增训练。状态为REMOTE_CLEANUP_UNCONFIRMED_HOST_UNREACHABLE，不能声明资源已释放，也不能仅据SSH超时断言主机故障原因。已将补充交独立R2审查，继续可在本地完成的A观察触发点定位。资源分支的最小解除条件是211访问恢复后再次有界只读身份核验，再处理明确属于本次的残留；不重复轮询。

### 2026-09-17：R2独立接收与207共享文件补取

独立[R2审查](acceptance/FRESH-PROCESS-V9-R2-20260917/REPORT.md)已完成，协调者核对6文件64823bytes一致，HASHES.json自身SHA256 `940d7c9eb5ae5cd38e9c558c5cbd567632f0683b214c45f2543cdb8c228d7071`。C PASS_C_PRODUCTION，连续四次更新/global steps1–4/exit0及36文件checkpoint内容清单可复用；B仍恢复超时，不接受exit或cleanup。A的[FINDING-A-OBSERVER-001](acceptance/FRESH-PROCESS-V9-R2-20260917/FINDING-A-OBSERVER-001.md)确认观察/采集缺口，实际生产源码有先保存driver/vLLM RNG后发布marker的路径，尚无生产发布缺陷证据。必须补同次A raw events及marker引用状态，不能从其他时点补造RNG。

用户要求的[存储核查](STORAGE_STATUS_20260917.md)发现207可连接且能读取共享R2目录，主JuiceFS72%、conda89%，未见容量/inode耗尽。已派执行者在存储报告冻结后从207只读补取A/B小体积原件到新R2-SHARED-EVIDENCE-20260917；不扫描/复制权重、不启动新训练、不处理211进程。准备者仅本地定位最小观察方案；补取后再判断是否需代码修复或A重跑。共享文件可读不等于211进程已退出，资源释放仍UNCONFIRMED。

准备者本地补充已冻结至14c8 `FRESH-PROCESS-V9-R2-A-OBSERVATION-SUPPLEMENT-20260917/`，协调者8文件18060bytes核对一致，HASHES_AUDIT.json自身SHA256 `b8fe209fdbc580bca1045b9fcf33f568913565fcfd8c8bd0eca652059cf79d9d`。结论NO_CODE_CHANGE_YET：marker及stdout支持实际发布，缺原始事件/marker引用文件时不能判断observer条件是否命中，不修生产、不补造RNG。交付缺失已经确认，但其是否是boundary派生不完整的唯一原因尚未证实，需补取同次原件后判断。补充中的本机C/D盘扫描不属于用户集群核查范围，已要求停止扩大该分支，结果不用于集群因果判断。

### 2026-09-17：共享原件已补回，独立定位实际失败阶段

71a6 `R2-SHARED-EVIDENCE-20260917/` 交付252文件38692471bytes协调者逐项一致，DELIVERY_MANIFEST-SHARED-EVIDENCE.json自身SHA256 `0a6d7c601db17be196c3d457c7a5acbc849e17b9ffde11758a48ac40ae0e284f`；EVIDENCE_INDEX自身 `cc30ab4dce800a08697dea21ae8327a9edce3f4933c4b3bdd828da3307051dc0`，包含215实际证据文件38523445bytes，最大单文件12830694bytes，满足16MiB/64MiB采集预算。通过207只读复制A/B事件、状态和日志，无checkpoint权重或新训练，旧原件不改。

A的marker及driver/vLLM/EMA文件齐备，exit0，但boundary-expected仍缺实际post-publication driver RNG。准备者现按真实A事件定位条件或采集故障，原生产发布缺陷仍未证实。B补回process-end exit-6、完整保存的stdout/stderr及前后边界清单比较equal=true，Task2更新0；相同边界清单不证明恢复成功。run_v9.py按returncode==0填model_constructed/training_started，故失败结果中的false不可独立证明未构造模型或未进入某个阶段。已交独立新审查 `FRESH-PROCESS-R2-SHARED-20260917/`，按原始日志/事件区分监督SIGTERM、最终exit-6与原始卡点；不预先归因I/O、NCCL或生产代码。

取证中的inventory尾部CRLF导致exit127，八组实际复制exit0，清单与字节校验有效；完整worker-log候选仅列清单，若审查需要则精确补少量文件。共享终态文件可读仍不等于211存活进程/显卡现场已核验，cleanup保持UNCONFIRMED。

### 2026-09-19：独立共享复核纠正B阶段与信号归因

独立[共享复核](acceptance/FRESH-PROCESS-R2-SHARED-20260917/REPORT.md)交付8文件63824bytes，协调者逐项hash一致，HASHES.json自身SHA256 `94af87385e7319b389c03ecb143bd25bdafeaf9a0df5a3ae3a59febc3c3169cb`。清单采用路径到hash映射，不能按旧entries数组解释。overall保持PARTIAL_EVIDENCE_SUPPLEMENT。

[B finding](acceptance/FRESH-PROCESS-R2-SHARED-20260917/FINDING-B-ANCHOR-INIT-001.md)确认已完成模型/FSDP/vLLM/persistent-worker初始化。rank0 PID1161595与rank1 PID1162100分别在1789572776.472536/1789572777.2901604进入init_anchor，均无after；run_task、native load/restore与fit事件均0。child于00:17:44.816206 exit-6，supervisor 00:18:33已见退出且child_term_sent=0/child_kill_sent=0；后续Raylet/dashboard SIGTERM在00:18:43–54。此前“restore阶段卡住、监督SIGTERM终止child”来自执行摘要，现被更强原件纠正，旧摘要保留但不再作为当前事实。aggregate stderr无owner的SIGTERM不足以归因，内部abort原因仍未知。

[A finding](acceptance/FRESH-PROCESS-R2-SHARED-20260917/FINDING-A-DRIVER-RNG-002.md)确认marker引用driver/EMA/vLLM原件齐且hash匹配，但81事件文件435记录中实际run_task wrapper调用0，post-publication driver RNG证据未形成。准备任务本地继续定位Ray包装/实际调用路径，不以marker替代独立观察、不改生产。已续派执行任务只读经207补取两个B worker准确对应的stdout/stderr，保存枚举与源身份、预算16MiB/64MiB，不重跑或整树复制。C已接受结果不重跑，211现场资源释放仍UNCONFIRMED。

### 2026-09-19：A观察器装饰时序delta交独立复核

准备者交付14c8 `FRESH-PROCESS-V9-R2-A-OBSERVER-DELTA-20260919/`，协调者核对7文件53631bytes一致，HASHES_DELTA.json自身SHA256 `1d6106911223b061e93e1219509c51b8600458e11bd10f479240d4bf744f4cbe`。新child_observer_v6.py SHA256 `e9c2f17115c44348d1e9e056ee8b3b0b691d2f4ce40e3af0f5ca483f4cd53bd1`；生产、冻结v9与boundary_evidence未改。

准备者定位为Ray装饰时序：生产模块顶层先创建ActorClass，旧loader在模块执行后才包装修改类，installed=true不能保证dispatch表实际经过wrapper。新副本在ray.remote装饰前包装raw class，返回ActorClass后另有兜底。根已核diff并交独立 `FRESH-PROCESS-A-OBSERVER-DELTA-20260919/` 审查其实际Ray语义和影响范围。

现有CPU脚本用FakeActorClass/fake_remote，事件和RNG采集亦stub，只能作局部分支检查，不构成真实Ray dispatch或实际RNG门通过；不采纳准备报告“无需重跑观察器测试”的默认建议。独立任务须明确最小真实零GPU验证，以及新observer如何绑定新的部署/清单/入口身份，不能覆盖冻结v9后沿用旧清单。若本地环境不具备真实Ray则先提交具体方案，由对应角色使用既有环境完成，不安装新依赖、不直接跳到A GPU重跑。C通过范围继续复用，B证据定位另行推进。

### 2026-09-19：B两worker日志限定搜索无匹配

71a6 `R2-B-WORKER-EVIDENCE-20260919/` 已冻结，协调者逐项核对20文件13695bytes一致，DELIVERY_MANIFEST-R2-B-WORKER-EVIDENCE-20260919.json自身SHA256 `4a0783da323cec6858fc8d3729db4909a1a845607d3182dc321b1461d9a902e6`。207于11:28:59严格hostkey连接成功；针对本次私有Ray session，按PID1161595/1162100文件名、日志内容以及session根文件名做三次限定查询，stdout/stderr均空，记录exit0，无worker文件复制。

协调者读到查询使用pipeline且未启用pipefail，因此exit0不独立证明每个find/grep成功；结论仅为本次限定搜索未找到，不宣称日志从未存在或完整目录已证明为空。已交独立任务在A验收后按既有inventory窄查是否有具体遗漏/轮转/链接线索，无需新增远端搜索；没有明确遗漏则保留内部abort未解，不盲目重跑。已通知执行任务结束本分支。原B阶段勘误有效，211现场资源释放仍UNCONFIRMED。

### 用户继续推进：A delta未就绪，补新runtime与真实零GPU验证

独立[A delta验收](acceptance/FRESH-PROCESS-A-OBSERVER-DELTA-20260919/REPORT.md)为PARTIAL_NOT_READY；协调者核对10文件27130bytes及全部hash一致，HASHES.json自身SHA256 `583dc6e07e68f0fc213946e274643bba257e76fd540c9250def2e4b7a6e98380`。静态方向合理，但真实Ray dispatch/序列化/重复包装/非目标透传未验证；原run_v9 HERE与runtime_entry仍优先选旧观察器，现有delta不是可运行的新身份。

用户明确继续后，已派准备者新独立诊断runtime candidate：绑定完整entry/bootstrap/sitecustomize/event_writer/observer/支持文件及manifest，执行前核验导入路径与hash，生产和科学配置不改。使用207既有Ray2.46.0、CUDA_VISIBLE_DEVICES空、num_gpus0、最多3CPU，真实PersistentRunner仅构造并调用run_task至未初始化trainer的预期异常，不调用init/model/dataloader/fit；限600秒加120秒本次资源收尾，不全局清理、不接触211残留。

独立验收附带的零GPU参考脚本未执行，根发现其conditions将两个固定false与正向条件一起all()导致恒FAIL，并且driver/实际runner双身份、版本/期望hash、精确异常和ray.get时限检查不足。旧参考原件保持冻结，准备者在新副本修正后执行真实无mock验证，保存全部事件和释放证据；实际post-publication RNG仍必须在后续A-only两步训练验证，零GPU不替代该门。B限定搜索的窄本地复核并行，C不重跑，不新增GPU训练。

### 2026-09-19：B日志窄复核结束，根因仍未恢复

独立[B日志复核](acceptance/FRESH-PROCESS-R2-B-WORKER-EVIDENCE-20260919/REPORT.md)保持PARTIAL_EVIDENCE_SUPPLEMENT，finding OPEN/NOT_RECOVERED。协调者7文件26614bytes逐项核对一致，HASHES.json自身SHA256 `1cafb14e9ff96b20a7e6e9845381bcd9805759696eb5403d02bdefc7fa088d6d`。既有Ray inventory有318条regular-file记录（56 python-core-worker、112 worker out/err），目标PID只出现在两份observer路径，Ray部分无匹配；旧查询超时/CRLF/pipeline状态与不枚举symlink的限制仍保留，未发现可明确补取的轮转/删除/链接路径，不继续扩大扫描。

后续如进入B诊断，最小新增观察为两目标rank bootstrap时PID/start ticks/Ray worker ID/cwd/fd1-fd2实际目标及exact log path、独立阶段退出状态和有界日志尾；不能用新的概括摘要替代真实记录。该规格已传准备者供后续使用，不扩大当前A零GPU任务，也未启动B。C复用、B内部abort未解、211资源释放UNCONFIRMED。

### 2026-09-19：新runtime真实零GPU自测已交独立验收，资源预检并行

准备者冻结14c8 `docs/acceptance/FRESH-PROCESS-A-OBSERVER-RUNTIME-CANDIDATE-20260919/`，协调者核对40文件646309bytes一致，HASHES_RUNTIME.json自身SHA256 `72f53b1238624c9c9b160b856168505cca2ef5b6048fffa567546c1614a6d5b1`，RUNTIME_CANDIDATE_MANIFEST.json自身 `e3417329860bbfb4dd43298b4d760e24caff60e39a3f93539d02b5071de7e338`。新observer身份仍为 `e9c2f17115c44348d1e9e056ee8b3b0b691d2f4ce40e3af0f5ca483f4cd53bd1`，生产R3.1和原v9不改。

207远端 `/mnt/conda/zhenglifeng/t/aob2` 自测结果为PASS_REAL_RAY_ZERO_GPU_DISPATCH，Ray2.46.0、零GPU、最多3CPU。原件包含118事件/14事件文件，实际PersistentRunner.run_task的before/after配对call id为 `3915086:1789807978239168413:f2f92994383f410f9859c9a959d13973`，PID3915086；after为未初始化trainer的预期AttributeError。准备报告称禁止初始化/模型/训练调用为0，finally已kill本次runner并shutdown。该报告由准备者产生，其标题或措辞不构成独立验收。

已交独立任务在新 `FRESH-PROCESS-A-OBSERVER-RUNTIME-20260919/` 验证driver及真实Runner身份、实际dispatch、非目标透传、重复安装、退出证据、支持文件差异、生产启动链及manifest检查；特别区分零GPUmanifest和后续两GPU A身份。实际post-publication driver RNG仍须A两步验证，零GPUPASS不能替代。准备过程中失败尝试按RUN_METADATA保存，不改写为首次成功。

用户再次要求继续后，专用执行任务同步做211/207一次有界只读预检，输出 `A-ONLY-RESOURCE-PREFLIGHT-20260919/`。只核当前SSH、GPU UUID/占用、容量/inode及本次旧进程身份，211失败不循环；不启Ray/模型/训练，不kill或删旧资产。A尚未调度，独立就绪与现场资源都满足后再冻结具体两步运行。C不重跑，B日志扩搜结束，B内部abort与211释放仍保留未解状态。

### 2026-09-19 22:18：211恢复可访问，空闲卡和空间现场已核实

71a6 `docs/diagnostics/A-ONLY-RESOURCE-PREFLIGHT-20260919/` 已冻结；协调者逐项核对12文件13418bytes一致，HASHES.json自身SHA256 `7cfb64dc7ff716ca9c1699ebc357240e5aa9f66d371721e3a13fc31a3f0b8b13`。211/207各一次严格hostkey连接均exit0，remote采样22:18:44+08:00。211原件列出0–6共7张RTX3090，各1MiB/0%，compute-app query为空；优先4/5 UUID `GPU-4bd5a062-f6e3-e8bf-83d1-a44675314850` / `GPU-ad2d5d4b-c278-e728-c742-6913c7a3437d`，不是固定只能用这两张。207备选3/4各4MiB，其他部分卡有活动负载，实际启动前重新检查。

共享/mnt/conda容量使用86%、inode78%，剩余1906862348个1KiB块（约1.78TiB），211本地盘剩余298718968个1KiB块（约285GiB）；未见本次所查文件系统耗尽，不推断先前SSH故障原因。三个旧PID1115245/1153372/1152533与两个私有路径cmd查询没有匹配，后者pipeline未pipefail；不等于所有Ray/worker残留均已核查。旧目录保留与当前GPU空闲是不同事实，不再沿用“211不可达、GPU完全未知”的当前摘要；未清理任何资产。

预检建议的长Ray临时路径不直接采用：前次零GPU出现过AF_UNIX长度问题，已告知执行者后续选用户专属短新路径（例如/tmp/zlf-a19r1），先核不存在/归属。A执行仍待runtime独立结论和具体入口身份，沿用1800秒主预算及最多120秒收尾，不自动加时，不重复已接受C。

### 2026-09-19：真实dispatch独立确认，生产启动清单校验待补

独立[新runtime验收](acceptance/FRESH-PROCESS-A-OBSERVER-RUNTIME-20260919/REPORT.md)已完成，协调者核对8文件59245bytes全部一致，HASHES.json自身SHA256 `0df8e1ec3ffef5112662efbbf3178ed8d56bebf8ba174b4d633e7d0801071381`。真实Ray零GPUdispatch为INDEPENDENTLY_CORROBORATED，实际生产Runner PID3915086的同PID/start bootstrap及run_task配对事件成立，辅助ProbeActor PID3913646未被用来替代生产actor。非目标透传、重复安装、预期异常和finally收尾亦有独立原件支持。支持文件差异核实包含仅尾空行变化，不能误报为逻辑修订。

整体仍NOT_READY_FOR_BOUNDED_A_ONLY。[GUARD-001](acceptance/FRESH-PROCESS-A-OBSERVER-RUNTIME-20260919/FINDING-A-RUNTIME-MANIFEST-GUARD-001.md)：零GPUlauncher有manifest核验，但生产run_v9只设置candidate-first路径及runtime root，没有在Popen前核对/绑定manifest，bootstrap也仅记录传入值。[TWO-GPU-002](acceptance/FRESH-PROCESS-A-OBSERVER-RUNTIME-20260919/FINDING-A-TWO-GPU-IDENTITY-002.md)：旧manifest的零GPUmetadata不是A两GPU运行身份；实际发布后driver_rng_expected必须由未来A运行生成，不能据此设置“先有GPU结果才能启动GPU”的循环前置条件。

已派准备者新独立 `FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919/` 最小修订，仅run_v9及必要manifest验证support、A运行配置/命令和测试证据。生产R3.1、原v9、旧candidate保持冻结，已确认的observer/event_writer/boundary字节复用。在真实子进程启动前核对runtime完整依赖、冻结v9和91项source身份，并在同一env绑定runtime manifest/root、v9 root及candidate-first路径；正向与缺失/漂移负向检查必须证明拒绝发生在spawn前。配置绑定原v9模板/expected、既有Python、两卡、A两步及1800秒上限；不启动A或新Ray，必要时仅用既有Linux Python做零GPUguard检查。准备后只做变更增量独立验收，C/B/42CPU及已确认真实dispatch均不重复。

### A launch guard候选接收，根发现预算实现与契约不符

14c8 `FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919/` 协调者逐项核对14文件74540bytes一致，HASHES_LAUNCH_GUARD.json自身SHA256 `0bbc37a4a04ef7f2031d9ace2a70444d4271a983e41d9cba7a0cdadbb7fee98d`；LAUNCH_GUARD_MANIFEST自身 `072f91694421782b4ba448eaf03785d516ba355f4e319786dfe10f6c43154b10`，guard_support `2856546e943ed4d5d74ba000a5fcc347658301df10f514702f4a0a6c16738b2f`，run_v9 `aa6c65a0b410fd9900b6a93c5bbf932067cd76379853cfd099c1607ad4bf93f9`。准备者本地正例及四个拒绝例、211纯Pythonguard检查通过，未运行Ray/模型/训练；该自测不替代独立验收。

新入口限定A，在Popen前调用标准库guard，核新4文件、父observer13文件、v9完整205文件及91项source；父observer入口/支持按hash引用，未重写。独立任务已续派 `FRESH-PROCESS-A-LAUNCH-GUARD-20260919/` 验实际接线、参数和测试证据。根同时确认预算问题：guard返回timeout_seconds=1920，launcher将其直接用于production communicate，而不是production_timeout_seconds=1800；超时kill后的communicate又无timeout，因此不能声明已实现1800秒运行加最多120秒收尾。

已要求准备者另存r2修正，保持此快照不变：分开主预算和基于monotonic的剩余收尾时限，不做无界communicate；避免TimeoutExpired保存输出与后续communicate重复拼接。用真实轻量子进程验证正常/超时和必要的管道继承情形，禁止模型或Ray。A命令还须明确FRESH_RAY_ADDRESS属于本次专属新Ray，由实际步骤记录身份并有限收尾，不能接共享Ray。独立者并行审其他部分，新版到达只补有关delta，不重复已通过的真实dispatch、C/B或42CPU。

### A launch guard独立验收接收：仅预算和Ray生命周期待修

独立[guard验收](acceptance/FRESH-PROCESS-A-LAUNCH-GUARD-20260919/REPORT.md)已冻结，协调者核对8文件27677bytes一致，HASHES.json自身SHA256 `9ffee8b7bbcb677e767c176db094154c15dc9529c99a58dbc0b6634b1b397574`。GUARD-001为RESOLVED_FOR_THIS_FROZEN_CANDIDATE：实际入口在Popen前验证并绑定同一子环境，正例与四负例通过，负例Popen=0；既有211Python原件亦通过，未运行Ray/模型/训练。A recipe/path独立比对一致，生产argv与冻结v9仅launch_script路径不同。

整体NOT_READY_FOR_BOUNDED_A_ONLY，新增[003](acceptance/FRESH-PROCESS-A-LAUNCH-GUARD-20260919/FINDING-A-TIMEOUT-CONTRACT-003.md)和[004](acceptance/FRESH-PROCESS-A-LAUNCH-GUARD-20260919/FINDING-A-RAY-LIFECYCLE-004.md)均与根已派r2修正范围一致，无额外算法问题。004要求实际专属Ray启动/UID及PID-start/session地址身份/正常和超时收尾的负责人，不是非空地址占位。报告P1为本次运行门的严重度，不升级为论文或生产算法P1。已将独立结论传给正在修r2的准备者，不重启任务、不重复已通过范围；实际A与发布后RNG仍待未来运行。

### R2候选已交窄复核，专属Ray须由说明落到可执行实现

14c8 `FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2/` 协调者核对15文件94630bytes及全部hash一致，HASHES_LAUNCH_GUARD自身SHA256 `593e612c93c55d72104e7ee0aeb29515df78916ed7cd7334a642edb399f53ad7`；LAUNCH_GUARD_MANIFEST自身 `58b2cf82328120c9f4b45d1229684b03940d3f7aef9b36514d25137bc9e0329a`，guard_support `3bc0023bbd67c915c198722f331e78a8a79b6cde79792b1a9dd0880494412dcc`，run_v9 `db64938bb5ae3208187c77295710d8856a8dd173ab0dae3af1337eb178d6beff`。准备者标准库5负例及真实轻量子进程normal/timeout/inherited-pipe测试通过；本版没有远端Ray/GPU/模型/训练运行，R1远端Python证据只作lineage。

根已派独立 `FRESH-PROCESS-A-LAUNCH-GUARD-R2-20260919/` 核003/004有关diff。R2的PRIVATE_RAY_SUPERVISOR_CONTRACT明确仅schema/example，实际write/verify record与teardown仍是注释，尚不能直接执行A。已同时派准备者保持R2冻结另补具体一次性supervisor：创建私有head、核实际UID/PID-start/session/temp/address、原子记录、调用冻结R2、在正常/失败/timeout/finally核身份停止本次进程。Ray与child收尾共享总计最多120秒，不在两层各追加；禁止共享Ray、全局stop/pkill或删除旧资产。当前仅实现和轻量测试，需真实零GPURay检查时先冻结具体120秒主预算加最多120秒总收尾的命令，再交专用执行角色；不提前启动A。独立者并行审已有R2，其后只补新supervisor增量。

### R2超时策略独立通过，Ray记录仍须live核验

独立[R2窄复核](acceptance/FRESH-PROCESS-A-LAUNCH-GUARD-R2-20260919/REPORT.md)8文件32157bytes协调者一致，HASHES.json自身SHA256 `4185f3fef432dcc016b67228c5bc1869eb0badd78f2f0ff80d14bd2a5d425c4f`。003 runtime helper通过：monotonic 1800/120、两个communicate均finite timeout、二次TimeoutExpired后不再等待、本次child新session及限定pid/group信号；正常/超时/继承管道路径无重复输出。A配方/边界/生产身份保持一致，已有通过范围复用。

[004](acceptance/FRESH-PROCESS-A-LAUNCH-GUARD-R2-20260919/FINDING-A-PRIVATE-RAY-LIFECYCLE-004.md)保持CONTRACT_BOUND_PENDING_REAL_SUPERVISOR_LIFECYCLE：只有JSON字段检查，独立伪造不存在的temp_root、PID999999999、虚构start及owner仍accepted。已传准备者要求实际live身份及目录核验，并覆盖可能脱离head进程组的本次Ray后代，不能仅凭kill head组声称资源已释放。具体supervisor继续补，不扩大为生产代码问题。

[测试稳定性note](acceptance/FRESH-PROCESS-A-LAUNCH-GUARD-R2-20260919/TIMEOUT-FIXTURE-STABILITY-NOTE.md)记录50ms fixture五次3通过/2失败，失败是exact timeout-line为0，未见重复；不足以把首次自测PASS当成稳定复现。新补充采用ready握手后计时，保留exact-once断言，不采用削弱断言的修法；旧R2不改。实际命令还需统一a19r1/a19r2历史路径例子，以新冻结短路径为准。无新增SSH/Ray/GPU/模型/训练，A gate仍OPEN。

### 2026-09-20：具体supervisor补充已接收，零GPU命令仍须修正

14c8 `FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-SUPERVISOR-SUPPLEMENT/` 协调者核对10文件65323bytes一致，HASHES_SUPERVISOR自身SHA256 `f4914b91d91b1b31873457e195805762c930b89c656fe09115d25b9502ee98d9`，SUPERVISOR_MANIFEST自身 `cac9d08d0c3b68d47218183ca21d61cb944d647d15d15746ec01ed350a84c119`。补充实际代码包含proc身份、私有目录、原子record、launcher调用及进程树清理；fake-head/launcher标准库测试通过，但没有真实Ray或GPU执行。

已交独立 `FRESH-PROCESS-A-PRIVATE-RAY-SUPERVISOR-20260920/` 窄复核004、Linux路径及中断/超时/后代进程收尾，不重复已通过范围。根读到zeroGPU命令仍使用production-timeout1800，Ray head无显式num-gpus=0/CPU上限，动态RayTmp也较长；已派准备者保持旧补充冻结另存新版：空CUDA可见列表、0GPU/最多3CPU，startup/readiness/probe合计120秒加最多120秒共享收尾，短唯一私有路径。A模式仍两GPU/1800秒，两个模式分别绑定；CLI `python -m ray` 的既有环境可执行性不能用fake-head证明，需核实际入口。当前只准备和独立审查，真实零GPU测试命令就绪后再派专用执行者，无A运行。

零GPU独立sibling `FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-ZEROGPU-SUPPLEMENT/` 已收，9文件34234bytes根核对一致，HASHES_ZEROGPU自身SHA256 `3635a3afd975d35770a1e9c41841da62fe3051be37ff95d39ffeeb5d19e3a003`，MANIFEST_ZEROGPU自身 `eae681218644bd759152658d425777b7cc3c6e80869a681e1415b01da104c4ed`。wrapper引用冻结父supervisor，0GPU/3CPU/CUDA空、含startup的120秒主预算、共享120秒收尾和短/tmp目录已实现并完成标准库自测。已并入正在进行的独立组合复核，不重复另启验收任务。CLI仍未实证，另派专用执行者 `RAY-CLI-ENTRY-PREFLIGHT-20260920/` 对211一次有界只读import/version/help检查；如缺ray.__main__，同次检查既有env/bin/ray或ray.scripts.scripts入口，逐命令保存退出状态，不安装或启动Ray。

### 2026-09-20 00:16：CLI入口已实证，候选模块调用不可执行

71a6 `RAY-CLI-ENTRY-PREFLIGHT-20260920/` 根核对30文件16933bytes一致，HASHES.json自身SHA256 `9c8bc7cac8c7c85fd795ab860f8a357c1e4c65461cbbfbff6870c6a72f868775`。gpu-211、UID1115、采样00:16:48+08:00，既有Python3.11.6/Ray2.46.0；find_spec(ray.__main__)=None，python -m ray start/status --help均exit1、No module named ray.__main__。实际可用入口 `/mnt/conda/zhenglifeng/rapo-author-diagnostic-20260908/env/rapo-author/bin/ray`，start/status help均exit0，shebang绑定同环境python3.11。首次metadata内联转义SyntaxError原样保留，不用于环境结论；最终模块/CLI检查各有独立退出状态。

该结果证明现候选CLI调用不能直接启动，不是Ray服务故障。已传准备者和独立者，下一版修实际head start/status代码及命令文档，合并其余独立反馈后冻结；允许基于已冻父/zeroGPU sibling另存清晰的最终组合runtime，避免多层补丁，旧快照保持不变。没有新Ray/GPU/模型/训练、安装或清理，也不再重复已确认的CLI探测。

### 2026-09-20：组合审查未就绪，六项执行问题集中修正

独立[组合审查](acceptance/FRESH-PROCESS-A-PRIVATE-RAY-SUPERVISOR-20260920/REPORT.md)已冻结，根核12文件43089bytes一致，HASHES.json自身SHA256 `f980ccf9c91bb29c7580a92ab71ec3f45613563c0f0e5e6de5e7e5d9ab26d5b1`，NOT_READY_FOR_BOUNDED_ZERO_GPU。父与zeroGPU两组stdlib测试独立通过，但strict_linux=False且fake head/readiness、head_command override，不能覆盖真正head builder、procfs或Ray。

005/009为两个入口启动前未验证自身/父文件清单；006为execute没有finally/SIGTERM/SIGINT处理，KeyboardInterrupt不属于Exception；007为launcher group被杀后R2另newsession的production child可能逃逸；008为head stdout/stderr PIPE长时间不drain导致阻塞和日志缺失；010为已实证不可用的python -m ray。zeroGPU资源和含startup预算静态方向正确，但CLI可覆盖120秒上限。已一次集中派给准备者在新组合runtime修复，避免单项交付反复追加；优先私有日志文件、真实live身份及跨session子树、幂等有界finally和已验证bin/ray入口，旧快照不变。

新增针对性验证只覆盖这些具体问题：损坏清单head不启动、真实轻量子进程的SIGINT/SIGTERM与新session孙进程退出、大日志不阻塞、总时限。Windows fake模式不得冒充Linux验证；必要的既有211Linux纯Python检查先冻结命令交专用执行，无模型/Ray启动。A科学参数、源码、R2已过helper和观察器不重做。准备后的Linux实际检查和零GPURay生命周期仍是后续步骤，当前无A运行。

### FINAL集中修订接收，先审Linux进程验证入口

14c8 `FRESH-PROCESS-A-LAUNCH-GUARD-CANDIDATE-20260919-R2-ZEROGPU-CLI-FINAL-SUPPLEMENT/` 的HASHES_FINAL覆盖4文件86564bytes，根逐项核对一致，自身SHA256 `3b9f055da492741754f80b63e2255716e118fea546bca429267c542877136f67`；MANIFEST_FINAL自身 `fc97026c8e51f137d3106d0f918ff3577d8a2886b230f443023e2579d08de0b0`，private_ray_supervisor.py 68147bytes / `fc37f34dd4459fb3050fe7ffee79cfc8d5da1bd69da022ae721fe827486eb302`。命令和报告不在runtime清单，根另记FINAL_COMMAND.md `a2a867abcc7fce4e7b65279e52909d04454a1aee6137baf1a85b70d09181b7b3`、REPORT.md `64ec623844aee8bc4c520891c0a2157e56db59d206b55fa41eee5390341321e8`。

已派独立 `FRESH-PROCESS-A-PRIVATE-RAY-FINAL-20260920/` 核005–010有关修订，区分可进入Linux纯Python进程验证和可进入真实Ray验证。根发现Phase1命令直接run_supervisor_tests.main会覆盖ROOT/test-results.json，该文件已被HASHES_FINAL与manifest绑定，随后Phase2必漂移；已要求评估外置加载冻结模块并调用run_linux_process_check、结果写新目录的方式，避免修改代码或覆盖冻结证据。Linux函数当前主要验证timeout/procfs/跨session后代，本地信号测试仅直接调用handler，不能宣称真实SIGINT/SIGTERM已通过。候选冻结不改，准备者待独立具体反馈；当前没有执行Phase1/Phase2或A。

### FINAL静态复核接收，改用direct-call推进实际Linux阶段

独立[FINAL复核](acceptance/FRESH-PROCESS-A-PRIVATE-RAY-FINAL-20260920/REPORT.md)9文件28649bytes根核对一致，HASHES.json自身SHA256 `ad74c5411b33c88c8d659ae4dcae5eda8ca1ef3df232d4db5412f5e97940a6de`。005–010实现静态闭合，独立直接import后run()通过，冻结test-results前后不变。整体NOT_READY_FOR_BOUNDED_LINUX_STDLIB_AS_WRITTEN指原文档main覆盖结果的011，而[PHASE1_DIRECT_CALL](acceptance/FRESH-PROCESS-A-PRIVATE-RAY-FINAL-20260920/PHASE1_DIRECT_CALL.md)明确允许外置import调用Linux函数、新目录输出；无需再修改subject。012为真实SIGINT/SIGTERM缺证据，不能拿直接handler调用或向后代清理发信号替代。

向既有准备/执行任务send均实际失败thread not found；read仍找到sameID/cwd但notLoaded，准备任务显式hostlocal重试仍失败，未将失败派发记成功。为继续已授权工作，已用项目允许的子Agent角色分离：linux_phase1_execution在211既有Python执行direct-call、保留兄弟snapshot原basename布局和前后外部固定hash、不触发main、不启动Ray；linux_signal_harness在独立目录只准备真实信号harness，不SSH或改subject。Phase1总main最多120秒/本次收尾最多120秒，只核身份处理自身进程，失败保存原件不改代码。根继续接收实际结果与独立验收，尚未进入真实Ray或A。

### 211 Phase1真实早期失败，外层测试PASS不采纳

执行者已取得Linux direct-call原件：runtime身份前后不变，但supervisor-result为FAIL_ZERO_GPU_SUPERVISOR_LIFECYCLE，failure是private Ray executable identity changed，head PID299497已启动，launcher未进入、RUNNING record未写。外层linux-process-check却返回PASS并exit0；测试仅要求任意FAIL及清理字段为true，提前失败后的空集合亦能满足，不能证明预期timeout/launcher/跨session后代曾执行。

原件未保存前后两个executable值，fakeCLI的env shebang与启动exec切换只构成可能机制，不是已证根因。head stdout250019bytes、stderr0和私有temp目录移除有记录；head_returncode=null、owned初始/最终集合为空，因此不能据all_owned_processes_gone=true宣称head/后代已被实际核验释放。真实Ray/GPU/模型/训练均未启动。执行者只补本地报告/hash；独立phase1_failure_audit核具体finding、最低修复allowlist与必要测试，不修subject，不新增SSH或盲重跑。

012信号harness已准备，9文件49825bytes逐项核对，HASHES自身SHA256 `df39bf0f4f146f881a9bdf266a80983dd86662099286d77a977892a0460facb2`。仅Windows AST/静态通过，真实Linux未运行；必须等待RUNNING/head/launcher/两个后代的live身份再向supervisor发送SIGINT/SIGTERM，不接受提前失败。MANIFEST/RUN_METADATA/COMMAND三处runtime hash少写一个a，代码常量正确；另存ERRATA.md（SHA256 `32acce9c0d7d01541a769854cf6ae8fd019bfa7fac26a1182220f9a4ad2fef7b`），旧原件不改。用户中止后明确恢复，已续派被usage limit中断的封存/独立审查子任务，继续同一目标，不重启已完成验证。

独立初步审查进一步核对supervisor-result.json SHA256 `70dfa9018d5536efa0c51fb2a66088f0a3a2d07b92b860030c1fae6f1d2ef1c7` / 5155bytes，根复核一致，给出最小整改allowlist。根据此派独立phase1_identity_remediation在隔离codex分支另存candidate：Popen后于主预算内等待exe稳定并保留before/after观测，同时PID/start/UID/session/pgid锚定前后不变；head已spawn时必须保留归属，无法核清则unknown/fail而非空集合PASS或删除temp；测试须实际ready、launcher/跨session子进程已登记、预期productiontimeout成立。fake正常case可用绝对解释器shebang，启动exec窗口另有专门回归，不能放宽真实bin/ray身份门。原始exe值未留存，因此不能把该假说写成既证事实。代码/训练配方/科学gate范围不扩大，Windows自测后再做Linux实际验证。

执行证据最终冻结于 [PRIVATE-RAY-FINAL-LINUX-PHASE1-20260920](diagnostics/PRIVATE-RAY-FINAL-LINUX-PHASE1-20260920/REPORT.md)：根逐项核对34文件608549bytes，最大单文件250019bytes，HASHES.json自身SHA256 `f1f9573c831ce802f40e8975a110452c749cfbf1d2e2893bdf53e931ffbba2ef`。包含两次尝试/调用历史、完整basename修正、缺失launcher/record说明、前后runtime身份与原始supervisor结果；递归传输的nested重复证据保留。报告明确资源释放未验证，没有在封存阶段再次SSH或重跑；已交独立任务按此身份完成报告。
