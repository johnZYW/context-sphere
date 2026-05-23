"""Vectorized triangular relational update for Context Sphere v3."""

from __future__ import annotations

import math

try:  # Keep Slice 0/1 importable in environments before PyTorch is installed.
    import torch
    from torch import nn
    from torch.utils.checkpoint import checkpoint
except ModuleNotFoundError:  # pragma: no cover - exercised by no-torch shells.
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    checkpoint = None  # type: ignore[assignment]


def _require_torch() -> None:
    if torch is None:
        raise RuntimeError("PyTorch is required for Context Sphere v3 triangular attention")


def assert_pair_tensor(name: str, value: "torch.Tensor") -> tuple[int, int, int, int]:
    _require_torch()
    assert value.ndim == 4, f"{name} must have shape (B, N, N, D), observed {tuple(value.shape)}"
    batch_size, chunk_count, chunk_count_2, pair_dim = value.shape
    assert chunk_count == chunk_count_2, f"{name} pair matrix must be square, observed {tuple(value.shape)}"
    assert pair_dim > 0, f"{name} pair dimension must be positive"
    return int(batch_size), int(chunk_count), int(chunk_count_2), int(pair_dim)


def triangular_update_vectorized(
    z: "torch.Tensor",
    q_ij: "torch.Tensor",
    k_ik: "torch.Tensor",
    v_ik: "torch.Tensor",
) -> "torch.Tensor":
    """Apply z_ij <- z_ij + sum_k softmax_k(q_ij dot k_ik) v_ik.

    Shapes:
    - z: FloatTensor[B, N, N, D]
    - q_ij: FloatTensor[B, N, N, D]
    - k_ik: FloatTensor[B, N, N, D]
    - v_ik: FloatTensor[B, N, N, D]
    - attn_ijk: FloatTensor[B, N, N, N]
    - updated_z: FloatTensor[B, N, N, D]
    """
    _require_torch()
    batch_size, chunk_count, _, pair_dim = assert_pair_tensor("z", z)
    assert q_ij.shape == (batch_size, chunk_count, chunk_count, pair_dim), "q_ij shape mismatch"
    assert k_ik.shape == (batch_size, chunk_count, chunk_count, pair_dim), "k_ik shape mismatch"
    assert v_ik.shape == (batch_size, chunk_count, chunk_count, pair_dim), "v_ik shape mismatch"

    scores = torch.einsum("bijd,bikd->bijk", q_ij, k_ik) / math.sqrt(pair_dim)
    assert scores.shape == (batch_size, chunk_count, chunk_count, chunk_count)
    attn_ijk = torch.softmax(scores, dim=-1)
    assert attn_ijk.shape == (batch_size, chunk_count, chunk_count, chunk_count)
    update = torch.einsum("bijk,bikd->bijd", attn_ijk, v_ik)
    assert update.shape == (batch_size, chunk_count, chunk_count, pair_dim)
    updated_z = z + update
    assert updated_z.shape == (batch_size, chunk_count, chunk_count, pair_dim)
    return updated_z


def triangular_update_tiled(
    z: "torch.Tensor",
    q_ij: "torch.Tensor",
    k_ik: "torch.Tensor",
    v_ik: "torch.Tensor",
    *,
    tile_size: int,
) -> "torch.Tensor":
    """Tiled triangular update over the j dimension.

    This keeps the same i-j-k math as the vectorized implementation while
    materializing only B x N x tile_j x N attention scores at a time.
    """
    _require_torch()
    batch_size, chunk_count, _, pair_dim = assert_pair_tensor("z", z)
    assert q_ij.shape == (batch_size, chunk_count, chunk_count, pair_dim), "q_ij shape mismatch"
    assert k_ik.shape == (batch_size, chunk_count, chunk_count, pair_dim), "k_ik shape mismatch"
    assert v_ik.shape == (batch_size, chunk_count, chunk_count, pair_dim), "v_ik shape mismatch"
    if tile_size <= 0:
        raise ValueError("tile_size must be positive")

    updated = z.clone()
    scale = math.sqrt(pair_dim)
    for start in range(0, chunk_count, tile_size):
        end = min(chunk_count, start + tile_size)
        q_tile = q_ij[:, :, start:end, :]
        scores = torch.einsum("bijd,bikd->bijk", q_tile, k_ik) / scale
        assert scores.shape == (batch_size, chunk_count, end - start, chunk_count)
        attn_ijk = torch.softmax(scores, dim=-1)
        update = torch.einsum("bijk,bikd->bijd", attn_ijk, v_ik)
        assert update.shape == (batch_size, chunk_count, end - start, pair_dim)
        updated[:, :, start:end, :] = z[:, :, start:end, :] + update
    assert updated.shape == (batch_size, chunk_count, chunk_count, pair_dim)
    return updated


