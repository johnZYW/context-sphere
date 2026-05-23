"""Fair local baseline accounting for Context Sphere v3 SWE-bench scaffolds."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from context_sphere_v3.evaluation import EvaluationConfig
from context_sphere_v3.evaluation import assert_baseline_fairness
from context_sphere_v3.evaluation import token_reduction_vs_full
from context_sphere_v3.roles import ROLE_PM
from context_sphere_v3.roles import ROLE_REVIEWER
from context_sphere_v3.roles import ROLE_WORKER


TOKEN_COUNT_POLICY = "whitespace_v1"
PROMPT_SHELL_ID = "context_sphere_v3_swebench_patch_prompt_shell_v1"
METHOD_FULL_CONTEXT = "full_context"
METHOD_STANDARD_RAG = "standard_rag"
METHOD_CONTEXT_SPHERE_V3 = "context_sphere_v3"
METHODS = (METHOD_FULL_CONTEXT, METHOD_STANDARD_RAG, METHOD_CONTEXT_SPHERE_V3)
STOPWORDS = {
    "about",
    "after",
    "also",
    "because",
    "before",
    "could",
    "does",
    "from",
    "have",
    "into",
    "should",
    "that",
    "their",
    "there",
    "this",
    "with",
    "would",
}
ROLE_TERMS = {
    ROLE_PM: {
        "acceptance",
        "behavior",
        "description",
        "expected",
        "goal",
        "issue",
        "requirements",
        "ticket",
    },
    ROLE_WORKER: {
        "class",
        "code",
        "command",
        "file",
        "function",
        "implementation",
        "method",
        "module",
        "test",
    },
    ROLE_REVIEWER: {
        "bug",
        "edge",
        "fail",
        "incorrect",
        "missing",
        "regression",
        "should",
        "test",
        "wrong",
    },
}


def count_tokens(text: str) -> int:
    return len([piece for piece in text.split() if piece])


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def evaluation_config_from_payload(payload: dict[str, Any]) -> EvaluationConfig:
    return EvaluationConfig(
        instance_ids=tuple(str(instance_id) for instance_id in payload["instance_ids"]),
        agent_model=str(payload["agent_model"]),
        temperature=float(payload["temperature"]),
        max_generation_tokens=int(payload["max_generation_tokens"]),
        visible_repo_state=str(payload["visible_repo_state"]),
        prompt_template_id=str(payload["prompt_template_id"]),
        seed=int(payload["seed"]),
    ).validate()


def text_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text.lower())
        if token not in STOPWORDS
    }


def split_problem_statement(problem_statement: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    raw_blocks = re.split(r"\n\s*\n+", problem_statement.strip())
    for block_index, block in enumerate(raw_blocks):
        cleaned = "\n".join(line.rstrip() for line in block.splitlines()).strip()
        if not cleaned:
            continue
        chunks.append(
            {
                "chunk_id": f"problem_chunk_{block_index:02d}",
                "text": cleaned,
                "token_count": count_tokens(cleaned),
                "terms": text_terms(cleaned),
            }
        )
    if not chunks and problem_statement.strip():
        text = problem_statement.strip()
        chunks.append(
            {
                "chunk_id": "problem_chunk_00",
                "text": text,
                "token_count": count_tokens(text),
                "terms": text_terms(text),
            }
        )
    return chunks


def query_terms_for_row(row: dict[str, Any]) -> set[str]:
    title = str(row.get("problem_statement", "")).strip().splitlines()[0] if row.get("problem_statement") else ""
    repo = str(row.get("repo", ""))
    return text_terms(f"{repo} {title}")


def score_standard_rag_chunk(chunk: dict[str, Any], query_terms: set[str]) -> tuple[int, int, str]:
    terms = set(chunk["terms"])
    overlap = len(terms & query_terms)
    codeish = sum(1 for term in terms if "_" in term or term.endswith(("error", "test", "field", "model")))
    return (overlap, codeish, str(chunk["chunk_id"]))


def score_role_folded_chunk(chunk: dict[str, Any], chunks: list[dict[str, Any]], role: str) -> tuple[float, int, str]:
    terms = set(chunk["terms"])
    role_overlap = len(terms & ROLE_TERMS[role])
    pair_scores = []
    for other in chunks:
        if other["chunk_id"] == chunk["chunk_id"]:
            continue
        other_terms = set(other["terms"])
        pair_scores.append(len(terms & other_terms) / max(1, len(terms | other_terms)))
    folded_neighbor_signal = sum(sorted(pair_scores, reverse=True)[:3])
    return (role_overlap + 0.25 * folded_neighbor_signal, chunk["token_count"], str(chunk["chunk_id"]))


def select_by_budget(
    chunks: list[dict[str, Any]],
    ranked_chunk_ids: list[str],
    *,
    max_context_tokens: int,
    min_chunks: int = 1,
) -> list[dict[str, Any]]:
    by_id = {str(chunk["chunk_id"]): chunk for chunk in chunks}
    selected: list[dict[str, Any]] = []
    token_total = 0
    for chunk_id in ranked_chunk_ids:
        chunk = by_id[chunk_id]
        if selected and token_total + int(chunk["token_count"]) > max_context_tokens and len(selected) >= min_chunks:
            continue
        selected.append(chunk)
        token_total += int(chunk["token_count"])
    return selected or chunks[:1]


def full_context_selection(chunks: list[dict[str, Any]], *, max_context_tokens: int) -> dict[str, Any]:
    del max_context_tokens
    return {
        "selector": METHOD_FULL_CONTEXT,
        "selection_strategy": "all_visible_problem_statement_chunks",
        "role_sections": {},
        "selected_chunks": chunks,
    }


def standard_rag_selection(
    chunks: list[dict[str, Any]],
    *,
    row: dict[str, Any],
    max_context_tokens: int,
) -> dict[str, Any]:
    query_terms = query_terms_for_row(row)
    ranked = sorted(
        chunks,
        key=lambda chunk: score_standard_rag_chunk(chunk, query_terms),
        reverse=True,
    )
    selected = select_by_budget(
        chunks,
        [str(chunk["chunk_id"]) for chunk in ranked],
        max_context_tokens=max_context_tokens,
        min_chunks=2,
    )
    return {
        "selector": METHOD_STANDARD_RAG,
        "selection_strategy": "lexical_title_repo_overlap_top_chunks",
        "query_terms": sorted(query_terms),
        "role_sections": {},
        "selected_chunks": selected,
    }


def context_sphere_v3_selection(chunks: list[dict[str, Any]], *, max_context_tokens: int) -> dict[str, Any]:
    role_budget = max(1, max_context_tokens // 3)
    role_sections: dict[str, Any] = {}
    selected_by_id: dict[str, dict[str, Any]] = {}
    for role in (ROLE_PM, ROLE_WORKER, ROLE_REVIEWER):
        ranked = sorted(
            chunks,
            key=lambda chunk: score_role_folded_chunk(chunk, chunks, role),
            reverse=True,
        )
        role_selected = select_by_budget(
            chunks,
            [str(chunk["chunk_id"]) for chunk in ranked],
            max_context_tokens=role_budget,
            min_chunks=1,
        )
        for chunk in role_selected:
            selected_by_id[str(chunk["chunk_id"])] = chunk
        role_sections[role] = {
            "role_terms": sorted(ROLE_TERMS[role]),
            "selected_chunk_ids": [str(chunk["chunk_id"]) for chunk in role_selected],
            "selected_token_count": sum(int(chunk["token_count"]) for chunk in role_selected),
        }
    selected = [chunk for chunk in chunks if str(chunk["chunk_id"]) in selected_by_id]
    return {
        "selector": METHOD_CONTEXT_SPHERE_V3,
        "selection_strategy": "deterministic_role_conditioned_pair_folding_proxy",
        "proxy_boundary": (
            "Visible-text role/pair scoring proxy for fair context accounting only; "
            "not a trained SWE-bench Context Sphere model."
        ),
        "role_sections": role_sections,
        "selected_chunks": selected,
    }


def build_context_section(method: str, selection: dict[str, Any]) -> str:
    if method == METHOD_CONTEXT_SPHERE_V3:
        lines = []
        selected_by_id = {str(chunk["chunk_id"]): chunk for chunk in selection["selected_chunks"]}
        for role in (ROLE_PM, ROLE_WORKER, ROLE_REVIEWER):
            lines.append(f"[{role.upper()} CONTEXT]")
            for chunk_id in selection["role_sections"][role]["selected_chunk_ids"]:
                lines.append(selected_by_id[chunk_id]["text"])
        return "\n\n".join(lines)
    return "\n\n".join(str(chunk["text"]) for chunk in selection["selected_chunks"])


def build_prompt_shell(row: dict[str, Any], context_section: str) -> str:
    return (
        "You are an LLM software agent preparing a patch for a SWE-bench Lite issue.\n"
        "Use only the visible issue context below. Do not assume access to gold patches or hidden tests.\n\n"
        f"INSTANCE_ID: {row['instance_id']}\n"
        f"REPO: {row['repo']}\n"
        f"BASE_COMMIT: {row['base_commit']}\n\n"
        "[CONTEXT_SELECTION]\n"
        f"{context_section}\n\n"
        "[TASK]\n"
        "Return a unified git diff that plausibly fixes the issue.\n"
    )


def prompt_shell_hash() -> str:
    placeholder = build_prompt_shell(
        {"instance_id": "{instance_id}", "repo": "{repo}", "base_commit": "{base_commit}"},
        "{context_section}",
    )
    return hashlib.sha256(placeholder.encode("utf-8")).hexdigest()


def method_selection(
    method: str,
    chunks: list[dict[str, Any]],
    row: dict[str, Any],
    *,
    max_context_tokens: int,
) -> dict[str, Any]:
    if method == METHOD_FULL_CONTEXT:
        return full_context_selection(chunks, max_context_tokens=max_context_tokens)
    if method == METHOD_STANDARD_RAG:
        return standard_rag_selection(chunks, row=row, max_context_tokens=max_context_tokens)
    if method == METHOD_CONTEXT_SPHERE_V3:
        return context_sphere_v3_selection(chunks, max_context_tokens=max_context_tokens)
    raise ValueError(f"unknown method {method!r}")


def build_method_row(
    *,
    method: str,
    source_row: dict[str, Any],
    config: EvaluationConfig,
    max_context_tokens: int,
) -> dict[str, Any]:
    chunks = split_problem_statement(str(source_row.get("problem_statement", "")))
    selection = method_selection(method, chunks, source_row, max_context_tokens=max_context_tokens)
    context_section = build_context_section(method, selection)
    prompt = build_prompt_shell(source_row, context_section)
    selected_tokens = sum(int(chunk["token_count"]) for chunk in selection["selected_chunks"])
    full_tokens = sum(int(chunk["token_count"]) for chunk in chunks)
    return {
        "instance_id": source_row["instance_id"],
        "method": method,
        "status": "prepared_not_executed",
        "evaluation_config": asdict(config),
        "token_count_policy": TOKEN_COUNT_POLICY,
        "prompt_shell_id": PROMPT_SHELL_ID,
        "prompt_shell_sha256": prompt_shell_hash(),
        "selection_strategy": selection["selection_strategy"],
        "selected_chunk_ids": [str(chunk["chunk_id"]) for chunk in selection["selected_chunks"]],
        "selected_chunks": [
            {
                "chunk_id": str(chunk["chunk_id"]),
                "text": str(chunk["text"]),
                "token_count": int(chunk["token_count"]),
            }
            for chunk in selection["selected_chunks"]
        ],
        "role_sections": selection["role_sections"],
        "full_visible_context_tokens": full_tokens,
        "selected_context_tokens": selected_tokens,
        "prompt_tokens": count_tokens(prompt),
        "max_context_tokens": max_context_tokens,
        "official_pass_at_1_claimed": False,
        "claim_boundary": "Context prepared for fair baseline accounting only; no LLM call or SWE-bench harness run.",
    }


def aggregate_method_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_method: dict[str, list[dict[str, Any]]] = {method: [] for method in METHODS}
    for row in rows:
        by_method[str(row["method"])].append(row)
    full_by_instance = {
        str(row["instance_id"]): int(row["selected_context_tokens"])
        for row in by_method[METHOD_FULL_CONTEXT]
    }
    aggregate: dict[str, Any] = {}
    for method, method_rows in by_method.items():
        selected_total = sum(int(row["selected_context_tokens"]) for row in method_rows)
        full_total = sum(full_by_instance[str(row["instance_id"])] for row in method_rows)
        aggregate[method] = {
            "instance_count": len(method_rows),
            "selected_context_tokens_total": selected_total,
            "full_context_tokens_total": full_total,
            "mean_selected_context_tokens": selected_total / max(1, len(method_rows)),
            "token_reduction_vs_full_context": token_reduction_vs_full(full_total, selected_total)
            if full_total
            else 0.0,
            "all_statuses": sorted({str(row["status"]) for row in method_rows}),
        }
    return aggregate


def run_fair_baseline_comparison(
    *,
    scaffold_dir: str | Path = "outputs/swebench_lite_10",
    report_path: str | Path = "outputs/reports/context_sphere_v3_baseline_comparison.json",
    contexts_path: str | Path | None = None,
    max_context_tokens: int = 180,
) -> dict[str, Any]:
    scaffold_path = Path(scaffold_dir)
    config_payload = load_json(scaffold_path / "evaluation_config.json")
    subset_payload = load_json(scaffold_path / "subset.json")
    visible_rows = load_jsonl(scaffold_path / "visible_sources.jsonl")
    config = evaluation_config_from_payload(config_payload)
    method_configs = {method: config for method in METHODS}
    assert_baseline_fairness(method_configs)

    visible_by_id = {str(row["instance_id"]): row for row in visible_rows}
    method_rows: list[dict[str, Any]] = []
    for instance_id in config.instance_ids:
        if instance_id not in visible_by_id:
            raise ValueError(f"missing visible source row for {instance_id}")
        for method in METHODS:
            method_rows.append(
                build_method_row(
                    method=method,
                    source_row=visible_by_id[instance_id],
                    config=config,
                    max_context_tokens=max_context_tokens,
                )
            )

    report = {
        "schema_version": 1,
        "runner": "context_sphere_v3_fair_baseline_comparison",
        "passed": (
            len(method_rows) == len(config.instance_ids) * len(METHODS)
            and all(row["status"] == "prepared_not_executed" for row in method_rows)
        ),
        "scaffold_dir": str(scaffold_path),
        "dataset_name": subset_payload.get("dataset_name"),
        "dataset_card_url": subset_payload.get("dataset_card_url"),
        "swebench_dataset_guide_url": subset_payload.get("swebench_dataset_guide_url"),
        "instance_ids": list(config.instance_ids),
        "methods": list(METHODS),
        "method_configs": {method: asdict(method_configs[method]) for method in METHODS},
        "non_selector_config_equal": True,
        "token_count_policy": TOKEN_COUNT_POLICY,
        "prompt_shell_id": PROMPT_SHELL_ID,
        "prompt_shell_sha256": prompt_shell_hash(),
        "max_context_tokens_for_selector_methods": max_context_tokens,
        "method_rows": method_rows,
        "aggregate": aggregate_method_rows(method_rows),
        "official_swebench_harness_run": False,
        "official_pass_at_1_claimed": False,
        "claim_boundary": (
            "Fair baseline context-accounting scaffold only. It records token budgets, selected chunks, "
            "and identical non-selector config; it is not official SWE-bench scoring and made no provider call."
        ),
    }

    report_out = Path(report_path)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if contexts_path is not None:
        context_out = Path(contexts_path)
        context_out.parent.mkdir(parents=True, exist_ok=True)
        context_out.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in method_rows) + "\n",
            encoding="utf-8",
        )
    return report
