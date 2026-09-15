"""Static source checks for the CTAN-to-actor-loss path in the target tree."""

import hashlib
import json
from pathlib import Path


TARGET_ROOT = Path(r"C:\Users\Administrator\.codex\worktrees\b7ae\RaPO-author")


def read(path: str) -> str:
    return (TARGET_ROOT / path).read_text(encoding="utf-8")


def line_of(source: str, fragment: str) -> int:
    for number, line in enumerate(source.splitlines(), 1):
        if fragment in line:
            return number
    raise AssertionError(f"missing fragment: {fragment}")


def ordered(source: str, *fragments: str) -> list[int]:
    lines = [line_of(source, fragment) for fragment in fragments]
    assert lines == sorted(lines), (fragments, lines)
    return lines


def main() -> None:
    shared = read("examples/baselines/_rapo_components.py")
    ray = read("verl/trainer/ray_trainer.py")
    fsdp = read("verl/workers/fsdp_workers.py")
    actor = read("verl/workers/actor/dp_actor.py")
    image = read("examples/baselines/img_cls_cil/image_cls_cil_rapo.py")
    det = read("examples/baselines/cil_det/image_det_cil_rapo.py")

    checks = {
        "hook_retention_then_ctan": ordered(
            shared,
            "data, dm = _apply_retention_reward(data, self.retention_cfg)",
            "return self.ema_adv.compute_grpo_advantage(data)",
        ),
        "fit_installs_hook_before_super_and_restores": ordered(
            shared,
            "ray_trainer_module.compute_advantage = self._compute_advantage_with_hooks",
            "super().fit()",
            "ray_trainer_module.compute_advantage = self._orig_compute_advantage",
        ),
        "driver_advantage_before_update_actor": ordered(
            ray,
            "batch = compute_advantage(",
            "self.actor_rollout_ref_wg.update_actor(batch)",
        ),
        "worker_forwards_batch_to_actor": ordered(
            fsdp,
            "def update_actor(self, data: DataProto):",
            "self.actor.update_policy(data=data)",
        ),
        "actor_reads_advantages_for_policy_loss": ordered(
            actor,
            'advantages = model_inputs["advantages"]',
            "advantages=advantages,",
        ),
        "image_runner_loads_passes_and_saves_ema": ordered(
            image,
            "ema_initial_state = _load_ema_state(ema_state_path)",
            "ema_adv_state=ema_initial_state",
            "_save_ema_state(ema_state_path, ema_payload, task_id=task_id)",
        ),
        "det_runner_loads_passes_and_saves_ema": ordered(
            det,
            "ema_initial_state = _load_ema_state(ema_state_path)",
            "ema_adv_state=ema_initial_state",
            "_save_ema_state(ema_state_path, ema_payload, task_id=task_id)",
        ),
    }

    source_paths = [
        "examples/baselines/_rapo_components.py",
        "examples/baselines/img_cls_cil/image_cls_cil_rapo.py",
        "examples/baselines/cil_det/image_det_cil_rapo.py",
        "verl/trainer/ray_trainer.py",
        "verl/workers/fsdp_workers.py",
        "verl/workers/actor/dp_actor.py",
    ]
    hashes = {
        path: hashlib.sha256((TARGET_ROOT / path).read_bytes()).hexdigest()
        for path in source_paths
    }
    print(json.dumps({"target_root": str(TARGET_ROOT), "checks": checks, "source_sha256": hashes}, indent=2))


if __name__ == "__main__":
    main()
