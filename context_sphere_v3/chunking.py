"""Synthetic chunk generation for early Context Sphere v3 slices."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from context_sphere_v3.data_parser import ContextSphereBatch
from context_sphere_v3.roles import ROLE_PM
from context_sphere_v3.roles import ROLE_REVIEWER
from context_sphere_v3.roles import ROLE_WORKER
from context_sphere_v3.roles import ROLES
from context_sphere_v3.tensor import SimpleTensor


TOY_CHUNK_COUNT = 50
TOY_CHUNK_DIM = 8
TOY_ROLE_DIM = 4

ROLE_RELEVANCE = {
    ROLE_PM: (0, 1, 2, 3, 4, 5),
    ROLE_WORKER: (20, 21, 22, 23, 24, 25),
    ROLE_REVIEWER: (7, 13, 37, 42, 45, 48),
}


@dataclass(frozen=True)
class ToyIssue:
    issue_id: str
    chunk_embeddings: SimpleTensor
    chunk_text: list[list[str]]
    chunk_metadata: list[list[dict[str, Any]]]
    role_embeddings: dict[str, SimpleTensor]
    target_relevance: dict[str, SimpleTensor]

    def batch_for_role(self, role: str) -> ContextSphereBatch:
        if role not in self.role_embeddings:
            raise ValueError(f"unknown role {role!r}")
        return ContextSphereBatch(
            issue_id=self.issue_id,
            chunks=self.chunk_embeddings,
            chunk_text=self.chunk_text,
            chunk_metadata=self.chunk_metadata,
            role=role,
            role_embedding=self.role_embeddings[role],
            target_relevance=self.target_relevance[role],
        ).validate()

    def to_json_summary(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "chunk_count": TOY_CHUNK_COUNT,
            "chunk_dim": TOY_CHUNK_DIM,
            "role_dim": TOY_ROLE_DIM,
            "roles": list(ROLES),
            "chunk_embeddings": self.chunk_embeddings.to_json_summary(),
            "role_embeddings": {role: tensor.to_json_summary() for role, tensor in self.role_embeddings.items()},
            "target_relevant_indices": {role: list(indices) for role, indices in ROLE_RELEVANCE.items()},
        }


def _deterministic_values(count: int, *, seed: int) -> list[float]:
    rng = random.Random(seed)
    return [round(rng.uniform(-1.0, 1.0), 6) for _ in range(count)]


def _target_tensor(relevant_indices: tuple[int, ...]) -> SimpleTensor:
    values = [0.0] * TOY_CHUNK_COUNT
    for index in relevant_indices:
        if index < 0 or index >= TOY_CHUNK_COUNT:
            raise ValueError(f"relevant index out of range: {index}")
        values[index] = 1.0
    return SimpleTensor.from_flat((1, TOY_CHUNK_COUNT), values)


def make_toy_issue(*, seed: int = 7) -> ToyIssue:
    chunk_values = _deterministic_values(TOY_CHUNK_COUNT * TOY_CHUNK_DIM, seed=seed)
    chunk_embeddings = SimpleTensor.from_flat((1, TOY_CHUNK_COUNT, TOY_CHUNK_DIM), chunk_values)
    chunk_text = [[f"toy chunk {index:02d}" for index in range(TOY_CHUNK_COUNT)]]
    chunk_metadata = [[{"chunk_id": f"toy_chunk_{index:02d}", "source": "synthetic"} for index in range(TOY_CHUNK_COUNT)]]
    role_embeddings = {
        role: SimpleTensor.from_flat((1, TOY_ROLE_DIM), _deterministic_values(TOY_ROLE_DIM, seed=seed + offset))
        for offset, role in enumerate(ROLES, start=101)
    }
    target_relevance = {
        role: _target_tensor(indices)
        for role, indices in ROLE_RELEVANCE.items()
    }
    return ToyIssue(
        issue_id=f"toy-context-sphere-v3-seed-{seed}",
        chunk_embeddings=chunk_embeddings,
        chunk_text=chunk_text,
        chunk_metadata=chunk_metadata,
        role_embeddings=role_embeddings,
        target_relevance=target_relevance,
    )
