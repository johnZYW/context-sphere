"""Local micro-training utilities for the Context Sphere v3 neural selector."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

try:
    import torch
    import torch.nn.functional as F
except ModuleNotFoundError:  # pragma: no cover - no-torch shell.
    torch = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]

from context_sphere_v3.baselines import load_json
from context_sphere_v3.baselines import load_jsonl
from context_sphere_v3.baselines import split_problem_statement
from context_sphere_v3.model import RoleConditionedEvoformer
from context_sphere_v3.model import RoleConditionedEvoformerConfig
from context_sphere_v3.roles import ROLE_WORKER


DEFAULT_CHUNK_DIM = 24
DEFAULT_ROLE_DIM = 4


def _require_torch() -> None:
    if torch is None or F is None:
        raise RuntimeError("PyTorch is required for neural selector micro-training")


def hashed_text_embedding(text: str, *, dim: int = DEFAULT_CHUNK_DIM) -> list[float]:
    values = [0.0] * dim
    for token in text.lower().replace("/", " ").replace("_", " ").replace(".", " ").split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % dim
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        values[index] += sign
    norm = sum(value * value for value in values) ** 0.5 or 1.0
    return [value / norm for value in values]


def worker_role_embedding(*, dim: int = DEFAULT_ROLE_DIM) -> list[float]:
    if dim < 4:
        raise ValueError("role dim must be at least 4")
    return [1.0, 0.0, 0.0, 0.0] + [0.0] * (dim - 4)


def labels_for_chunks(chunks: list[dict[str, Any]], touched_chunk_ids: list[str]) -> list[float]:
    touched = set(touched_chunk_ids)
    return [1.0 if str(chunk["chunk_id"]) in touched else 0.0 for chunk in chunks]


def load_selector_examples(
    *,
    scaffold_dir: str | Path,
    visible_sources_path: str | Path,
    labels_path: str | Path,
    chunk_dim: int = DEFAULT_CHUNK_DIM,
) -> list[dict[str, Any]]:
    subset = load_json(Path(scaffold_dir) / "subset.json")
    visible = {str(row["instance_id"]): row for row in load_jsonl(visible_sources_path)}
    labels = {str(row["instance_id"]): row for row in load_jsonl(labels_path)}
    examples = []
    for instance_id in [str(value) for value in subset["instance_ids"]]:
        problem_statement = str(visible[instance_id].get("problem_statement", ""))
        chunks = split_problem_statement(problem_statement)
        chunk_embeddings = [hashed_text_embedding(str(chunk["text"]), dim=chunk_dim) for chunk in chunks]
        target = labels_for_chunks(chunks, list(labels[instance_id]["touched_chunk_ids"]))
        examples.append(
            {
                "instance_id": instance_id,
                "chunks": chunks,
                "chunk_embeddings": chunk_embeddings,
                "target": target,
                "touched_files": list(labels[instance_id]["touched_files"]),
                "touched_chunk_ids": list(labels[instance_id]["touched_chunk_ids"]),
            }
        )
    return examples


def train_neural_selector(
    *,
    scaffold_dir: str | Path = "outputs/swebench_lite_10",
    visible_sources_path: str | Path = "outputs/swebench_lite_10/leakage_safe_visible_sources.jsonl",
    labels_path: str | Path = "outputs/swebench_lite_10/worker_labels.jsonl",
    out_path: str | Path = "outputs/reports/context_sphere_v3_neural_microtrain.json",
    state_path: str | Path = "outputs/models/context_sphere_v3_neural_selector.pt",
    epochs: int = 50,
    learning_rate: float = 0.01,
    positive_weight: float = 4.0,
    seed: int = 20260522,
    chunk_dim: int = DEFAULT_CHUNK_DIM,
    role_dim: int = DEFAULT_ROLE_DIM,
    pair_dim: int = 16,
    tile_size: int = 8,
) -> dict[str, Any]:
    _require_torch()
    torch.manual_seed(seed)
    examples = load_selector_examples(
        scaffold_dir=scaffold_dir,
        visible_sources_path=visible_sources_path,
        labels_path=labels_path,
        chunk_dim=chunk_dim,
    )
    config = RoleConditionedEvoformerConfig(
        chunk_dim=chunk_dim,
        role_dim=role_dim,
        pair_dim=pair_dim,
        num_layers=1,
        triangular_tile_size=tile_size,
        use_gradient_checkpointing=True,
    )
    model = RoleConditionedEvoformer(config)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    role = torch.tensor([worker_role_embedding(dim=role_dim)], dtype=torch.float32)
    losses = []
    for _epoch in range(epochs):
        epoch_loss = 0.0
        for example in examples:
            target_values = example["target"]
            if not any(target_values):
                continue
            chunks = torch.tensor([example["chunk_embeddings"]], dtype=torch.float32)
            target = torch.tensor([target_values], dtype=torch.float32)
            weights = torch.where(target == 1.0, torch.full_like(target, positive_weight), torch.ones_like(target))
            optimizer.zero_grad()
            predictions = model(chunks, role)
            loss = F.binary_cross_entropy(predictions, target, weight=weights)
            loss.backward()
            optimizer.step()
            epoch_loss += float(loss.item())
        losses.append(epoch_loss / max(1, len(examples)))

    state_out = Path(state_path)
    state_out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schema_version": 1,
            "model_state_dict": model.state_dict(),
            "config": {
                "chunk_dim": chunk_dim,
                "role_dim": role_dim,
                "pair_dim": pair_dim,
                "num_layers": 1,
                "triangular_tile_size": tile_size,
                "use_gradient_checkpointing": True,
            },
            "role": ROLE_WORKER,
            "claim_boundary": "Local micro-trained selector state only; not cloud training or SWE-bench evidence.",
        },
        state_out,
    )
    report = {
        "schema_version": 1,
        "run": "context_sphere_v3_neural_selector_microtrain",
        "passed": bool(losses),
        "epochs": epochs,
        "learning_rate": learning_rate,
        "positive_weight": positive_weight,
        "seed": seed,
        "instance_count": len(examples),
        "final_loss": losses[-1] if losses else None,
        "losses": losses,
        "state_path": str(state_out),
        "config": {
            "chunk_dim": chunk_dim,
            "role_dim": role_dim,
            "pair_dim": pair_dim,
            "triangular_tile_size": tile_size,
            "use_gradient_checkpointing": True,
        },
        "claim_boundary": "Local micro-training only. This does not justify cloud training unless selector metrics beat BM25.",
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def load_neural_selector(state_path: str | Path) -> tuple[Any, dict[str, Any]]:
    _require_torch()
    payload = torch.load(state_path, map_location="cpu")
    config_payload = payload["config"]
    config = RoleConditionedEvoformerConfig(**config_payload)
    model = RoleConditionedEvoformer(config)
    model.load_state_dict(payload["model_state_dict"])
    model.eval()
    return model, config_payload


def neural_scores_for_chunks(model: Any, chunks: list[dict[str, Any]], *, chunk_dim: int, role_dim: int) -> list[float]:
    _require_torch()
    embeddings = [hashed_text_embedding(str(chunk["text"]), dim=chunk_dim) for chunk in chunks]
    chunk_tensor = torch.tensor([embeddings], dtype=torch.float32)
    role_tensor = torch.tensor([worker_role_embedding(dim=role_dim)], dtype=torch.float32)
    with torch.no_grad():
        scores = model(chunk_tensor, role_tensor)[0]
    return [float(value) for value in scores.detach().cpu().tolist()]
