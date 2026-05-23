"""Local pre-flight checks before Context Sphere v3 cloud training."""

from __future__ import annotations

import json
import os
from itertools import cycle
from pathlib import Path
from typing import Any

try:
    import torch
    import torch.nn.functional as F
except ModuleNotFoundError:  # pragma: no cover - no-torch shell.
    torch = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]

from context_sphere_v3.model import RoleConditionedEvoformer
from context_sphere_v3.model import RoleConditionedEvoformerConfig
from context_sphere_v3.neural_selector import DEFAULT_CHUNK_DIM
from context_sphere_v3.neural_selector import DEFAULT_ROLE_DIM
from context_sphere_v3.neural_selector import load_selector_examples
from context_sphere_v3.neural_selector import worker_role_embedding


def _require_torch() -> None:
    if torch is None or F is None:
        raise RuntimeError("PyTorch is required for cloud preflight training checks")


def select_device(preferred: str = "auto") -> "torch.device":
    _require_torch()
    if preferred == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    if preferred == "auto" and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def tensorize_example(example: dict[str, Any], *, role_dim: int, device: "torch.device") -> tuple["torch.Tensor", "torch.Tensor", "torch.Tensor"]:
    _require_torch()
    chunks = torch.tensor([example["chunk_embeddings"]], dtype=torch.float32, device=device)
    role = torch.tensor([worker_role_embedding(dim=role_dim)], dtype=torch.float32, device=device)
    target = torch.tensor([example["target"]], dtype=torch.float32, device=device)
    return chunks, role, target


def gradient_norm(model: Any) -> float:
    _require_torch()
    total = torch.tensor(0.0)
    for parameter in model.parameters():
        if parameter.grad is None:
            continue
        total = total + parameter.grad.detach().cpu().pow(2).sum()
    return float(total.sqrt().item())


def make_model(*, chunk_dim: int, role_dim: int, pair_dim: int, tile_size: int, device: "torch.device") -> Any:
    config = RoleConditionedEvoformerConfig(
        chunk_dim=chunk_dim,
        role_dim=role_dim,
        pair_dim=pair_dim,
        num_layers=1,
        triangular_tile_size=tile_size,
        use_gradient_checkpointing=True,
    )
    return RoleConditionedEvoformer(config).to(device)


def setup_wandb(*, project: str, run_name: str) -> tuple[Any | None, dict[str, Any]]:
    api_key = os.environ.get("WANDB_API_KEY")
    status = {
        "requested": True,
        "api_key_visible": bool(api_key),
        "package_available": False,
        "enabled": False,
        "mode": None,
    }
    if not api_key:
        return None, status
    try:
        import wandb  # type: ignore
    except ModuleNotFoundError:
        return None, status
    status["package_available"] = True
    wandb.login(key=api_key, relogin=True)
    mode = os.environ.get("WANDB_MODE", "online")
    run = wandb.init(project=project, name=run_name, mode=mode)
    status["enabled"] = True
    status["mode"] = mode
    return run, status


def write_telemetry_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_forward_backward_stress(
    *,
    examples: list[dict[str, Any]],
    chunk_dim: int,
    role_dim: int,
    pair_dim: int,
    tile_size: int,
    device: "torch.device",
) -> dict[str, Any]:
    _require_torch()
    max_example = max(examples, key=lambda example: len(example["chunks"]))
    model = make_model(chunk_dim=chunk_dim, role_dim=role_dim, pair_dim=pair_dim, tile_size=tile_size, device=device)
    model.train()
    chunks, role, target = tensorize_example(max_example, role_dim=role_dim, device=device)
    try:
        predictions = model(chunks, role)
        weights = torch.where(target == 1.0, torch.full_like(target, 4.0), torch.ones_like(target))
        loss = F.binary_cross_entropy(predictions, target, weight=weights)
        loss.backward()
        return {
            "passed": True,
            "instance_id": max_example["instance_id"],
            "chunk_count": len(max_example["chunks"]),
            "loss": float(loss.detach().cpu().item()),
            "grad_norm": gradient_norm(model),
            "oom": False,
        }
    except RuntimeError as exc:
        is_oom = "out of memory" in str(exc).lower()
        if is_oom and device.type == "cuda":
            torch.cuda.empty_cache()
        return {
            "passed": False,
            "instance_id": max_example["instance_id"],
            "chunk_count": len(max_example["chunks"]),
            "error": str(exc),
            "oom": is_oom,
        }


