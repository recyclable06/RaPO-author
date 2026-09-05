> **Active reproduction workspace (2026-09-05).** The immutable author drop is tag `author-drop-20260904`; identity is in [`docs/BASELINE.json`](docs/BASELINE.json). Two P1 findings remain open, so this repository is not yet cleared for paper-faithful experiments. Read [`docs/AUTHOR_CODE_STATUS.md`](docs/AUTHOR_CODE_STATUS.md) before using the launchers. The author-provided README begins below and is preserved verbatim in the baseline tag.

---

# RaPO

Retention-aware Policy Optimization for class-incremental learning with vision-language models.

This package is self-contained. It does not depend on any other checkout or internal experiment tree. Data builders, few-shot ID lists, launchers, and the training code all live here.

## Scope

Method: RaPO (GRPO + retention reward + CTAN).

Task families:

1. Image classification CIL
2. Video classification CIL
3. COCO object detection CIL

## Install

The training environment used for the paper runs is `Python 3.11.6` with `torch==2.6.0+cu124`, `vllm==0.8.1`, and `ray==2.46.0`.

Recommended:

```bash
conda create -n rapo python=3.11
conda activate rapo
pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
```

To recreate the exported conda environment used here:

```bash
conda env create -f environment.lock.yml
conda activate rapo
```

`environment.lock.yml` records the exact conda/pip set from the paper training env. Some CUDA wheels (`torch==2.6.0+cu124`) need a matching local driver/toolkit. The `verl` package is vendored under `verl/` and is not a pip dependency; launchers add this repository root to `PYTHONPATH`.

## Data

See [`data/DATASET.md`](data/DATASET.md) for dataset construction.

## Launch

Paper tables report mean ± std over **three class-order seeds**. Each launcher runs one seed. Do not treat 10-task and 20-task (or 5-task and 10-task) as different single-seed protocols.

| Family | Settings | Class-order seeds (report mean) |
|---|---|---|
| Image CIL | 10-task and 20-task | `1990 1993 1996` |
| Video CIL | 5-task and 10-task | `1990 1993 1996` |
| Detection CIL | 5-task (`16+16`) | `136 377 639` |
| Detection CIL | 10-task (`8+8`) | `277 305 738` |

Image and video use the same three seeds for both task counts. Detection is multi-label, so 5-task (`16+16`) and 10-task (`8+8`) are different partitions and use different class-order seeds; each split is still a 3-seed mean.

Run from this repository root after the corresponding dataset is built:

```bash
for seed in 1990 1993 1996; do
  bash scripts/image/10task.sh inr "$seed"
  bash scripts/image/20task.sh cub "$seed"
  bash scripts/video/5task.sh ucf101 "$seed"
  bash scripts/video/10task.sh ucf101 "$seed"
done

for seed in 136 377 639; do
  COCO_IMAGE_ROOT=/path/to/coco bash scripts/det/5task.sh "$seed"
done
for seed in 277 305 738; do
  COCO_IMAGE_ROOT=/path/to/coco bash scripts/det/10task.sh "$seed"
done
```

RaPO hyperparameters live in the per-family files:

```text
scripts/image/rapo_cfg.json
scripts/video/rapo_cfg.json
scripts/det/rapo_cfg.json
```

Override data or model locations with environment variables (`DATA_ROOT_BASE`, `DATA_ROOT`, `MODEL_PATH`, `COCO_IMAGE_ROOT`).

## Models

```text
image / video: Qwen/Qwen2-VL-2B-Instruct
detection:     Qwen/Qwen2-VL-7B-Instruct
```

## Layout

```text
data/                         builders, few-shot lists, packaged COCO JSONL
data/DATASET.md               dataset construction
examples/baselines/           CIL trainers
examples/reward_function/     classification and detection rewards
examples/format_prompt/       prompt templates
scripts/{image,video,det}/    launchers + rapo_cfg.json
verl/                         training backend (vendored)
```
