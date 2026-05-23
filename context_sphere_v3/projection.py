"""Persona-conditioned Context Projection helpers."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from context_sphere_v3.assembler import ContextFile
from context_sphere_v3.assembler import collect_core_files
from context_sphere_v3.assembler import expand_neighborhood
from context_sphere_v3.assembler import markdown_code_block
from context_sphere_v3.assembler import render_persona_instructions
from context_sphere_v3.assembler import validate_role


PERSONAS = ("PM", "WORKER", "REVIEWER")


def load_projection_thresholds(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if "persona_thresholds" not in payload:
        raise ValueError(f"projection thresholds missing persona_thresholds: {path}")
    return payload


def problem_statement_from_selector(selector_output: dict[str, Any]) -> str:
    issue = selector_output.get("issue") if isinstance(selector_output.get("issue"), dict) else {}
    for key in ("problem_statement", "body", "title", "source"):
        value = issue.get(key)
        if isinstance(value, str) and value.strip():
            if key == "title" and isinstance(issue.get("body"), str):
                return f"{value}\n\n{issue['body']}".strip()
            return value.strip()
    chunks = selector_output.get("top_chunks") or []
    text = "\n\n".join(str(chunk.get("text", "")) for chunk in chunks if isinstance(chunk, dict))
    return text.strip()


def python_skeleton(source: str) -> str:
    """Return imports/classes/functions/signatures while stripping bodies."""

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return "\n".join(line for line in source.splitlines() if line.lstrip().startswith(("import ", "from ")))

    lines = source.splitlines()
    output: list[str] = []

    def snippet(node: ast.AST) -> str:
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
        return ""

    def function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef, indent: str) -> str:
        raw = lines[node.lineno - 1].strip()
        if raw.endswith(":"):
            return f"{indent}{raw} ..."
        return f"{indent}{raw}"

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            output.append(snippet(node).strip())
        elif isinstance(node, ast.ClassDef):
            bases = []
            for base in node.bases:
                try:
                    bases.append(ast.unparse(base))
                except Exception:
                    pass
            suffix = f"({', '.join(bases)})" if bases else ""
            output.append(f"class {node.name}{suffix}:")
            child_lines = []
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    child_lines.append(function_signature(child, "    "))
                elif isinstance(child, (ast.Assign, ast.AnnAssign)):
                    text = snippet(child).strip().split("=", 1)[0].rstrip()
                    if text:
                        child_lines.append(f"    {text} = ...")
            output.extend(child_lines or ["    ..."])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            output.append(function_signature(node, ""))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            text = snippet(node).strip().split("=", 1)[0].rstrip()
            if text:
                output.append(f"{text} = ...")
    return "\n".join(line for line in output if line.strip()).strip() + "\n"


def node_text_for_persona(node: dict[str, Any], persona: str) -> tuple[str, str, int]:
    content = str(node.get("content") or "")
    role = validate_role(persona)
    if role == "pm":
        if str(node.get("path", "")).endswith((".py", ".pyi")):
            return python_skeleton(content), "pm_skeleton", 0
        preview = "\n".join(content.splitlines()[:40])
        return preview, "pm_metadata_preview", 0
    return content, "full_text", len(content)


def make_projection_query(*, persona: str, problem_statement: str) -> str:
    return f"Persona: {persona} | Task: {problem_statement}"


def score_nodes_with_cross_encoder(
    *,
    nodes: list[dict[str, Any]],
    problem_statement: str,
    model_dir: str | Path,
    device: str,
    batch_size: int,
) -> list[dict[str, Any]]:
    try:
        from sentence_transformers import CrossEncoder
    except ModuleNotFoundError as exc:  # pragma: no cover - environment guard.
        raise RuntimeError("sentence-transformers is required for projection mode") from exc

    if device == "auto":
        try:
            import torch

            if torch.cuda.is_available():
                device = "cuda"
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        except Exception:
            device = "cpu"
    model = CrossEncoder(str(model_dir), device=device)
    enriched = [dict(node) for node in nodes]
    for persona in PERSONAS:
        pairs = []
        for node in enriched:
            text, _kind, _raw_chars = node_text_for_persona(node, persona)
            pairs.append([make_projection_query(persona=persona, problem_statement=problem_statement), text])
        raw_scores = model.predict(
            pairs,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        for node, score in zip(enriched, raw_scores):
            score_value = float(score)
            if score_value < 0.0 or score_value > 1.0:
                import math

                score_value = 1.0 / (1.0 + math.exp(-score_value))
            node.setdefault("projection_scores", {})[persona] = score_value
    return enriched


def apply_persona_thresholds(
    nodes: list[dict[str, Any]],
    thresholds: dict[str, Any],
    *,
    min_k: int = 0,
) -> dict[str, list[dict[str, Any]]]:
    threshold_rows = thresholds.get("persona_thresholds") or {}
    output: dict[str, list[dict[str, Any]]] = {}
    for persona in PERSONAS:
        threshold = float(threshold_rows[persona]["recommended_threshold"])
        scored_nodes = sorted(
            nodes,
            key=lambda node: (float((node.get("projection_scores") or {}).get(persona, 0.0)), str(node.get("path") or "")),
            reverse=True,
        )
        threshold_selected = [
            node
            for node in scored_nodes
            if float((node.get("projection_scores") or {}).get(persona, 0.0)) >= threshold
        ]
        if len(threshold_selected) < min_k:
            selected_source = scored_nodes[: min(min_k, len(scored_nodes))]
            selection_reason = "min_k_floor"
        else:
            selected_source = threshold_selected
            selection_reason = "threshold"
        selected = []
        for node in selected_source:
            score = float((node.get("projection_scores") or {}).get(persona, 0.0))
            node_text, kind, raw_body_chars = node_text_for_persona(node, persona)
            selected.append(
                {
                    "path": node["path"],
                    "source": node.get("source"),
                    "selector_score": node.get("selector_score"),
                    "projection_score": score,
                    "projection_threshold": threshold,
                    "projection_min_k": min_k,
                    "projection_selection_reason": selection_reason,
                    "node_text": node_text,
                    "node_text_kind": kind,
                    "raw_body_chars": raw_body_chars,
                    "section": node.get("section", "core"),
                    "truncated": bool(node.get("truncated")),
                    "import_reason": node.get("import_reason"),
                }
            )
        output[persona] = selected
    return output


def files_to_projection_nodes(files: list[ContextFile], *, section: str) -> list[dict[str, Any]]:
    return [
        {
            "path": file.path,
            "source": file.source,
            "selector_score": file.selector_score,
            "content": file.content,
            "section": section,
            "truncated": file.truncated,
            "import_reason": file.import_reason,
        }
        for file in files
    ]


def render_projected_markdown(
    *,
    selector_output: dict[str, Any],
    repo_path: str | Path,
    persona: str,
    selected_nodes: list[dict[str, Any]],
) -> str:
    issue = selector_output.get("issue") or {}
    title = str(issue.get("title") or issue.get("source") or "Selector Output")
    core = [node for node in selected_nodes if node.get("section") == "core"]
    neighborhood = [node for node in selected_nodes if node.get("section") == "neighborhood"]
    lines = [
        "# Context Sphere Lens",
        "",
        f"- Persona: `{validate_role(persona)}`",
        f"- Repository root: `{Path(repo_path).resolve()}`",
        f"- Selector source: `{issue.get('source', 'unknown')}`",
        f"- Issue/title: {title}",
        "- Retrieval mode: `projection`",
        f"- Core files: `{len(core)}`",
        f"- Neighborhood files: `{len(neighborhood)}`",
        "",
        render_persona_instructions(persona),
        "",
        "## Core Evidence",
        "",
    ]
    if not core:
        lines.append("_No projected core files passed the persona threshold._")
    for index, node in enumerate(core, start=1):
        lines.append(render_projected_node(node, index=index, section="Core"))
        lines.append("")
    lines.extend(["## Neighborhood", ""])
    if not neighborhood:
        lines.append("_No projected neighborhood files passed the persona threshold._")
    for index, node in enumerate(neighborhood, start=1):
        lines.append(render_projected_node(node, index=index, section="Neighborhood"))
        lines.append("")
    lines.extend(["## Selector Chunks", "", "These chunks explain the centroid that produced the master sphere.", ""])
    for index, chunk in enumerate(selector_output.get("top_chunks", []) or [], start=1):
        text = str(chunk.get("text", "")).replace("\n", " ").strip()
        if len(text) > 500:
            text = f"{text[:500].rstrip()} ..."
        lines.append(f"- `{index}` `{chunk.get('chunk_id', 'chunk')}` score `{float(chunk.get('score', 0.0)):.4f}`: {text}")
    return "\n".join(lines).rstrip() + "\n"


def render_projected_node(node: dict[str, Any], *, index: int, section: str) -> str:
    metadata = [
        f"source: `{node.get('source')}`",
        f"projection score: `{float(node.get('projection_score', 0.0)):.4f}`",
        f"threshold: `{float(node.get('projection_threshold', 0.0)):.4f}`",
        f"text kind: `{node.get('node_text_kind')}`",
        f"raw body chars: `{int(node.get('raw_body_chars') or 0)}`",
    ]
    if node.get("selector_score") is not None:
        metadata.append(f"selector score: `{float(node['selector_score']):.4f}`")
    if node.get("import_reason"):
        metadata.append(f"reason: {node['import_reason']}")
    if node.get("truncated"):
        metadata.append("content clipped")
    return "\n".join(
        [
            f"### {section} {index}: `{node['path']}`",
            "",
            "- " + "; ".join(metadata),
            "",
            markdown_code_block(str(node["path"]), str(node.get("node_text") or "")),
        ]
    )


def assemble_projected_context_spheres(
    *,
    selector_output: dict[str, Any],
    repo_path: str | Path,
    model_dir: str | Path,
    thresholds_path: str | Path,
    device: str = "cpu",
    batch_size: int = 32,
    min_k: int = 2,
    max_core_files: int | None = None,
    max_file_chars: int = 12_000,
    max_neighborhood_files: int = 24,
) -> dict[str, Any]:
    thresholds = load_projection_thresholds(thresholds_path)
    core_files, missing_core_files = collect_core_files(
        selector_output,
        repo_path,
        max_core_files=max_core_files,
        max_file_chars=max_file_chars,
    )
    neighborhood_files = expand_neighborhood(
        core_files,
        repo_path,
        max_file_chars=max_file_chars,
        max_neighborhood_files=max_neighborhood_files,
    )
    nodes = files_to_projection_nodes(core_files, section="core") + files_to_projection_nodes(
        neighborhood_files,
        section="neighborhood",
    )
    problem_statement = problem_statement_from_selector(selector_output)
    scored_nodes = score_nodes_with_cross_encoder(
        nodes=nodes,
        problem_statement=problem_statement,
        model_dir=model_dir,
        device=device,
        batch_size=batch_size,
    )
    projected = apply_persona_thresholds(scored_nodes, thresholds, min_k=min_k)
    personas = {}
    for persona, selected_nodes in projected.items():
        markdown = render_projected_markdown(
            selector_output=selector_output,
            repo_path=repo_path,
            persona=persona,
            selected_nodes=selected_nodes,
        )
        personas[persona.lower()] = {
            "schema_version": 1,
            "target_persona": persona,
            "retrieval_mode": "projection",
            "repo_path": str(Path(repo_path).resolve()),
            "threshold": thresholds["persona_thresholds"][persona]["recommended_threshold"],
            "min_k": min_k,
            "selected_node_count": len(selected_nodes),
            "core_file_count": sum(1 for node in selected_nodes if node.get("section") == "core"),
            "neighborhood_file_count": sum(1 for node in selected_nodes if node.get("section") == "neighborhood"),
            "selected_nodes": selected_nodes,
            "core_files": [node["path"] for node in selected_nodes if node.get("section") == "core"],
            "neighborhood_files": [node["path"] for node in selected_nodes if node.get("section") == "neighborhood"],
            "markdown": markdown,
        }
    return {
        "schema_version": 1,
        "retrieval_mode": "projection",
        "model_dir": str(model_dir),
        "thresholds_path": str(thresholds_path),
        "missing_core_files": missing_core_files,
        "master_node_count": len(scored_nodes),
        "master_core_file_count": len(core_files),
        "master_neighborhood_file_count": len(neighborhood_files),
        "master_nodes": [
            {key: value for key, value in node.items() if key != "content"}
            | {"content_chars": len(str(node.get("content") or ""))}
            for node in scored_nodes
        ],
        "personas": personas,
    }
