#!/usr/bin/env python3
"""Run Context Sphere v3 selector inference on a GitHub issue or raw text."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from context_sphere_v3.inference import fetch_github_issue
from context_sphere_v3.inference import fetch_github_repo_files
from context_sphere_v3.inference import list_repo_python_files
from context_sphere_v3.inference import load_candidate_files
from context_sphere_v3.inference import merge_file_rankings
from context_sphere_v3.inference import prefilter_candidate_files
from context_sphere_v3.inference import rank_files_from_selected_chunks
from context_sphere_v3.inference import rank_files_with_dense_vectors
from context_sphere_v3.inference import score_problem_chunks
from context_sphere_v3.baselines import split_problem_statement


def issue_shorthand_to_url(value: str) -> str:
    if value.startswith("https://github.com/"):
        return value
    if "#" not in value or "/" not in value:
        raise argparse.ArgumentTypeError("expected owner/repo#number or a GitHub issue URL")
    repo, number = value.split("#", 1)
    owner_repo = repo.strip("/")
    if not number.isdigit() or owner_repo.count("/") != 1:
        raise argparse.ArgumentTypeError("expected owner/repo#number or a GitHub issue URL")
    return f"https://github.com/{owner_repo}/issues/{number}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default="outputs/runpod_downloads/models/context_sphere_v3_best.pt")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--issue", help="GitHub issue shorthand, e.g. psf/requests#7188")
    source.add_argument("--issue-url", help="GitHub issue URL, e.g. https://github.com/owner/repo/issues/123")
    source.add_argument("--problem-statement", help="Raw issue/problem text")
    source.add_argument("--problem-file", help="Path to a text file containing issue/problem text")
    parser.add_argument("--candidate-files", help="Optional newline-delimited candidate file paths")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--top-k-chunks", type=int, default=5)
    parser.add_argument("--top-k-files", type=int, default=5)
    parser.add_argument("--max-candidate-files", type=int, default=200)
    parser.add_argument(
        "--retriever",
        choices=("context_sphere", "baseline", "hybrid"),
        default="context_sphere",
        help=(
            "context_sphere uses the trained selector; baseline uses dense vector RAG over repo .py files; "
            "hybrid merges dense vector RAG with Context Sphere."
        ),
    )
    parser.add_argument("--repo-path", help="Repository workspace root; required for --retriever baseline or hybrid")
    parser.add_argument("--dense-model", default="all-MiniLM-L6-v2")
    parser.add_argument("--dense-max-file-tokens", type=int, default=768)
    parser.add_argument("--out", dest="out_json", help="Alias for --out-json")
    parser.add_argument("--out-json", help="Optional path to write the full inference payload")
    args = parser.parse_args()

    issue_meta = {"source": "raw_text"}
    issue_url = issue_shorthand_to_url(args.issue) if args.issue else args.issue_url
    if issue_url:
        issue_meta = fetch_github_issue(issue_url)
        problem_statement = issue_meta["problem_statement"]
    elif args.problem_file:
        problem_statement = Path(args.problem_file).read_text(encoding="utf-8")
        issue_meta = {"source": str(args.problem_file), "problem_statement": problem_statement}
    else:
        problem_statement = str(args.problem_statement)
        issue_meta = {"source": "raw_text", "problem_statement": problem_statement}

    candidate_files = []
    if args.retriever == "baseline":
        if not args.repo_path:
            raise SystemExit("--repo-path is required when --retriever baseline is used")
        chunks = split_problem_statement(problem_statement)
        top_chunks = [
            {
                "chunk_id": str(chunk["chunk_id"]),
                "score": 1.0 / float(index + 1),
                "text": str(chunk["text"]),
            }
            for index, chunk in enumerate(chunks[: args.top_k_chunks])
        ]
        chunk_result = {
            "checkpoint_path": None,
            "checkpoint_step": None,
            "checkpoint_epoch": None,
            "chunks": chunks,
            "scores": [row["score"] for row in top_chunks],
            "top_indices": list(range(len(top_chunks))),
            "top_chunks": top_chunks,
        }
        file_rows = rank_files_with_dense_vectors(
            problem_statement=problem_statement,
            repo_path=args.repo_path,
            top_k_files=args.top_k_files,
            model_name=args.dense_model,
            max_file_tokens=args.dense_max_file_tokens,
        )
        candidate_file_count = len(list_repo_python_files(args.repo_path))
        boundary = (
            "Baseline dense vector retriever over repository .py file contents using all-MiniLM-L6-v2. No Context Sphere "
            "topological expansion or trained selector is used."
        )
    elif args.retriever == "hybrid":
        if not args.repo_path:
            raise SystemExit("--repo-path is required when --retriever hybrid is used")
        if args.candidate_files:
            candidate_files = load_candidate_files(args.candidate_files)
        elif issue_url:
            candidate_files = fetch_github_repo_files(issue_meta["owner"], issue_meta["repo"])
        candidate_files = prefilter_candidate_files(
            problem_statement,
            candidate_files,
            limit=args.max_candidate_files,
        ) if candidate_files else []
        chunk_result = score_problem_chunks(
            checkpoint_path=args.checkpoint,
            problem_statement=problem_statement,
            device=args.device,
            top_k_chunks=args.top_k_chunks,
        )
        vector_rows = rank_files_with_dense_vectors(
            problem_statement=problem_statement,
            repo_path=args.repo_path,
            top_k_files=3,
            model_name=args.dense_model,
            max_file_tokens=args.dense_max_file_tokens,
        )
        sphere_rows = rank_files_from_selected_chunks(
            problem_statement=problem_statement,
            selected_chunks=chunk_result["top_chunks"],
            candidate_files=candidate_files,
            top_k_files=3,
        ) if candidate_files else []
        file_rows = merge_file_rankings(
            primary_rows=vector_rows,
            secondary_rows=sphere_rows,
            primary_label="dense_vector",
            secondary_label="context_sphere",
        )
        candidate_file_count = len(candidate_files)
        boundary = (
            "Hybrid retriever: dense vector RAG top-3 files are prioritized, then unique Context Sphere "
            "top-3 files are appended."
        )
    else:
        if args.candidate_files:
            candidate_files = load_candidate_files(args.candidate_files)
        elif issue_url:
            candidate_files = fetch_github_repo_files(issue_meta["owner"], issue_meta["repo"])
        candidate_files = prefilter_candidate_files(
            problem_statement,
            candidate_files,
            limit=args.max_candidate_files,
        ) if candidate_files else []

        chunk_result = score_problem_chunks(
            checkpoint_path=args.checkpoint,
            problem_statement=problem_statement,
            device=args.device,
            top_k_chunks=args.top_k_chunks,
        )
        file_rows = rank_files_from_selected_chunks(
            problem_statement=problem_statement,
            selected_chunks=chunk_result["top_chunks"],
            candidate_files=candidate_files,
            top_k_files=args.top_k_files,
        ) if candidate_files else []
        candidate_file_count = len(candidate_files)
        boundary = (
            "The trained v3 model scores visible issue chunks. File recommendations are an "
            "experimental lexical projection from model-selected chunks onto candidate repo files."
        )
    payload = {
        "schema_version": 1,
        "issue": issue_meta,
        "retriever": args.retriever,
        "checkpoint_path": chunk_result["checkpoint_path"],
        "checkpoint_step": chunk_result["checkpoint_step"],
        "checkpoint_epoch": chunk_result["checkpoint_epoch"],
        "boundary": boundary,
        "candidate_file_count_after_prefilter": candidate_file_count,
        "top_chunks": chunk_result["top_chunks"],
        "top_files": file_rows,
    }
    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("Top files")
    if file_rows:
        for index, row in enumerate(file_rows, start=1):
            print(f"{index}. {row['path']}  score={row['score']:.3f}")
    else:
        print("(no candidate files available; showing top chunks only)")
    print("\nTop chunks")
    for index, row in enumerate(chunk_result["top_chunks"], start=1):
        preview = row["text"].replace("\n", " ")[:180]
        print(f"{index}. {row['chunk_id']}  score={row['score']:.4f}  {preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
