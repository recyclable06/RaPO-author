# 集群存储核查（2026-09-17）

用户要求核查空间占用，并提供公告：`/home` 与 `/mnt/Datasets` 共用主 JuiceFS，新增权重和日志应放 `/mnt/conda/<用户名>/` 或节点本地。此次仅分析，不删除、移动、清理文件或启动训练。

## 10:40经207取得的现场结果

207可以登录，能够访问211诊断写入的共享目录。2026-09-17 10:40:53开始的原始检查显示：

| 文件系统 | 容量与剩余（df -h显示） | 使用率 | inode使用率 |
|---|---|---:|---:|
| `/home` 与 `/mnt/Datasets`：`JuiceFS:isee-jfs` | 425 TiB总量，120 TiB剩余 | 72% | 78% |
| `/mnt/conda`：`JuiceFS:isee-jfs-conda` | 12 TiB总量，1.4 TiB剩余 | 89% | 79% |
| 207本地`/`及`/tmp`：`/dev/sda2` ext4 | 880 GiB总量，778 GiB剩余 | 7% | 2% |

这次可见的共享文件系统容量和inode均未耗尽。`/mnt/conda`较紧张，但不能把211的SSH失败归因于已满盘；207本地盘状态也不能代表211本地盘。未取得个人配额或211节点本地状态，不能排除配额、节点I/O或其他问题。

限时du已获得以下分项（按返回的分配块字节折算十进制GB）：

| 目录 | 现场占用 |
|---|---:|
| `/mnt/conda/zhenglifeng/t/r9r211d16b` 本次R2整个运行根 | 54.586 GB |
| 其中 `results`（包含在上项，勿重复相加） | 54.546 GB |
| 其中 `results/B-valid`（包含在上项） | 2.37 MB |
| `/mnt/conda/zhenglifeng/t/r9xr2b` Ray临时目录 | 42.93 MB |
| `/mnt/conda/zhenglifeng/rapo-author-diagnostic-20260908` 环境/安装根 | 15.883 GB |
| 其中 `env/rapo-author`（包含在上项） | 9.110 GB |
| `/home/zhenglifeng/models` | 4.430 GB |
| `/home/zhenglifeng/.cache` | 3.199 GB，其中pip为3.151 GB |
| `/home/zhenglifeng/logs` | 2.19 MB |
| `/home/zhenglifeng/data` | 15.562 GB，数据归属及本次增量未审定 |

本次明确的大量写入是`/mnt/conda`下的checkpoint；B失败输出和Ray日志本身没有出现巨量增长。已检查的home日志/缓存也没有发现TB级异常膨胀，但不能据此排除未扫描目录。个人home和conda根目录限时扫描未返回完整总计，不能将局部分项当作个人总量。

原始扫描后段发生shell语法错误，整体exit2；以上挂载/容量/分项du位于已成功执行的前半段。保留原始失败，未把整次命令标为完全成功。执行任务只补必要缺项或登记限制，不重做成功扫描。

最终存储交付已冻结：71a6 `STORAGE-CHECK-20260917/DELIVERY_MANIFEST-STORAGE.json` 自身SHA256 `867769c82a57e5e8fb49b432cfef664a858151d23d679f48ff10d71810baf5fa`，18文件26922bytes协调者逐项一致。仅补缓存列举的follow-up输出已保留；虽先通过本地bash语法检查，远端尾部CRLF仍导致exit127，不能把命令整体标PASS。已列举HF缓存仅0字节更新标记，W&B/Ray常见home缓存目录不存在；已有容量与du结果不因末尾错误改写。未取得个人目录全量总计，也未执行任何清理。

## 此前能确认的事实

