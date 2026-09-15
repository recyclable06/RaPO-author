# CAND-RESUME-CIL-001 初始化与前置身份

日期：2026-09-09。角色：独立整改；未承担审查或验收。

## 输入身份

- 只读整合输入：`C:/Users/Administrator/.codex/worktrees/5ced/RaPO-author`
- 输入分支：`codex/integrate-accepted-fixes`
- 输入 HEAD：`da0c5ad521387bab75e74dc0bf0fd47dc13a3647`
- 作者基线：`author-drop-20260904` / `7fe2a73291f208ad9784a8333523825718881907`
- `docs/INTEGRATION_HASHES.json` SHA256：`6514f4dca401ffc805ae57031d1926f742e531ce0fbb981448315538ade8b0b1`
- 本工作树：`C:/Users/Administrator/.codex/worktrees/8ac5/RaPO-author`
- 本分支：`codex/remediate-cil-resume-001`
- 本分支初始 HEAD：`da0c5ad521387bab75e74dc0bf0fd47dc13a3647`

manifest 在拷贝前逐项验证了 6 个生产/配置文件的输入 hash。只拷入 manifest 列出的 6 个生产/配置文件和 4 个既有 `tests/author_fixes` 文件；没有复制 `.git`、缓存、checkpoint、旧工程或无关审查文档。

## 拷贝前后

拷贝前工作树在新分支上相对 HEAD clean。manifest 的 baseline hash 与拷贝前目标状态如下：

| 文件 | 拷贝前目标 | manifest baseline | 拷贝后/输入 SHA256 |
|---|---|---|---|
| `examples/baselines/_rapo_components.py` | baseline | `73aac97f816c124e4fbf06ab3ac0e270045fc79a91c62dc534e8d5d39f99243c` | `58499b6642943cd7b8360c39173dba266231516cd50e7c01d61a724054180155` |
| `examples/baselines/cil_det/image_det_cil_rapo.py` | baseline | `7f36ef88964cc7b56e8e6384f49c2c3f8c570d41961b20a0e12dc82e1da6dc65` | `22216a30eb2d293280d0bd6e65075acb3d969a239a2d4a73b2321605fa7bf25a` |
| `examples/baselines/img_cls_cil/image_cls_cil_rapo.py` | baseline | `0e06cce12ecde79a1fc965a421b6fa8910fb6dd4e39cd6fac3ce854998ead93d` | `8a13974e3dfa7756a076844ce25ef6d66c71c29751fd2dec2f00a52b49092f3d` |
| `scripts/image/rapo_cfg.json` | baseline | `0e3e72bb6510cc0c176983cf46efc70d400ac6f4f79acafe2a6c5409e15df99a` | `9853b9c53e5601b1f3ff9e56fccef03c2697571ccdaa8e77d3a2a75f65e11861` |
| `scripts/video/rapo_cfg.json` | baseline | `0e3e72bb6510cc0c176983cf46efc70d400ac6f4f79acafe2a6c5409e15df99a` | `9853b9c53e5601b1f3ff9e56fccef03c2697571ccdaa8e77d3a2a75f65e11861` |
| `scripts/det/rapo_cfg.json` | baseline | `0e3e72bb6510cc0c176983cf46efc70d400ac6f4f79acafe2a6c5409e15df99a` | `9853b9c53e5601b1f3ff9e56fccef03c2697571ccdaa8e77d3a2a75f65e11861` |
| `tests/author_fixes/run_evidence.py` | missing | — | `32c8b19d3501f7a96ed83ce824235bc017da671b812fb15e79addba761255d34` |
| `tests/author_fixes/source_loader.py` | missing | — | `310540efd2ce9584e9bfa12739c2de33af380cd577b5e3ed80b92b6a7d17d746` |
| `tests/author_fixes/test_coco.py` | missing | — | `7052ecc16f4c0a31689010238bb5848f578bea4d423db05f90c7cf449227e9a9` |
| `tests/author_fixes/test_ctan.py` | missing | — | `f91e8c67b9a087e311e89e0f2aa7c4f6f3d1fd27c136f41b6885478f764161b2` |

拷贝完成后逐项重新计算，10 个输入文件均与 manifest/source 匹配；后续只有图像 CIL 生产文件和新增测试文件发生 finding 差异。`_rapo_components.py`、检测实现与三份配置的当前 hash 仍等于上述整合输入 hash，既有 CTAN/COCO 修复未被遗漏或改写。