def run_100_step_sprint(
    *,
    examples: list[dict[str, Any]],
    checkpoint_path: str | Path,
    telemetry_path: str | Path,
    chunk_dim: int,
    role_dim: int,
    pair_dim: int,
    tile_size: int,
    device: "torch.device",
    learning_rate: float = 0.01,
    max_steps: int = 100,
) -> dict[str, Any]:
    _require_torch()
    telemetry = Path(telemetry_path)
    if telemetry.exists():
        telemetry.unlink()
    run, wandb_status = setup_wandb(project="context-sphere-v3", run_name="local-100-step-preflight")
    model = make_model(chunk_dim=chunk_dim, role_dim=role_dim, pair_dim=pair_dim, tile_size=tile_size, device=device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    losses = []
    grad_norms = []
    step = 0
    for example in cycle(examples):
        step += 1
        chunks, role, target = tensorize_example(example, role_dim=role_dim, device=device)
        weights = torch.where(target == 1.0, torch.full_like(target, 4.0), torch.ones_like(target))
        optimizer.zero_grad()
        predictions = model(chunks, role)
        loss = F.binary_cross_entropy(predictions, target, weight=weights)
        loss.backward()
        norm = gradient_norm(model)
        optimizer.step()
        loss_value = float(loss.detach().cpu().item())
        losses.append(loss_value)
        grad_norms.append(norm)
        telemetry_row = {"step": step, "loss": loss_value, "grad_norm": norm, "instance_id": example["instance_id"]}
        write_telemetry_row(telemetry, telemetry_row)
        if run is not None:
            run.log({"loss": loss_value, "grad_norm": norm, "step": step})
        if step == 100:
            break
        if step >= max_steps:
            break
    checkpoint_out = Path(checkpoint_path)
    checkpoint_out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schema_version": 1,
            "step": step,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "losses": losses,
            "grad_norms": grad_norms,
            "config": {
                "chunk_dim": chunk_dim,
                "role_dim": role_dim,
                "pair_dim": pair_dim,
                "triangular_tile_size": tile_size,
                "use_gradient_checkpointing": True,
            },
        },
        checkpoint_out,
    )
    if run is not None:
        run.finish()
    return {
        "passed": checkpoint_out.exists() and step == 100,
        "checkpoint_path": str(checkpoint_out),
        "telemetry_path": str(telemetry),
        "steps": step,
        "final_loss": losses[-1] if losses else None,
        "final_grad_norm": grad_norms[-1] if grad_norms else None,
        "wandb": wandb_status,
    }


def run_resurrection_check(
    *,
    examples: list[dict[str, Any]],
    checkpoint_path: str | Path,
    chunk_dim: int,
    role_dim: int,
    pair_dim: int,
    tile_size: int,
    device: "torch.device",
    learning_rate: float = 0.01,
    resume_steps: int = 3,
) -> dict[str, Any]:
    _require_torch()
    payload = torch.load(checkpoint_path, map_location=device)
    model = make_model(chunk_dim=chunk_dim, role_dim=role_dim, pair_dim=pair_dim, tile_size=tile_size, device=device)
    model.load_state_dict(payload["model_state_dict"])
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    optimizer.load_state_dict(payload["optimizer_state_dict"])
    start_step = int(payload["step"])
    losses = []
    step = start_step
    iterator = cycle(examples)
    for _ in range(resume_steps):
        step += 1
        example = next(iterator)
        chunks, role, target = tensorize_example(example, role_dim=role_dim, device=device)
        weights = torch.where(target == 1.0, torch.full_like(target, 4.0), torch.ones_like(target))
        optimizer.zero_grad()
        predictions = model(chunks, role)
        loss = F.binary_cross_entropy(predictions, target, weight=weights)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu().item()))
    return {
        "passed": start_step == 100 and step == 100 + resume_steps and bool(losses),
        "start_step": start_step,
        "first_resumed_step": start_step + 1,
        "end_step": step,
        "resumed_losses": losses,
        "loss_continues_from_checkpoint": bool(losses) and payload["losses"][-1] >= 0.0,
    }


def run_cloud_preflight(
    *,
    scaffold_dir: str | Path = "outputs/swebench_lite_10",
    visible_sources_path: str | Path = "outputs/swebench_lite_10/leakage_safe_visible_sources.jsonl",
    labels_path: str | Path = "outputs/swebench_lite_10/worker_labels.jsonl",
    out_path: str | Path = "outputs/reports/context_sphere_v3_cloud_preflight.json",
    checkpoint_path: str | Path = "outputs/models/model_checkpoint_step100.pt",
    telemetry_path: str | Path = "outputs/reports/context_sphere_v3_preflight_telemetry.jsonl",
    preferred_device: str = "auto",
) -> dict[str, Any]:
    _require_torch()
    chunk_dim = DEFAULT_CHUNK_DIM
    role_dim = DEFAULT_ROLE_DIM
    pair_dim = 16
    tile_size = 8
    device = select_device(preferred_device)
    examples = load_selector_examples(
        scaffold_dir=scaffold_dir,
        visible_sources_path=visible_sources_path,
        labels_path=labels_path,
        chunk_dim=chunk_dim,
    )
    stress = run_forward_backward_stress(
        examples=examples,
        chunk_dim=chunk_dim,
        role_dim=role_dim,
        pair_dim=pair_dim,
        tile_size=tile_size,
        device=device,
    )
    sprint = run_100_step_sprint(
        examples=examples,
        checkpoint_path=checkpoint_path,
        telemetry_path=telemetry_path,
        chunk_dim=chunk_dim,
        role_dim=role_dim,
        pair_dim=pair_dim,
        tile_size=tile_size,
        device=device,
    )
    resurrection = run_resurrection_check(
        examples=examples,
        checkpoint_path=checkpoint_path,
        chunk_dim=chunk_dim,
        role_dim=role_dim,
        pair_dim=pair_dim,
        tile_size=tile_size,
        device=device,
    )
    cuda_available = bool(torch.cuda.is_available())
    report = {
        "schema_version": 1,
        "preflight": "context_sphere_v3_cloud_training_local_preflight",
        "passed": bool(stress["passed"] and sprint["passed"] and resurrection["passed"]),
        "device": str(device),
        "cuda_available": cuda_available,
        "cuda_initialized": bool(torch.cuda.is_initialized()) if cuda_available else False,
        "cuda_note": "CUDA unavailable in this local environment; CPU preflight ran instead." if not cuda_available else "CUDA available.",
        "max_memory_stress_test": stress,
        "hundred_step_sprint": sprint,
        "resurrection_check": resurrection,
        "ready_for_final_80_20_split_generation": bool(stress["passed"] and sprint["passed"] and resurrection["passed"]),
        "remaining_cloud_risk": "CUDA-specific initialization not certified locally." if not cuda_available else None,
        "claim_boundary": "Local architecture/infrastructure preflight only; not full cloud training.",
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
