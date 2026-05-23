#!/usr/bin/env python3
"""Generate a reproducible pure-Python SWE-bench Verified ablation subset."""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "outputs" / "ablation_benchmark_verified.json"
DATASET_NAME = "princeton-nlp/SWE-bench_Verified"
ALLOWED_REPOS = {
    "django/django",
    "pytest-dev/pytest",
    "sphinx-doc/sphinx",
    "pallets/flask",
    "psf/requests",
}
MAX_PASS_TO_PASS_SMOKE_TESTS = 3


def slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()


def issue_url(repo: str, instance_id: str) -> str:
    match = re.search(r"-(\d+)$", instance_id)
    if not match:
        return f"{repo}#{instance_id}"
    return f"{repo}#{match.group(1)}"


def parse_test_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if not raw:
        return []
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def django_test_label(label: str) -> str:
    match = re.fullmatch(r"(.+?) \((.+)\)", label)
    if not match:
        return label
    method, dotted_class = match.groups()
    return f"{dotted_class}.{method}"


def test_command_for_row(row: dict[str, Any]) -> str | None:
    # Use existing regression tests for local smoke verification. FAIL_TO_PASS
    # tests often come from test_patch and should only be applied inside a
    # leakage-safe verifier path, not before selector/model context assembly.
    tests = parse_test_list(row.get("PASS_TO_PASS"))[:MAX_PASS_TO_PASS_SMOKE_TESTS]
    if not tests:
        return None
    repo = str(row["repo"])
    if repo == "django/django":
        labels = " ".join(django_test_label(test) for test in tests)
        return f"python tests/runtests.py --verbosity 1 {labels}"
    if repo in {"pytest-dev/pytest", "sphinx-doc/sphinx", "pallets/flask", "psf/requests"}:
        return "python -m pytest -q " + " ".join(tests)
    return None


def case_from_row(row: dict[str, Any]) -> dict[str, Any]:
    repo = str(row["repo"])
    instance_id = str(row["instance_id"])
    number = issue_url(repo, instance_id).split("#")[-1]
    return {
        "slug": f"verified_{slugify(repo.split('/')[-1])}_{number}",
        "category": "pure_python_verified",
        "instance_id": instance_id,
        "issue": issue_url(repo, instance_id),
        "repo": repo,
        "base_commit": str(row["base_commit"]),
        "reason": (
            "Seeded pure-Python SWE-bench Verified ablation case from "
            f"{DATASET_NAME}; sampled with seed=42 from stable repos."
        ),
        "control": False,
        "problem_statement": str(row["problem_statement"]),
        "test_cmd": test_command_for_row(row),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument(
        "--allow-missing-test-cmd",
        action="store_true",
        help="Allow rows without PASS_TO_PASS-derived smoke commands.",
    )
    args = parser.parse_args()

    try:
        from datasets import load_dataset
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing dependency: datasets. Install with `.venv/bin/python -m pip install datasets`."
        ) from exc

    dataset = load_dataset(DATASET_NAME, split="test")
    filtered = [dict(row) for row in dataset if str(row.get("repo")) in ALLOWED_REPOS]
    eligible = filtered if args.allow_missing_test_cmd else [row for row in filtered if test_command_for_row(row)]
    if len(eligible) < args.sample_size:
        raise SystemExit(
            f"Only found {len(eligible)} eligible pure-Python rows in {sorted(ALLOWED_REPOS)}; "
            f"cannot sample {args.sample_size}."
        )

    rng = random.Random(args.seed)
    sampled = rng.sample(eligible, args.sample_size)
    cases = [case_from_row(row) for row in sampled]
    cases.sort(key=lambda row: (row["repo"], row["instance_id"]))

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    repo_counts: dict[str, int] = {}
    for case in cases:
        repo_counts[case["repo"]] = repo_counts.get(case["repo"], 0) + 1
    print(
        json.dumps(
            {
                "output": str(output),
                "dataset": DATASET_NAME,
                "split": "test",
                "seed": args.seed,
                "sample_size": len(cases),
                "filtered_pool_size": len(filtered),
                "eligible_pool_size": len(eligible),
                "require_test_cmd": not args.allow_missing_test_cmd,
                "repo_counts": repo_counts,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
