"""Selector-only evaluation for leakage-safe Context Sphere v3 data."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from context_sphere_v3.baselines import METHOD_CONTEXT_SPHERE_V3
from context_sphere_v3.baselines import METHOD_FULL_CONTEXT
from context_sphere_v3.baselines import METHOD_STANDARD_RAG
from context_sphere_v3.baselines import count_tokens
from context_sphere_v3.baselines import load_json
from context_sphere_v3.baselines import load_jsonl
from context_sphere_v3.baselines import score_role_folded_chunk
from context_sphere_v3.baselines import split_problem_statement
from context_sphere_v3.baselines import text_terms
from context_sphere_v3.roles import ROLE_WORKER
from context_sphere_v3.worker_labels import path_terms

try:
    from context_sphere_v3.neural_selector import load_neural_selector
    from context_sphere_v3.neural_selector import neural_scores_for_chunks
except Exception:  # pragma: no cover - no-torch shell or partial import.
    load_neural_selector = None  # type: ignore[assignment]
    neural_scores_for_chunks = None  # type: ignore[assignment]


METHOD_STANDARD_BM25 = "standard_rag_bm25"
SELECTOR_METHODS = (METHOD_FULL_CONTEXT, METHOD_STANDARD_BM25, METHOD_CONTEXT_SPHERE_V3)


def bm25_rank(chunks: list[dict[str, Any]], query_terms: set[str]) -> list[dict[str, Any]]:
    doc_terms = [list(chunk["terms"]) for chunk in chunks]
    avgdl = sum(len(terms) for terms in doc_terms) / max(1, len(doc_terms))
    dfs = {term: sum(1 for terms in doc_terms if term in terms) for term in query_terms}
    ranked = []
    for chunk, terms in zip(chunks, doc_terms):
        score = 0.0
        dl = len(terms)
        for term in query_terms:
            tf = terms.count(term)
            if tf == 0:
                continue
            df = dfs.get(term, 0)
            idf = math.log(1 + (len(chunks) - df + 0.5) / (df + 0.5))
            score += idf * (tf * 2.2) / (tf + 1.2 * (1 - 0.75 + 0.75 * dl / max(avgdl, 1e-9)))
        ranked.append((score, int(chunk["token_count"]), str(chunk["chunk_id"]), chunk))
    return [item[3] for item in sorted(ranked, reverse=True)]


def query_terms_for_touched_files(problem_statement: str, touched_files: list[str]) -> set[str]:
    query = text_terms(problem_statement.splitlines()[0] if problem_statement.strip() else problem_statement)
    for path in touched_files:
        query |= path_terms(path)
    return query


def context_sphere_rank(
    chunks: list[dict[str, Any]],
    *,
    neural_model: Any | None = None,
    neural_config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if neural_model is not None and neural_config is not None:
        if neural_scores_for_chunks is None:
            raise RuntimeError("neural selector support is unavailable")
        scores = neural_scores_for_chunks(
            neural_model,
            chunks,
            chunk_dim=int(neural_config["chunk_dim"]),
            role_dim=int(neural_config["role_dim"]),
        )
        ranked_with_scores = [
            (score, int(chunk["token_count"]), str(chunk["chunk_id"]), chunk)
            for score, chunk in zip(scores, chunks)
        ]
        return [item[3] for item in sorted(ranked_with_scores, reverse=True)]
    ranked = sorted(
        chunks,
        key=lambda chunk: score_role_folded_chunk(chunk, chunks, ROLE_WORKER),
        reverse=True,
    )
    return ranked


def chunk_file_hits(chunk: dict[str, Any], touched_files: list[str]) -> set[str]:
    text = str(chunk["text"]).lower()
    terms = set(chunk["terms"])
    hits = set()
    for path in touched_files:
        lowered = path.lower()
        basename = Path(path).name.lower()
        if lowered in text or basename in text or path_terms(path) & terms:
            hits.add(path)
    return hits


def ranked_metrics(ranked_chunks: list[dict[str, Any]], touched_files: list[str], touched_chunk_ids: list[str], k_values: tuple[int, ...]) -> dict[str, Any]:
    touched_file_set = set(touched_files)
    touched_chunk_set = set(touched_chunk_ids)
    metrics: dict[str, Any] = {}
    for k in k_values:
        top = ranked_chunks[:k]
        recovered_files = set().union(*(chunk_file_hits(chunk, touched_files) for chunk in top)) if top else set()
        recovered_chunks = {str(chunk["chunk_id"]) for chunk in top} & touched_chunk_set
        metrics[f"file_recall_at_{k}"] = len(recovered_files) / max(1, len(touched_file_set))
        metrics[f"chunk_recall_at_{k}"] = (
            len(recovered_chunks) / len(touched_chunk_set)
            if touched_chunk_set
            else None
        )
    relevances = [len(chunk_file_hits(chunk, touched_files)) for chunk in ranked_chunks]
    ideal = sorted(relevances, reverse=True)
    dcg = sum((rel / math.log2(index + 2)) for index, rel in enumerate(relevances))
    idcg = sum((rel / math.log2(index + 2)) for index, rel in enumerate(ideal))
    metrics["ndcg"] = dcg / idcg if idcg else 0.0
    first_relevant = next((index + 1 for index, rel in enumerate(relevances) if rel > 0), None)
    metrics["mrr"] = 1.0 / first_relevant if first_relevant else 0.0
    return metrics


def tokens_to_recover(ranked_chunks: list[dict[str, Any]], touched_files: list[str], target_recall: float) -> int | None:
    if not touched_files:
        return None
    recovered: set[str] = set()
    tokens = 0
    for chunk in ranked_chunks:
        tokens += int(chunk["token_count"])
        recovered |= chunk_file_hits(chunk, touched_files)
        if len(recovered) / len(set(touched_files)) >= target_recall:
            return tokens
    return None


def ranked_chunks_for_method(
    method: str,
    chunks: list[dict[str, Any]],
    problem_statement: str,
    touched_files: list[str],
    *,
    neural_model: Any | None = None,
    neural_config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if method == METHOD_FULL_CONTEXT:
        return chunks
    if method == METHOD_STANDARD_BM25:
        return bm25_rank(chunks, query_terms_for_touched_files(problem_statement, touched_files))
    if method == METHOD_CONTEXT_SPHERE_V3:
        return context_sphere_rank(chunks, neural_model=neural_model, neural_config=neural_config)
    raise ValueError(f"unknown selector method {method!r}")


def run_selector_only_evaluation(
    *,
    scaffold_dir: str | Path = "outputs/swebench_lite_10",
    visible_sources_path: str | Path | None = None,
    labels_path: str | Path = "outputs/swebench_lite_10/worker_labels.jsonl",
    leakage_audit_path: str | Path = "outputs/reports/context_sphere_v3_leakage_audit.json",
    out_path: str | Path = "outputs/reports/context_sphere_v3_selector_only_eval.json",
    k_values: tuple[int, ...] = (1, 3, 5),
    neural_state_path: str | Path | None = None,
) -> dict[str, Any]:
    scaffold_path = Path(scaffold_dir)
    subset = load_json(scaffold_path / "subset.json")
    visible_path = Path(visible_sources_path) if visible_sources_path is not None else scaffold_path / "visible_sources.jsonl"
    visible = {str(row["instance_id"]): row for row in load_jsonl(visible_path)}
    labels = {str(row["instance_id"]): row for row in load_jsonl(labels_path)}
    leakage_audit = load_json(leakage_audit_path)
    instance_ids = [str(instance_id) for instance_id in subset["instance_ids"]]
    rows = []
    aggregates: dict[str, dict[str, float]] = {method: {} for method in SELECTOR_METHODS}
    neural_model = None
    neural_config = None
    if neural_state_path is not None:
        if load_neural_selector is None:
            raise RuntimeError("neural selector state was provided but torch support is unavailable")
        neural_model, neural_config = load_neural_selector(neural_state_path)

    for instance_id in instance_ids:
        visible_row = visible[instance_id]
        label_row = labels[instance_id]
        problem_statement = str(visible_row.get("problem_statement", ""))
        chunks = split_problem_statement(problem_statement)
        full_tokens = sum(int(chunk["token_count"]) for chunk in chunks)
        touched_files = list(label_row["touched_files"])
        touched_chunk_ids = list(label_row["touched_chunk_ids"])
        method_rows = []
        for method in SELECTOR_METHODS:
            ranked = ranked_chunks_for_method(
                method,
                chunks,
                problem_statement,
                touched_files,
                neural_model=neural_model,
                neural_config=neural_config,
            )
            selected = ranked if method == METHOD_FULL_CONTEXT else ranked[:max(k_values)]
            selected_tokens = sum(int(chunk["token_count"]) for chunk in selected)
            metric_values = ranked_metrics(ranked, touched_files, touched_chunk_ids, k_values)
            metric_values["tokens_to_recover_80pct_files"] = tokens_to_recover(ranked, touched_files, 0.8)
            metric_values["tokens_to_recover_90pct_files"] = tokens_to_recover(ranked, touched_files, 0.9)
            metric_values["token_reduction_vs_full_context"] = 1.0 - (selected_tokens / full_tokens) if full_tokens else 0.0
            method_rows.append(
                {
                    "method": method,
                    "selected_chunk_ids": [str(chunk["chunk_id"]) for chunk in selected],
                    "selected_chunks": [
                        {"chunk_id": str(chunk["chunk_id"]), "text": str(chunk["text"]), "token_count": int(chunk["token_count"])}
                        for chunk in selected
                    ],
                    "token_count": selected_tokens,
                    "metrics": metric_values,
                }
            )
            for key, value in metric_values.items():
                if isinstance(value, (int, float)):
                    aggregates[method][key] = aggregates[method].get(key, 0.0) + float(value)
        rows.append(
            {
                "instance_id": instance_id,
                "visible_input_sources": {
                    "fields": ["instance_id", "repo", "base_commit", "problem_statement"],
                    "source": str(visible_path),
                },
                "label_source": label_row["label_source"],
                "touched_files": touched_files,
                "touched_chunk_ids": touched_chunk_ids,
                "full_visible_token_count": full_tokens,
                "methods": method_rows,
                "leakage_audit_status": {
                    "passed": bool(leakage_audit["passed"]),
                    "audit_path": str(leakage_audit_path),
                },
            }
        )

    for method in SELECTOR_METHODS:
        for key in list(aggregates[method]):
            aggregates[method][key] /= max(1, len(instance_ids))
    report = {
        "schema_version": 1,
        "evaluation": "context_sphere_v3_selector_only",
        "passed": bool(leakage_audit["passed"]) and bool(rows),
        "instance_ids": instance_ids,
        "methods": list(SELECTOR_METHODS),
        "context_sphere_v3_selector_source": "neural_model" if neural_state_path is not None else "heuristic_proxy",
        "neural_state_path": str(neural_state_path) if neural_state_path is not None else None,
        "k_values": list(k_values),
        "rows": rows,
        "aggregate_metrics": aggregates,
        "leakage_audit": leakage_audit,
        "claim_boundary": (
            "Selector-only evaluation. It evaluates visible issue chunk ranking against "
            "gold-patch touched-file labels; it does not train the model, call an LLM, "
            "or claim SWE-bench Pass@1."
        ),
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
