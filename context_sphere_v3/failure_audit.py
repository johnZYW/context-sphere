"""Failure-mode auditing for trained Context Sphere v3 selector checkpoints."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

try:
    import torch
except ModuleNotFoundError:  # pragma: no cover - no-torch shell.
    torch = None  # type: ignore[assignment]

from context_sphere_v3.baselines import count_tokens
from context_sphere_v3.checkpoints import load_checkpoint_model
from context_sphere_v3.neural_selector import worker_role_embedding


COMMON_AMBIGUOUS_BASENAMES = {
    "__init__.py",
    "base.py",
    "conf.py",
    "config.py",
    "conftest.py",
    "core.py",
    "exceptions.py",
    "fields.py",
    "helpers.py",
    "models.py",
    "test_utils.py",
    "tests.py",
    "utils.py",
}


def _require_torch() -> None:
    if torch is None:
        raise RuntimeError("PyTorch is required for failure auditing")


def file_extension(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return suffix or "<none>"


def basename(path: str) -> str:
    return Path(path).name.lower()


def categorize_failure(item: dict[str, Any]) -> list[str]:
    """Attach lightweight proxy tags to a zero-recall validation item.

    These tags are triage hints, not causal proof. They point to examples that
    deserve manual inspection before changing the dataset recipe.
    """

    touched_files = [str(path) for path in item.get("touched_files", [])]
    chunks = list(item.get("chunks", []))
    problem_statement = str(item.get("problem_statement", ""))
    names = [basename(path) for path in touched_files]
    name_counts = Counter(names)
    extensions = {file_extension(path) for path in touched_files}
    tags = []
    if len(touched_files) >= 10:
        tags.append("many_touched_files_ge_10")
    if len(chunks) >= 10:
        tags.append("many_visible_chunks_ge_10")
    if count_tokens(problem_statement) >= 500:
        tags.append("long_problem_statement_ge_500_tokens")
    if any(count > 1 for count in name_counts.values()) or any(name in COMMON_AMBIGUOUS_BASENAMES for name in names):
        tags.append("ambiguous_or_common_basename_proxy")
    non_python_exts = {ext for ext in extensions if ext not in {".py", ".pyi", ".rst", ".md", ".txt"}}
    if non_python_exts:
        tags.append("non_python_or_config_extension_proxy")
    if not tags:
        tags.append("no_obvious_proxy_pattern")
    return tags


def score_item(
    model: Any,
    item: dict[str, Any],
    *,
    role_dim: int,
    device: "torch.device",
    top_k: int,
) -> dict[str, Any]:
    _require_torch()
    chunks_tensor = item["chunk_embeddings"].to(device=device, dtype=torch.float32).unsqueeze(0)
    target = item["target_chunk_labels"].to(device=device, dtype=torch.float32)
    role_tensor = torch.tensor([worker_role_embedding(dim=role_dim)], dtype=torch.float32, device=device)
    with torch.no_grad():
        scores = model(chunks_tensor, role_tensor)[0]
    k = min(top_k, int(scores.shape[0]))
    top_indices = torch.topk(scores, k=k).indices.detach().cpu().tolist() if k > 0 else []
    target_indices = torch.nonzero(target > 0.5, as_tuple=False).flatten().detach().cpu().tolist()
    selected = set(int(index) for index in top_indices)
    positives = set(int(index) for index in target_indices)
    recall = None if not positives else len(selected & positives) / len(positives)
    chunks = list(item.get("chunks", []))
    return {
        "instance_id": str(item.get("instance_id", "")),
        "repo": str(item.get("repo", "")),
        "chunk_count": len(chunks),
        "visible_token_count": count_tokens(str(item.get("problem_statement", ""))),
        "touched_file_count": len(item.get("touched_files", [])),
        "touched_chunk_count": len(target_indices),
        "touched_files": [str(path) for path in item.get("touched_files", [])],
        "touched_chunk_ids": [str(chunks[index]["chunk_id"]) for index in target_indices if index < len(chunks)],
        "top_indices": top_indices,
        "top_chunk_ids": [str(chunks[index]["chunk_id"]) for index in top_indices if index < len(chunks)],
        "top_scores": [float(scores[index].detach().cpu().item()) for index in top_indices],
        "recall_at_k": recall,
        "zero_recall": bool(positives and recall == 0.0),
        "failure_tags": categorize_failure(item) if positives and recall == 0.0 else [],
        "top_chunk_text_preview": [
            str(chunks[index].get("text", "")).replace("\n", " ")[:240] for index in top_indices if index < len(chunks)
        ],
    }


def audit_checkpoint_failures(
    *,
    checkpoint_path: str | Path,
    val_dataset_path: str | Path,
    top_k: int = 5,
    device: str = "cpu",
    max_items: int = 0,
) -> dict[str, Any]:
    _require_torch()
    dataset = torch.load(val_dataset_path, map_location="cpu")
    items = list(dataset["items"])
    if max_items > 0:
        items = items[:max_items]
    if not items:
        raise ValueError("validation dataset is empty")

    fallback_chunk_dim = int(items[0]["chunk_embeddings"].shape[1])
    torch_device = torch.device(device)
    model, config, payload = load_checkpoint_model(
        checkpoint_path,
        device=torch_device,
        fallback_chunk_dim=fallback_chunk_dim,
    )
    rows = [score_item(model, item, role_dim=config.role_dim, device=torch_device, top_k=top_k) for item in items]
    positive_rows = [row for row in rows if row["touched_chunk_count"] > 0]
    zero_recall_rows = [row for row in positive_rows if row["zero_recall"]]
    recalls = [float(row["recall_at_k"]) for row in positive_rows if row["recall_at_k"] is not None]
    tag_counts = Counter(tag for row in zero_recall_rows for tag in row["failure_tags"])
    repo_counts = Counter(row["repo"] for row in zero_recall_rows)
    extension_counts = Counter(
        file_extension(path)
        for row in zero_recall_rows
        for path in row.get("touched_files", [])
    )
    return {
        "schema_version": 1,
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_step": payload.get("step"),
        "checkpoint_epoch": payload.get("epoch"),
        "val_dataset_path": str(val_dataset_path),
        "top_k": top_k,
        "evaluated_items": len(rows),
        "positive_label_items": len(positive_rows),
        "zero_positive_label_items": len(rows) - len(positive_rows),
        "mean_recall_at_k": mean(recalls) if recalls else 0.0,
        "zero_recall_count": len(zero_recall_rows),
        "zero_recall_rate_among_positive": len(zero_recall_rows) / max(1, len(positive_rows)),
        "zero_recall_tag_counts": dict(tag_counts.most_common()),
        "zero_recall_repo_counts_top20": dict(repo_counts.most_common(20)),
        "zero_recall_extension_counts": dict(extension_counts.most_common()),
        "high_level_read": {
            "long_context_proxy_count": tag_counts.get("many_visible_chunks_ge_10", 0)
            + tag_counts.get("long_problem_statement_ge_500_tokens", 0),
            "many_touched_files_proxy_count": tag_counts.get("many_touched_files_ge_10", 0),
            "naming_proxy_count": tag_counts.get("ambiguous_or_common_basename_proxy", 0),
            "non_python_or_config_proxy_count": tag_counts.get("non_python_or_config_extension_proxy", 0),
        },
        "rows": rows,
        "zero_recall_rows": zero_recall_rows,
    }


def render_failure_audit_markdown(report: dict[str, Any], *, max_examples: int = 20) -> str:
    lines = [
        "# Context Sphere v3 Failure Audit",
        "",
        "## Summary",
        "",
        f"- Checkpoint: `{report['checkpoint_path']}`",
        f"- Step / epoch: `{report.get('checkpoint_step')}` / `{report.get('checkpoint_epoch')}`",
        f"- Evaluated items: `{report['evaluated_items']}`",
        f"- Positive-label items: `{report['positive_label_items']}`",
        f"- Mean Recall@{report['top_k']}: `{report['mean_recall_at_k']:.6f}`",
        f"- Zero-recall count: `{report['zero_recall_count']}`",
        f"- Zero-recall rate among positive-label items: `{report['zero_recall_rate_among_positive']:.6f}`",
        "",
        "## Proxy Tag Counts",
        "",
    ]
    for tag, count in report["zero_recall_tag_counts"].items():
        lines.append(f"- `{tag}`: `{count}`")
    lines.extend(["", "## Zero-Recall Examples", ""])
    for row in report["zero_recall_rows"][:max_examples]:
        lines.extend(
            [
                f"### {row['instance_id']}",
                "",
                f"- Repo: `{row['repo']}`",
                f"- Chunks / touched files / touched chunks: `{row['chunk_count']}` / `{row['touched_file_count']}` / `{row['touched_chunk_count']}`",
                f"- Tags: {', '.join(f'`{tag}`' for tag in row['failure_tags'])}",
                f"- Touched files: {', '.join(f'`{path}`' for path in row['touched_files'][:10])}",
                f"- Top chunk ids: {', '.join(f'`{chunk_id}`' for chunk_id in row['top_chunk_ids'])}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"
