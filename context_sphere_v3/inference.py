"""Inference helpers for consuming trained Context Sphere v3 selector weights."""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any

try:
    import torch
except ModuleNotFoundError:  # pragma: no cover - no-torch shell.
    torch = None  # type: ignore[assignment]

from context_sphere_v3.baselines import split_problem_statement
from context_sphere_v3.baselines import text_terms
from context_sphere_v3.checkpoints import load_checkpoint_model
from context_sphere_v3.neural_selector import DEFAULT_CHUNK_DIM
from context_sphere_v3.neural_selector import hashed_text_embedding
from context_sphere_v3.neural_selector import worker_role_embedding


GITHUB_ISSUE_RE = re.compile(r"https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<number>\d+)")
FILE_EXTENSIONS = {
    ".cfg",
    ".css",
    ".go",
    ".h",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".pyi",
    ".rb",
    ".rs",
    ".rst",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
IGNORED_REPO_DIRS = {
    ".eggs",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "node_modules",
    "venv",
}
DEFAULT_DENSE_RETRIEVER_MODEL = "all-MiniLM-L6-v2"
DEFAULT_DENSE_FILE_TOKEN_LIMIT = 768


def _require_torch() -> None:
    if torch is None:
        raise RuntimeError("PyTorch is required for inference")


def github_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "context-sphere-v3-inference",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_github_issue_url(issue_url: str) -> tuple[str, str, int]:
    match = GITHUB_ISSUE_RE.fullmatch(issue_url.rstrip("/"))
    if not match:
        raise ValueError(f"unsupported GitHub issue URL: {issue_url}")
    return match.group("owner"), match.group("repo"), int(match.group("number"))


def fetch_github_issue(issue_url: str) -> dict[str, Any]:
    owner, repo, number = parse_github_issue_url(issue_url)
    issue = github_json(f"https://api.github.com/repos/{owner}/{repo}/issues/{number}")
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    return {
        "source": issue_url,
        "owner": owner,
        "repo": repo,
        "number": number,
        "title": title,
        "body": body,
        "problem_statement": f"{title}\n\n{body}".strip(),
    }


def fetch_github_repo_files(owner: str, repo: str, *, max_raw_files: int = 5000) -> list[str]:
    repo_payload = github_json(f"https://api.github.com/repos/{owner}/{repo}")
    default_branch = str(repo_payload.get("default_branch") or "main")
    tree = github_json(f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1")
    files = []
    for row in tree.get("tree", []):
        if row.get("type") != "blob":
            continue
        path = str(row.get("path") or "")
        if Path(path).suffix.lower() in FILE_EXTENSIONS:
            files.append(path)
        if len(files) >= max_raw_files:
            break
    return files


def load_candidate_files(path: str | Path) -> list[str]:
    return [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def prefilter_candidate_files(problem_statement: str, candidate_files: list[str], *, limit: int) -> list[str]:
    issue_terms = text_terms(problem_statement)

    def score(path: str) -> tuple[int, int, int, str]:
        path_terms = text_terms(path.replace("/", " "))
        overlap = len(issue_terms & path_terms)
        basename_bonus = 1 if Path(path).stem.lower() in issue_terms else 0
        depth_penalty = -path.count("/")
        return (overlap, basename_bonus, depth_penalty, path)

    ranked = sorted(candidate_files, key=score, reverse=True)
    return ranked[:limit]


def score_problem_chunks(
    *,
    checkpoint_path: str | Path,
    problem_statement: str,
    device: str = "cpu",
    top_k_chunks: int = 5,
) -> dict[str, Any]:
    _require_torch()
    chunks = split_problem_statement(problem_statement)
    if not chunks:
        raise ValueError("problem statement has no nonempty chunks")
    chunk_dim = DEFAULT_CHUNK_DIM
    embeddings = [hashed_text_embedding(str(chunk["text"]), dim=chunk_dim) for chunk in chunks]
    model, config, payload = load_checkpoint_model(checkpoint_path, device=device, fallback_chunk_dim=chunk_dim)
    torch_device = torch.device(device)
    chunk_tensor = torch.tensor([embeddings], dtype=torch.float32, device=torch_device)
    role_tensor = torch.tensor([worker_role_embedding(dim=config.role_dim)], dtype=torch.float32, device=torch_device)
    with torch.no_grad():
        scores = model(chunk_tensor, role_tensor)[0]
    k = min(top_k_chunks, int(scores.shape[0]))
    top_indices = torch.topk(scores, k=k).indices.detach().cpu().tolist()
    return {
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_step": payload.get("step"),
        "checkpoint_epoch": payload.get("epoch"),
        "chunks": chunks,
        "scores": [float(value) for value in scores.detach().cpu().tolist()],
        "top_indices": top_indices,
        "top_chunks": [
            {
                "chunk_id": str(chunks[index]["chunk_id"]),
                "score": float(scores[index].detach().cpu().item()),
                "text": str(chunks[index]["text"]),
            }
            for index in top_indices
        ],
    }


def rank_files_from_selected_chunks(
    *,
    problem_statement: str,
    selected_chunks: list[dict[str, Any]],
    candidate_files: list[str],
    top_k_files: int = 5,
) -> list[dict[str, Any]]:
    issue_terms = text_terms(problem_statement)
    selected_terms = set()
    for chunk in selected_chunks:
        selected_terms |= text_terms(str(chunk.get("text", "")))

    rows = []
    for path in candidate_files:
        path_terms = text_terms(path.replace("/", " "))
        exact_mention = path in problem_statement
        basename_mention = Path(path).name in problem_statement
        score = (
            4.0 * int(exact_mention)
            + 2.0 * int(basename_mention)
            + 1.5 * len(path_terms & selected_terms)
            + 0.5 * len(path_terms & issue_terms)
            - 0.01 * path.count("/")
        )
        rows.append(
            {
                "path": path,
                "score": score,
                "exact_mention": exact_mention,
                "basename_mention": basename_mention,
                "overlap_terms": sorted(path_terms & (selected_terms | issue_terms)),
            }
        )
    rows.sort(key=lambda row: (row["score"], row["path"]), reverse=True)
    return rows[:top_k_files]


def list_repo_python_files(repo_path: str | Path) -> list[str]:
    root = Path(repo_path)
    files = []
    for path in root.rglob("*.py"):
        if any(part in IGNORED_REPO_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            files.append(path.relative_to(root).as_posix())
    return sorted(files)


def rank_files_with_tfidf(
    *,
    problem_statement: str,
    repo_path: str | Path,
    top_k_files: int = 5,
    max_file_chars: int = 100_000,
) -> list[dict[str, Any]]:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ModuleNotFoundError as exc:  # pragma: no cover - environment guard.
        raise RuntimeError("scikit-learn is required for --retriever baseline") from exc

    root = Path(repo_path)
    file_paths = list_repo_python_files(root)
    documents: list[str] = []
    readable_paths: list[str] = []
    for relative_path in file_paths:
        path = root / relative_path
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        documents.append(text[:max_file_chars])
        readable_paths.append(relative_path)
    if not documents:
        return []

    matrix = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        token_pattern=r"(?u)\b[A-Za-z_][A-Za-z0-9_./-]*\b",
        max_features=100_000,
    ).fit_transform([problem_statement] + documents)
    similarities = cosine_similarity(matrix[0:1], matrix[1:]).ravel()
    order = sorted(range(len(readable_paths)), key=lambda index: (float(similarities[index]), readable_paths[index]), reverse=True)
    rows = []
    for index in order[:top_k_files]:
        score = float(similarities[index])
        rows.append(
            {
                "path": readable_paths[index],
                "score": score,
                "retriever": "baseline_tfidf",
                "content_chars": len(documents[index]),
                "exact_mention": readable_paths[index] in problem_statement,
                "basename_mention": Path(readable_paths[index]).name in problem_statement,
            }
        )
    return rows


def truncate_whitespace_tokens(text: str, *, max_tokens: int) -> tuple[str, int]:
    tokens = text.split()
    if len(tokens) <= max_tokens:
        return text, len(tokens)
    return " ".join(tokens[:max_tokens]), len(tokens)


def rank_files_with_dense_vectors(
    *,
    problem_statement: str,
    repo_path: str | Path,
    top_k_files: int = 5,
    model_name: str = DEFAULT_DENSE_RETRIEVER_MODEL,
    max_file_tokens: int = DEFAULT_DENSE_FILE_TOKEN_LIMIT,
    batch_size: int = 32,
) -> list[dict[str, Any]]:
    try:
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as exc:  # pragma: no cover - environment guard.
        raise RuntimeError("sentence-transformers is required for the dense baseline retriever") from exc

    root = Path(repo_path)
    file_paths = list_repo_python_files(root)
    documents: list[str] = []
    token_counts: list[int] = []
    readable_paths: list[str] = []
    for relative_path in file_paths:
        path = root / relative_path
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        truncated, token_count = truncate_whitespace_tokens(text, max_tokens=max_file_tokens)
        if not truncated.strip():
            continue
        documents.append(truncated)
        token_counts.append(token_count)
        readable_paths.append(relative_path)
    if not documents:
        return []

    model = SentenceTransformer(model_name)
    query_embedding = model.encode(
        [problem_statement],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0]
    file_embeddings = model.encode(
        documents,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    scores = file_embeddings @ query_embedding
    order = sorted(range(len(readable_paths)), key=lambda index: (float(scores[index]), readable_paths[index]), reverse=True)
    rows = []
    for index in order[:top_k_files]:
        rows.append(
            {
                "path": readable_paths[index],
                "score": float(scores[index]),
                "retriever": "baseline_dense_vector",
                "model": model_name,
                "content_tokens_before_truncation": token_counts[index],
                "content_tokens_used": min(token_counts[index], max_file_tokens),
                "exact_mention": readable_paths[index] in problem_statement,
                "basename_mention": Path(readable_paths[index]).name in problem_statement,
            }
        )
    return rows


def merge_file_rankings(
    *,
    primary_rows: list[dict[str, Any]],
    secondary_rows: list[dict[str, Any]],
    primary_label: str,
    secondary_label: str,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for source_label, rows in ((primary_label, primary_rows), (secondary_label, secondary_rows)):
        for row in rows:
            path = str(row.get("path") or "")
            if not path or path in seen:
                continue
            seen.add(path)
            enriched = dict(row)
            enriched["hybrid_source"] = source_label
            merged.append(enriched)
    return merged
