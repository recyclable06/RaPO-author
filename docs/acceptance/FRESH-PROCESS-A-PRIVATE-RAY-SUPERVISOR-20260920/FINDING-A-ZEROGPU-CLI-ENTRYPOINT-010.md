# FINDING-A-ZEROGPU-CLI-ENTRYPOINT-010

状态：OPEN / BLOCKING

独立只读入口证据 `C:/Users/Administrator/.codex/worktrees/71a6/RaPO-author/docs/diagnostics/RAY-CLI-ENTRY-PREFLIGHT-20260920/`
（30 文件、16,933 bytes，`HASHES.json` self SHA
`9c8bc7cac8c7c85fd795ab860f8a357c1e4c65461cbbfbff6870c6a72f868775`）显示：
在既有 Python 3.11.6 / Ray 2.46.0 环境中，`python -m ray start --help`
和 `python -m ray status --help` 都 exit 1，stderr 为
`No module named ray.__main__; 'ray' is a package and cannot be directly executed`。
同环境的 `bin/ray start/status --help` 才 exit 0，shebang 指向该环境的
Python 3.11.6。

因此 zero-GPU command 和父 supervisor 当前硬编码的
`python_executable -m ray start/status` 在目标环境不可用；尚未进入真实
head lifecycle。只读 preflight 本身未启动 Ray/GPU/模型/训练。

最小修正：把 head、readiness 和 help preflight 统一改为目标环境中已验证的
`bin/ray` 入口（或提供并验证等价 CLI executable），同时保留 Ray 版本、
shebang/环境 identity 和真实命令 argv 证据；修正后重新做 bounded zero-GPU
lifecycle 验收。
