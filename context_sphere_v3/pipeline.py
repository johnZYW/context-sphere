"""Toy PM -> Worker -> Reviewer pipeline for Context Sphere v3."""

from __future__ import annotations

from typing import Any

from context_sphere_v3.chunking import make_toy_issue
from context_sphere_v3.roles import ROLE_PM
from context_sphere_v3.roles import ROLE_REVIEWER
from context_sphere_v3.roles import ROLE_WORKER
from context_sphere_v3.training import run_role_separation_probe


def count_text_tokens(text: str) -> int:
    return len([piece for piece in text.split() if piece])


def run_toy_agent_pipeline(*, seed: int = 29, epochs: int = 1000, top_k: int = 6) -> dict[str, Any]:
    """Run a local three-role pipeline from learned synthetic selections.

    This is a pipeline mechanics check. It does not call an LLM and does not
    measure SWE-bench performance.
    """
    issue = make_toy_issue(seed=7)
    role_report = run_role_separation_probe(seed=seed, epochs=epochs)
    stages = []
    context_sphere_tokens = 0
    full_context_tokens = sum(count_text_tokens(text) for text in issue.chunk_text[0]) * 3

    for role in (ROLE_PM, ROLE_WORKER, ROLE_REVIEWER):
        selected_indices = role_report["top_k_by_role"][role][:top_k]
        selected_chunks = [issue.chunk_text[0][index] for index in selected_indices]
        selected_tokens = sum(count_text_tokens(text) for text in selected_chunks)
        context_sphere_tokens += selected_tokens
        if role == ROLE_PM:
            output = "toy_plan: identify goals, constraints, and acceptance hints from selected chunks"
        elif role == ROLE_WORKER:
            output = "toy_patch_plan: identify local implementation neighborhood from selected chunks"
        else:
            output = "toy_review: inspect defect signals and provenance bridge chunks"
        stages.append(
            {
                "role": role,
                "input_issue_id": issue.issue_id,
                "selected_chunk_indices": selected_indices,
                "selected_chunks": selected_chunks,
                "selected_token_count": selected_tokens,
                "output": output,
            }
        )

    token_reduction = 1.0 - (context_sphere_tokens / full_context_tokens)
    return {
        "schema_version": 1,
        "pipeline": "context_sphere_v3_toy_pm_worker_reviewer",
        "claim_boundary": "Toy pipeline mechanics only. This is not SWE-bench evidence and not an LLM agent result.",
        "seed": seed,
        "epochs": epochs,
        "issue_id": issue.issue_id,
        "roles": [ROLE_PM, ROLE_WORKER, ROLE_REVIEWER],
        "stages": stages,
        "full_context_tokens": full_context_tokens,
        "context_sphere_tokens": context_sphere_tokens,
        "token_reduction_vs_full_context": token_reduction,
        "role_separation_passed": bool(role_report["passed"]),
        "passed": bool(role_report["passed"]) and len(stages) == 3 and context_sphere_tokens < full_context_tokens,
    }
