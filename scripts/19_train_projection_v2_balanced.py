#!/usr/bin/env python3
"""Train Context Projection v2 with persona-balanced routing.

Compared with v1, this script:

- oversamples WORKER positive rows in the training split until they match the
  PM/REVIEWER positive count;
- applies per-persona, per-label loss weights in a custom PyTorch loop;
- reports validation distribution means and threshold-0.5 metrics by persona.
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
from sklearn.metrics import precision_recall_fscore_support
from torch.utils.data import DataLoader, TensorDataset
from tqdm.auto import tqdm
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup


PERSONA_TO_ID = {"WORKER": 0, "PM": 1, "REVIEWER": 2}
ID_TO_PERSONA = {value: key for key, value in PERSONA_TO_ID.items()}


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
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
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


def load_split_from_v1_report(
    rows: list[dict[str, Any]], report_path: Path | None, validation_fraction: float, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    if report_path and report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        val_cases = set(report["split"]["validation_case_slugs"])
        train_rows = [row for row in rows if row["case_slug"] not in val_cases]
        val_rows = [row for row in rows if row["case_slug"] in val_cases]
        return train_rows, val_rows, sorted(val_cases)
    return grouped_split(rows, validation_fraction=validation_fraction, seed=seed)


def count_by_persona_label(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for row in rows:
        counts[f"{row['persona']}_{int(row['label'])}"] += 1
    return dict(sorted(counts.items()))


def oversample_worker_positives(rows: list[dict[str, Any]], seed: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rng = random.Random(seed)
    positives_by_persona: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if int(row["label"]) == 1:
            positives_by_persona[row["persona"]].append(row)

    worker_pos = positives_by_persona.get("WORKER", [])
    target = max(
        len(positives_by_persona.get("PM", [])),
        len(positives_by_persona.get("REVIEWER", [])),
        len(worker_pos),
    )
    extras: list[dict[str, Any]] = []
    if worker_pos and len(worker_pos) < target:
        for _ in range(target - len(worker_pos)):
            clone = dict(rng.choice(worker_pos))
            clone["_oversampled"] = True
            extras.append(clone)
    balanced = list(rows) + extras
    rng.shuffle(balanced)
    return balanced, {
        "worker_positive_before": len(worker_pos),
        "target_positive_count": target,
        "worker_positive_added": len(extras),
        "rows_before": len(rows),
        "rows_after": len(balanced),
    }


def sample_weight(row: dict[str, Any], positive_weights: dict[str, float], negative_weight: float) -> float:
    if int(row["label"]) == 1:
        return float(positive_weights[row["persona"]])
    return float(negative_weight)


def encode_rows(
    rows: list[dict[str, Any]],
    tokenizer: AutoTokenizer,
    max_document_chars: int,
    max_length: int,
    positive_weights: dict[str, float],
    negative_weight: float,
) -> TensorDataset:
    queries = []
    documents = []
    labels = []
    weights = []
    persona_ids = []
    for row in rows:
        query, document = make_pair(row, max_document_chars=max_document_chars)
        queries.append(query)
        documents.append(document)
        labels.append(float(row["label"]))
        weights.append(sample_weight(row, positive_weights, negative_weight))
        persona_ids.append(PERSONA_TO_ID[row["persona"]])
    tokenized = tokenizer(
        queries,
        documents,
        padding=True,
        truncation=True,
        max_length=max_length,
        return_tensors="pt",
    )
    tensors = [
        tokenized["input_ids"],
        tokenized["attention_mask"],
    ]
    if "token_type_ids" in tokenized:
        tensors.append(tokenized["token_type_ids"])
    else:
        tensors.append(torch.zeros_like(tokenized["input_ids"]))
    tensors.extend(
        [
            torch.tensor(labels, dtype=torch.float32),
            torch.tensor(weights, dtype=torch.float32),
            torch.tensor(persona_ids, dtype=torch.long),
        ]
    )
    return TensorDataset(*tensors)


def batch_to_device(batch: tuple[torch.Tensor, ...], device: str) -> tuple[torch.Tensor, ...]:
    return tuple(t.to(device) for t in batch)


def run_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    scheduler: Any,
    device: str,
    grad_clip: float,
) -> dict[str, float]:
    model.train()
    losses = []
    progress = tqdm(loader, desc="train", leave=False)
    for batch in progress:
        input_ids, attention_mask, token_type_ids, labels, weights, _persona_ids = batch_to_device(batch, device)
        optimizer.zero_grad(set_to_none=True)
        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
        )
        logits = outputs.logits.reshape(-1)
        loss_raw = torch.nn.functional.binary_cross_entropy_with_logits(
            logits,
            labels,
            reduction="none",
        )
        loss = (loss_raw * weights).mean()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        optimizer.step()
        scheduler.step()
        losses.append(float(loss.detach().cpu()))
        progress.set_postfix(loss=f"{losses[-1]:.4f}")
    return {"loss": float(np.mean(losses)) if losses else 0.0}


@torch.no_grad()
def predict_dataset(model: torch.nn.Module, loader: DataLoader, device: str) -> dict[str, np.ndarray]:
    model.eval()
    scores = []
    labels = []
    persona_ids = []
    for batch in tqdm(loader, desc="eval", leave=False):
        input_ids, attention_mask, token_type_ids, batch_labels, _weights, batch_persona_ids = batch_to_device(batch, device)
        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
        )
        probs = torch.sigmoid(outputs.logits.reshape(-1))
        scores.extend(probs.detach().cpu().numpy().tolist())
        labels.extend(batch_labels.detach().cpu().numpy().astype(int).tolist())
        persona_ids.extend(batch_persona_ids.detach().cpu().numpy().astype(int).tolist())
    return {
        "scores": np.asarray(scores, dtype=np.float64),
        "labels": np.asarray(labels, dtype=np.int64),
        "persona_ids": np.asarray(persona_ids, dtype=np.int64),
    }


def metrics_at_threshold(labels: np.ndarray, scores: np.ndarray, threshold: float = 0.5) -> dict[str, Any]:
    preds = (scores >= threshold).astype(np.int64)
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels,
        preds,
        labels=[1],
        zero_division=0,
    )
    tp = int(((preds == 1) & (labels == 1)).sum())
    fp = int(((preds == 1) & (labels == 0)).sum())
    tn = int(((preds == 0) & (labels == 0)).sum())
    fn = int(((preds == 0) & (labels == 1)).sum())
    return {
        "threshold": threshold,
        "precision": float(precision[0]),
        "recall": float(recall[0]),
        "f1": float(f1[0]),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "selected_rate": float(preds.mean()) if len(preds) else 0.0,
        "support_positive": int(labels.sum()),
        "support_negative": int((labels == 0).sum()),
    }


def distribution_summary(labels: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
    pos_scores = scores[labels == 1]
    neg_scores = scores[labels == 0]
    return {
        "positive_mean": float(pos_scores.mean()) if len(pos_scores) else None,
        "negative_mean": float(neg_scores.mean()) if len(neg_scores) else None,
        "positive_median": float(np.median(pos_scores)) if len(pos_scores) else None,
        "negative_median": float(np.median(neg_scores)) if len(neg_scores) else None,
        "positive_min": float(pos_scores.min()) if len(pos_scores) else None,
        "positive_max": float(pos_scores.max()) if len(pos_scores) else None,
        "negative_min": float(neg_scores.min()) if len(neg_scores) else None,
        "negative_max": float(neg_scores.max()) if len(neg_scores) else None,
        "mean_margin": float(pos_scores.mean() - neg_scores.mean()) if len(pos_scores) and len(neg_scores) else None,
    }


def evaluate_predictions(pred: dict[str, np.ndarray]) -> dict[str, Any]:
    labels = pred["labels"]
    scores = pred["scores"]
    persona_ids = pred["persona_ids"]
    results = {
        "overall": {
            "metrics_at_0_5": metrics_at_threshold(labels, scores, threshold=0.5),
            "distribution": distribution_summary(labels, scores),
        },
        "by_persona": {},
    }
    for persona, persona_id in PERSONA_TO_ID.items():
        mask = persona_ids == persona_id
        persona_labels = labels[mask]
        persona_scores = scores[mask]
        results["by_persona"][persona] = {
            "row_count": int(mask.sum()),
            "metrics_at_0_5": metrics_at_threshold(persona_labels, persona_scores, threshold=0.5),
            "distribution": distribution_summary(persona_labels, persona_scores),
        }
    return results


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="outputs/datasets/context_projection_v1.jsonl")
    parser.add_argument("--v1-training-report", default="outputs/models/context_projector_v1_training_report.json")
    parser.add_argument("--model-name", default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    parser.add_argument("--output-dir", default="models/context_projector_v2")
    parser.add_argument("--report-out", default="outputs/models/context_projector_v2_training_report.json")
    parser.add_argument("--validation-fraction", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--eval-batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--max-document-chars", type=int, default=6000)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--worker-positive-weight", type=float, default=18.0)
    parser.add_argument("--reviewer-positive-weight", type=float, default=10.0)
    parser.add_argument("--pm-positive-weight", type=float, default=8.0)
    parser.add_argument("--negative-weight", type=float, default=1.0)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    rows = load_rows(Path(args.dataset))
    train_rows, val_rows, val_cases = load_split_from_v1_report(
        rows,
        report_path=Path(args.v1_training_report) if args.v1_training_report else None,
        validation_fraction=args.validation_fraction,
        seed=args.seed,
    )
    balanced_train_rows, oversampling = oversample_worker_positives(train_rows, seed=args.seed)
    positive_weights = {
        "WORKER": args.worker_positive_weight,
        "REVIEWER": args.reviewer_positive_weight,
        "PM": args.pm_positive_weight,
    }
    device = choose_device(args.device)

    print(
        json.dumps(
            {
                "dataset": args.dataset,
                "model_name": args.model_name,
                "device": device,
                "train_counts_before": count_by_persona_label(train_rows),
                "train_counts_after": count_by_persona_label(balanced_train_rows),
                "val_counts": count_by_persona_label(val_rows),
                "oversampling": oversampling,
                "positive_weights": positive_weights,
                "negative_weight": args.negative_weight,
                "validation_case_slugs": val_cases,
            },
            indent=2,
            sort_keys=True,
        )
    )

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModelForSequenceClassification.from_pretrained(args.model_name, num_labels=1)
    model.to(device)

    train_dataset = encode_rows(
        balanced_train_rows,
        tokenizer=tokenizer,
        max_document_chars=args.max_document_chars,
        max_length=args.max_length,
        positive_weights=positive_weights,
        negative_weight=args.negative_weight,
    )
    val_dataset = encode_rows(
        val_rows,
        tokenizer=tokenizer,
        max_document_chars=args.max_document_chars,
        max_length=args.max_length,
        positive_weights=positive_weights,
        negative_weight=args.negative_weight,
    )
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.eval_batch_size, shuffle=False)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    total_steps = len(train_loader) * args.epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=max(1, int(total_steps * 0.1)),
        num_training_steps=total_steps,
    )

    start = time.time()
    epoch_reports = []
    for epoch in range(1, args.epochs + 1):
        train_metrics = run_epoch(
            model,
            train_loader,
            optimizer=optimizer,
            scheduler=scheduler,
            device=device,
            grad_clip=args.grad_clip,
        )
        val_pred = predict_dataset(model, val_loader, device=device)
        val_metrics = evaluate_predictions(val_pred)
        epoch_report = {
            "epoch": epoch,
            "train": train_metrics,
            "validation": val_metrics,
        }
        epoch_reports.append(epoch_report)
        worker_dist = val_metrics["by_persona"]["WORKER"]["distribution"]
        worker_m = val_metrics["by_persona"]["WORKER"]["metrics_at_0_5"]
        print(
            json.dumps(
                {
                    "epoch": epoch,
                    "train_loss": train_metrics["loss"],
                    "worker_positive_mean": worker_dist["positive_mean"],
                    "worker_negative_mean": worker_dist["negative_mean"],
                    "worker_mean_margin": worker_dist["mean_margin"],
                    "worker_recall_at_0_5": worker_m["recall"],
                    "worker_f1_at_0_5": worker_m["f1"],
                },
                indent=2,
                sort_keys=True,
            )
        )

    training_seconds = time.time() - start
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    final_pred = predict_dataset(model, val_loader, device=device)
    final_eval = evaluate_predictions(final_pred)
    report = {
        "schema_version": 1,
        "dataset": args.dataset,
        "model_name": args.model_name,
        "output_dir": str(output_dir),
        "device": device,
        "training_seconds": training_seconds,
        "hyperparameters": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "eval_batch_size": args.eval_batch_size,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "max_length": args.max_length,
            "max_document_chars": args.max_document_chars,
            "positive_weights": positive_weights,
            "negative_weight": args.negative_weight,
            "grad_clip": args.grad_clip,
            "seed": args.seed,
        },
        "split": {
            "validation_case_slugs": val_cases,
            "train_rows_before_oversampling": len(train_rows),
            "train_rows_after_oversampling": len(balanced_train_rows),
            "val_rows": len(val_rows),
            "train_counts_before": count_by_persona_label(train_rows),
            "train_counts_after": count_by_persona_label(balanced_train_rows),
            "val_counts": count_by_persona_label(val_rows),
            "oversampling": oversampling,
        },
        "epoch_reports": epoch_reports,
        "validation": final_eval,
        "success_criterion": {
            "worker_positive_mean_gt_worker_negative_mean": (
                final_eval["by_persona"]["WORKER"]["distribution"]["positive_mean"]
                > final_eval["by_persona"]["WORKER"]["distribution"]["negative_mean"]
            )
        },
    }
    write_json(Path(args.report_out), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
