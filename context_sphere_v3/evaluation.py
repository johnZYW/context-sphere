"""Evaluation interfaces for Context Sphere v3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvaluationConfig:
    instance_ids: tuple[str, ...]
    agent_model: str
    temperature: float
    max_generation_tokens: int
    visible_repo_state: str
    prompt_template_id: str
    seed: int

    def validate(self) -> "EvaluationConfig":
        if not self.instance_ids:
            raise ValueError("instance_ids must be non-empty")
        if len(set(self.instance_ids)) != len(self.instance_ids):
            raise ValueError("instance_ids must be unique")
        if not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if self.max_generation_tokens <= 0:
            raise ValueError("max_generation_tokens must be positive")
        return self


@dataclass(frozen=True)
class SwebenchPredictionRow:
    instance_id: str
    model_name_or_path: str
    model_patch: str

    def as_json_dict(self) -> dict[str, str]:
        if not self.instance_id:
            raise ValueError("instance_id must be non-empty")
        if not self.model_name_or_path:
            raise ValueError("model_name_or_path must be non-empty")
        if not self.model_patch.startswith("diff --git "):
            raise ValueError("model_patch must be an actual git diff starting with 'diff --git '")
        return {
            "instance_id": self.instance_id,
            "model_name_or_path": self.model_name_or_path,
            "model_patch": self.model_patch,
        }


def assert_baseline_fairness(configs: dict[str, EvaluationConfig]) -> None:
    """Require all methods to share the same non-selector evaluation settings."""
    if not configs:
        raise ValueError("configs must be non-empty")
    names = sorted(configs)
    reference_name = names[0]
    reference = configs[reference_name].validate()
    for name in names[1:]:
        candidate = configs[name].validate()
        if candidate != reference:
            raise ValueError(f"baseline {name!r} does not match reference {reference_name!r}")


def token_reduction_vs_full(full_context_tokens: int, context_sphere_tokens: int) -> float:
    if full_context_tokens <= 0:
        raise ValueError("full_context_tokens must be positive")
    if context_sphere_tokens < 0:
        raise ValueError("context_sphere_tokens must be non-negative")
    return 1.0 - (context_sphere_tokens / full_context_tokens)
