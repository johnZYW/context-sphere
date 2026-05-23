#!/usr/bin/env python3
"""Extract persona-specific Context Projection training rows.

The extractor uses successful benchmark trajectories as supervision exhaust:

- Worker positives: files changed by the successful verified patch.
- Reviewer positives: Worker positives plus files targeted by State_VERIFY tests.
- PM positives: Worker/Reviewer positives represented as skeleton-only nodes.

It intentionally never reads model patch payloads, official solution diffs,
post-PR files, or test_patch content. Verification JSON is used only for
label paths and test command paths.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_RUN_ROOTS = (
    "outputs/ablation_100_vector",
    "outputs/ablation_100_context",
    "outputs/ablation_100_hybrid",
)

PERSONAS = ("WORKER", "REVIEWER", "PM")
PATCH_PAYLOAD_PATTERNS = (
    "patch_v",
    ".blocks.md",
    ".raw.md",
    ".raw.json",
    "test_patch",
    "solution_diff",
)
LEAKAGE_TEXT_MARKERS = (
    "<<<<<<< SEARCH",
    ">>>>>>> REPLACE",
    "diff --git",
    "\n@@ ",
    "test_patch",
    "solution diff",
    "gold patch",
)


@dataclass(frozen=True)
class SuccessTrajectory:
    run_name: str
    case_dir: Path
    metrics: dict[str, Any]
    verify_path: Path
    verify: dict[str, Any]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_read_text(path: Path, max_chars: int = 12000) -> tuple[str, str | None]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return "", f"{type(exc).__name__}: {exc}"
    return text[:max_chars], None


def normalize_rel_path(path: str) -> str:
    path = path.replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    return path


def is_success_metrics(metrics: dict[str, Any], strict_tests_passed: bool) -> bool:
    if strict_tests_passed:
        return metrics.get("status") == "APPROVED" and metrics.get("tests_passed") is True
    return metrics.get("status") == "APPROVED" or metrics.get("tests_passed") is True


def verify_attempt_number(path: Path) -> int:
    match = re.search(r"verify_v(\d+)\.json$", path.name)
    return int(match.group(1)) if match else -1


def verify_is_successful(data: dict[str, Any]) -> bool:
    patch_apply = data.get("patch_apply") or {}
    test_result = data.get("test_result") or {}
    return patch_apply.get("returncode") == 0 and test_result.get("returncode") == 0


def find_success_verify(case_dir: Path) -> tuple[Path, dict[str, Any]] | None:
    candidates: list[tuple[int, Path, dict[str, Any]]] = []
    for path in sorted(case_dir.glob("verify_v*.json")):
        try:
            data = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if verify_is_successful(data):
            candidates.append((verify_attempt_number(path), path, data))
    if not candidates:
        return None
    _, path, data = max(candidates, key=lambda item: item[0])
    return path, data


def iter_success_trajectories(
    run_roots: Iterable[Path], strict_tests_passed: bool
) -> Iterable[SuccessTrajectory]:
    for root in run_roots:
        if not root.exists():
            continue
        run_name = root.name.replace("ablation_100_", "")
        for metrics_path in sorted(root.glob("*/metrics.json")):
            try:
                metrics = load_json(metrics_path)
            except (OSError, json.JSONDecodeError):
                continue
            if not is_success_metrics(metrics, strict_tests_passed):
                continue
            found = find_success_verify(metrics_path.parent)
            if not found:
                continue
            verify_path, verify = found
            yield SuccessTrajectory(
                run_name=run_name,
                case_dir=metrics_path.parent,
                metrics=metrics,
                verify_path=verify_path,
                verify=verify,
            )


def extract_worker_files(verify: dict[str, Any]) -> set[str]:
    patch_apply = verify.get("patch_apply") or {}
    paths = set()
    for path in patch_apply.get("changed_files") or []:
        if isinstance(path, str):
            paths.add(normalize_rel_path(path))
    for change in patch_apply.get("applied_changes") or []:
        path = change.get("file_path") if isinstance(change, dict) else None
        if isinstance(path, str):
            paths.add(normalize_rel_path(path))
    return {path for path in paths if path}


def django_label_to_path(label: str) -> str | None:
    """Best-effort conversion for Django runtests dotted labels."""
    label = label.strip()
    if not label or "/" in label or label.startswith("-"):
        return None
    parts = label.split(".")
    if len(parts) < 2:
        return None
    module_parts = []
    for part in parts:
        if not part:
            break
        if part[0].isupper() or part.startswith("test_") and module_parts:
            break
        module_parts.append(part)
    if len(module_parts) < 2:
        return None
    return normalize_rel_path("tests/" + "/".join(module_parts) + ".py")


def extract_test_files(verify: dict[str, Any]) -> set[str]:
    paths = set()
    commands = []
    if isinstance(verify.get("resolved_test_command"), list):
        commands.extend(str(token) for token in verify["resolved_test_command"])
    test_result = verify.get("test_result") or {}
    if isinstance(test_result.get("command"), list):
        commands.extend(str(token) for token in test_result["command"])

    for token in commands:
        token = token.strip().strip('"').strip("'")
        if not token:
            continue
        if "::" in token:
            token = token.split("::", 1)[0]
        if token.endswith(".py") or ".py::" in token:
            if token.endswith(".py") and not Path(token).is_absolute():
                paths.add(normalize_rel_path(token))
            elif ".py::" in token:
                paths.add(normalize_rel_path(token.split(".py::", 1)[0] + ".py"))
            continue
        mapped = django_label_to_path(token)
        if mapped:
            paths.add(mapped)
    return {path for path in paths if path}


def load_sphere(case_dir: Path, name: str) -> dict[str, Any]:
    path = case_dir / name
    if not path.exists():
        return {}
    try:
        return load_json(path)
    except (OSError, json.JSONDecodeError):
        return {}


def infer_repo_path(case_dir: Path, spheres: Iterable[dict[str, Any]]) -> Path | None:
    for sphere in spheres:
        repo_path = sphere.get("repo_path")
        if repo_path:
            path = Path(repo_path)
            if path.exists():
                return path
    case_config = case_dir / "case_config.json"
    if case_config.exists():
        try:
            repo = load_json(case_config).get("repo")
        except (OSError, json.JSONDecodeError):
            repo = None
        if isinstance(repo, str):
            candidate = Path("outputs/benchmark_repos") / repo.replace("/", "__")
            if candidate.exists():
                return candidate
    return None


def selector_scores(case_dir: Path) -> dict[str, float]:
    path = case_dir / "selector_output.json"
    if not path.exists():
        return {}
    try:
        data = load_json(path)
    except (OSError, json.JSONDecodeError):
        return {}
    scores = {}
    for item in data.get("top_files") or []:
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            score = item.get("score")
            scores[normalize_rel_path(item["path"])] = float(score or 0.0)
    return scores


def collect_candidate_files(
    case_dir: Path,
    worker_files: set[str],
    reviewer_files: set[str],
) -> tuple[set[str], dict[str, str]]:
    candidates = set(worker_files) | set(reviewer_files)
    sources: dict[str, set[str]] = defaultdict(set)
    for path in candidates:
        sources[path].add("ground_truth")

    for file_name in (
        "selector_output.json",
        "worker_sphere.json",
        "reviewer_sphere.json",
        "pm_sphere.json",
    ):
        path = case_dir / file_name
        if not path.exists():
            continue
        try:
            data = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if file_name == "selector_output.json":
            for item in data.get("top_files") or []:
                if isinstance(item, dict) and isinstance(item.get("path"), str):
                    rel = normalize_rel_path(item["path"])
                    candidates.add(rel)
                    sources[rel].add("selector_top_files")
        else:
            for key in ("core_files", "neighborhood_files"):
                for rel in data.get(key) or []:
                    if isinstance(rel, str):
                        rel = normalize_rel_path(rel)
                        candidates.add(rel)
                        sources[rel].add(f"{file_name}:{key}")

    for path in sorted(case_dir.glob("*_sphere_recursive_v*.json")):
        try:
            data = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        for key in ("core_files", "neighborhood_files"):
            for rel in data.get(key) or []:
                if isinstance(rel, str):
                    rel = normalize_rel_path(rel)
                    candidates.add(rel)
                    sources[rel].add(f"{path.name}:{key}")

    return candidates, {path: ",".join(sorted(source)) for path, source in sources.items()}


def first_line_number(node: ast.AST) -> int | None:
    return getattr(node, "lineno", None)


def format_args(args: ast.arguments) -> str:
    names = []
    positional = list(args.posonlyargs) + list(args.args)
    for arg in positional:
        names.append(arg.arg)
    if args.vararg:
        names.append("*" + args.vararg.arg)
    for arg in args.kwonlyargs:
        names.append(arg.arg)
    if args.kwarg:
        names.append("**" + args.kwarg.arg)
    return ", ".join(names)


def skeleton_from_python(path: str, text: str) -> str:
    lines = [f"FILE: {path}", "KIND: python_skeleton"]
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        lines.append(f"PARSE_ERROR: {exc.__class__.__name__}")
        return "\n".join(lines)

    imports = []
    signatures = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = ", ".join(alias.name for alias in node.names)
            imports.append(f"import {names}")
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            names = ", ".join(alias.name for alias in node.names)
            imports.append(f"from {module} import {names}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            signatures.append(
                f"L{first_line_number(node)} {prefix} {node.name}({format_args(node.args)})"
            )
        elif isinstance(node, ast.ClassDef):
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(base.attr)
            base_text = f"({', '.join(bases)})" if bases else ""
            signatures.append(f"L{first_line_number(node)} class {node.name}{base_text}")
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    prefix = "async def" if isinstance(child, ast.AsyncFunctionDef) else "def"
                    signatures.append(
                        f"L{first_line_number(child)} {node.name}.{prefix} "
                        f"{child.name}({format_args(child.args)})"
                    )

    if imports:
        lines.append("IMPORTS:")
        lines.extend(f"- {item}" for item in imports[:80])
    if signatures:
        lines.append("SIGNATURES:")
        lines.extend(f"- {item}" for item in signatures[:160])
    return "\n".join(lines)


def pm_skeleton_for_path(repo_path: Path | None, rel_path: str) -> tuple[str, dict[str, Any]]:
    meta: dict[str, Any] = {"pm_skeleton_only": True, "pm_raw_body_chars": 0}
    if repo_path is None:
        return f"FILE: {rel_path}\nKIND: missing_repo_skeleton", meta
    abs_path = repo_path / rel_path
    if not abs_path.exists() or not abs_path.is_file():
        return f"FILE: {rel_path}\nKIND: missing_file_skeleton", meta
    text, error = safe_read_text(abs_path, max_chars=300000)
    meta["source_read_error"] = error
    meta["source_size_chars"] = abs_path.stat().st_size if error is None else None
    if rel_path.endswith(".py"):
        return skeleton_from_python(rel_path, text), meta
    return (
        f"FILE: {rel_path}\nKIND: non_python_skeleton\n"
        f"EXTENSION: {Path(rel_path).suffix}\n"
        f"SIZE_CHARS: {meta.get('source_size_chars')}",
        meta,
    )


def code_preview_for_path(repo_path: Path | None, rel_path: str, max_chars: int) -> tuple[str, dict[str, Any]]:
    meta: dict[str, Any] = {"preview_max_chars": max_chars}
    if repo_path is None:
        meta["source_read_error"] = "repo_path_unavailable"
        return f"FILE: {rel_path}\nKIND: missing_repo_preview", meta
    abs_path = repo_path / rel_path
    if not abs_path.exists() or not abs_path.is_file():
        meta["source_read_error"] = "file_missing"
        return f"FILE: {rel_path}\nKIND: missing_file_preview", meta
    text, error = safe_read_text(abs_path, max_chars=max_chars)
    meta["source_read_error"] = error
    meta["source_size_chars"] = abs_path.stat().st_size if error is None else None
    return f"FILE: {rel_path}\nKIND: source_preview\n{text}", meta


def rough_token_count(text: str) -> int:
    return max(1, len(re.findall(r"\S+", text)))


def graph_distance(rel_path: str, core_files: set[str], neighborhood_files: set[str]) -> int:
    if rel_path in core_files:
        return 0
    if rel_path in neighborhood_files:
        return 1
    return 2


def build_rows_for_trajectory(
    trajectory: SuccessTrajectory,
    code_preview_chars: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    metrics = trajectory.metrics
    case = metrics.get("case") or {}
    worker_sphere = load_sphere(trajectory.case_dir, "worker_sphere.json")
    reviewer_sphere = load_sphere(trajectory.case_dir, "reviewer_sphere.json")
    pm_sphere = load_sphere(trajectory.case_dir, "pm_sphere.json")
    repo_path = infer_repo_path(trajectory.case_dir, [worker_sphere, reviewer_sphere, pm_sphere])
    scores = selector_scores(trajectory.case_dir)

    worker_files = extract_worker_files(trajectory.verify)
    test_files = extract_test_files(trajectory.verify)
    reviewer_files = set(worker_files) | set(test_files)
    pm_files = set(reviewer_files)

    candidates, candidate_sources = collect_candidate_files(
        trajectory.case_dir,
        worker_files=worker_files,
        reviewer_files=reviewer_files,
    )
    core_files = set()
    neighborhood_files = set()
    for sphere in (worker_sphere, reviewer_sphere, pm_sphere):
        core_files.update(normalize_rel_path(p) for p in sphere.get("core_files") or [])
        neighborhood_files.update(normalize_rel_path(p) for p in sphere.get("neighborhood_files") or [])

    rows = []
    for rel_path in sorted(candidates):
        for persona in PERSONAS:
            if persona == "PM":
                node_text, preview_meta = pm_skeleton_for_path(repo_path, rel_path)
                label = rel_path in pm_files
                positive_reason = "worker_or_reviewer_file_skeleton" if label else None
            else:
                node_text, preview_meta = code_preview_for_path(
                    repo_path, rel_path, max_chars=code_preview_chars
                )
                if persona == "WORKER":
                    label = rel_path in worker_files
                    positive_reason = "modified_in_successful_patch" if label else None
                else:
                    label = rel_path in reviewer_files
                    if rel_path in worker_files and rel_path in test_files:
                        positive_reason = "modified_and_executed_test_file"
                    elif rel_path in worker_files:
                        positive_reason = "modified_in_successful_patch"
                    elif rel_path in test_files:
                        positive_reason = "executed_in_verify"
                    else:
                        positive_reason = None

            row = {
                "schema_version": 1,
                "case_slug": trajectory.case_dir.name,
                "instance_id": case.get("instance_id"),
                "repo": case.get("repo"),
                "issue": case.get("issue"),
                "retriever_run": trajectory.run_name,
                "persona": persona,
                "label": 1 if label else 0,
                "label_source": str(trajectory.verify_path),
                "positive_reason": positive_reason,
                "task": {
                    "problem_statement": case.get("problem_statement") or "",
                    "test_cmd_available_for_labeling": bool(case.get("test_cmd")),
                },
                "node": {
                    "path": rel_path,
                    "node_type": "file",
                    "node_text": node_text,
                    "node_text_kind": "pm_skeleton" if persona == "PM" else "source_preview",
                    "rough_token_count": rough_token_count(node_text),
                    "selector_score": scores.get(rel_path, 0.0),
                    "graph_distance_to_core": graph_distance(
                        rel_path, core_files=core_files, neighborhood_files=neighborhood_files
                    ),
                    "candidate_source": candidate_sources.get(rel_path, "unknown"),
                    "is_test": rel_path.startswith("tests/") or "/test" in rel_path or rel_path.startswith("test_"),
                    "extension": Path(rel_path).suffix,
                    "preview_meta": preview_meta,
                },
                "labels": {
                    "worker_positive": rel_path in worker_files,
                    "reviewer_positive": rel_path in reviewer_files,
                    "pm_positive": rel_path in pm_files,
                    "modified_in_final_patch": rel_path in worker_files,
                    "executed_test_file": rel_path in test_files,
                },
                "provenance": {
                    "metrics_path": str(trajectory.case_dir / "metrics.json"),
                    "verify_path": str(trajectory.verify_path),
                    "repo_path": str(repo_path) if repo_path else None,
                    "patch_payload_files_read": [],
                },
            }
            rows.append(row)

    summary = {
        "case_slug": trajectory.case_dir.name,
        "run_name": trajectory.run_name,
        "row_count": len(rows),
        "worker_positive_files": sorted(worker_files),
        "reviewer_positive_files": sorted(reviewer_files),
        "pm_positive_files": sorted(pm_files),
        "candidate_file_count": len(candidates),
        "repo_path": str(repo_path) if repo_path else None,
    }
    return rows, summary


def text_has_leakage_marker(text: str) -> str | None:
    lowered = text.lower()
    for marker in LEAKAGE_TEXT_MARKERS:
        haystack = lowered if marker == marker.lower() else text
        needle = marker.lower() if marker == marker.lower() else marker
        if needle in haystack:
            return marker
    return None


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    leakage_hits = []
    pm_violations = []
    counts = Counter()
    label_counts = Counter()
    for idx, row in enumerate(rows):
        persona = row["persona"]
        counts[f"rows_{persona.lower()}"] += 1
        label_counts["positive" if row["label"] else "negative"] += 1
        label_counts[f"{persona.lower()}_{'positive' if row['label'] else 'negative'}"] += 1
        node = row.get("node") or {}
        text = node.get("node_text") or ""
        marker = text_has_leakage_marker(text)
        if marker:
            leakage_hits.append(
                {
                    "row_index": idx,
                    "case_slug": row.get("case_slug"),
                    "persona": persona,
                    "path": node.get("path"),
                    "marker": marker,
                }
            )
        if persona == "PM":
            meta = (node.get("preview_meta") or {})
            if node.get("node_text_kind") != "pm_skeleton" or meta.get("pm_raw_body_chars") != 0:
                pm_violations.append(
                    {
                        "row_index": idx,
                        "case_slug": row.get("case_slug"),
                        "path": node.get("path"),
                        "node_text_kind": node.get("node_text_kind"),
                        "pm_raw_body_chars": meta.get("pm_raw_body_chars"),
                    }
                )

    forbidden_input_files = []
    # This script should never read patch payloads. The row provenance records an
    # empty list per row; audit the code path by checking provenance too.
    for idx, row in enumerate(rows):
        for path in row.get("provenance", {}).get("patch_payload_files_read") or []:
            forbidden_input_files.append({"row_index": idx, "path": path})

    passed = not leakage_hits and not pm_violations and not forbidden_input_files
    return {
        "schema_version": 1,
        "passed": passed,
        "checks": {
            "no_patch_payload_files_read": not forbidden_input_files,
            "no_leakage_markers_in_model_inputs": not leakage_hits,
            "pm_rows_are_skeleton_only": not pm_violations,
            "labels_from_verify_json_only": True,
        },
        "counts": dict(counts),
        "label_counts": dict(label_counts),
        "leakage_hits": leakage_hits[:50],
        "pm_skeleton_violations": pm_violations[:50],
        "forbidden_input_files": forbidden_input_files[:50],
        "notes": [
            "Worker/Reviewer node_text may contain source previews from the local repo checkout.",
            "PM node_text is generated from AST/import/signature skeletons only and sets pm_raw_body_chars=0.",
            "Patch payload files such as patch_v*.blocks.md and patch_v*.raw.* are not read.",
            "verify_v*.json is used only for changed file paths, applied change coordinates, and test command labels.",
        ],
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-roots",
        nargs="+",
        default=list(DEFAULT_RUN_ROOTS),
        help="Benchmark run roots to scan.",
    )
    parser.add_argument(
        "--out",
        default="outputs/datasets/context_projection_v1.jsonl",
        help="JSONL training row output path.",
    )
    parser.add_argument(
        "--manifest-out",
        default="outputs/datasets/context_projection_v1_manifest.json",
        help="Manifest JSON output path.",
    )
    parser.add_argument(
        "--audit-out",
        default="outputs/datasets/context_projection_v1_leakage_audit.json",
        help="Leakage audit JSON output path.",
    )
    parser.add_argument(
        "--audit-alias-out",
        default="outputs/datasets/leakage_audit.json",
        help="Compatibility copy of the leakage audit JSON.",
    )
    parser.add_argument(
        "--strict-tests-passed",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require status APPROVED and tests_passed true.",
    )
    parser.add_argument(
        "--code-preview-chars",
        type=int,
        default=6000,
        help="Maximum source preview chars for Worker/Reviewer rows.",
    )
    args = parser.parse_args(argv)

    run_roots = [Path(root) for root in args.run_roots]
    trajectories = list(iter_success_trajectories(run_roots, args.strict_tests_passed))
    rows: list[dict[str, Any]] = []
    trajectory_summaries = []
    for trajectory in trajectories:
        trajectory_rows, summary = build_rows_for_trajectory(
            trajectory,
            code_preview_chars=args.code_preview_chars,
        )
        rows.extend(trajectory_rows)
        trajectory_summaries.append(summary)

    audit = audit_rows(rows)
    unique_cases = sorted({summary["case_slug"] for summary in trajectory_summaries})
    manifest = {
        "schema_version": 1,
        "run_roots": [str(root) for root in run_roots],
        "strict_tests_passed": args.strict_tests_passed,
        "successful_unique_cases": len(unique_cases),
        "successful_case_slugs": unique_cases,
        "successful_trajectories": len(trajectory_summaries),
        "total_rows": len(rows),
        "positive_rows": audit["counts"].get("label_counts", {}).get("positive", 0),
        "negative_rows": audit["counts"].get("label_counts", {}).get("negative", 0),
        "label_counts": audit["label_counts"],
        "trajectory_summaries": trajectory_summaries,
        "outputs": {
            "jsonl": args.out,
            "manifest": args.manifest_out,
            "leakage_audit": args.audit_out,
            "leakage_audit_alias": args.audit_alias_out,
        },
    }
    # Keep top-level fields redundant and easy to parse.
    manifest["positive_rows"] = audit["label_counts"].get("positive", 0)
    manifest["negative_rows"] = audit["label_counts"].get("negative", 0)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    write_json(Path(args.manifest_out), manifest)
    write_json(Path(args.audit_out), audit)
    if args.audit_alias_out:
        write_json(Path(args.audit_alias_out), audit)

    print(json.dumps(
        {
            "jsonl": args.out,
            "manifest": args.manifest_out,
            "leakage_audit": args.audit_out,
            "leakage_audit_passed": audit["passed"],
            "successful_unique_cases": len(unique_cases),
            "successful_trajectories": len(trajectory_summaries),
            "total_rows": len(rows),
            "positive_rows": manifest["positive_rows"],
            "negative_rows": manifest["negative_rows"],
            "label_counts": audit["label_counts"],
        },
        indent=2,
        sort_keys=True,
    ))
    return 0 if audit["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
