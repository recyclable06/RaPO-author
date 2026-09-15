# AUTH-CTAN-001 独立验收进度

状态：已完成，结论为“通过（CTAN 本地代码行为规格）”。

1. 核对自身工作区、目标工作树、main、HEAD、作者 tag、基线 commit 和根规则；角色保持独立验收，未切换到整改或 COCO。
2. 阅读目标 `AGENTS.md`、`AUTHOR_CODE_STATUS.md`、`PROJECT_MAP.md`、`BASELINE.json`、整改 HANDOFF/SPEC/PROGRESS/BLOCKED、production/tests patch、红绿日志及现有 audit/recheck/pipeline 资料。
3. 首轮逐项重算冻结清单：265/265 文件存在且 hash 一致，清单自身为用户给定 hash；没有刷新清单。
4. 在目标 cwd 通过独立子进程运行指定公开测试：22 passed，exit 0，stdout/stderr 已保存到本验收目录。
5. 运行独立 CPU probe：字符串 UID/非连续组与 padding、缺失 JSON loader 的 Task 2 失败、有效零 EMA 历史续算；3/3 passed。
6. 完成 7 个 Python AST parse、6 个 shell `bash -n`、`git diff --check`、配置精确解析、静态 fit→advantages→worker/loss 线路和白名单/保全检查。
7. 末轮重新核对 265 文件及清单自身，结果与首轮一致；未改目标树、根状态或冻结资料。

现场原始输出、环境、scope、静态 flow、config 和 hash 记录见 `REPORT.md` 及 `tmp/`。
