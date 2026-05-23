"""Leakage-safe Worker labels derived from SWE-bench gold patch paths only."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from context_sphere_v3.baselines import load_json
from context_sphere_v3.baselines import load_jsonl
from context_sphere_v3.baselines import split_problem_statement
from context_sphere_v3.swebench_scaffold import fetch_swebench_lite_rows
from context_sphere_v3.swebench_scaffold import write_jsonl


DIFF_GIT_RE = re.compile(r"^diff --git a/(.*?) b/(.*?)$")
FILE_HEADER_RE = re.compile(r"^(?:---|\+\+\+) (?:a|b)/(.*?)$")


def normalize_path(path: str) -> str:
    return path.strip().strip('"').lstrip("./")


def touched_files_from_patch(patch: str) -> list[str]:
    files: set[str] = set()
    current_old: str | None = None
    current_new: str | None = None
    for raw_line in patch.splitlines():
        line = raw_line.strip()
        diff_match = DIFF_GIT_RE.match(line)
        if diff_match:
            old_path, new_path = diff_match.groups()
            for path in (old_path, new_path):
                normalized = normalize_path(path)
                if normalized and normalized != "/dev/null":
                    files.add(normalized)
            continue
        header_match = FILE_HEADER_RE.match(line)
        if header_match:
            normalized = normalize_path(header_match.group(1))
            if normalized and normalized != "/dev/null":
                files.add(normalized)
            if line.startswith("---"):
                current_old = normalized
            else:
                current_new = normalized
    for path in (current_old, current_new):
        if path and path != "/dev/null":
            files.add(path)
    return sorted(files)


def path_terms(path: str) -> set[str]:
    pieces = re.split(r"[/_.\\-]+", path.lower())
    return {piece for piece in pieces if len(piece) >= 2}


def touched_chunk_ids_for_visible_text(problem_statement: str, touched_files: list[str]) -> list[str]:
    chunks = split_problem_statement(problem_statement)
    touched_chunk_ids = set()
    for touched_file in touched_files:
        terms = path_terms(touched_file)
        basename = Path(touched_file).name.lower()
        for chunk in chunks:
            chunk_text = str(chunk["text"]).lower()
            chunk_terms = set(chunk["terms"])
            if touched_file.lower() in chunk_text or basename in chunk_text or terms & chunk_terms:
                touched_chunk_ids.add(str(chunk["chunk_id"]))
    return sorted(touched_chunk_ids)


def fetch_rows_by_instance_id(instance_ids: list[str], *, fetch_length: int = 300) -> dict[str, dict[str, Any]]:
    rows = fetch_swebench_lite_rows(length=fetch_length)
    by_id = {str(row.get("instance_id")): row for row in rows}
    missing = [instance_id for instance_id in instance_ids if instance_id not in by_id]
    if missing:
        raise ValueError(f"missing SWE-bench rows for instance ids: {missing}")
    return {instance_id: by_id[instance_id] for instance_id in instance_ids}


def build_worker_label_rows(
    *,
    scaffold_dir: str | Path = "outputs/swebench_lite_10",
    visible_sources_path: str | Path | None = None,
    out_path: str | Path = "outputs/swebench_lite_10/worker_labels.jsonl",
    fetch_length: int = 300,
) -> list[dict[str, Any]]:
    scaffold_path = Path(scaffold_dir)
    subset = load_json(scaffold_path / "subset.json")
    visible_path = Path(visible_sources_path) if visible_sources_path is not None else scaffold_path / "visible_sources.jsonl"
    visible_by_id = {str(row["instance_id"]): row for row in load_jsonl(visible_path)}
    instance_ids = [str(instance_id) for instance_id in subset["instance_ids"]]
    source_rows = fetch_rows_by_instance_id(instance_ids, fetch_length=fetch_length)

    label_rows = []
    for instance_id in instance_ids:
        source_row = source_rows[instance_id]
        patch = str(source_row.get("patch", ""))
        touched_files = touched_files_from_patch(patch)
        visible_problem = str(visible_by_id[instance_id].get("problem_statement", ""))
        touched_chunks = touched_chunk_ids_for_visible_text(visible_problem, touched_files)
        label_rows.append(
            {
                "schema_version": 1,
                "instance_id": instance_id,
                "label_source": "gold_patch_touched_file_paths_only",
                "label_source_allowed_for_training": True,
                "label_source_forbidden_as_model_input": True,
                "touched_files": touched_files,
                "touched_chunk_ids": touched_chunks,
                "visible_chunk_label_rule": (
                    "A visible chunk is labeled touched only when visible issue text mentions "
                    "a touched file path, basename, or path token. Patch content is never used "
                    "as model input."
                ),
                "gold_patch_content_stored": False,
                "test_patch_content_stored": False,
                "post_pr_code_used": False,
            }
        )
    write_jsonl(Path(out_path), label_rows)
    return label_rows
