"""Assemble selector output into persona-specific Context Sphere prompts."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from context_sphere_v3.roles import ROLE_PM
from context_sphere_v3.roles import ROLE_REVIEWER
from context_sphere_v3.roles import ROLE_WORKER
from context_sphere_v3.roles import validate_role


PYTHON_SUFFIXES = (".py", ".pyi")
DEFAULT_MAX_FILE_CHARS = 12_000
DEFAULT_MAX_NEIGHBORHOOD_FILES = 24

PERSONA_TEMPLATES = {
    ROLE_WORKER: {
        "title": "Worker Lens",
        "focus": "logical correctness, diff generation, code implementation, tests, control flow, and breaking changes",
        "instructions": [
            "Use the Core Evidence first when deciding what to edit.",
            "Use the Neighborhood only to understand dependencies, imported helpers, and adjacent contracts.",
            "Produce concrete implementation steps and patches; avoid product speculation unless it affects code shape.",
            "Call out tests that should be added or updated before claiming the change is complete.",
        ],
    },
    ROLE_PM: {
        "title": "PM Lens",
        "focus": "product impact, user experience, project timeline, requirements, and trade-offs",
        "instructions": [
            "Translate the Core Evidence into user-visible behavior and requirement risk.",
            "Use the Neighborhood to identify dependency or ownership areas that may affect scope.",
            "Prefer crisp trade-off framing over implementation detail unless the detail changes delivery risk.",
            "Call out decisions that need human prioritization.",
        ],
    },
    ROLE_REVIEWER: {
        "title": "Reviewer Lens",
        "focus": "security vulnerabilities, architecture, maintainability, standards, regressions, and test adequacy",
        "instructions": [
            "Review the Core Evidence for correctness, security, and maintainability risks.",
            "Use the Neighborhood to check imported contracts and architectural boundaries.",
            "Prioritize concrete defects, missing tests, and unsafe assumptions.",
            "Do not approve broad rewrites unless the evidence shows the current design is the problem.",
        ],
    },
}


@dataclass(frozen=True)
class ContextFile:
    path: str
    absolute_path: Path
    content: str
    truncated: bool
    source: str
    selector_score: float | None = None
    import_reason: str | None = None


def load_selector_output(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def safe_repo_relative(repo_path: str | Path, candidate: str | Path) -> Path | None:
    repo = Path(repo_path).resolve()
    path = (repo / candidate).resolve() if not Path(candidate).is_absolute() else Path(candidate).resolve()
    try:
        path.relative_to(repo)
    except ValueError:
        return None
    return path


def clip_content(content: str, *, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0 or len(content) <= max_chars:
        return content, False
    clipped = content[:max_chars].rstrip()
    return f"{clipped}\n\n[... clipped after {max_chars} characters ...]", True


def file_exists_under_repo(repo_path: str | Path, relative_path: str) -> Path | None:
    path = safe_repo_relative(repo_path, relative_path)
    if path is None or not path.is_file():
        return None
    return path


def selected_file_rows(selector_output: dict[str, Any], *, max_core_files: int | None = None) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for row in selector_output.get("top_files", []) or []:
        path = str(row.get("path", "")).strip()
        if not path or path in seen:
            continue
        seen.add(path)
        rows.append({"path": path, "score": row.get("score"), "source": "top_files"})
    if not rows:
        for path in paths_mentioned_in_chunks(selector_output.get("top_chunks", []) or []):
            if path in seen:
                continue
            seen.add(path)
            rows.append({"path": path, "score": None, "source": "top_chunks_path_mention"})
    return rows if max_core_files is None else rows[:max_core_files]


def paths_mentioned_in_chunks(chunks: list[dict[str, Any]]) -> list[str]:
    pattern = re.compile(r"(?P<path>(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.(?:py|pyi|js|ts|tsx|jsx|go|rs|java|md|rst|txt|yaml|yml|toml|json))")
    paths = []
    for chunk in chunks:
        text = str(chunk.get("text", ""))
        for match in pattern.finditer(text):
            paths.append(match.group("path").lstrip("/"))
    return paths


def read_context_file(
    repo_path: str | Path,
    relative_path: str,
    *,
    source: str,
    max_file_chars: int,
    selector_score: float | None = None,
    import_reason: str | None = None,
) -> ContextFile | None:
    absolute = file_exists_under_repo(repo_path, relative_path)
    if absolute is None:
        return None
    content, truncated = clip_content(absolute.read_text(encoding="utf-8", errors="replace"), max_chars=max_file_chars)
    return ContextFile(
        path=relative_path,
        absolute_path=absolute,
        content=content,
        truncated=truncated,
        source=source,
        selector_score=float(selector_score) if selector_score is not None else None,
        import_reason=import_reason,
    )


def collect_core_files(
    selector_output: dict[str, Any],
    repo_path: str | Path,
    *,
    max_core_files: int | None,
    max_file_chars: int,
) -> tuple[list[ContextFile], list[str]]:
    core = []
    missing = []
    for row in selected_file_rows(selector_output, max_core_files=max_core_files):
        file = read_context_file(
            repo_path,
            row["path"],
            source=str(row["source"]),
            max_file_chars=max_file_chars,
            selector_score=row.get("score"),
        )
        if file is None:
            missing.append(row["path"])
        else:
            core.append(file)
    return core, missing


def parse_python_imports(file_path: Path, *, repo_path: str | Path) -> list[str]:
    if file_path.suffix not in PYTHON_SUFFIXES:
        return []
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = resolve_import_from_module(node, file_path=file_path, repo_path=repo_path)
            if module:
                modules.append(module)
    return modules


def resolve_import_from_module(node: ast.ImportFrom, *, file_path: Path, repo_path: str | Path) -> str | None:
    module = node.module or ""
    if node.level <= 0:
        return module or None
    repo = Path(repo_path).resolve()
    try:
        rel_parts = file_path.parent.resolve().relative_to(repo).parts
    except ValueError:
        return module or None
    package_parts = list(rel_parts)
    if package_parts and package_parts[0] in {"src", "lib"}:
        package_parts = package_parts[1:]
    if node.level > 1:
        package_parts = package_parts[: -(node.level - 1)]
    if module:
        package_parts.extend(module.split("."))
    return ".".join(part for part in package_parts if part)


def module_candidate_paths(module_name: str, *, importing_file: Path, repo_path: str | Path) -> list[str]:
    parts = [part for part in module_name.split(".") if part]
    if not parts:
        return []
    repo = Path(repo_path).resolve()
    roots = [repo, repo / "src", repo / "lib"]
    candidates: list[str] = []
    for root in roots:
        module_path = Path(*parts)
        for candidate in (root / module_path.with_suffix(".py"), root / module_path / "__init__.py"):
            try:
                relative = candidate.resolve().relative_to(repo)
            except ValueError:
                continue
            candidates.append(relative.as_posix())
    # Also handle intra-package imports where a local module name is imported without package prefix.
    for candidate in (
        importing_file.parent / Path(*parts).with_suffix(".py"),
        importing_file.parent / Path(*parts) / "__init__.py",
    ):
        try:
            relative = candidate.resolve().relative_to(repo)
        except ValueError:
            continue
        candidates.append(relative.as_posix())
    return list(dict.fromkeys(candidates))


def resolve_import_to_file(module_name: str, *, importing_file: Path, repo_path: str | Path) -> str | None:
    for relative in module_candidate_paths(module_name, importing_file=importing_file, repo_path=repo_path):
        if file_exists_under_repo(repo_path, relative) is not None:
            return relative
    return None


def expand_neighborhood(
    core_files: list[ContextFile],
    repo_path: str | Path,
    *,
    max_file_chars: int,
    max_neighborhood_files: int,
) -> list[ContextFile]:
    if max_neighborhood_files <= 0:
        return []
    core_paths = {file.path for file in core_files}
    neighborhood: list[ContextFile] = []
    seen = set(core_paths)
    for core_file in core_files:
        for module in parse_python_imports(core_file.absolute_path, repo_path=repo_path):
            relative = resolve_import_to_file(module, importing_file=core_file.absolute_path, repo_path=repo_path)
            if relative is None or relative in seen:
                continue
            file = read_context_file(
                repo_path,
                relative,
                source="one_level_import_expansion",
                max_file_chars=max_file_chars,
                import_reason=f"imported by {core_file.path} as {module}",
            )
            if file is None:
                continue
            neighborhood.append(file)
            seen.add(relative)
            if len(neighborhood) >= max_neighborhood_files:
                return neighborhood
    return neighborhood


def markdown_code_block(path: str, content: str) -> str:
    suffix = Path(path).suffix.lower()
    language = "python" if suffix in PYTHON_SUFFIXES else ""
    fence = "```"
    if "```" in content:
        fence = "````"
    return f"{fence}{language}\n{content}\n{fence}"


def render_context_file(file: ContextFile, *, index: int, section: str) -> str:
    metadata = [f"source: `{file.source}`"]
    if file.selector_score is not None:
        metadata.append(f"selector score: `{file.selector_score:.4f}`")
    if file.import_reason:
        metadata.append(f"reason: {file.import_reason}")
    if file.truncated:
        metadata.append("content clipped")
    return "\n".join(
        [
            f"### {section} {index}: `{file.path}`",
            "",
            "- " + "; ".join(metadata),
            "",
            markdown_code_block(file.path, file.content),
        ]
    )


def render_persona_instructions(role: str) -> str:
    template = PERSONA_TEMPLATES[validate_role(role)]
    lines = [
        f"## Persona Instructions: {template['title']}",
        "",
        f"Focus: {template['focus']}.",
        "",
    ]
    lines.extend(f"- {instruction}" for instruction in template["instructions"])
    return "\n".join(lines)


def assemble_context_sphere(
    *,
    selector_output: dict[str, Any],
    repo_path: str | Path,
    target_persona: str,
    max_core_files: int | None = None,
    max_file_chars: int = DEFAULT_MAX_FILE_CHARS,
    max_neighborhood_files: int = DEFAULT_MAX_NEIGHBORHOOD_FILES,
) -> dict[str, Any]:
    role = validate_role(target_persona)
    core_files, missing_core_files = collect_core_files(
        selector_output,
        repo_path,
        max_core_files=max_core_files,
        max_file_chars=max_file_chars,
    )
    neighborhood = expand_neighborhood(
        core_files,
        repo_path,
        max_file_chars=max_file_chars,
        max_neighborhood_files=max_neighborhood_files,
    )
    markdown = render_context_sphere_markdown(
        selector_output=selector_output,
        repo_path=repo_path,
        target_persona=role,
        core_files=core_files,
        neighborhood_files=neighborhood,
        missing_core_files=missing_core_files,
    )
    return {
        "schema_version": 1,
        "target_persona": role,
        "repo_path": str(Path(repo_path).resolve()),
        "core_file_count": len(core_files),
        "neighborhood_file_count": len(neighborhood),
        "missing_core_files": missing_core_files,
        "core_files": [file.path for file in core_files],
        "neighborhood_files": [file.path for file in neighborhood],
        "markdown": markdown,
    }


def render_context_sphere_markdown(
    *,
    selector_output: dict[str, Any],
    repo_path: str | Path,
    target_persona: str,
    core_files: list[ContextFile],
    neighborhood_files: list[ContextFile],
    missing_core_files: list[str],
) -> str:
    issue = selector_output.get("issue") or {}
    title = str(issue.get("title") or issue.get("source") or "Selector Output")
    lines = [
        "# Context Sphere Lens",
        "",
        f"- Persona: `{validate_role(target_persona)}`",
        f"- Repository root: `{Path(repo_path).resolve()}`",
        f"- Selector source: `{issue.get('source', 'unknown')}`",
        f"- Issue/title: {title}",
        f"- Core files: `{len(core_files)}`",
        f"- Neighborhood files: `{len(neighborhood_files)}`",
        "",
        render_persona_instructions(target_persona),
        "",
        "## Core Evidence",
        "",
    ]
    if not core_files:
        lines.append("_No selector files were found under the provided repo path._")
    for index, file in enumerate(core_files, start=1):
        lines.append(render_context_file(file, index=index, section="Core"))
        lines.append("")
    if missing_core_files:
        lines.extend(["### Missing Core Files", ""])
        lines.extend(f"- `{path}`" for path in missing_core_files)
        lines.append("")
    lines.extend(["## Neighborhood", ""])
    if not neighborhood_files:
        lines.append("_No one-level local import dependencies were resolved._")
    for index, file in enumerate(neighborhood_files, start=1):
        lines.append(render_context_file(file, index=index, section="Neighborhood"))
        lines.append("")
    lines.extend(
        [
            "## Selector Chunks",
            "",
            "These chunks explain the centroid that produced the core file ranking.",
            "",
        ]
    )
    for index, chunk in enumerate(selector_output.get("top_chunks", []) or [], start=1):
        text = str(chunk.get("text", "")).replace("\n", " ").strip()
        if len(text) > 500:
            text = f"{text[:500].rstrip()} ..."
        lines.append(f"- `{index}` `{chunk.get('chunk_id', 'chunk')}` score `{float(chunk.get('score', 0.0)):.4f}`: {text}")
    return "\n".join(lines).rstrip() + "\n"
