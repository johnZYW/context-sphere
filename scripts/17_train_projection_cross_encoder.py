#!/usr/bin/env python3
"""Train the Context Projection cross-encoder.

This consumes `outputs/datasets/context_projection_v1.jsonl` and trains a
lightweight discriminative ranker over pairs:

    query = "Persona: {persona} | Task: {problem_statement}"
    document = row["node"]["node_text"]

The split is grouped by `case_slug` to prevent issue-level leakage.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sentence_transformers import CrossEncoder, InputExample
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
from torch.utils.data import DataLoader


def choose_device(requested: str) -> str:
    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
            rows.append(row)
    return rows


def make_pair(row: dict[str, Any], max_document_chars: int) -> tuple[str, str]:
    persona = row.get("persona") or ""
    problem = ((row.get("task") or {}).get("problem_statement") or "").strip()
    node_text = ((row.get("node") or {}).get("node_text") or "").strip()
    query = f"Persona: {persona} | Task: {problem}"
    document = node_text[:max_document_chars]
    return query, document


def grouped_split(
    rows: list[dict[str, Any]], validation_fraction: float, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_case[str(row["case_slug"])].append(row)

    cases = sorted(by_case)
    rng = random.Random(seed)
    rng.shuffle(cases)
    val_count = max(1, int(math.ceil(len(cases) * validation_fraction)))
    val_cases = set(cases[:val_count])
    train_rows = []
    val_rows = []
    for case, case_rows in by_case.items():
        if case in val_cases:
            val_rows.extend(case_rows)
        else:
            train_rows.extend(case_rows)
    return train_rows, val_rows, sorted(val_cases)


def rows_to_examples(rows: list[dict[str, Any]], max_document_chars: int) -> list[InputExample]:
    examples = []
    for row in rows:
        query, document = make_pair(row, max_document_chars=max_document_chars)
        examples.append(InputExample(texts=[query, document], label=float(row["label"])))
    return examples


def row_labels(rows: list[dict[str, Any]]) -> np.ndarray:
    return np.asarray([int(row["label"]) for row in rows], dtype=np.int64)


def normalize_scores(scores: Any) -> np.ndarray:
    arr = np.asarray(scores, dtype=np.float64).reshape(-1)
    if len(arr) == 0:
        return arr
    # CrossEncoder.predict may return either logits or sigmoid-like scores
    # depending on model configuration. Normalize only when needed.
    if arr.min() < 0.0 or arr.max() > 1.0:
        arr = 1.0 / (1.0 + np.exp(-arr))
    return arr


def evaluate_model(
    model: CrossEncoder,
    rows: list[dict[str, Any]],
    max_document_chars: int,
    batch_size: int,
    threshold: float,
) -> dict[str, Any]:
    pairs = [list(make_pair(row, max_document_chars=max_document_chars)) for row in rows]
    labels = row_labels(rows)
    raw_scores = model.predict(
        pairs,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    scores = normalize_scores(raw_scores)
    preds = (scores >= threshold).astype(np.int64)
    report = classification_report(
        labels,
        preds,
        labels=[0, 1],
        target_names=["negative", "positive"],
        output_dict=True,
        zero_division=0,
    )
    cm = confusion_matrix(labels, preds, labels=[0, 1]).tolist()

    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, preds, labels=[0, 1], zero_division=0
    )
    return {
        "threshold": threshold,
        "classification_report": report,
        "confusion_matrix_labels": ["negative", "positive"],
        "confusion_matrix": cm,
        "positive_recall": float(recall[1]),
        "positive_precision": float(precision[1]),
        "positive_f1": float(f1[1]),
        "score_summary": {
            "min": float(scores.min()) if len(scores) else None,
            "max": float(scores.max()) if len(scores) else None,
            "mean": float(scores.mean()) if len(scores) else None,
        },
    }


def threshold_sweep(scores: np.ndarray, labels: np.ndarray) -> list[dict[str, float]]:
    rows = []
    for threshold in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.70]:
        preds = (scores >= threshold).astype(np.int64)
        precision, recall, f1, _ = precision_recall_fscore_support(
            labels, preds, labels=[1], zero_division=0
        )
        selected_rate = float(preds.mean()) if len(preds) else 0.0
        rows.append(
            {
                "threshold": threshold,
                "positive_precision": float(precision[0]),
                "positive_recall": float(recall[0]),
                "positive_f1": float(f1[0]),
                "selected_rate": selected_rate,
            }
        )
    return rows


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="outputs/datasets/context_projection_v1.jsonl")
    parser.add_argument("--model-name", default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    parser.add_argument("--output-dir", default="models/context_projector_v1")
    parser.add_argument("--report-out", default="outputs/models/context_projector_v1_training_report.json")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--validation-fraction", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--max-document-chars", type=int, default=6000)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--eval-threshold", type=float, default=0.5)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    dataset_path = Path(args.dataset)
    rows = load_rows(dataset_path)
    if not rows:
        raise ValueError(f"No rows loaded from {dataset_path}")

    train_rows, val_rows, val_cases = grouped_split(
        rows,
        validation_fraction=args.validation_fraction,
        seed=args.seed,
    )
    train_counts = Counter(row["label"] for row in train_rows)
    val_counts = Counter(row["label"] for row in val_rows)
    pos_weight_value = train_counts[0] / max(1, train_counts[1])
    device = choose_device(args.device)

    print(
        json.dumps(
            {
                "dataset": str(dataset_path),
                "total_rows": len(rows),
                "train_rows": len(train_rows),
                "val_rows": len(val_rows),
                "val_cases": val_cases,
                "train_counts": dict(train_counts),
                "val_counts": dict(val_counts),
                "pos_weight": pos_weight_value,
                "device": device,
                "model_name": args.model_name,
            },
            indent=2,
            sort_keys=True,
        )
    )

    train_examples = rows_to_examples(train_rows, max_document_chars=args.max_document_chars)
    train_loader = DataLoader(
        train_examples,
        shuffle=True,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
    )

    model = CrossEncoder(
        args.model_name,
        num_labels=1,
        max_length=args.max_length,
        device=device,
    )
    pos_weight = torch.tensor([pos_weight_value], dtype=torch.float32, device=device)
    loss_fct = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    output_dir = Path(args.output_dir)
    report_path = Path(args.report_out)
    start = time.time()
    model.fit(
        train_dataloader=train_loader,
        epochs=args.epochs,
        loss_fct=loss_fct,
        warmup_steps=max(1, int(len(train_loader) * args.epochs * 0.1)),
        optimizer_params={"lr": args.learning_rate},
        weight_decay=args.weight_decay,
        output_path=str(output_dir),
        save_best_model=False,
        show_progress_bar=True,
    )
    train_seconds = time.time() - start
    model.save(str(output_dir))

    eval_report = evaluate_model(
        model,
        val_rows,
        max_document_chars=args.max_document_chars,
        batch_size=args.batch_size,
        threshold=args.eval_threshold,
    )

    # Reuse predicted scores once for threshold diagnostics.
    val_pairs = [list(make_pair(row, max_document_chars=args.max_document_chars)) for row in val_rows]
    val_scores = normalize_scores(
        model.predict(
            val_pairs,
            batch_size=args.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
    )
    sweep = threshold_sweep(val_scores, row_labels(val_rows))

    report = {
        "schema_version": 1,
        "dataset": str(dataset_path),
        "model_name": args.model_name,
        "output_dir": str(output_dir),
        "device": device,
        "hyperparameters": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "max_length": args.max_length,
            "max_document_chars": args.max_document_chars,
            "validation_fraction": args.validation_fraction,
            "seed": args.seed,
            "pos_weight": pos_weight_value,
        },
        "split": {
            "total_rows": len(rows),
            "train_rows": len(train_rows),
            "val_rows": len(val_rows),
            "train_counts": {str(k): v for k, v in train_counts.items()},
            "val_counts": {str(k): v for k, v in val_counts.items()},
            "validation_case_slugs": val_cases,
        },
        "training_seconds": train_seconds,
        "validation": eval_report,
        "threshold_sweep": sweep,
    }
    write_json(report_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
