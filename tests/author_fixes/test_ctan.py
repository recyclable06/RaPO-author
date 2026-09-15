import json
import math
import sys
from dataclasses import asdict
from types import SimpleNamespace

import pytest
import torch

from source_loader import ROOT, IMAGE, DET, load, select

N = load()
Config = N["EMAAdvConfig"]
Normalizer = N["EMAAdvNormalizer"]
EXPECTED = dict(enabled=True, beta=0.999, eps=1e-6, bootstrap_steps=0,
                activate_from_task=1, min_std=0.0, guard_abs_max=0.0,
                bias_correction=False, beta_warmup_steps=0, beta_warmup_init=0.9)


def paper_config():
    return Config(**EXPECTED)


def batch(scores):
    # Multi-token rewards and unequal lengths exercise sum and padding behavior.
    rewards = torch.tensor([[x / 4, x * 3 / 4, 0] for x in scores], dtype=torch.float32)
    mask = torch.tensor([[1, 1, 0] for _ in scores], dtype=torch.float32)
    mask[0] = torch.tensor([1, 0, 0])
    rewards[0] = torch.tensor([scores[0], 0, 0])
    return SimpleNamespace(batch={"token_level_rewards": rewards, "response_mask": mask},
                           non_tensor_batch={"uid": [i % 2 for i in range(len(scores))]})


def sigma(xs):
    mean = sum(xs) / len(xs)
    return math.sqrt(sum((x - mean) ** 2 for x in xs) / (len(xs) - 1))


def expected(xs, old=None, grpo=False):
    std = sigma(xs)
    ema = std if old is None else 0.999 * old + 0.001 * std
    result = []
    for i, x in enumerate(xs):
        group = xs[i % 2::2]
        denom = sigma(group) if grpo else ema
        result.append((x - sum(group) / len(group)) / (denom + 1e-6))
    return ema, result


def check_output(data, values):
    want = torch.tensor(values).unsqueeze(-1) * data.batch["response_mask"]
    torch.testing.assert_close(data.batch["advantages"], want, rtol=1e-5, atol=1e-6)
    torch.testing.assert_close(data.batch["returns"], want, rtol=1e-5, atol=1e-6)
    assert torch.count_nonzero(data.batch["advantages"][data.batch["response_mask"] == 0]) == 0


def step(normalizer, xs, old):
    ema, values = expected(xs, old)
    data = normalizer.compute_grpo_advantage(batch(xs))
    assert normalizer.ema_std == pytest.approx(ema, rel=1e-5, abs=1e-6)
    check_output(data, values)
    return ema


def test_task1_first_and_multiple_batches_default_config():
    normalizer = Normalizer(Config(enabled=True), task_id=1)
    assert normalizer.should_use_ema_grpo()
    old = None
    for count, xs in enumerate(([0, 1, 2, 5], [1, 2, 4, 8], [0, 0, 0, 0]), 1):
        old = step(normalizer, xs, old)
        assert normalizer.update_count == count


def test_task123_matches_uninterrupted_and_scalar_formula():
    continuous = Normalizer(paper_config(), task_id=1)
    split = Normalizer(paper_config(), task_id=1)
    old = None
    count = 0
    for task in (1, 2, 3):
        if task > 1:
            split = Normalizer(paper_config(), split.state_dict(), task_id=task)
        for xs in ([0, task, 2, 5], [1, 3, 1, 3]):
            step(continuous, xs, old)
            old = step(split, xs, old)
            count += 1
            assert split.update_count == continuous.update_count == count
            assert split.ema_std == continuous.ema_std


def test_different_histories_same_nonzero_last_batch():
    next_values = []
    for first in ([0, 0, 2, 2], [0, 0, 8, 8]):
        n = Normalizer(paper_config(), task_id=1)
        old = step(n, first, None)
        old = step(n, [0, 1, 2, 3], old)
        restored = Normalizer(paper_config(), n.state_dict(), task_id=2)
        assert restored.ema_std == n.ema_std
        next_values.append(step(restored, [0, 1, 2, 3], old))
    assert abs(next_values[0] - next_values[1]) > 1


def test_real_json_roundtrip_count_and_next_advantage(tmp_path):
    path = N["_ema_stats_file_from_task_dir"](str(tmp_path / "task1"))
    old = None
    n = Normalizer(paper_config(), task_id=1)
    for task in (1, 2, 3):
        if task > 1:
            state = N["_load_ema_state"](path)
            assert state["update_count"] == (task - 1) * 2
            assert state["ema_std"] == n.ema_std
            n = Normalizer(paper_config(), state, task_id=task)
        for xs in ([0, 1, 4, 9], [2, 2, 2, 2]):
            old = step(n, xs, old)
        N["_save_ema_state"](path, n.state_dict(), task)
    payload = json.loads(open(path, encoding="utf-8").read())
    assert [x["task"] for x in payload["task_history"]] == [1, 2, 3]
    assert payload["latest"]["update_count"] == 6
    assert N["_load_ema_state"](path)["ema_std"] == n.ema_std


@pytest.mark.parametrize("xs", [[0, 0, 0, 0], [0, 0, 2e-8, 4e-8]])
def test_zero_and_tiny_variance_no_floor(xs):
    n = Normalizer(Config(enabled=True), task_id=1)
    step(n, xs, None)
    assert n.ema_std < 1e-6
    step(n, [0, 1, 2, 3], sigma(xs))
    assert n.update_count == 2


def test_old_guard_threshold_exceeded_without_fallback():
    n = Normalizer(Config(enabled=True), task_id=1)
    step(n, [0, 0, 0, 0], None)
    xs = [0, 0, 2, 2]
    ema, values = expected(xs, 0)
    assert max(values) > 5
    step(n, xs, 0)
    assert n.ema_std == pytest.approx(ema, rel=1e-5, abs=1e-6)