def triangular_update_reference(
    z: "torch.Tensor",
    q_ij: "torch.Tensor",
    k_ik: "torch.Tensor",
    v_ik: "torch.Tensor",
) -> "torch.Tensor":
    """Small explicit mathematical reference for tests only.

    This intentionally uses loops over B/i/j for readability and must not be
    used as production inference. Tests compare it against the vectorized path.
    """
    _require_torch()
    batch_size, chunk_count, _, pair_dim = assert_pair_tensor("z", z)
    assert q_ij.shape == (batch_size, chunk_count, chunk_count, pair_dim), "q_ij shape mismatch"
    assert k_ik.shape == (batch_size, chunk_count, chunk_count, pair_dim), "k_ik shape mismatch"
    assert v_ik.shape == (batch_size, chunk_count, chunk_count, pair_dim), "v_ik shape mismatch"

    updated = z.clone()
    scale = math.sqrt(pair_dim)
    for b in range(batch_size):
        for i in range(chunk_count):
            for j in range(chunk_count):
                scores = torch.empty(chunk_count, dtype=z.dtype, device=z.device)
                for k in range(chunk_count):
                    scores[k] = torch.dot(q_ij[b, i, j], k_ik[b, i, k]) / scale
                weights = torch.softmax(scores, dim=0)
                folded = torch.zeros(pair_dim, dtype=z.dtype, device=z.device)
                for k in range(chunk_count):
                    folded = folded + weights[k] * v_ik[b, i, k]
                updated[b, i, j] = z[b, i, j] + folded
    assert updated.shape == (batch_size, chunk_count, chunk_count, pair_dim)
    return updated


if nn is not None:

    class TriangularSelfAttention(nn.Module):
        """AlphaFold-style triangular update preserving the i-j-k relation."""

        def __init__(
            self,
            dim: int,
            *,
            tile_size: int | None = None,
            use_gradient_checkpointing: bool = False,
        ) -> None:
            super().__init__()
            self.dim = dim
            self.tile_size = tile_size
            self.use_gradient_checkpointing = use_gradient_checkpointing
            self.q_proj = nn.Linear(dim, dim)
            self.k_proj = nn.Linear(dim, dim)
            self.v_proj = nn.Linear(dim, dim)

        def forward(self, z: "torch.Tensor") -> "torch.Tensor":
            batch_size, chunk_count, _, pair_dim = assert_pair_tensor("z", z)
            assert pair_dim == self.dim, f"expected pair dim {self.dim}, observed {pair_dim}"
            q_ij = self.q_proj(z)
            k_ik = self.k_proj(z)
            v_ik = self.v_proj(z)
            assert q_ij.shape == (batch_size, chunk_count, chunk_count, pair_dim)
            assert k_ik.shape == (batch_size, chunk_count, chunk_count, pair_dim)
            assert v_ik.shape == (batch_size, chunk_count, chunk_count, pair_dim)
            if self.tile_size is not None:
                if self.use_gradient_checkpointing and self.training:
                    assert checkpoint is not None

                    def _tiled_update(
                        z_arg: "torch.Tensor",
                        q_arg: "torch.Tensor",
                        k_arg: "torch.Tensor",
                        v_arg: "torch.Tensor",
                    ) -> "torch.Tensor":
                        return triangular_update_tiled(z_arg, q_arg, k_arg, v_arg, tile_size=self.tile_size or 1)

                    return checkpoint(_tiled_update, z, q_ij, k_ik, v_ik, use_reentrant=False)
                return triangular_update_tiled(z, q_ij, k_ik, v_ik, tile_size=self.tile_size)
            if self.use_gradient_checkpointing and self.training:
                assert checkpoint is not None
                return checkpoint(triangular_update_vectorized, z, q_ij, k_ik, v_ik, use_reentrant=False)
            return triangular_update_vectorized(z, q_ij, k_ik, v_ik)

else:

    class TriangularSelfAttention:  # pragma: no cover - no-torch placeholder.
        def __init__(self, dim: int) -> None:
            self.dim = dim

        def forward(self, z: object) -> object:
            raise RuntimeError("PyTorch is required for Context Sphere v3 triangular attention")
