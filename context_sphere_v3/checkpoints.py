"""Checkpoint loading helpers for Context Sphere v3 selector models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import torch
except ModuleNotFoundError:  # pragma: no cover - no-torch shell.
    torch = None  # type: ignore[assignment]

from context_sphere_v3.model import RoleConditionedEvoformer
from context_sphere_v3.model import RoleConditionedEvoformerConfig
from context_sphere_v3.neural_selector import DEFAULT_ROLE_DIM


def _require_torch() -> None:
    if torch is None:
        raise RuntimeError("PyTorch is required to load Context Sphere checkpoints")


def config_from_checkpoint_payload(
    payload: dict[str, Any],
    *,
    fallback_chunk_dim: int | None = None,
    fallback_role_dim: int = DEFAULT_ROLE_DIM,
) -> RoleConditionedEvoformerConfig:
    """Recover the model config from a training checkpoint.

    Early cloud checkpoints stored the optimizer/run config rather than a pure
    model config, so this function also infers missing dimensions from tensor
    shapes.
    """

    config_payload = dict(payload.get("config") or {})
    state_dict = payload.get("model_state_dict") or payload.get("state_dict")
    if not isinstance(state_dict, dict):
        raise ValueError("checkpoint payload does not contain a model state dict")

    pair_init_weight = state_dict.get("pair_init.weight")
    relevance_weight = state_dict.get("relevance_head.weight")
    if pair_init_weight is None or relevance_weight is None:
        raise ValueError("checkpoint does not look like a RoleConditionedEvoformer state")

    pair_dim = int(config_payload.get("pair_dim") or relevance_weight.shape[1])
    role_dim = int(config_payload.get("role_dim") or fallback_role_dim)
    pair_input_dim = int(pair_init_weight.shape[1])
    if "chunk_dim" in config_payload:
        chunk_dim = int(config_payload["chunk_dim"])
    elif fallback_chunk_dim is not None:
        chunk_dim = int(fallback_chunk_dim)
        role_dim = pair_input_dim - 2 * chunk_dim
    else:
        chunk_dim = (pair_input_dim - role_dim) // 2

    if chunk_dim <= 0 or role_dim <= 0:
        raise ValueError(f"invalid inferred dims: chunk_dim={chunk_dim}, role_dim={role_dim}")
    if pair_input_dim != chunk_dim * 2 + role_dim:
        raise ValueError(
            "checkpoint dimensions are inconsistent: "
            f"pair_input_dim={pair_input_dim}, chunk_dim={chunk_dim}, role_dim={role_dim}"
        )

    tile_size = config_payload.get("triangular_tile_size", config_payload.get("tile_size"))
    gradient_checkpointing = bool(
        config_payload.get("use_gradient_checkpointing", config_payload.get("gradient_checkpointing", False))
    )
    return RoleConditionedEvoformerConfig(
        chunk_dim=chunk_dim,
        role_dim=role_dim,
        pair_dim=pair_dim,
        num_layers=int(config_payload.get("num_layers", 1)),
        triangular_tile_size=int(tile_size) if tile_size is not None else None,
        use_gradient_checkpointing=gradient_checkpointing,
    ).validate()


def load_checkpoint_model(
    checkpoint_path: str | Path,
    *,
    device: str | "torch.device" = "cpu",
    fallback_chunk_dim: int | None = None,
) -> tuple[Any, RoleConditionedEvoformerConfig, dict[str, Any]]:
    """Load a trained selector checkpoint and return `(model, config, payload)`."""

    _require_torch()
    torch_device = torch.device(device)
    payload = torch.load(checkpoint_path, map_location=torch_device)
    config = config_from_checkpoint_payload(payload, fallback_chunk_dim=fallback_chunk_dim)
    model = RoleConditionedEvoformer(config).to(torch_device)
    model.load_state_dict(payload["model_state_dict"])
    model.eval()
    return model, config, payload
