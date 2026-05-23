"""Model interfaces for Context Sphere v3.

Slice 0 intentionally defines contracts only. The mathematical implementation
begins in later slices and must preserve role-conditioned pair initialization,
triangular relational update, and folded-pair relevance extraction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from context_sphere_v3.data_parser import tensor_shape

try:  # Keep early-slice interfaces importable before PyTorch is installed.
    import torch
    from torch import nn
except ModuleNotFoundError:  # pragma: no cover - exercised by no-torch shells.
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]

if torch is not None:
    from context_sphere_v3.triangular_attention import TriangularSelfAttention


@dataclass(frozen=True)
class RoleConditionedEvoformerConfig:
    chunk_dim: int = 768
    role_dim: int = 768
    pair_dim: int = 128
    num_layers: int = 1
    triangular_tile_size: int | None = None
    use_gradient_checkpointing: bool = False

    def validate(self) -> "RoleConditionedEvoformerConfig":
        for name, value in (
            ("chunk_dim", self.chunk_dim),
            ("role_dim", self.role_dim),
            ("pair_dim", self.pair_dim),
            ("num_layers", self.num_layers),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.triangular_tile_size is not None and self.triangular_tile_size <= 0:
            raise ValueError("triangular_tile_size must be positive when set")
        return self


class _NoTorchRoleConditionedEvoformer:
    """Interface placeholder used only before PyTorch is installed."""

    def __init__(self, config: RoleConditionedEvoformerConfig | None = None) -> None:
        self.config = (config or RoleConditionedEvoformerConfig()).validate()

    def validate_inputs(self, chunks: Any, role_embedding: Any) -> tuple[int, int, int]:
        chunk_shape = tensor_shape(chunks, "chunks")
        role_shape = tensor_shape(role_embedding, "role_embedding")
        if len(chunk_shape) != 3:
            raise ValueError(f"chunks must have shape (B, N, C), observed {chunk_shape}")
        if len(role_shape) != 2:
            raise ValueError(f"role_embedding must have shape (B, R), observed {role_shape}")
        batch_size, chunk_count, chunk_dim = chunk_shape
        role_batch_size, role_dim = role_shape
        if role_batch_size != batch_size:
            raise ValueError("Batch mismatch between chunks and role_embedding")
        if chunk_dim != self.config.chunk_dim:
            raise ValueError(f"Unexpected chunk embedding dimension: {chunk_dim}")
        if role_dim != self.config.role_dim:
            raise ValueError(f"Unexpected role embedding dimension: {role_dim}")
        return batch_size, chunk_count, chunk_dim

    def forward(self, chunks: Any, role_embedding: Any) -> Any:
        self.validate_inputs(chunks, role_embedding)
        raise NotImplementedError("Slice 2 will implement vectorized role-conditioned triangular folding")


if nn is not None:

    class RoleConditionedEvoformer(nn.Module):
        """Role-conditioned pair folding model.

        Input shapes:
        - chunks: FloatTensor[B, N, C]
        - role_embedding: FloatTensor[B, R]

        Internal shapes:
        - z: FloatTensor[B, N, N, D]

        Output shape:
        - relevance: FloatTensor[B, N]
        """

        def __init__(self, config: RoleConditionedEvoformerConfig | None = None) -> None:
            super().__init__()
            self.config = (config or RoleConditionedEvoformerConfig()).validate()
            self.pair_init = nn.Linear(self.config.chunk_dim * 2 + self.config.role_dim, self.config.pair_dim)
            self.layers = nn.ModuleList(
                TriangularSelfAttention(
                    self.config.pair_dim,
                    tile_size=self.config.triangular_tile_size,
                    use_gradient_checkpointing=self.config.use_gradient_checkpointing,
                )
                for _ in range(self.config.num_layers)
            )
            self.relevance_head = nn.Linear(self.config.pair_dim, 1)

        def validate_inputs(self, chunks: Any, role_embedding: Any) -> tuple[int, int, int]:
            chunk_shape = tensor_shape(chunks, "chunks")
            role_shape = tensor_shape(role_embedding, "role_embedding")
            if len(chunk_shape) != 3:
                raise ValueError(f"chunks must have shape (B, N, C), observed {chunk_shape}")
            if len(role_shape) != 2:
                raise ValueError(f"role_embedding must have shape (B, R), observed {role_shape}")
            batch_size, chunk_count, chunk_dim = chunk_shape
            role_batch_size, role_dim = role_shape
            if role_batch_size != batch_size:
                raise ValueError("Batch mismatch between chunks and role_embedding")
            if chunk_dim != self.config.chunk_dim:
                raise ValueError(f"Unexpected chunk embedding dimension: {chunk_dim}")
            if role_dim != self.config.role_dim:
                raise ValueError(f"Unexpected role embedding dimension: {role_dim}")
            return batch_size, chunk_count, chunk_dim

        def initialize_pairs(self, chunks: "torch.Tensor", role_embedding: "torch.Tensor") -> "torch.Tensor":
            batch_size, chunk_count, chunk_dim = self.validate_inputs(chunks, role_embedding)
            role_dim = int(role_embedding.shape[1])
            assert chunks.shape == (batch_size, chunk_count, chunk_dim)
            assert role_embedding.shape == (batch_size, role_dim)

            chunks_i = chunks.unsqueeze(2).expand(batch_size, chunk_count, chunk_count, chunk_dim)
            chunks_j = chunks.unsqueeze(1).expand(batch_size, chunk_count, chunk_count, chunk_dim)
            roles = role_embedding.unsqueeze(1).unsqueeze(2).expand(batch_size, chunk_count, chunk_count, role_dim)
            assert chunks_i.shape == (batch_size, chunk_count, chunk_count, chunk_dim)
            assert chunks_j.shape == (batch_size, chunk_count, chunk_count, chunk_dim)
            assert roles.shape == (batch_size, chunk_count, chunk_count, role_dim)

            pair_input = torch.cat([chunks_i, chunks_j, roles], dim=-1)
            assert pair_input.shape == (
                batch_size,
                chunk_count,
                chunk_count,
                self.config.chunk_dim * 2 + self.config.role_dim,
            )
            z = self.pair_init(pair_input)
            assert z.shape == (batch_size, chunk_count, chunk_count, self.config.pair_dim)
            return z

        def forward(self, chunks: "torch.Tensor", role_embedding: "torch.Tensor") -> "torch.Tensor":
            batch_size, chunk_count, _ = self.validate_inputs(chunks, role_embedding)
            z = self.initialize_pairs(chunks, role_embedding)
            assert z.shape == (batch_size, chunk_count, chunk_count, self.config.pair_dim)
            for layer in self.layers:
                z = layer(z)
                assert z.shape == (batch_size, chunk_count, chunk_count, self.config.pair_dim)

            z_summed = z.sum(dim=2)
            assert z_summed.shape == (batch_size, chunk_count, self.config.pair_dim)
            relevance_logits = self.relevance_head(z_summed).squeeze(-1)
            assert relevance_logits.shape == (batch_size, chunk_count)
            relevance = torch.sigmoid(relevance_logits)
            assert relevance.shape == (batch_size, chunk_count)
            return relevance

else:
    RoleConditionedEvoformer = _NoTorchRoleConditionedEvoformer
