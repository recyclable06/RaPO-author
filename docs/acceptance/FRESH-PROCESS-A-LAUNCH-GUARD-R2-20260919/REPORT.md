# A-only launch guard R2 — independent narrow review

日期：2026-09-19

## 结论

`PASS_R2_TIMEOUT_POLICY_NARROW_REVIEW_CONTRACT_ONLY_NOT_A_RUN`。

R2 的 003 runtime 修正经独立窄复核成立：production 使用 monotonic 的
1800 秒预算，超时后另给最多 120 秒 cleanup；第二次
`TimeoutExpired` 也有 deadline，不存在无界 `communicate()`。child 使用本次
launcher 创建的 session/process group，POSIX 路径只针对该 group 清理。

004 仍未关闭。R2 新增的 private-Ray record guard 能拒绝 `shared_ray=true`
等错误记录，但它只验证 JSON 字段，不能证明 Ray head 真实运行、PID/start
identity、owner、temp root 或 teardown。`PRIVATE_RAY_SUPERVISOR_CONTRACT.md`
明确是未执行的 contract/example，候选目录没有实际 supervisor、record writer
或 cleanup 实现。因此 R2 还不能作为 bounded A dispatch ready 或实际 A
acceptance。

本轮没有启动 Ray、SSH、GPU、模型、训练或 production `Popen`。

## 独立复核结果

- R2 的 15 个声明文件共 94,630 bytes，独立 SHA-256 全部匹配；
  `HASHES_LAUNCH_GUARD.json` self SHA 为
  `593e612c93c55d72104e7ee0aeb29515df78916ed7cd7334a642edb399f53ad7`。
- R1→R2 的新增文件只有 `PRIVATE_RAY_SUPERVISOR_CONTRACT.md`；共同文件的
  变化集中在 003/004 contract、guard、launcher、测试和对应记录，R1 raw、
  parent observer、frozen v9、production source 没有被改写。
- AST 复核显示 `run_v9.py` 中两个 `communicate()` 调用分别在 193、213 行，
  都带 timeout；`time.monotonic()`、`start_new_session=True` 和 POSIX
  `killpg(process.pid, SIGKILL)` 均存在。
- 独立 fake child 强制触发 production timeout 与第二次 cleanup
  `TimeoutExpired`：timeout 参数均有限（约 0.1/0.2 秒），调用次数为 2，
  没有第三次等待，合并后的 stdout/stderr 各只保留一份。
- 候选的五个负例（含 shared-Ray record）均声称在 `Popen` 前拒绝，
  `Popen` sentinel 为 0；独立调用候选 `run()` 至少一次通过。但其内置
  50ms timeout fixture 对“必须抓到一行 stdout”有启动时序依赖：独立五次
  assertion run 为 3 次通过、2 次失败；无断言的直接复测只得到 0 或 1 次
  `timeout-line`，从未出现重复。详见 `TIMEOUT-FIXTURE-STABILITY-NOTE.md`。
- R2 recipe、boundary、production identity、model/input/config path 与 R1
  及 frozen v9 一致，A argv 只有 `--launch_script` 路径不同。R2 manifest
  的 example output/temp 仍写着 `a19r1`，而 R2 命令使用 `a19r2`；这是当前
  不参与 guard 的 contract 文档漂移，执行前应统一。

## `FINDING-A-PRIVATE-RAY-LIFECYCLE-004`

R2 guard 在 `guard_support.py:251-285` 检查 schema、`RUNNING`、
`private_per_run`、`shared_ray=false`、cleanup scope、地址相等、正整数
`head_pid` 以及非空 start/session/owner 字段。这些检查能拒绝明显的共享或
缺字段记录，但不能验证字段对应真实外部状态。

独立构造的 record 使用不存在的 temp root、`head_pid=999999999`、
`head_process_start=not-a-real-process-start`、`owner=forged-owner`，仍被
`_verify_private_ray_record()` 接受。实现没有查询 Ray status、PID 存活和
start identity、当前用户/目录 owner/mode，也没有验证 record 与
`RAY_TMPDIR` 或实际 supervisor 的绑定。

最低闭合条件：提供真实的一次性 private supervisor，实现新 Ray head 的
启动、地址验证、原子 record 写入，以及 normal/timeout 两条路径都只清理
本次 PID/session/temp root；然后用实际生成的 record 做一次独立窄验收。
contract 字符串和手工伪造 record 不能代替该证据。

## 科学与运行边界

world size 2、rollout `n=4`、两 task 各 2 updates、Task-1 boundary、冻结
model/input/config/source identity 均仍是 future A 的既定合同。实际 A、两
GPU worker identity、post-publication `driver_rng_expected` 和 Task-1
evidence 仍未产生；它们不是本轮 R2 prelaunch loop 的结果。
