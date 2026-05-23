from __future__ import annotations

import pytest

from context_sphere_v3.evaluation import EvaluationConfig
from context_sphere_v3.evaluation import assert_baseline_fairness


def base_config() -> EvaluationConfig:
    return EvaluationConfig(
        instance_ids=("a", "b", "c"),
        agent_model="MiniMax-M2.7",
        temperature=0.0,
        max_generation_tokens=1200,
        visible_repo_state="swebench_lite_base_commit_only",
        prompt_template_id="context_sphere_v3_pm_worker_reviewer_scaffold_v1",
        seed=20260522,
    )


def test_baseline_fairness_accepts_identical_non_selector_config() -> None:
    config = base_config()
    assert_baseline_fairness(
        {
            "full_context": config,
            "standard_rag": config,
            "context_sphere_v3": config,
        }
    )


def test_baseline_fairness_rejects_changed_generation_budget() -> None:
    config = base_config()
    changed = EvaluationConfig(
        instance_ids=config.instance_ids,
        agent_model=config.agent_model,
        temperature=config.temperature,
        max_generation_tokens=2400,
        visible_repo_state=config.visible_repo_state,
        prompt_template_id=config.prompt_template_id,
        seed=config.seed,
    )
    with pytest.raises(ValueError, match="does not match reference"):
        assert_baseline_fairness(
            {
                "full_context": config,
                "standard_rag": config,
                "context_sphere_v3": changed,
            }
        )
