
# Dataset construction

Download the raw datasets, then build the paper few-shot splits. Run the commands below from this repository root.

# Image Classification CIL

TinyImageNet, CUB-200-2011, ImageNet-R, and ImageNet-A. Each uses a 5-shot training split.

```text
TinyImageNet: 200 classes, train_5shots, val
CUB-200-2011: 200 classes, train_5shots, test
ImageNet-R: 200 classes, train_5shots, test
ImageNet-A: 200 classes, train_5shots, test
```

Download sources:

```text
TinyImageNet: http://cs231n.stanford.edu/tiny-imagenet-200.zip
CUB-200-2011: https://www.vision.caltech.edu/datasets/cub_200_2011/
ImageNet-R: https://drive.google.com/file/d/1SG4TbiL8_DooekztyCVK8mPmfhMo8fkR/view
ImageNet-A: https://drive.google.com/file/d/19l52ua_vvTtttgVRziCZJjal0TPE9f2p/view
```

Included assets:

```text
data/image_cls_cil/label_maps/
data/image_cls_cil/fewshot_lists/
data/image_cls_cil/metadata.json
```

The few-shot datalists are the source of truth for the exact 5-shot training selections. The trainers do not resample few-shot IDs at runtime.

```text
TinyImageNet train_5shots: 1000 images
CUB train_5shots: 1000 images
ImageNet-R train_5shots: 1000 images
ImageNet-A train_5shots: 985 images
```

ImageNet-A has fewer than 1000 selected images because some classes contain fewer than five available examples.

ImageNet-R and ImageNet-A `--raw-root` is the extracted Google Drive tree:

```text
<raw-root>/train/<class_name>/*.jpg
<raw-root>/test/<class_name>/*.jpg
```

```bash
python data/create_image_cls_cil_dataset.py \
  --dataset tinyimagenet \
  --raw-root /path/to/tiny-imagenet-200 \
  --copy-mode symlink

python data/create_image_cls_cil_dataset.py \
  --dataset cub \
  --raw-root /path/to/CUB_200_2011 \
  --copy-mode symlink

python data/create_image_cls_cil_dataset.py \
  --dataset inr \
  --raw-root /path/to/imagenet-r \
  --copy-mode symlink

python data/create_image_cls_cil_dataset.py \
  --dataset ina \
  --raw-root /path/to/imagenet-a \
  --copy-mode symlink
```

Use `--copy-mode copy` if symlinks are not suitable.

Expected output:

```text
data/image_cls_cil_dataset/
  tiny-imagenet-200/{train,train_5shots,val,metadata.json}
  CUB_200/{train,train_5shots,test,metadata.json}
  imagenet-r/{train,train_5shots,test,metadata.json}
  imagenet-a/{train,train_5shots,test,metadata.json}
```

Paper image-CIL numbers are the mean over class-order seeds `1990 1993 1996` for **both** 10-task and 20-task.

```bash
for seed in 1990 1993 1996; do
  bash scripts/image/10task.sh inr "$seed"
  bash scripts/image/20task.sh cub "$seed"
done
```

```bash
DATA_ROOT_BASE=/path/to/image_cls_cil_dataset \
  bash scripts/image/10task.sh inr 1993
```

# UCF101 Video CIL

This package ships UCF101 assets only.

```text
UCF101: https://opendatalab.com/OpenDataLab/UCF101
```

Expected raw layout:

```text
/path/to/UCF101/raw/
  UCF-101/<RawClassName>/*.avi
  ucfTrainTestlist/classInd.txt
  ucfTrainTestlist/trainlist01.txt
  ucfTrainTestlist/testlist01.txt
```

Included assets:

```text
data/video_cls_cil/ucf101_split01_metadata.json
data/video_cls_cil/fewshot_lists/ucf101_split01_train_5shots.jsonl
data/video_cls_cil/metadata.json
```

The metadata maps raw CamelCase UCF101 names to the underscore class folder names used by the launchers. The few-shot datalist is the source of truth for the exact 5-shot training selections.

