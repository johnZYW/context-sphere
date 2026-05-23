"""Leakage audit for Context Sphere v3 selector-only data."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from context_sphere_v3.baselines import load_json
from context_sphere_v3.baselines import load_jsonl
from context_sphere_v3.swebench_scaffold import write_jsonl
from context_sphere_v3.swebench_scaffold import ALLOWED_VISIBLE_FIELDS
from context_sphere_v3.swebench_scaffold import FORBIDDEN_CONTEXT_FIELDS
from context_sphere_v3.worker_labels import fetch_rows_by_instance_id


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalized_snippets(text: str, *, min_length: int = 32) -> list[str]:
    snippets = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line.strip())
        if len(line) >= min_length:
            snippets.append(line.lower())
    return snippets


def visible_input_texts(visible_sources_path: str | Path) -> dict[str, str]:
    rows = load_jsonl(visible_sources_path)
    return {str(row["instance_id"]): str(row.get("problem_statement", "")) for row in rows}


def sanitize_problem_statement(problem_statement: str, forbidden_contents: list[str]) -> tuple[str, int]:
    forbidden_snippets = []
    for content in forbidden_contents:
        forbidden_snippets.extend(normalized_snippets(content))
    redacted_lines = []
    redaction_count = 0
    for raw_line in problem_statement.splitlines():
        normalized_line = re.sub(r"\s+", " ", raw_line.strip()).lower()
        if normalized_line and any(snippet in normalized_line for snippet in forbidden_snippets):
            redacted_lines.append("[REDACTED_FOR_LEAKAGE_AUDIT: patch_or_test_patch_overlap]")
            redaction_count += 1
        else:
            redacted_lines.append(raw_line)
    return "\n".join(redacted_lines), redaction_count


def write_leakage_safe_visible_sources(
    *,
    scaffold_dir: str | Path = "outputs/swebench_lite_10",
    out_path: str | Path = "outputs/swebench_lite_10/leakage_safe_visible_sources.jsonl",
    fetch_length: int = 300,
) -> dict[str, Any]:
    scaffold_path = Path(scaffold_dir)
    subset = load_json(scaffold_path / "subset.json")
    instance_ids = [str(instance_id) for instance_id in subset["instance_ids"]]
    visible_rows = load_jsonl(scaffold_path / "visible_sources.jsonl")
    source_rows = fetch_rows_by_instance_id(instance_ids, fetch_length=fetch_length)
    sanitized_rows = []
    redactions: dict[str, int] = {}
    for row in visible_rows:
        instance_id = str(row["instance_id"])
        source_row = source_rows[instance_id]
        sanitized_text, redaction_count = sanitize_problem_statement(
            str(row.get("problem_statement", "")),
            [str(source_row.get("patch", "")), str(source_row.get("test_patch", ""))],
        )
        sanitized = dict(row)
        sanitized["problem_statement"] = sanitized_text
        sanitized["sanitized_for_leakage_audit"] = True
        sanitized["redacted_patch_or_test_patch_overlap_lines"] = redaction_count
        redactions[instance_id] = redaction_count
        sanitized_rows.append(sanitized)
    write_jsonl(Path(out_path), sanitized_rows)
    return {
        "schema_version": 1,
        "out_path": str(out_path),
        "row_count": len(sanitized_rows),
        "total_redactions": sum(redactions.values()),
        "redactions_by_instance": redactions,
        "passed": len(sanitized_rows) == len(instance_ids),
    }


def audit_leakage(
    *,
    scaffold_dir: str | Path = "outputs/swebench_lite_10",
    visible_sources_path: str | Path | None = None,
    labels_path: str | Path = "outputs/swebench_lite_10/worker_labels.jsonl",
    out_path: str | Path = "outputs/reports/context_sphere_v3_leakage_audit.json",
    fetch_length: int = 300,
) -> dict[str, Any]:
    scaffold_path = Path(scaffold_dir)
    visible_path = Path(visible_sources_path) if visible_sources_path is not None else scaffold_path / "visible_sources.jsonl"
    subset = load_json(scaffold_path / "subset.json")
    instance_ids = [str(instance_id) for instance_id in subset["instance_ids"]]
    visible_rows = load_jsonl(visible_path)
    labels = load_jsonl(labels_path)
    source_rows = fetch_rows_by_instance_id(instance_ids, fetch_length=fetch_length)
    visible_text_by_id = visible_input_texts(visible_path)

    failures: list[dict[str, Any]] = []
    for row in visible_rows:
        extra_keys = sorted(set(row) & set(FORBIDDEN_CONTEXT_FIELDS))
        if extra_keys:
            failures.append({"instance_id": row.get("instance_id"), "failure": "forbidden_visible_field", "fields": extra_keys})
        allowed_plus_metadata = set(ALLOWED_VISIBLE_FIELDS) | {
            "visible_field_names",
            "excluded_forbidden_fields",
            "no_leakage_boundary",
            "sanitized_for_leakage_audit",
            "redacted_patch_or_test_patch_overlap_lines",
        }
        unexpected = sorted(set(row) - allowed_plus_metadata)
        if unexpected:
            failures.append({"instance_id": row.get("instance_id"), "failure": "unexpected_visible_field", "fields": unexpected})

    for label in labels:
        for forbidden in ("patch", "test_patch", "solution_diff", "post_pr_code"):
            if forbidden in label:
                failures.append({"instance_id": label.get("instance_id"), "failure": "forbidden_label_payload_field", "field": forbidden})

    content_checks = []
    for instance_id in instance_ids:
        row = source_rows[instance_id]
        visible_text = visible_text_by_id[instance_id].lower()
        patch = str(row.get("patch", ""))
        test_patch = str(row.get("test_patch", ""))
        for field_name, content in (("patch", patch), ("test_patch", test_patch)):
            field_hash = sha256_text(content) if content else None
            leaked_snippets = [snippet for snippet in normalized_snippets(content) if snippet in visible_text]
            if leaked_snippets:
                failures.append(
                    {
                        "instance_id": instance_id,
                        "failure": "forbidden_content_snippet_in_visible_input",
                        "field": field_name,
                        "snippet_count": len(leaked_snippets),
                    }
                )
            content_checks.append(
                {
                    "instance_id": instance_id,
                    "field": field_name,
                    "sha256": field_hash,
                    "snippet_count_checked": len(normalized_snippets(content)),
                    "leaked_snippet_count": len(leaked_snippets),
                }
            )

    audit = {
        "schema_version": 1,
        "audit": "context_sphere_v3_leakage_audit",
        "passed": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "instance_ids": instance_ids,
        "labels_path": str(labels_path),
        "visible_sources_path": str(visible_path),
        "forbidden_context_fields": list(FORBIDDEN_CONTEXT_FIELDS),
        "allowed_visible_fields": list(ALLOWED_VISIBLE_FIELDS),
        "content_checks": content_checks,
        "post_pr_code_used": False,
        "solution_diffs_used_as_model_input": False,
        "gold_patch_used_as_model_input": False,
        "test_patch_used_as_model_input": False,
        "claim_boundary": (
            "Gold patch/test patch content may be inspected only to derive labels/audit hashes. "
            "Visible model input is restricted to issue metadata/problem statements."
        ),
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return audit