- 211 在2026-09-17 10:29的严格hostkey只读SSH检查超时，未建立会话。因此尚无211当前容量、inode、配额或个人目录总量，不能断言空间耗尽导致SSH失败。
- 历史真实df显示 `/mnt/conda` 是 `JuiceFS:isee-jfs-conda`，不是节点本地盘。2026-09-15 08:28在211看到总量13194139533312bytes、可用1703942496256bytes、使用率88%；207当时也显示同一命名挂载和近似容量。该历史值不代表现在剩余空间。
- 近期诊断的源码部署、环境、输入、checkpoint、日志和Ray临时目录均配置在 `/mnt/conda/zhenglifeng/`。既有模型位于 `/home/zhenglifeng/models/Qwen2-VL-2B-Instruct-895c3a4`，其两份权重分片历史大小合计4418050768bytes，运行按只读输入复用。
- 上述显式路径不能证明所有库的默认缓存均未写入 `/home`；当前仍需核对缓存、符号链接和实际挂载。

## 已知大目录（历史文件长度，不是当前全量du）

GB采用十进制。下列条目时间不同，不能当作当前个人总量，也不能直接当作可释放空间。

| 目录或内容 | 大小 | 证据与限制 |
|---|---:|---|
| `/mnt/conda/zhenglifeng/t/r9r211d16b/results/C` 两份checkpoint | 36.314 GB | R2远端36文件逐项内容hash清单，每任务18.157 GB |
| 同一R2的 `results/A-valid` checkpoint | 约18.2 GB | 已发布marker，体积按同配置单份checkpoint估计；不等同内容完整性验收 |
| `/mnt/conda/zhenglifeng/t/r9g211d16/results` | 约17 GiB | 首轮v9执行报告的目录占用，完整本地镜像未取得 |
| `/mnt/conda/zhenglifeng/t/effective-update-20260909` 旧model-only输出 | 19.605 GB | 9月9日远端清单，四个非空输出树；不能作为完整恢复checkpoint |
| `/mnt/conda/zhenglifeng/rapo-author-cross-task-resume-20260909-attempt3` 两份完整checkpoint | 约36.3 GB | 旧连续诊断记录，当前仍需现场确认 |
| `/home/zhenglifeng/outputs/rapo-b4-gpu-diagnostic` | 13.80 GB | 9月8日旧项目存储盘点，包含历史输出 |
| `/home/zhenglifeng/miniforge3/envs/` 中三个旧RaPO环境 | 合计17.62 GB | 9月8日指定三环境盘点，并非整个envs目录 |
| `/home/zhenglifeng/.cache/pip` | 3.14 GB | 9月8日盘点；只是待核实缓存候选，未获删除授权 |

近期及旧诊断确实累计保存了多份大权重。保存这些历史结果便于回溯，但重复尝试的输出应列入后续精简评估；当前C对照、A边界及未完成审查的证据须先确定保留/归档方案。已有记录不足以证明这些文件导致整个集群容量告急。

## 只读核查边界

211刚超时，不反复探测；经207有界SSH读取共享目录。先检查挂载、容量和inode，再限定个人已知目录做限时浅层占用与缓存检查，不扫描全体用户或整个数据集。新的训练保持停止。

取证输出：71a6工作树 `docs/diagnostics/STORAGE-CHECK-20260917/`，上述现场数据来自`raw/207-readonly.stdout.txt`及配对stderr/exit。此次没有删除或移动操作。旧输出与环境可以列入后续精简评估，但删除具体对象仍需用户授权；当前复现的唯一检查点和审查证据不能未经核对直接处理。

## 证据来源

- 71a6 `docs/diagnostics/FRESH-PROCESS-V8-GPU-20260915/raw/gpu-211.stdout.txt` 与 `gpu-207.stdout.txt`：历史df。
- 71a6 `docs/diagnostics/FRESH-PROCESS-V9-GPU-20260916-R2/raw/C-supervisor/checkpoint-hashes-C.tsv`：两份checkpoint内容清单。
- 71a6 `docs/diagnostics/FRESH-PROCESS-V9-GPU-20260917-CLOSEOUT/`：211本次SSH失败。
- 14c8 `docs/diagnostics/legacy-storage/REPORT.md`、`cross-task-resume-20260909/RETENTION_TABLE.md`：旧home指定目录。
- 14c8 `docs/diagnostics/checkpoint-scope-correction-20260909/REMOTE_OUTPUTS_INVENTORY.json`：旧model-only输出。
- 14c8 `docs/diagnostics/server-inventory/REPORT.md`：既有模型权重与路径。
