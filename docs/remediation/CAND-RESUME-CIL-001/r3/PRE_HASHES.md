# CAND-RESUME-CIL-001 R3 冻结前后身份

日期：2026-09-09。角色：independent remediation。R2 原始交付与验收证据保持不变；本页只记录 R3 输入、输出和对照身份。

## R2 冻结输入

编辑前已将 R2 最终目标文件逐字复制到 `r3/inputs/`，并核对如下：

| 文件 | bytes | SHA-256 |
| --- | ---: | --- |
| `inputs/image_cls_cil_rapo.py` | 99,349 | `ba8a5da9341785178bd444112c4fc78dd352b52fe359b768218f4a4a6f5f7863` |
| `inputs/test_cil_resume.py` | 14,217 | `331e62782cc63ef9a2fb4d2de1afe921593f629309f263c6728a7de5299e3f64` |

R2 对照工作树的 image source：99,349 bytes，SHA-256 `ba8a5da9341785178bd444112c4fc78dd352b52fe359b768218f4a4a6f5f7863`；R2 测试同样以冻结输入副本为准。

5ced 对照 image source：45,529 bytes，SHA-256 `8a13974e3dfa7756a076844ce25ef6d66c71c29751fd2dec2f00a52b49092f3d`；5ced 对照没有本轮新增测试文件。

## R3 输出

| 文件 | bytes | SHA-256 |
| --- | ---: | --- |
| `examples/baselines/img_cls_cil/image_cls_cil_rapo.py` | 102,269 | `3cc1fd18b178d05da6481b64ba55ea87c1f50683a4a3897dea9103372c6583c3` |
| `tests/author_fixes/test_cil_resume.py` | 24,215 | `2bb64dccbce91409840d04344a30a58b76265ae77145ab33b4819a3613b4aadf` |

R3 只编辑上述两个 allowlist 文件；没有修改共享 loader、模型配置、trainer/checkpoint/sharding、检测/视频路径，也没有 GPU、SSH、安装、训练、推理、commit 或 push。
