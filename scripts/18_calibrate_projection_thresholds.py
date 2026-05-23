#!/usr/bin/env python3
"""Calibrate persona-specific Context Projection thresholds.

Rules:

- WORKER: highest threshold that guarantees recall >= target.
- PM/REVIEWER: threshold that maximizes positive-class F1.

The validation set is reconstructed from the v1 training report's held-out
`case_slug` list, so calibration uses the same split as training evaluation.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sentence_transformers import CrossEncoder
from sklearn.metrics import precision_recall_curve


def load_trainer_module() -> Any:
    script_path = Path(__file__).with_name("17_train_projection_cross_encoder.py")
    spec = importlib.util.spec_from_file_location("projection_trainer", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load trainer helpers from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def choose_device(requested: str) -> str:
    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def metrics_at_threshold(labels: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, Any]:
    preds = (scores >= threshold).astype(np.int64)
    tp = int(((preds == 1) & (labels == 1)).sum())
    fp = int(((preds == 1) & (labels == 0)).sum())
    tn = int(((preds == 0) & (labels == 0)).sum())
    fn = int(((preds == 0) & (labels == 1)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "threshold": float(threshold),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "selected_rate": float(preds.mean()) if len(preds) else 0.0,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "support_positive": int(labels.sum()),
        "support_negative": int((labels == 0).sum()),
        "selected_count": int(preds.sum()),
    }


def candidate_thresholds(scores: np.ndarray) -> list[float]:
    values = sorted({float(score) for score in scores})
    thresholds = [0.0]
    thresholds.extend(values)
    thresholds.append(1.0)
    return thresholds


def precision_recall_points(labels: np.ndarray, scores: np.ndarray) -> list[dict[str, float]]:
    precision, recall, thresholds = precision_recall_curve(labels, scores)
    points = []
    for idx, threshold in enumerate(thresholds):
        points.append(
            {
                "threshold": float(threshold),
                "precision": float(precision[idx]),
                "recall": float(recall[idx]),
                "f1": float(
                    2 * precision[idx] * recall[idx] / (precision[idx] + recall[idx])
                )
                if precision[idx] + recall[idx]
                else 0.0,
            }
        )
    # Add the final endpoint returned by sklearn where no threshold exists.
    if len(precision):
        points.append(
            {
                "threshold": 1.0,
                "precision": float(precision[-1]),
                "recall": float(recall[-1]),
                "f1": float(
                    2 * precision[-1] * recall[-1] / (precision[-1] + recall[-1])
                )
                if precision[-1] + recall[-1]
                else 0.0,
            }
        )
    return points


def choose_worker_threshold(
    labels: np.ndarray, scores: np.ndarray, target_recall: float
) -> dict[str, Any]:
    feasible = []
    for threshold in candidate_thresholds(scores):
        metric = metrics_at_threshold(labels, scores, threshold)
        if metric["recall"] >= target_recall:
            feasible.append(metric)
    if not feasible:
        best = max(
            (metrics_at_threshold(labels, scores, threshold) for threshold in candidate_thresholds(scores)),
            key=lambda item: (item["recall"], item["precision"], item["threshold"]),
        )
        best["selection_rule"] = "no_threshold_met_target_recall_best_available"
        best["target_recall"] = target_recall
        return best
    chosen = max(feasible, key=lambda item: (item["threshold"], item["precision"]))
    chosen["selection_rule"] = "highest_threshold_with_recall_at_least_target"
    chosen["target_recall"] = target_recall
    return chosen


def choose_f1_threshold(labels: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
    metrics = [metrics_at_threshold(labels, scores, threshold) for threshold in candidate_thresholds(scores)]
    chosen = max(metrics, key=lambda item: (item["f1"], item["recall"], item["precision"]))
    chosen["selection_rule"] = "max_positive_f1"
    return chosen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--model-dir", default=None)
    parser.add_argument("--training-report", default="outputs/models/context_projector_v1_training_report.json")
    parser.add_argument("--out", default="outputs/models/persona_thresholds.json")
    parser.add_argument("--scores-out", default="outputs/models/context_projector_v1_validation_scores.jsonl")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-document-chars", type=int, default=None)
    parser.add_argument("--worker-target-recall", type=float, default=0.85)
    parser.add_argument("--precision-warning-floor", type=float, default=0.05)
    args = parser.parse_args()

    trainer = load_trainer_module()
    report_path = Path(args.training_report)
    training_report = json.loads(report_path.read_text(encoding="utf-8"))
    dataset = Path(args.dataset or training_report["dataset"])
    model_dir = args.model_dir or training_report["output_dir"]
    max_document_chars = int(
        args.max_document_chars
        if args.max_document_chars is not None
        else training_report.get("hyperparameters", {}).get("max_document_chars", 6000)
    )
    val_cases = set(training_report["split"]["validation_case_slugs"])

    rows = [row for row in trainer.load_rows(dataset) if row["case_slug"] in val_cases]
    if not rows:
        raise ValueError("No validation rows found from training report case split.")

    pairs = [list(trainer.make_pair(row, max_document_chars=max_document_chars)) for row in rows]
    labels = np.asarray([int(row["label"]) for row in rows], dtype=np.int64)
    device = choose_device(args.device)
    model = CrossEncoder(model_dir, device=device)
    raw_scores = model.predict(
        pairs,
        batch_size=args.batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    scores = trainer.normalize_scores(raw_scores)

    score_path = Path(args.scores_out)
    score_path.parent.mkdir(parents=True, exist_ok=True)
    with score_path.open("w", encoding="utf-8") as handle:
        for row, score in zip(rows, scores):
            handle.write(
                json.dumps(
                    {
                        "case_slug": row["case_slug"],
                        "retriever_run": row["retriever_run"],
                        "persona": row["persona"],
                        "path": row["node"]["path"],
                        "label": int(row["label"]),
                        "score": float(score),
                    },
                    sort_keys=True,
                )
                + "\n"
            )

    persona_results: dict[str, Any] = {}
    warnings = []
    for persona in ("WORKER", "PM", "REVIEWER"):
        indices = np.asarray([idx for idx, row in enumerate(rows) if row["persona"] == persona])
        y = labels[indices]
        s = scores[indices]
        if persona == "WORKER":
            chosen = choose_worker_threshold(y, s, target_recall=args.worker_target_recall)
            if chosen["precision"] < args.precision_warning_floor:
                warnings.append(
                    {
                        "persona": persona,
                        "kind": "precision_below_floor_at_target_recall",
                        "precision": chosen["precision"],
                        "floor": args.precision_warning_floor,
                        "recommended_action": "Plan B: retrain v2 with explicit up-sampling or per-persona loss.",
                    }
                )
        else:
            chosen = choose_f1_threshold(y, s)

        persona_results[persona] = {
            "recommended_threshold": chosen["threshold"],
            "metrics_at_recommended_threshold": chosen,
            "default_0_5_metrics": metrics_at_threshold(y, s, 0.5),
            "score_summary": {
                "min": float(s.min()) if len(s) else None,
                "max": float(s.max()) if len(s) else None,
                "mean": float(s.mean()) if len(s) else None,
                "positive_mean": float(s[y == 1].mean()) if int(y.sum()) else None,
                "negative_mean": float(s[y == 0].mean()) if int((y == 0).sum()) else None,
            },
            "precision_recall_curve": precision_recall_points(y, s),
        }

    output = {
        "schema_version": 1,
        "model_dir": model_dir,
        "dataset": str(dataset),
        "training_report": str(report_path),
        "validation_case_slugs": sorted(val_cases),
        "validation_rows": len(rows),
        "max_document_chars": max_document_chars,
        "device": device,
        "worker_target_recall": args.worker_target_recall,
        "precision_warning_floor": args.precision_warning_floor,
        "persona_thresholds": persona_results,
        "warnings": warnings,
        "scores_out": str(score_path),
    }
    write_json(Path(args.out), output)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