```text
split_id: 1
shots: 5
fewshot seed: 42
train_5shots videos: 505
```

```bash
python data/create_video_cls_cil_ucf101_dataset.py \
  --raw-root /path/to/UCF101/raw \
  --copy-mode symlink
```

Use `--copy-mode copy` if symlinks are not suitable.

Expected output:

```text
data/video_cls_cil_dataset/UCF101/cil_split01/
  train/<Class_Name>/*.avi
  train_5shots/<Class_Name>/*.avi
  test/<Class_Name>/*.avi
  metadata.json
```

Paper video-CIL numbers are the mean over the same class-order seeds `1990 1993 1996` for **both** 5-task and 10-task.

```bash
for seed in 1990 1993 1996; do
  bash scripts/video/5task.sh ucf101 "$seed"
  bash scripts/video/10task.sh ucf101 "$seed"
done
```

```bash
DATA_ROOT_BASE=/path/to/video_cls_cil_dataset \
  bash scripts/video/5task.sh ucf101 1993
```

# COCO Object Detection CIL

Prepare COCO 2017 with the following layout:

```text
/path/to/coco/
  annotations/instances_train2017.json
  annotations/instances_val2017.json
  train2017/*.jpg
  val2017/*.jpg
```

JSONL image paths are relative to `COCO_IMAGE_ROOT`. Set `COCO_IMAGE_ROOT=/path/to/coco` before running detection experiments.

Included JSONL package:

```text
data/object_det_cil_dataset/
  train_5shots.jsonl
  val.jsonl
  categories.json
  metadata.json
```

`train_5shots.jsonl` is the paper few-shot snapshot (206 images, 80 categories). The trainers read this file as-is and do not resample IDs at runtime. Use this packaged file to reproduce the reported detection runs.

```text
train_5shots.jsonl: 206 records
val.jsonl: 4952 records
categories.json: 80 COCO categories
```

Each JSONL record contains `answer` for bounding-box training and evaluation. The package also stores `answer_seg` polygons so the same records can be checked against COCO annotations. The task here is object detection (`--det_only` in the launchers).

To normalize an existing selection JSONL against raw COCO annotations (relative image paths, regenerated `answer_seg`) while keeping the same images:

```bash
python data/create_object_det_cil_dataset.py \
  --coco-root /path/to/coco \
  --source-train-jsonl data/object_det_cil_dataset/train_5shots.jsonl \
  --source-val-jsonl data/object_det_cil_dataset/val.jsonl \
  --source-categories data/object_det_cil_dataset/categories.json \
  --output-dir data/object_det_cil_dataset_rebuilt
```

A new deterministic split from raw COCO (not the paper snapshot):

```bash
python data/create_object_det_cil_dataset.py \
  --coco-root /path/to/coco \
  --output-dir data/object_det_cil_dataset_rebuilt \
  --fewshot 5 \
  --fewshot-seed 42 \
  --base-classes 16 \
  --incremental-classes 16 \
  --class-order-seed 377 \
  --class-order-mode numpy
```

This creates a new split. Exact reproduction of the paper detection runs requires the packaged `data/object_det_cil_dataset/train_5shots.jsonl`.

Paper detection numbers are also a 3-seed mean, not one seed per task count:

```text
5-task  (16+16): 136 377 639
10-task (8+8):   277 305 738
```

COCO images are multi-label, so each image can belong to several categories. Under a strict class-incremental split the image is assigned to one task, and that assignment depends on the class order. 5-task (`16+16`) and 10-task (`8+8`) are different partitions, so they use different class-order seeds; each setting is a 3-seed mean.

```bash
for seed in 136 377 639; do
  COCO_IMAGE_ROOT=/path/to/coco bash scripts/det/5task.sh "$seed"
done
for seed in 277 305 738; do
  COCO_IMAGE_ROOT=/path/to/coco bash scripts/det/10task.sh "$seed"
done
```

```bash
DATA_ROOT=/path/to/object_det_cil_dataset \
COCO_IMAGE_ROOT=/path/to/coco \
  bash scripts/det/5task.sh 377
```
