"""Independent CPU checks for the frozen AUTH-CTAN-001 standard path."""

import ast
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

import torch


TARGET_ROOT = Path(r"C:\Users\Administrator\.codex\worktrees\b7ae\RaPO-author")
SHARED_PATH = Path("examples/baselines/_rapo_components.py")
TMP_ROOT = Path(__file__).resolve().parent / "tmp"


def load_subject() -> dict[str, Any]:
    source_path = TARGET_ROOT / SHARED_PATH
    source = source_path.read_bytes()
    tree = ast.parse(source, filename=str(source_path))
    wanted = {"EMAAdvConfig", "EMAAdvNormalizer", "_load_ema_state"}
    nodes = [node for node in tree.body if getattr(node, "name", None) in wanted]
    assert {node.name for node in nodes} == wanted
    namespace = {
        "Any": Any,
        "DataProto": SimpleNamespace,
        "Optional": Optional,
        "dataclass": dataclass,
        "json": json,
        "math": math,
        "os": os,
        "torch": torch,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source_path), "exec"), namespace)
    return namespace


def make_data(rewards: list[list[float]], mask: list[list[float]], uids: list[Any]) -> SimpleNamespace:
    return SimpleNamespace(
        batch={
            "token_level_rewards": torch.tensor(rewards, dtype=torch.float32),
            "response_mask": torch.tensor(mask, dtype=torch.float32),
        },
        non_tensor_batch={"uid": uids},
    )


def scalar_expected(scores: list[float], uids: list[Any], old_std: Optional[float] = None) -> tuple[float, list[float]]:
    mean = sum(scores) / len(scores)
    current_std = math.sqrt(sum((score - mean) ** 2 for score in scores) / (len(scores) - 1))
    ema_std = current_std if old_std is None else 0.999 * old_std + 0.001 * current_std
    grouped: dict[Any, list[float]] = {}
    for uid, score in zip(uids, scores):
        grouped.setdefault(uid, []).append(score)
    group_means = {uid: sum(values) / len(values) for uid, values in grouped.items()}
    values = [(score - group_means[uid]) / (ema_std + 1e-6) for uid, score in zip(uids, scores)]
    return ema_std, values


def check_tensor_output(data: SimpleNamespace, values: list[float]) -> None:
    mask = data.batch["response_mask"]
    expected = torch.tensor(values, dtype=torch.float32).unsqueeze(-1) * mask
    torch.testing.assert_close(data.batch["advantages"], expected, rtol=1e-5, atol=1e-6)
    torch.testing.assert_close(data.batch["returns"], expected, rtol=1e-5, atol=1e-6)
    assert torch.count_nonzero(data.batch["advantages"][mask == 0]) == 0


def main() -> None:
    subject = load_subject()
    config = subject["EMAAdvConfig"](enabled=True)
    normalizer = subject["EMAAdvNormalizer"](config, task_id=1)

    rewards = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 2.0, 0.0, 0.0],
        [3.0, 0.0, 4.0, 0.0],
        [0.5, 0.5, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0],
        [4.0, 0.0, 0.0, 0.0],
    ]
    mask = [
        [1.0, 0.0, 0.0, 0.0],
        [1.0, 1.0, 0.0, 0.0],
        [1.0, 0.0, 1.0, 0.0],
        [1.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0, 0.0],
    ]
    uids = ["prompt-a", "prompt-b", "prompt-a", "prompt-b", "prompt-a", "prompt-b"]
    scores = [sum(row) for row in rewards]
    expected_std, expected_values = scalar_expected(scores, uids)
    string_normalizer = subject["EMAAdvNormalizer"](config, task_id=1)
    data = string_normalizer.compute_grpo_advantage(make_data(rewards, mask, uids))
    assert data.batch["advantages"].shape == (6, 4)
    assert math.isclose(string_normalizer.ema_std, expected_std, rel_tol=1e-5, abs_tol=1e-6)
    assert string_normalizer.update_count == 1
    check_tensor_output(data, expected_values)

    missing_root = TMP_ROOT / f"missing-history-{os.getpid()}"
    missing_root.mkdir(parents=True, exist_ok=False)
    missing_path = missing_root / "ema_online_stats.json"
    assert subject["_load_ema_state"](str(missing_path)) is None
    try:
        subject["EMAAdvNormalizer"](config, initial_state=None, task_id=2)
    except ValueError as exc:
        assert "history" in str(exc).lower()
    else:
        raise AssertionError("task 2 accepted a missing EMA JSON history")

    zero_history = {"ema_mean": 123.0, "ema_std": 0.0, "update_count": 7}
    restored = subject["EMAAdvNormalizer"](config, initial_state=zero_history, task_id=2)
    next_rewards = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [6.0, 0.0, 0.0]]
    next_mask = [[1.0, 0.0, 0.0] for _ in next_rewards]
    next_uids = [0, 0, 1, 1]
    next_scores = [sum(row) for row in next_rewards]
    next_std, next_values = scalar_expected(next_scores, next_uids, old_std=0.0)
    next_data = restored.compute_grpo_advantage(make_data(next_rewards, next_mask, next_uids))
    assert restored.update_count == 8
    assert math.isclose(restored.ema_std, next_std, rel_tol=1e-5, abs_tol=1e-6)
    assert restored.ema_std > 0.0 and restored.ema_std < 0.01
    assert max(abs(value) for value in next_values) > 5.0
    check_tensor_output(next_data, next_values)

    result = {
        "target_root": str(TARGET_ROOT),
        "python": sys.version,
        "torch": torch.__version__,
        "source_sha256": {
            SHARED_PATH.as_posix(): hashlib.sha256((TARGET_ROOT / SHARED_PATH).read_bytes()).hexdigest(),
        },
        "checks": [
            {
                "id": "noncontiguous_string_groups_and_padding",
                "status": "passed",
                "sample_std": expected_std,
                "rows": 6,
                "tokens": 4,
            },
            {
                "id": "missing_json_loader_requires_task2_history",
                "status": "passed",
                "loader_result": None,
            },
            {
                "id": "valid_zero_history_uses_updated_ema_without_floor",
                "status": "passed",
                "updated_ema_std": restored.ema_std,
                "update_count": restored.update_count,
            },
        ],
    }
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
