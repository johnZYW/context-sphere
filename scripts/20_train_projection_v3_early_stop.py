#!/usr/bin/env python3
"""Train Context Projection v3 with Worker-margin checkpointing.

v3 intentionally keeps the v2 data recipe:

- same v1 grouped validation split;
- same Worker-positive oversampling;
- same persona-specific loss weights.

The behavioral change is checkpoint selection. The saved model is the checkpoint
with the largest validation Worker margin:

    worker_positive_mean - worker_negative_mean

This protects the fragile Worker distribution from being overwritten by the
easier PM/Reviewer objectives in later epochs.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader
from tqdm.auto import tqdm
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup


def load_v2_module() -> Any:
    script_path = Path(__file__).with_name("19_train_projection_v2_balanced.py")
    spec = importlib.util.spec_from_file_location("projection_v2", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load v2 helpers from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def is_better_worker_checkpoint(candidate: dict[str, Any], current: dict[str, Any] | None) -> bool:
    """Return True when candidate should replace current best checkpoint.

    Primary key is Worker margin. Ties prefer Worker recall at threshold 0.5,
    then lower validation loss, then earlier global step.
    """

    if current is None:
        return True
    candidate_key = (
        float(candidate.get("worker_margin", float("-inf"))),
        float(candidate.get("worker_recall_at_0_5", float("-inf"))),
        -float(candidate.get("validation_loss", float("inf"))),
        -int(candidate.get("global_step", 0)),
    )
    current_key = (
        float(current.get("worker_margin", float("-inf"))),
        float(current.get("worker_recall_at_0_5", float("-inf"))),
        -float(current.get("validation_loss", float("inf"))),
        -int(current.get("global_step", 0)),
    )
    return candidate_key > current_key


@torch.no_grad()
def validation_loss(
    model: torch.nn.Module,
    loader: DataLoader,
    device: str,
) -> float:
    model.eval()
    losses: list[float] = []
    for batch in tqdm(loader, desc="val-loss", leave=False):
        input_ids, attention_mask, token_type_ids, labels, weights, _persona_ids = tuple(
            tensor.to(device) for tensor in batch
        )
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
        losses.append(float((loss_raw * weights).mean().detach().cpu()))
    return float(np.mean(losses)) if losses else 0.0


def checkpoint_metric_from_eval(
    *,
    epoch: int,
    global_step: int,
    train_loss: float,
    val_loss: float,
    val_metrics: dict[str, Any],
) -> dict[str, Any]:
    worker = val_metrics["by_persona"]["WORKER"]
    worker_distribution = worker["distribution"]
    worker_metrics = worker["metrics_at_0_5"]
    return {
        "epoch": epoch,
        "global_step": global_step,
        "train_loss": float(train_loss),
        "validation_loss": float(val_loss),
        "worker_positive_mean": worker_distribution["positive_mean"],
        "worker_negative_mean": worker_distribution["negative_mean"],
        "worker_margin": worker_distribution["mean_margin"],
        "worker_recall_at_0_5": worker_metrics["recall"],
        "worker_f1_at_0_5": worker_metrics["f1"],
    }


def save_checkpoint(
    *,
    model: torch.nn.Module,
    tokenizer: Any,
    output_dir: Path,
    metric: dict[str, Any],
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    (output_dir / "best_worker_margin.json").write_text(
        json.dumps(metric, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="outputs/datasets/context_projection_v1.jsonl")
    parser.add_argument("--v1-training-report", default="outputs/models/context_projector_v1_training_report.json")
    parser.add_argument("--model-name", default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    parser.add_argument("--output-dir", default="models/context_projector_v3")
    parser.add_argument("--report-out", default="outputs/models/context_projector_v3_training_report.json")
    parser.add_argument("--validation-fraction", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--eval-batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
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

    v2 = load_v2_module()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    rows = v2.load_rows(Path(args.dataset))
    train_rows, val_rows, val_cases = v2.load_split_from_v1_report(
        rows,
        report_path=Path(args.v1_training_report) if args.v1_training_report else None,
        validation_fraction=args.validation_fraction,
        seed=args.seed,
    )
    balanced_train_rows, oversampling = v2.oversample_worker_positives(train_rows, seed=args.seed)
    positive_weights = {
        "WORKER": args.worker_positive_weight,
        "REVIEWER": args.reviewer_positive_weight,
        "PM": args.pm_positive_weight,
    }
    device = v2.choose_device(args.device)

    print(
        json.dumps(
            {
                "dataset": args.dataset,
                "model_name": args.model_name,
                "device": device,
                "train_counts_before": v2.count_by_persona_label(train_rows),
                "train_counts_after": v2.count_by_persona_label(balanced_train_rows),
                "val_counts": v2.count_by_persona_label(val_rows),
                "oversampling": oversampling,
                "positive_weights": positive_weights,
                "negative_weight": args.negative_weight,
                "learning_rate": args.learning_rate,
                "checkpoint_selection": "maximize_worker_margin",
                "validation_case_slugs": val_cases,
            },
            indent=2,
            sort_keys=True,
        )
    )

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModelForSequenceClassification.from_pretrained(args.model_name, num_labels=1)
    model.to(device)

    train_dataset = v2.encode_rows(
        balanced_train_rows,
        tokenizer=tokenizer,
        max_document_chars=args.max_document_chars,
        max_length=args.max_length,
        positive_weights=positive_weights,
        negative_weight=args.negative_weight,
    )
    val_dataset = v2.encode_rows(
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

    output_dir = Path(args.output_dir)
    start = time.time()
    epoch_reports: list[dict[str, Any]] = []
    best_metric: dict[str, Any] | None = None
    global_step = 0

    for epoch in range(1, args.epochs + 1):
        model.train()
        train_losses: list[float] = []
        progress = tqdm(train_loader, desc=f"train epoch {epoch}", leave=False)
        for batch in progress:
            input_ids, attention_mask, token_type_ids, labels, weights, _persona_ids = tuple(
                tensor.to(device) for tensor in batch
            )
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
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            optimizer.step()
            scheduler.step()
            global_step += 1
            train_losses.append(float(loss.detach().cpu()))
            progress.set_postfix(loss=f"{train_losses[-1]:.4f}", step=global_step)

        train_loss = float(np.mean(train_losses)) if train_losses else 0.0
        val_loss = validation_loss(model, val_loader, device=device)
        val_pred = v2.predict_dataset(model, val_loader, device=device)
        val_metrics = v2.evaluate_predictions(val_pred)
        checkpoint_metric = checkpoint_metric_from_eval(
            epoch=epoch,
            global_step=global_step,
            train_loss=train_loss,
            val_loss=val_loss,
            val_metrics=val_metrics,
        )
        improved = is_better_worker_checkpoint(checkpoint_metric, best_metric)
        if improved:
            best_metric = checkpoint_metric
            save_checkpoint(
                model=model,
                tokenizer=tokenizer,
                output_dir=output_dir,
                metric=checkpoint_metric,
            )

        epoch_report = {
            "epoch": epoch,
            "global_step": global_step,
            "train": {"loss": train_loss},
            "validation_loss": val_loss,
            "validation": val_metrics,
            "checkpoint_metric": checkpoint_metric,
            "saved_as_best": improved,
        }
        epoch_reports.append(epoch_report)
        print(json.dumps(epoch_report["checkpoint_metric"] | {"saved_as_best": improved}, indent=2, sort_keys=True))

    if best_metric is None:
        raise RuntimeError("Training produced no checkpoint metric.")

    best_model = AutoModelForSequenceClassification.from_pretrained(output_dir)
    best_model.to(device)
    best_pred = v2.predict_dataset(best_model, val_loader, device=device)
    best_eval = v2.evaluate_predictions(best_pred)
    training_seconds = time.time() - start

    report = {
        "schema_version": 1,
        "dataset": args.dataset,
        "model_name": args.model_name,
        "output_dir": str(output_dir),
        "device": device,
        "training_seconds": training_seconds,
        "checkpoint_selection": {
            "metric": "worker_margin",
            "definition": "WORKER positive mean validation score minus WORKER negative mean validation score",
            "best": best_metric,
        },
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
            "train_counts_before": v2.count_by_persona_label(train_rows),
            "train_counts_after": v2.count_by_persona_label(balanced_train_rows),
            "val_counts": v2.count_by_persona_label(val_rows),
            "oversampling": oversampling,
        },
        "epoch_reports": epoch_reports,
        "validation": best_eval,
        "success_criterion": {
            "worker_positive_mean_gt_worker_negative_mean": (
                best_eval["by_persona"]["WORKER"]["distribution"]["positive_mean"]
                > best_eval["by_persona"]["WORKER"]["distribution"]["negative_mean"]
            )
        },
    }
    v2.write_json(Path(args.report_out), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
