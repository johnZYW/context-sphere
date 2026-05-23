"""Batch schema and shape validation for Context Sphere v3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from context_sphere_v3.roles import validate_role


Shape = tuple[int, ...]


def tensor_shape(value: Any, name: str) -> Shape:
    """Read a tensor-like shape without depending on a specific tensor library."""
    shape = getattr(value, "shape", None)
    if shape is None:
        raise TypeError(f"{name} must expose a .shape attribute")
    try:
        return tuple(int(dim) for dim in shape)
    except TypeError as exc:
        raise TypeError(f"{name}.shape must be iterable, got {shape!r}") from exc


def assert_shape(value: Any, expected: Shape, name: str) -> None:
    observed = tensor_shape(value, name)
    if observed != expected:
        raise ValueError(f"{name} shape mismatch: expected {expected}, observed {observed}")


@dataclass(frozen=True)
class ContextSphereBatch:
    """Central batch object for Role-Conditioned Temporal Folding.

    Schema:
    - issue_id: stable issue or benchmark instance id.
    - chunks: tensor-like object with shape (B, N, C).
    - chunk_text: nested text chunks with length B and N per batch item.
    - chunk_metadata: nested metadata dicts with length B and N per batch item.
    - role: one of "pm", "worker", or "reviewer".
    - role_embedding: tensor-like object with shape (B, R).
    - target_relevance: optional tensor-like labels with shape (B, N).
    """

    issue_id: str
    chunks: Any
    chunk_text: list[list[str]]
    chunk_metadata: list[list[dict[str, Any]]]
    role: str
    role_embedding: Any
    target_relevance: Any | None = None

    def validate(self) -> "ContextSphereBatch":
        if not self.issue_id:
            raise ValueError("issue_id must be non-empty")
        validate_role(self.role)

        chunk_shape = tensor_shape(self.chunks, "chunks")
        if len(chunk_shape) != 3:
            raise ValueError(f"chunks must have shape (B, N, C), observed {chunk_shape}")
        batch_size, chunk_count, _chunk_dim = chunk_shape

        role_shape = tensor_shape(self.role_embedding, "role_embedding")
        if len(role_shape) != 2:
            raise ValueError(f"role_embedding must have shape (B, R), observed {role_shape}")
        assert_shape(self.role_embedding, (batch_size, role_shape[1]), "role_embedding")

        if len(self.chunk_text) != batch_size:
            raise ValueError("chunk_text outer length must match batch size B")
        if len(self.chunk_metadata) != batch_size:
            raise ValueError("chunk_metadata outer length must match batch size B")
        for batch_index, texts in enumerate(self.chunk_text):
            if len(texts) != chunk_count:
                raise ValueError(f"chunk_text[{batch_index}] length must match chunk count N")
        for batch_index, metadata in enumerate(self.chunk_metadata):
            if len(metadata) != chunk_count:
                raise ValueError(f"chunk_metadata[{batch_index}] length must match chunk count N")

        if self.target_relevance is not None:
            assert_shape(self.target_relevance, (batch_size, chunk_count), "target_relevance")

        return self
