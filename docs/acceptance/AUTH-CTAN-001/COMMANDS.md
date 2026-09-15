# AUTH-CTAN-001 验收命令记录

所有目标树命令均以 `C:\Users\Administrator\.codex\worktrees\b7ae\RaPO-author` 为 cwd；测试 stdout/stderr 和 JSON 元数据另存于本目录，不覆盖整改证据。

## 公开测试

```powershell
& 'D:/anaconda3/envs/rapo-b01/python.exe' -B -m pytest tests/author_fixes/test_ctan.py -p no:cacheprovider -v --tb=short
```

子进程环境：`PYTHONDONTWRITEBYTECODE=1`、`PYTHONIOENCODING=utf-8`。exit 0，22 passed。

## 独立验收探针

```powershell
& 'D:/anaconda3/envs/rapo-b01/python.exe' -B docs/acceptance/AUTH-CTAN-001/acceptance_probe.py
& 'D:/anaconda3/envs/rapo-b01/python.exe' -B docs/acceptance/AUTH-CTAN-001/static_flow_probe.py
```

二者均从验收工作区启动，并显式读取目标工作树源码；均 exit 0。前者写出 3 个独立检查结果，后者只做静态顺序/线路检查。

## 语法与静态检查

```powershell
# 7 个 Python 文件由 Python 3.10 AST parse，exit 0
$files = @('examples/baselines/_rapo_components.py','examples/baselines/img_cls_cil/image_cls_cil_rapo.py','examples/baselines/cil_det/image_det_cil_rapo.py','tests/author_fixes/run_evidence.py','tests/author_fixes/source_loader.py','tests/author_fixes/test_ctan.py','docs/remediation/AUTH-CTAN-001/verify_scope.py')
& 'D:/anaconda3/envs/rapo-b01/python.exe' -B -c "import ast,sys; files=sys.argv[1:]; [ast.parse(open(p,encoding='utf-8').read(),filename=p) for p in files]; print('PARSED',len(files))" @files

实际 7 个文件：

```text
examples/baselines/_rapo_components.py
examples/baselines/img_cls_cil/image_cls_cil_rapo.py
examples/baselines/cil_det/image_det_cil_rapo.py
tests/author_fixes/run_evidence.py
tests/author_fixes/source_loader.py
tests/author_fixes/test_ctan.py
docs/remediation/AUTH-CTAN-001/verify_scope.py
```

D:/Git/bin/bash.exe -n scripts/det/10task.sh
D:/Git/bin/bash.exe -n scripts/det/5task.sh
D:/Git/bin/bash.exe -n scripts/image/10task.sh
D:/Git/bin/bash.exe -n scripts/image/20task.sh
D:/Git/bin/bash.exe -n scripts/video/10task.sh
D:/Git/bin/bash.exe -n scripts/video/5task.sh

git diff --check
```

六个 shell 全部 exit 0；`git diff --check` exit 0；没有执行任何 launcher。

## 保全与差分

独立 PowerShell 检查逐项读取 `SHA256SUMS.json` 的 265 个路径并计算 SHA-256，另算清单自身；首轮与末轮均 PASS。范围检查使用 `git diff --name-only`、`git ls-files --others --exclude-standard`、作者 tag 对照和受保护路径对照；生产 patch 再从作者 tag 现场生成并与冻结 patch 做规范化换行比较。