def hook_trainer(n, task, retention):
    return SimpleNamespace(ema_adv=n, retention_cfg=N["RetentionRewardConfig"](enabled=retention),
                           _task_id=task, _anchor_available=False, _pending_retention_metrics={},
                           _orig_compute_advantage=N["compute_advantage"])


def test_shared_hook_task123_retention_before_ctan():
    old = None
    n = Normalizer(Config(enabled=True), task_id=1)
    for task in (1, 2, 3):
        if task > 1:
            n = Normalizer(Config(enabled=True), n.state_dict(), task_id=task)
        xs = [0, 1, 2, 5]
        d = batch(xs)
        drift = [-0.2, 0, 0.05, 0.1]
        d.batch.update(old_log_probs=torch.tensor(drift).unsqueeze(-1).expand(-1, 3),
                       anchor_log_probs=torch.zeros(4, 3), ref_log_probs=torch.zeros(4, 3))
        trainer = hook_trainer(n, task, True)
        result = N["_compute_advantage_with_hooks"](trainer, d, N["AdvantageEstimator"].GRPO)
        scores = [x + (0.5 * math.exp(-20 * max(v, 0)) if task >= 2 else 0)
                  for x, v in zip(xs, drift)]
        old, values = expected(scores, old)
        torch.testing.assert_close(d.batch["token_level_rewards"].sum(-1), torch.tensor(scores, dtype=torch.float32), rtol=1e-5, atol=1e-6)
        check_output(result, values)
        assert n.ema_std == pytest.approx(old, rel=1e-5, abs=1e-6)
        assert n.update_count == task
        assert bool(trainer._pending_retention_metrics) == (task >= 2)


@pytest.mark.parametrize("task", [1, 2, 3])
def test_disabled_ctan_unchanged_original_grpo(task):
    xs = [0, 1, 2, 5]
    trainer = hook_trainer(None, task, False)
    actual = N["_compute_advantage_with_hooks"](trainer, batch(xs), N["AdvantageEstimator"].GRPO)
    original = N["compute_advantage"](batch(xs), N["AdvantageEstimator"].GRPO)
    assert torch.equal(actual.batch["advantages"], original.batch["advantages"])
    check_output(actual, expected(xs, grpo=True)[1])
    assert trainer.ema_adv is None


@pytest.mark.parametrize("state", [None, {}, {"ema_mean": 0, "ema_std": 1},
    {"ema_std": 1, "update_count": 0}, {"ema_std": float("nan"), "update_count": 2},
    {"ema_std": -1, "update_count": 2}])
def test_later_task_requires_valid_history(state):
    with pytest.raises((ValueError, RuntimeError), match="(?i)(history|state|EMA)"):
        Normalizer(paper_config(), initial_state=state, task_id=2)


@pytest.mark.parametrize("entry", [IMAGE, DET])
def test_actual_reinit_passes_state_and_fails_when_missing(entry):
    ns = load()
    select(entry, {"reinit_for_task"}, ns,
           "PersistentCILTrainer" if entry == IMAGE else "PersistentDetCILTrainer")
    n = Normalizer(paper_config(), task_id=1)
    old = step(n, [0, 1, 2, 7], None)
    old = step(n, [0, 1, 2, 3], old)
    trainer = SimpleNamespace(ema_adv=n, ema_adv_config=paper_config(),
                              config=SimpleNamespace(trainer=SimpleNamespace()))
    args = dict(train_dataloader=[], val_dataloader=[], task_id=2, per_task_steps=2,
                last_global_step=2, save_checkpoint_path="unused", load_checkpoint_path=None)
    ns["reinit_for_task"](trainer, **args, ema_adv_state=n.state_dict())
    assert trainer.ema_adv.ema_std == n.ema_std
    assert trainer.ema_adv.update_count == 2
    step(trainer.ema_adv, [0, 1, 2, 7], old)
    with pytest.raises((RuntimeError, ValueError), match="(?i)(history|state|EMA)"):
        ns["reinit_for_task"](trainer, **args)


@pytest.mark.parametrize("family,entry", [("image", IMAGE), ("video", IMAGE), ("det", DET)])
def test_real_configs_cli_and_environment_defaults(family, entry, monkeypatch):
    ns = load()
    select(entry, {"_parse_args", "_set_env"}, ns)
    for key in list(ns["os"].environ):
        if key.startswith(("EMA_ADV_", "RETENTION_")):
            monkeypatch.delenv(key)
    defaults = dict(EXPECTED, enabled=False)
    assert asdict(Config()) == defaults
    assert asdict(Config.from_env()) == defaults
    monkeypatch.setattr(sys, "argv", ["test"])
    args, extra = ns["_parse_args"]()
    assert not extra
    ns["_set_env"](args)
    assert asdict(Config.from_env()) == defaults
    monkeypatch.setattr(sys, "argv", ["test", "--cil_cfg", str(ROOT / f"scripts/{family}/rapo_cfg.json")])
    args, extra = ns["_parse_args"]()
    assert not extra
    ns["_set_env"](args)
    assert asdict(Config.from_env()) == EXPECTED
    assert args.retention_activate_from_task == args.rapo_activate_from_task == 2
    assert args.retention_reward_enable is True
    monkeypatch.setattr(sys, "argv", sys.argv + ["--ctan_beta_warmup_steps", "3", "--ctan_bias_correction"])
    variant, _ = ns["_parse_args"]()
    assert variant.ema_adv_beta_warmup_steps == 3
    assert variant.ema_adv_bias_correction is True
