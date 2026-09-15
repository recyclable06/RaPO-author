# CAND-RESUME-CIL-001 patch manifests

本目录包含本次整改的实际 unified patch 文件；以下身份信息以文件内容和 SHA-256 为准。`SUPPLEMENT_HASHES.json` 记录本页、实际 patch、原始日志和本目录首轮交付文档的完整字节清单。

## Finding-only patch relative to 5ced

实际文件：`CAND-RESUME-CIL-001-vs-5ced.patch`

- 内容：5ced 的 CIL image source 与当前整改后的 image source 的差异，以及新增 `tests/author_fixes/test_cil_resume.py`。
- patch headers 使用 `old/` 与 `new/` 前缀；从仓库根目录应用时使用 `git apply -p2 CAND-RESUME-CIL-001-vs-5ced.patch`。
- bytes：`70,900`
- SHA-256：`4bf2d1ccb29ad8f7f4e11100efd4890902c7bf5688bd1743c5cf6bfbbd797af2`
- 5ced source image SHA-256：`8a13974e3dfa7756a076844ce25ef6d66c71c29751fd2dec2f00a52b49092f3d`
- remediation image SHA-256：`23cbb3c01f69704eb304c2b9c884d8165a9783a913422d6e679e63bb42d71928`
- added test SHA-256：`a8b17b247eac0526108fbd7388af9b98946752bb8214d24229f00121bd200896`

## Author-tag overall patch

实际文件：`CAND-RESUME-CIL-001-vs-author-tag.patch`

- 内容：`author-drop-20260904` 到本整改工作树的 author-tag overall diff，包含当前基线相对 tag 的 tracked changes、allowlist 内生产/测试文件、首轮交付文档、原始验证日志和 finding-only patch。
- bytes：`4,003,574`
- SHA-256：`3ff866dcfd6bbb8445a844814eb7e384696202e61928af4ddf3765b94387ba60`
- 生成时点：在本补充页最终更新及 `SUPPLEMENT_HASHES.json` 创建前；因此该 patch 有意不包含这两个补充索引自身，避免索引与其所列 patch hash 形成循环依赖。
- 其余 tracked/untracked scope 以 patch 内的 `diff --git` headers 为准；未把 legacy `C:/Users/Administrator/Desktop/RaPO` 内容导入工作树。

## Raw evidence

四次命令的完整 stdout、stderr、exit code、command、环境、时间和工作树身份保存在 `raw/`：

- `01_py_compile.*`：语法编译，exit `0`。
- `02_cil_resume.*`：CIL protocol tests，`6 passed`，exit `0`。
- `03_ctan_coco.*`：CTAN/COCO regression，`25 passed`，exit `0`。
- `04_combined.*`：同一次完整 verbose 运行，`31 passed`，exit `0`。

四组 stderr 文件均为空。逐文件 bytes 与 SHA-256 见 `SUPPLEMENT_HASHES.json`。
