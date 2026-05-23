"""Memory strategies and probes for Context Sphere v3."""

from __future__ import annotations

from typing import Any

try:
    import torch
except ModuleNotFoundError:  # pragma: no cover - no-torch shell.
    torch = None  # type: ignore[assignment]

from context_sphere_v3.model import RoleConditionedEvoformer
from context_sphere_v3.model import RoleConditionedEvoformerConfig


def _require_torch() -> None:
    if torch is None:
        raise RuntimeError("PyTorch is required for Context Sphere v3 memory probes")


def estimate_full_attention_bytes(*, batch_size: int, chunk_count: int, pair_dim: int, dtype_bytes: int = 4) -> dict[str, int]:
    pair_matrix = batch_size * chunk_count * chunk_count * pair_dim * dtype_bytes
    attention = batch_size * chunk_count * chunk_count * chunk_count * dtype_bytes
    return {
        "pair_matrix_bytes": pair_matrix,
        "attention_ijk_bytes": attention,
        "total_bytes": pair_matrix + attention,
    }


def prefilter_top_k_chunks(
    chunks: "torch.Tensor",
    role_embedding: "torch.Tensor",
    *,
    keep_top_k: int,
) -> tuple["torch.Tensor", list[int]]:
    """Select a deterministic role-conditioned subset before full pair folding.

    This is a memory strategy for local probing, not the final scientific claim.
    It keeps the vectorized triangular update feasible by reducing N before the
    O(N^3) attention tensor is materialized.
    """
    _require_torch()
    assert chunks.ndim == 3, f"chunks must have shape (B, N, C), observed {tuple(chunks.shape)}"
    assert role_embedding.ndim == 2, f"role_embedding must have shape (B, R), observed {tuple(role_embedding.shape)}"
    batch_size, chunk_count, chunk_dim = chunks.shape
    role_batch_size, role_dim = role_embedding.shape
    assert batch_size == 1, "memory probe currently supports B=1"
    assert role_batch_size == batch_size, "role batch must match chunk batch"
    if keep_top_k <= 0 or keep_top_k > chunk_count:
        raise ValueError(f"keep_top_k must be in [1, {chunk_count}], got {keep_top_k}")

    if role_dim < chunk_dim:
        role_projection = torch.nn.functional.pad(role_embedding, (0, chunk_dim - role_dim))
    else:
        role_projection = role_embedding[:, :chunk_dim]
    assert role_projection.shape == (batch_size, chunk_dim)
    scores = torch.einsum("bnc,bc->bn", chunks, role_projection)
    assert scores.shape == (batch_size, chunk_count)
    indices = torch.topk(scores[0], k=keep_top_k).indices.sort().values
    selected = chunks[:, indices, :]
    assert selected.shape == (batch_size, keep_top_k, chunk_dim)
    return selected, [int(index) for index in indices.detach().cpu().tolist()]


def run_memory_probe(
    *,
    chunk_count: int = 2000,
    keep_top_k: int = 128,
    chunk_dim: int = 8,
    role_dim: int = 4,
    pair_dim: int = 8,
    seed: int = 19,
    memory_limit_gb: float = 64.0,
) -> dict[str, Any]:
    _require_torch()
    torch.manual_seed(seed)
    chunks = torch.randn(1, chunk_count, chunk_dim)
    role_embedding = torch.randn(1, role_dim)
    selected_chunks, selected_indices = prefilter_top_k_chunks(
        chunks,
        role_embedding,
        keep_top_k=keep_top_k,
    )
    config = RoleConditionedEvoformerConfig(chunk_dim=chunk_dim, role_dim=role_dim, pair_dim=pair_dim, num_layers=1)
    model = RoleConditionedEvoformer(config)
    with torch.no_grad():
        relevance = model(selected_chunks, role_embedding)

    full_estimate = estimate_full_attention_bytes(batch_size=1, chunk_count=chunk_count, pair_dim=pair_dim)
    selected_estimate = estimate_full_attention_bytes(batch_size=1, chunk_count=keep_top_k, pair_dim=pair_dim)
    memory_limit_bytes = int(memory_limit_gb * 1024**3)
    return {
        "schema_version": 1,
        "probe": "context_sphere_v3_memory_probe",
        "claim_boundary": "Local memory strategy probe only. This is not benchmark evidence.",
        "strategy": "role_conditioned_top_k_prefilter_before_triangular_folding",
        "seed": seed,
        "chunk_count": chunk_count,
        "keep_top_k": keep_top_k,
        "chunk_dim": chunk_dim,
        "role_dim": role_dim,
        "pair_dim": pair_dim,
        "memory_limit_gb": memory_limit_gb,
        "full_attention_estimate": full_estimate,
        "selected_attention_estimate": selected_estimate,
        "selected_under_memory_limit": selected_estimate["total_bytes"] < memory_limit_bytes,
        "full_attention_under_memory_limit": full_estimate["total_bytes"] < memory_limit_bytes,
        "selected_indices_count": len(selected_indices),
        "selected_indices_preview": selected_indices[:20],
        "relevance_shape": list(relevance.shape),
        "relevance_finite": bool(torch.isfinite(relevance).all().item()),
        "passed": (
            chunk_count >= 2000
            and len(selected_indices) == keep_top_k
            and selected_estimate["total_bytes"] < memory_limit_bytes
            and bool(torch.isfinite(relevance).all().item())
        ),
        "limitation": "Top-k prefiltering changes the candidate set before folding; later benchmark slices must compare it fairly against full-context and RAG baselines.",
    }
