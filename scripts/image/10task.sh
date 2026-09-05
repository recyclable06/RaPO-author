#!/usr/bin/env bash
# Paper table: mean over class-order seeds 1990 1993 1996 (same trio for 10-task and 20-task).
# This script runs one seed. Default 1993 is a single-run convenience only.
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/../.." && pwd)
cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"

RAPO_CFG=${RAPO_CFG:-"$SCRIPT_DIR/rapo_cfg.json"}
MODEL_PATH=${MODEL_PATH:-Qwen/Qwen2-VL-2B-Instruct}
SAVE_ROOT=${SAVE_ROOT:-$ROOT_DIR/saves/main_results}
NUM_GPUS=${NUM_GPUS:-4}
ROLLOUT_N=${ROLLOUT_N:-8}
ROLLOUT_BATCH_SIZE=${ROLLOUT_BATCH_SIZE:-8}
ACTOR_GLOBAL_BATCH_SIZE=${ACTOR_GLOBAL_BATCH_SIZE:-8}
ACTOR_MICRO_BATCH_SIZE_UPDATE=${ACTOR_MICRO_BATCH_SIZE_UPDATE:-4}
ACTOR_MICRO_BATCH_SIZE_EXPERIENCE=${ACTOR_MICRO_BATCH_SIZE_EXPERIENCE:-4}
TENSOR_PARALLEL_SIZE=${TENSOR_PARALLEL_SIZE:-1}
TOTAL_EPOCHS=${TOTAL_EPOCHS:-2}
PROJECT_NAME=${PROJECT_NAME:-rft_continual_learning}
KL_COEF=${KL_COEF:-2e-3}
DATASET=${1:-${DATASET:-inr}}
CLASS_ORDER_SEED=${2:-${CLASS_ORDER_SEED:-1993}}
DATA_ROOT_BASE=${DATA_ROOT_BASE:-$ROOT_DIR/data/image_cls_cil_dataset}
BASE_CLASSES=${BASE_CLASSES:-20}
INCREMENTAL_CLASSES=${INCREMENTAL_CLASSES:-20}
TASK_SETTING=10task

case "$DATASET" in
	inr)
		DATASET_ID=inr
		DEFAULT_DATA_ROOT=$DATA_ROOT_BASE/imagenet-r
		DEFAULT_TRAIN_PATH=train_5shots
		DEFAULT_VAL_PATH=test
		;;
	ina)
		DATASET_ID=ina
		DEFAULT_DATA_ROOT=$DATA_ROOT_BASE/imagenet-a
		DEFAULT_TRAIN_PATH=train_5shots
		DEFAULT_VAL_PATH=test
		;;
	tinyimagenet|tin)
		DATASET_ID=tinyimagenet
		DEFAULT_DATA_ROOT=$DATA_ROOT_BASE/tiny-imagenet-200
		DEFAULT_TRAIN_PATH=train_5shots
		DEFAULT_VAL_PATH=val
		;;
	cub)
		DATASET_ID=cub
		DEFAULT_DATA_ROOT=$DATA_ROOT_BASE/CUB_200
		DEFAULT_TRAIN_PATH=train_5shots
		DEFAULT_VAL_PATH=test
		;;
	*)
		echo "Unknown image CIL dataset: $DATASET" >&2
		exit 1
		;;
esac

DATA_ROOT=${DATA_ROOT:-$DEFAULT_DATA_ROOT}
TRAIN_FILES=${TRAIN_FILES:-$DATA_ROOT/$DEFAULT_TRAIN_PATH}
VAL_FILES=${VAL_FILES:-$DATA_ROOT/$DEFAULT_VAL_PATH}
EXP_NAME=${EXP_NAME:-image_cls_cil_rapo_${DATASET_ID}_${TASK_SETTING}_s${CLASS_ORDER_SEED}}
OUT_DIR=${OUT_DIR:-"$SAVE_ROOT/image_cls_cil/rapo/$DATASET_ID/$TASK_SETTING/seed$CLASS_ORDER_SEED"}
mkdir -p "$OUT_DIR"

python -m examples.baselines.img_cls_cil.image_cls_cil_rapo \
	--base_classes "$BASE_CLASSES" \
	--incremental_classes "$INCREMENTAL_CLASSES" \
	--class_order_seed "$CLASS_ORDER_SEED" \
	--save_dir "$OUT_DIR" \
	--launch_script "${BASH_SOURCE[0]}" \
	--prompt_seen_labels \
	--cil_cfg "$RAPO_CFG" \
	config=examples/config.yaml \
	data.train_files="$TRAIN_FILES" \
	data.val_files="$VAL_FILES" \
	data.rollout_batch_size="$ROLLOUT_BATCH_SIZE" \
	algorithm.kl_coef="$KL_COEF" \
	worker.actor.model.model_path="$MODEL_PATH" \
	worker.actor.global_batch_size="$ACTOR_GLOBAL_BATCH_SIZE" \
	worker.actor.micro_batch_size_per_device_for_update="$ACTOR_MICRO_BATCH_SIZE_UPDATE" \
	worker.actor.micro_batch_size_per_device_for_experience="$ACTOR_MICRO_BATCH_SIZE_EXPERIENCE" \
	worker.rollout.n="$ROLLOUT_N" \
	worker.rollout.tensor_parallel_size="$TENSOR_PARALLEL_SIZE" \
	trainer.total_epochs="$TOTAL_EPOCHS" \
	trainer.project_name="$PROJECT_NAME" \
	trainer.experiment_name="$EXP_NAME" \
	trainer.n_gpus_per_node="$NUM_GPUS"
