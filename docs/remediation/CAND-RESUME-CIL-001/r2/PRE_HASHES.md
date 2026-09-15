# CAND-RESUME-CIL-001 第二轮冻结前后身份

日期：2026-09-09。角色：independent remediation。首轮文件和首轮补充证据均保留不改；本页只记录 r2 输入与输出身份。

## 首轮输入快照

编辑前已将首轮冻结文件逐字复制到 `r2/inputs/`，并核对如下：

| 文件 | bytes | SHA-256 |
| --- | ---: | --- |
| `inputs/image_cls_cil_rapo.py` | 93,286 | `23cbb3c01f69704eb304c2b9c884d8165a9783a913422d6e679e63bb42d71928` |
| `inputs/test_cil_resume.py` | 8,722 | `a8b17b247eac0526108fbd7388af9b98946752bb8214d24229f00121bd200896` |

5ced 对照 image source：45,529 bytes，SHA-256 `8a13974e3dfa7756a076844ce25ef6d66c71c29751fd2dec2f00a52b49092f3d`。

## r2 输出身份

| 文件 | bytes | SHA-256 |
| --- | ---: | --- |
| `examples/baselines/img_cls_cil/image_cls_cil_rapo.py` | 99,349 | `ba8a5da9341785178bd444112c4fc78dd352b52fe359b768218f4a4a6f5f7863` |
| `tests/author_fixes/test_cil_resume.py` | 14,217 | `331e62782cc63ef9a2fb4d2de1afe921593f629309f263c6728a7de5299e3f64` |

首轮输入与 r2 输出的差异仅涉及上述两个 allowlist 文件；首轮 `HASHES.json`、`SUPPLEMENT_HASHES.json`、报告、patch、raw 和主目录独立验收原件未覆盖、未改写。
