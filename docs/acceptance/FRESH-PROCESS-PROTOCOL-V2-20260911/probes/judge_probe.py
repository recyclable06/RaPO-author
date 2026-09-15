from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path


PREP = Path(r"C:\Users\Administrator\.codex\worktrees\14c8\RaPO-author\docs\diagnostics\fresh-process-resume-20260911\v2")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    sys.path.insert(0, str(PREP))
    judge = load_module("judge_v2_acceptance_copy", PREP / "judge_v2.py")
    fixtures = load_module("test_judge_v2_acceptance_copy", PREP / "test_judge_v2.py")
    base = fixtures.valid_fixture()

    valid = judge.evaluate_evidence(copy.deepcopy(base), require_state=True)

    missing_digest = copy.deepcopy(base)
    del missing_digest["native_restore"][0]["actual"]["actor"]
    negative_missing_digest = judge.evaluate_evidence(missing_digest, require_state=True)

    effective_zero = copy.deepcopy(base)
    for update in effective_zero["updates"]:
        for group in update["batch"]["groups"]:
            group["effective_variation"] = 0.0
            group["effective"] = [0.2, 0.2, 0.2, 0.2]
    effective_zero_result = judge.evaluate_evidence(effective_zero, require_state=True)

    one_step = copy.deepcopy(base)
    one_step["updates"] = one_step["updates"][:1]
    one_step_result = judge.evaluate_evidence(one_step, require_state=True)

    result = {
        "status": "PASS_CPU_JUDGE_PROBE",
        "gpu_executed": False,
        "training_executed": False,
        "valid_fixture_pass": valid["pass"],
        "negative_missing_digest_rejected": not negative_missing_digest["pass"],
        "negative_one_step_rejected": not one_step_result["pass"],
        "effective_variation_zero_fixture_passed": effective_zero_result["pass"],
        "effective_variation_zero_reasons": effective_zero_result["reasons"],
        "interpretation": "judge checks raw_variation but does not require effective_variation > 0; this is a protocol/judge coverage gap, not GPU evidence",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    expected = result["valid_fixture_pass"] and result["negative_missing_digest_rejected"] and result["negative_one_step_rejected"] and result["effective_variation_zero_fixture_passed"]
    return 0 if expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
