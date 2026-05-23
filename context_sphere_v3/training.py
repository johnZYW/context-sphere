"""Training helpers for Context Sphere v3 local probes."""

from __future__ import annotations

from typing import Any

try:
    import torch
    from torch import nn
    import torch.nn.functional as F
except ModuleNotFoundError:  # pragma: no cover - no-torch shell.
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]

from context_sphere_v3.chunking import make_toy_issue
from context_sphere_v3.model import RoleConditionedEvoformer
from context_sphere_v3.model import RoleConditionedEvoformerConfig
from context_sphere_v3.roles import ROLES


def _require_torch() -> None:
    if torch is None or nn is None:
        raise RuntimeError("PyTorch is required for Context Sphere v3 training probes")


def simple_tensor_to_torch(simple_tensor: Any) -> "torch.Tensor":
    _require_torch()
    return torch.tensor(list(simple_tensor.values), dtype=torch.float32).reshape(simple_tensor.shape)


def top_k_indices(scores: "torch.Tensor", k: int) -> list[int]:
    _require_torch()
    assert scores.ndim == 2 and scores.shape[0] == 1, f"scores must have shape (1, N), observed {tuple(scores.shape)}"
    values = torch.topk(scores[0], k=k).indices.detach().cpu().tolist()
    return [int(value) for value in values]


def run_overfit_on_one(
    *,
    role: str = "reviewer",
    seed: int = 7,
    epochs: int = 800,
    learning_rate: float = 0.01,
    target_loss: float = 0.05,
    positive_weight: float = 8.0,
) -> dict[str, Any]:
    """Overfit the v3 model on one deterministic synthetic issue.

    The positive class is sparse in the 50-chunk toy issue, so this diagnostic
    uses an explicit positive weight. That makes the probe test gradient flow
    and memorization of the intended role labels rather than the trivial
    all-negative solution.
    """
    _require_torch()
    torch.manual_seed(seed)
    issue = make_toy_issue(seed=seed)
    batch = issue.batch_for_role(role)
    chunks = simple_tensor_to_torch(batch.chunks)
    role_embedding = simple_tensor_to_torch(batch.role_embedding)
    target = simple_tensor_to_torch(batch.target_relevance)
    assert chunks.shape == (1, 50, 8)
    assert role_embedding.shape == (1, 4)
    assert target.shape == (1, 50)

    config = RoleConditionedEvoformerConfig(chunk_dim=8, role_dim=4, pair_dim=16, num_layers=1)
    model = RoleConditionedEvoformer(config)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    weights = torch.ones_like(target)
    weights = torch.where(target == 1.0, torch.full_like(target, positive_weight), weights)

    loss = None
    for _epoch in range(epochs):
        optimizer.zero_grad()
        predictions = model(chunks, role_embedding)
        loss = F.binary_cross_entropy(predictions, target, weight=weights)
        loss.backward()
        optimizer.step()

    assert loss is not None
    with torch.no_grad():
        predictions = model(chunks, role_embedding)
        final_loss = float(F.binary_cross_entropy(predictions, target, weight=weights).item())
    relevant = [idx for idx, value in enumerate(target[0].tolist()) if value == 1.0]
    predicted_top_k = top_k_indices(predictions, k=len(relevant))
    hit_count = len(set(relevant).intersection(predicted_top_k))
    return {
        "schema_version": 1,
        "probe": "context_sphere_v3_overfit_on_one",
        "claim_boundary": "Synthetic overfit/gradient-flow check only. This is not benchmark evidence.",
        "role": role,
        "seed": seed,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "target_loss": target_loss,
        "positive_weight": positive_weight,
        "final_loss": final_loss,
        "passed": final_loss < target_loss,
        "relevant_indices": relevant,
        "predicted_top_k": predicted_top_k,
        "top_k_hit_count": hit_count,
        "chunk_shape": list(chunks.shape),
        "role_embedding_shape": list(role_embedding.shape),
        "target_shape": list(target.shape),
    }


def run_role_separation_probe(
    *,
    seed: int = 29,
    epochs: int = 1000,
    learning_rate: float = 0.01,
    positive_weight: float = 8.0,
) -> dict[str, Any]:
    """Train one model on one issue with three role-conditioned targets."""
    _require_torch()
    torch.manual_seed(seed)
    issue = make_toy_issue(seed=7)
    base_batch = issue.batch_for_role("pm")
    chunks_single = simple_tensor_to_torch(base_batch.chunks)
    role_embeddings = []
    targets = []
    relevant_by_role = {}
    for role in ROLES:
        batch = issue.batch_for_role(role)
        role_embeddings.append(simple_tensor_to_torch(batch.role_embedding))
        target = simple_tensor_to_torch(batch.target_relevance)
        targets.append(target)
        relevant_by_role[role] = [idx for idx, value in enumerate(target[0].tolist()) if value == 1.0]

    chunks = chunks_single.expand(len(ROLES), -1, -1).clone()
    role_tensor = torch.cat(role_embeddings, dim=0)
    target_tensor = torch.cat(targets, dim=0)
    assert chunks.shape == (3, 50, 8)
    assert role_tensor.shape == (3, 4)
    assert target_tensor.shape == (3, 50)

    config = RoleConditionedEvoformerConfig(chunk_dim=8, role_dim=4, pair_dim=24, num_layers=1)
    model = RoleConditionedEvoformer(config)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    weights = torch.ones_like(target_tensor)
    weights = torch.where(target_tensor == 1.0, torch.full_like(target_tensor, positive_weight), weights)

    loss = None
    for _epoch in range(epochs):
        optimizer.zero_grad()
        predictions = model(chunks, role_tensor)
        loss = F.binary_cross_entropy(predictions, target_tensor, weight=weights)
        loss.backward()
        optimizer.step()

    assert loss is not None
    with torch.no_grad():
        predictions = model(chunks, role_tensor)
        final_loss = float(F.binary_cross_entropy(predictions, target_tensor, weight=weights).item())

    top_k_by_role: dict[str, list[int]] = {}
    hit_count_by_role: dict[str, int] = {}
    for role_index, role in enumerate(ROLES):
        role_scores = predictions[role_index : role_index + 1]
        top_k = top_k_indices(role_scores, k=len(relevant_by_role[role]))
        top_k_by_role[role] = top_k
        hit_count_by_role[role] = len(set(top_k).intersection(relevant_by_role[role]))

    top_k_sets = {role: tuple(indices) for role, indices in top_k_by_role.items()}
    distinct_top_k_sets = len(set(top_k_sets.values()))
    return {
        "schema_version": 1,
        "probe": "context_sphere_v3_role_separation",
        "claim_boundary": "Synthetic role-separation check only. This is not benchmark evidence.",
        "seed": seed,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "positive_weight": positive_weight,
        "final_loss": final_loss,
        "passed": final_loss < 0.05 and distinct_top_k_sets == len(ROLES) and min(hit_count_by_role.values()) >= 5,
        "roles": list(ROLES),
        "relevant_by_role": relevant_by_role,
        "top_k_by_role": top_k_by_role,
        "hit_count_by_role": hit_count_by_role,
        "distinct_top_k_sets": distinct_top_k_sets,
        "chunk_shape": list(chunks.shape),
        "role_embedding_shape": list(role_tensor.shape),
        "target_shape": list(target_tensor.shape),
    }
