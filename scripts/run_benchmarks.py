#!/usr/bin/env python3
"""Run a 15-issue Context Sphere resolution benchmark batch."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import MISSING
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "resolution_history"
DEFAULT_REPO_ROOT = ROOT / "outputs" / "benchmark_repos"
DEFAULT_VAL_DATASET = ROOT / "outputs" / "datasets" / "swebench_val_v3.pt"
MODEL_STRATEGIES = ("monolithic", "heterogeneous", "fallback")
TEST_COMMAND_REGISTRY: dict[str, str] = {
    # Repository-level defaults. These commands run inside the checked-out repo.
    "django/django": "python tests/runtests.py --verbosity 1",
    "pytest-dev/pytest": "python -m pytest testing -q",
    "sphinx-doc/sphinx": "python -m pytest tests -q",
    "pallets/flask": "python -m pytest tests -q",
    "psf/requests": "python -m pytest tests -q",
    "numpy/numpy": "python -m pytest numpy/core/tests/test_overrides.py -q",
    "pandas-dev/pandas": "python -m pytest pandas/tests -q",
    "mesonbuild/meson": "python run_unittests.py",
    "pantsbuild/pants": "./pants test ::",
    "google/jax": "python -m pytest tests/lax_test.py -q",
    "pypa/pip": "python -m pytest tests/unit -q",
    "wagtail/wagtail": ".venv/bin/python runtests.py",
}
CASE_TEST_COMMAND_OVERRIDES: dict[str, str] = {}
BOOTSTRAP_COMMAND_REGISTRY: dict[str, list[str]] = {
    # Install the checked-out target repo into the harness venv before execution
    # verification. This prevents the verifier from importing stale packages from
    # the harness environment or failing before the target package is importable.
    "django/django": ["python -m pip install -e ."],
    "pytest-dev/pytest": ["python -m pip install -e ."],
    "sphinx-doc/sphinx": ["python -m pip install -e .[test]"],
    "pallets/flask": ["python -m pip install -e .[test]"],
    "psf/requests": ["python -m pip install -e ."],
}


@dataclass(frozen=True)
class BenchmarkCase:
    slug: str
    category: str
    instance_id: str
    issue: str
    repo: str
    base_commit: str
    reason: str
    control: bool = False
    problem_statement: str | None = None
    test_cmd: str | None = None

    @property
    def repo_url(self) -> str:
        return f"https://github.com/{self.repo}.git"


BATCH_CASES: tuple[BenchmarkCase, ...] = (
    # Easy: single-file, high Recall@5 validation cases.
    BenchmarkCase(
        slug="easy_numpy_22533",
        category="easy",
        instance_id="numpy__numpy-22533",
        issue="numpy/numpy#22533",
        repo="numpy/numpy",
        base_commit="21195337da3e87c0d153794bb65d2d32da542395",
        reason="Single-file high-recall validation case touching numpy/core/overrides.py.",
    ),
    BenchmarkCase(
        slug="easy_pandas_3959",
        category="easy",
        instance_id="pandas-dev__pandas-3959",
        issue="pandas-dev/pandas#3959",
        repo="pandas-dev/pandas",
        base_commit="4515995bc736f54402a34c512349a8d0f315dee4",
        reason="Single-file high-recall validation case touching setup.py.",
    ),
    BenchmarkCase(
        slug="easy_meson_7149",
        category="easy",
        instance_id="mesonbuild__meson-7149",
        issue="mesonbuild/meson#7149",
        repo="mesonbuild/meson",
        base_commit="3e134975749b67b8c799a8b8fd065721de1cb48a",
        reason="Single-file high-recall validation case touching mesonbuild/dependencies/boost.py.",
    ),
    BenchmarkCase(
        slug="easy_pants_5122",
        category="easy",
        instance_id="pantsbuild__pants-5122",
        issue="pantsbuild/pants#5122",
        repo="pantsbuild/pants",
        base_commit="a4fbf46e184e62fa007c40e71c7021936d1f8244",
        reason="Single-file high-recall validation case touching a register.py file.",
    ),
    BenchmarkCase(
        slug="easy_jax_2532",
        category="easy",
        instance_id="google__jax-2532",
        issue="google/jax#2532",
        repo="google/jax",
        base_commit="f371bfc0bfe927051738d7a8cdca2b4581b45e2f",
        reason="Single-file high-recall validation case touching jax/lax/lax.py.",
    ),
    # Architecture: cross-file cases selected to exercise Neighborhood expansion.
    BenchmarkCase(
        slug="arch_pandas_29313",
        category="architecture",
        instance_id="pandas-dev__pandas-29313",
        issue="pandas-dev/pandas#29313",
        repo="pandas-dev/pandas",
        base_commit="0efc71b53f019c6c5a8da7a38e08646ca75c17d9",
        reason="Cross-file case touching docs plus parser/groupby internals.",
    ),
    BenchmarkCase(
        slug="arch_jax_720",
        category="architecture",
        instance_id="google__jax-720",
        issue="google/jax#720",
        repo="google/jax",
        base_commit="c54ba8444d51cde3574fdab29970de1850a50c10",
        reason="Cross-file FFT/lax/numpy API refactoring case.",
    ),
    BenchmarkCase(
        slug="arch_pants_19264",
        category="architecture",
        instance_id="pantsbuild__pants-19264",
        issue="pantsbuild/pants#19264",
        repo="pantsbuild/pants",
        base_commit="362fe1b93505235fa07987b76b4742d732a63b3f",
        reason="Cross-file backend/goal/target-types case.",
    ),
    BenchmarkCase(
        slug="arch_pip_7319",
        category="architecture",
        instance_id="pypa__pip-7319",
        issue="pypa/pip#7319",
        repo="pypa/pip",
        base_commit="b8c16a0dc86519e283a94b14591f9ddae27f9c55",
        reason="Cross-file wheel/cache/build utility case.",
    ),
    BenchmarkCase(
        slug="arch_wagtail_1120",
        category="architecture",
        instance_id="wagtail__wagtail-1120",
        issue="wagtail/wagtail#1120",
        repo="wagtail/wagtail",
        base_commit="a83a16de5ca20d596d932d524b309cd74428d43f",
        reason="Cross-file admin/task/forms/settings case.",
    ),
    # Hard: directly from zero-Recall@5 failure audit.
    BenchmarkCase(
        slug="hard_jax_1736",
        category="hard_failure_prone",
        instance_id="google__jax-1736",
        issue="google/jax#1736",
        repo="google/jax",
        base_commit="2b0cde3648e3f405b87558e3a3eff352a6c377a8",
        reason="Zero-Recall@5 audit case with long/many-chunk visible context.",
    ),
    BenchmarkCase(
        slug="hard_meson_8262",
        category="hard_failure_prone",
        instance_id="mesonbuild__meson-8262",
        issue="mesonbuild/meson#8262",
        repo="mesonbuild/meson",
        base_commit="633264984b4b2278491476a0997193ff4996b3a6",
        reason="Zero-Recall@5 audit case with long visible context.",
    ),
    BenchmarkCase(
        slug="hard_jax_527",
        category="hard_failure_prone",
        instance_id="google__jax-527",
        issue="google/jax#527",
        repo="google/jax",
        base_commit="cefbea6a4220d0d1c074f1ed70b12808827fac3f",
        reason="Zero-Recall@5 audit case with no obvious proxy pattern.",
    ),
    BenchmarkCase(
        slug="hard_numpy_18351",
        category="hard_failure_prone",
        instance_id="numpy__numpy-18351",
        issue="numpy/numpy#18351",
        repo="numpy/numpy",
        base_commit="b66f57a32e0a6fc6f2d46a15fe9f2ff6486bd69b",
        reason="Zero-Recall@5 audit case with many visible chunks.",
    ),
    BenchmarkCase(
        slug="hard_pandas_7043",
        category="hard_failure_prone",
        instance_id="pandas-dev__pandas-7043",
        issue="pandas-dev/pandas#7043",
        repo="pandas-dev/pandas",
        base_commit="c9df3d4bc53f0fb6bf76fd4f0943ff757a346179",
        reason="Zero-Recall@5 audit case touching docs and period code.",
    ),
    # Bonus ablation: same architecture issue with Neighborhood disabled.
    BenchmarkCase(
        slug="arch_jax_720_control_no_neighborhood",
        category="architecture_control",
        instance_id="google__jax-720",
        issue="google/jax#720",
        repo="google/jax",
        base_commit="c54ba8444d51cde3574fdab29970de1850a50c10",
        reason="Control ablation for arch_jax_720 with Neighborhood disabled.",
        control=True,
    ),
)


def run_command(command: list[str], *, cwd: Path, timeout: int | None = None) -> dict[str, Any]:
    started = time.time()
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "elapsed_seconds": round(time.time() - started, 3),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_cases_file(path: Path) -> list[BenchmarkCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"cases file must contain a JSON array: {path}")
    cases = []
    required = {
        field.name
        for field in BenchmarkCase.__dataclass_fields__.values()
        if field.default is MISSING and field.default_factory is MISSING
    }
    required.discard("control")
    for index, row in enumerate(payload, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"case #{index} must be an object")
        missing = sorted(required - row.keys())
        if missing:
            raise ValueError(f"case #{index} is missing required fields: {missing}")
        allowed = set(BenchmarkCase.__dataclass_fields__)
        extra = sorted(set(row) - allowed)
        if extra:
            raise ValueError(f"case #{index} has unsupported fields: {extra}")
        cases.append(BenchmarkCase(**row))
    return cases


def repo_dir_for_case(repo_root: Path, case: BenchmarkCase) -> Path:
    return repo_root / case.repo.replace("/", "__")


def ensure_repo(case: BenchmarkCase, *, repo_root: Path, timeout: int) -> tuple[Path, list[dict[str, Any]]]:
    repo_path = repo_dir_for_case(repo_root, case)
    commands: list[dict[str, Any]] = []
    repo_root.mkdir(parents=True, exist_ok=True)
    if not (repo_path / ".git").exists():
        clone_result = run_command(
            [
                "git",
                "clone",
                "--no-checkout",
                "--filter=blob:none",
                case.repo_url,
                str(repo_path),
            ],
            cwd=ROOT,
            timeout=timeout,
        )
        commands.append(clone_result)
        if clone_result["returncode"] != 0:
            raise RuntimeError(f"clone failed for {case.repo}: {clone_result['stderr']}")
    fetch_result = run_command(
        ["git", "fetch", "--depth", "1", "origin", case.base_commit],
        cwd=repo_path,
        timeout=timeout,
    )
    commands.append(fetch_result)
    if fetch_result["returncode"] != 0:
        raise RuntimeError(f"fetch failed for {case.repo}@{case.base_commit}: {fetch_result['stderr']}")
    checkout_result = run_command(["git", "checkout", "--detach", case.base_commit], cwd=repo_path, timeout=timeout)
    commands.append(checkout_result)
    if checkout_result["returncode"] != 0:
        raise RuntimeError(f"checkout failed for {case.repo}@{case.base_commit}: {checkout_result['stderr']}")
    return repo_path, commands


def list_candidate_files(repo_path: Path) -> list[str]:
    suffixes = {
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
    ignored = {".git", "__pycache__", ".mypy_cache", ".pytest_cache", ".tox", ".venv", "venv", "node_modules"}
    files = []
    for path in repo_path.rglob("*"):
        if any(part in ignored for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in suffixes:
            files.append(path.relative_to(repo_path).as_posix())
    return sorted(files)


def load_val_items(dataset_path: Path) -> dict[str, dict[str, Any]]:
    try:
        import torch
    except ModuleNotFoundError as exc:
        raise RuntimeError("Torch is required to load the local SWE-bench .pt dataset; run with .venv/bin/python") from exc
    payload = torch.load(dataset_path, map_location="cpu")
    return {str(item["instance_id"]): item for item in payload["items"]}


def build_local_selector_output(
    *,
    case: BenchmarkCase,
    repo_path: Path,
    run_dir: Path,
    python_bin: str,
    val_items: dict[str, dict[str, Any]],
    timeout: int,
    retriever: str = "context_sphere",
) -> tuple[Path, dict[str, Any]]:
    item = val_items.get(case.instance_id)
    if item is None and not case.problem_statement:
        raise KeyError(
            f"{case.instance_id} not found in validation dataset and no problem_statement was provided by the case"
        )
    problem_statement = str(item["problem_statement"]) if item is not None else str(case.problem_statement)
    problem_file = run_dir / "problem_statement.txt"
    candidate_file = run_dir / "candidate_files.txt"
    selector_output = run_dir / "selector_output.json"
    problem_file.write_text(problem_statement, encoding="utf-8")
    candidate_file.write_text("\n".join(list_candidate_files(repo_path)) + "\n", encoding="utf-8")
    command = [
        python_bin,
        "scripts/inference.py",
        "--problem-file",
        str(problem_file),
        "--candidate-files",
        str(candidate_file),
        "--out",
        str(selector_output),
    ]
    if retriever != "context_sphere":
        command.extend(["--retriever", retriever, "--repo-path", str(repo_path)])
    result = run_command(command, cwd=ROOT, timeout=timeout)
    (run_dir / "selector.stdout").write_text(result["stdout"], encoding="utf-8")
    (run_dir / "selector.stderr").write_text(result["stderr"], encoding="utf-8")
    if result["returncode"] != 0:
        raise RuntimeError(f"local selector generation failed for {case.slug}: {result['stderr']}")
    return selector_output, result


def status_from_summary(summary: dict[str, Any] | None, returncode: int) -> str:
    if summary is None:
        return "MANUAL_INTERVENTION"
    if summary.get("approved") is True:
        return "APPROVED"
    if summary.get("status") == "manual_intervention" or returncode != 0:
        return "MANUAL_INTERVENTION"
    return "REJECTED"


def count_llm_calls(run_dir: Path) -> int:
    return len(list(run_dir.glob("*.raw.json")))


def test_command_for_case(case: BenchmarkCase) -> str | None:
    if case.test_cmd:
        return case.test_cmd
    return CASE_TEST_COMMAND_OVERRIDES.get(case.slug) or TEST_COMMAND_REGISTRY.get(case.repo)


def normalize_test_command(test_cmd: str | None, *, python_bin: str) -> str | None:
    if not test_cmd:
        return None
    parts = shlex.split(test_cmd)
    if parts and parts[0] in {"python", "python3"}:
        parts[0] = python_bin
        return shlex.join(parts)
    return test_cmd


def bootstrap_commands_for_case(case: BenchmarkCase) -> list[str]:
    return BOOTSTRAP_COMMAND_REGISTRY.get(case.repo, [])


def normalize_shell_command(command: str, *, python_bin: str) -> list[str]:
    parts = shlex.split(command)
    if parts and parts[0] in {"python", "python3"}:
        parts[0] = python_bin
    return parts


def bootstrap_repo_environment(
    case: BenchmarkCase,
    *,
    repo_path: Path,
    python_bin: str,
    timeout: int,
) -> list[dict[str, Any]]:
    results = []
    for command in bootstrap_commands_for_case(case):
        result = run_command(normalize_shell_command(command, python_bin=python_bin), cwd=repo_path, timeout=timeout)
        results.append(result)
        if result["returncode"] != 0:
            raise RuntimeError(f"bootstrap failed for {case.repo}: {result['stderr'] or result['stdout']}")
    return results


def metrics_for_run(
    *,
    case: BenchmarkCase,
    run_dir: Path,
    command_result: dict[str, Any] | None,
    repo_commands: list[dict[str, Any]],
    dry_run: bool,
    run_verify: bool,
    python_bin: str,
    error: str | None,
) -> dict[str, Any]:
    summary_path = run_dir / "resolution_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else None
    attempts = summary.get("attempts", []) if summary else []
    status = status_from_summary(summary, int(command_result["returncode"]) if command_result else 1)
    metrics = {
        "schema_version": 1,
        "case": asdict(case),
        "status": status,
        "iterations": len(attempts),
        "llm_calls": (
            0
            if dry_run
            else int((summary.get("model_usage") or {}).get("calls") or count_llm_calls(run_dir))
            if summary
            else count_llm_calls(run_dir)
        ),
        "model_strategy": summary.get("model_strategy") if summary else None,
        "retrieval_mode": summary.get("retrieval_mode") if summary else None,
        "projection_summary": summary.get("projection_summary") if summary else None,
        "routing_profile": summary.get("routing_profile") if summary else None,
        "model_usage": summary.get("model_usage") if summary else None,
        "estimated_inference_cost_usd": float(summary.get("estimated_inference_cost_usd", 0.0)) if summary else 0.0,
        "internal_approval_indicator": summary.get("internal_approval_indicator") if summary else None,
        "verification_success_indicator": summary.get("verification_success_indicator") if summary else None,
        "internal_approval_per_dollar": summary.get("internal_approval_per_dollar") if summary else None,
        "efficacy_per_dollar": summary.get("efficacy_per_dollar") if summary else None,
        "final_patch_exists": (run_dir / "final_patch.diff").exists(),
        "tests_passed": summary.get("tests_passed") if summary else None,
        "test_cmd": normalize_test_command(test_command_for_case(case), python_bin=python_bin) if run_verify else None,
        "run_verify": run_verify,
        "dry_run": dry_run,
        "run_dir": str(run_dir),
        "resolution_summary_path": str(summary_path) if summary_path.exists() else None,
        "error": error,
        "orchestrator_returncode": command_result["returncode"] if command_result else None,
        "orchestrator_elapsed_seconds": command_result["elapsed_seconds"] if command_result else None,
        "repo_command_count": len(repo_commands),
        "repo_commands": repo_commands,
    }
    write_json(run_dir / "metrics.json", metrics)
    return metrics


def run_case(
    case: BenchmarkCase,
    *,
    output_root: Path,
    repo_root: Path,
    python_bin: str,
    dry_run: bool,
    run_verify: bool,
    model_strategy: str,
    resume: bool,
    max_file_chars: int,
    timeout: int,
    val_items: dict[str, dict[str, Any]],
    bootstrap_lock: threading.Lock | None = None,
    retriever: str = "context_sphere",
    retrieval_mode: str = "standard",
) -> dict[str, Any]:
    run_dir = output_root / case.slug
    metrics_path = run_dir / "metrics.json"
    if resume and metrics_path.exists():
        return json.loads(metrics_path.read_text(encoding="utf-8"))
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "case_config.json", asdict(case))
    repo_commands: list[dict[str, Any]] = []
    command_result: dict[str, Any] | None = None
    error = None
    try:
        repo_path, repo_commands = ensure_repo(case, repo_root=repo_root, timeout=timeout)
        if run_verify:
            if bootstrap_lock is None:
                repo_commands.extend(
                    bootstrap_repo_environment(case, repo_path=repo_path, python_bin=python_bin, timeout=timeout)
                )
            else:
                with bootstrap_lock:
                    repo_commands.extend(
                        bootstrap_repo_environment(case, repo_path=repo_path, python_bin=python_bin, timeout=timeout)
                    )
        selector_output, selector_result = build_local_selector_output(
            case=case,
            repo_path=repo_path,
            run_dir=run_dir,
            python_bin=python_bin,
            val_items=val_items,
            timeout=timeout,
            retriever=retriever,
        )
        command = [
            python_bin,
            "scripts/orchestrate_resolution.py",
            case.issue,
            str(repo_path),
            "--run-dir",
            str(run_dir),
            "--selector-output",
            str(selector_output),
            "--max-file-chars",
            str(max_file_chars),
            "--model-strategy",
            model_strategy,
            "--retrieval-mode",
            retrieval_mode,
        ]
        if case.control:
            command.extend(["--max-neighborhood-files", "0"])
        test_cmd = normalize_test_command(test_command_for_case(case), python_bin=python_bin) if run_verify else None
        if test_cmd:
            command.extend(["--test-cmd", test_cmd])
        if dry_run:
            command.append("--dry-run")
        command_result = run_command(command, cwd=ROOT, timeout=timeout)
        (run_dir / "orchestrator.stdout").write_text(command_result["stdout"], encoding="utf-8")
        (run_dir / "orchestrator.stderr").write_text(command_result["stderr"], encoding="utf-8")
        repo_commands.append(selector_result)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    return metrics_for_run(
        case=case,
        run_dir=run_dir,
        command_result=command_result,
        repo_commands=repo_commands,
        dry_run=dry_run,
        run_verify=run_verify,
        python_bin=python_bin,
        error=error,
    )


def aggregate_report(metrics_rows: list[dict[str, Any]], *, output_root: Path, dry_run: bool) -> dict[str, Any]:
    by_category: dict[str, dict[str, Any]] = {}
    for row in metrics_rows:
        category = row["case"]["category"]
        bucket = by_category.setdefault(
            category,
            {
                "count": 0,
                "approved": 0,
                "manual_intervention": 0,
                "rejected": 0,
                "iterations_total": 0,
                "llm_calls_total": 0,
                "estimated_inference_cost_usd": 0.0,
                "tests_passed": 0,
                "tests_failed": 0,
                "tests_not_run": 0,
            },
        )
        bucket["count"] += 1
        bucket["approved"] += int(row["status"] == "APPROVED")
        bucket["manual_intervention"] += int(row["status"] == "MANUAL_INTERVENTION")
        bucket["rejected"] += int(row["status"] == "REJECTED")
        bucket["iterations_total"] += int(row["iterations"])
        bucket["llm_calls_total"] += int(row["llm_calls"])
        bucket["estimated_inference_cost_usd"] += float(row.get("estimated_inference_cost_usd") or 0.0)
        bucket["tests_passed"] += int(row.get("tests_passed") is True)
        bucket["tests_failed"] += int(row.get("tests_passed") is False)
        bucket["tests_not_run"] += int(row.get("tests_passed") is None)
    for bucket in by_category.values():
        cost = float(bucket["estimated_inference_cost_usd"])
        bucket["estimated_inference_cost_usd"] = round(cost, 8)
        bucket["internal_approvals_per_dollar"] = round(float(bucket["approved"]) / cost, 8) if cost > 0 else None
        bucket["verified_efficacy_per_dollar"] = (
            round(float(bucket["tests_passed"]) / cost, 8) if cost > 0 else None
        )
    total_cost = sum(float(row.get("estimated_inference_cost_usd") or 0.0) for row in metrics_rows)
    approved = sum(1 for row in metrics_rows if row["status"] == "APPROVED")
    tests_passed = sum(1 for row in metrics_rows if row.get("tests_passed") is True)
    report = {
        "schema_version": 1,
        "dry_run": dry_run,
        "case_count": len(metrics_rows),
        "approved": approved,
        "manual_intervention": sum(1 for row in metrics_rows if row["status"] == "MANUAL_INTERVENTION"),
        "rejected": sum(1 for row in metrics_rows if row["status"] == "REJECTED"),
        "llm_calls_total": sum(int(row["llm_calls"]) for row in metrics_rows),
        "estimated_inference_cost_usd": round(total_cost, 8),
        "mean_estimated_inference_cost_usd": round(total_cost / len(metrics_rows), 8) if metrics_rows else 0.0,
        "internal_approvals_per_dollar": round(float(approved) / total_cost, 8) if total_cost > 0 else None,
        "verified_efficacy_per_dollar": round(float(tests_passed) / total_cost, 8) if total_cost > 0 else None,
        "model_strategies": sorted({str(row.get("model_strategy")) for row in metrics_rows if row.get("model_strategy")}),
        "tests_passed": tests_passed,
        "tests_failed": sum(1 for row in metrics_rows if row.get("tests_passed") is False),
        "tests_not_run": sum(1 for row in metrics_rows if row.get("tests_passed") is None),
        "by_category": by_category,
        "cases": metrics_rows,
    }
    write_json(output_root / "benchmark_summary.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--python-bin", default=str(ROOT / ".venv" / "bin" / "python"))
    parser.add_argument("--val-dataset", default=str(DEFAULT_VAL_DATASET))
    parser.add_argument("--dry-run", action="store_true", help="Exercise full batch without MiniMax calls")
    parser.add_argument("--run-verify", action="store_true", help="Inject per-case --test-cmd into orchestrator runs")
    parser.add_argument(
        "--baseline-retriever",
        action="store_true",
        help="Use the dense vector baseline selector instead of the Context Sphere selector.",
    )
    parser.add_argument(
        "--retriever",
        choices=("context_sphere", "baseline", "hybrid"),
        default="context_sphere",
        help="Selector retriever mode. --baseline-retriever is a backward-compatible alias for --retriever baseline.",
    )
    parser.add_argument(
        "--retrieval-mode",
        choices=("standard", "projection"),
        default="standard",
        help="Context assembly mode passed to orchestrate_resolution.py.",
    )
    parser.add_argument("--include-control", action="store_true", help="Include the Neighborhood-disabled control ablation case")
    parser.add_argument(
        "--cases-file",
        default=None,
        help="Optional JSON array of BenchmarkCase-shaped objects to run instead of the built-in 15-case suite.",
    )
    parser.add_argument(
        "--model-strategy",
        choices=MODEL_STRATEGIES,
        default="monolithic",
        help="Model routing strategy to pass through to orchestrate_resolution.py; fallback is DeepSeek-primary/MiniMax-secondary.",
    )
    parser.add_argument("--resume", action="store_true", help="Skip cases that already have metrics.json")
    parser.add_argument("--max-workers", type=int, default=1, help="Maximum number of benchmark cases to run concurrently")
    parser.add_argument("--max-file-chars", type=int, default=60_000)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional first-N case limit for smoke testing; 0 means all cases including ablation.",
    )
    args = parser.parse_args()
    retriever = "baseline" if args.baseline_retriever else args.retriever

    if args.cases_file:
        cases = load_cases_file(Path(args.cases_file))
        if not args.include_control:
            cases = [case for case in cases if not case.control]
    else:
        cases = [case for case in BATCH_CASES if args.include_control or not case.control]
    if args.limit > 0:
        cases = cases[: args.limit]
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(
        output_root / "benchmark_config.json",
        {
            "model_strategy": args.model_strategy,
            "max_workers": max(1, args.max_workers),
            "run_verify": args.run_verify,
            "retriever": retriever,
            "retrieval_mode": args.retrieval_mode,
            "baseline_retriever": retriever == "baseline",
            "include_control": args.include_control,
            "cases": [asdict(case) for case in cases],
        },
    )
    val_items = load_val_items(Path(args.val_dataset))
    repo_locks = {case.repo: threading.Lock() for case in cases}
    bootstrap_lock = threading.Lock()

    def run_indexed_case(index: int, case: BenchmarkCase) -> tuple[int, dict[str, Any]]:
        print(
            json.dumps(
                {
                    "running": index,
                    "total": len(cases),
                    "slug": case.slug,
                    "dry_run": args.dry_run,
                    "model_strategy": args.model_strategy,
                }
            ),
            flush=True,
        )
        with repo_locks[case.repo]:
            metrics = run_case(
                case,
                output_root=output_root,
                repo_root=Path(args.repo_root),
                python_bin=args.python_bin,
                dry_run=args.dry_run,
                run_verify=args.run_verify,
                model_strategy=args.model_strategy,
                resume=args.resume,
                max_file_chars=args.max_file_chars,
                timeout=args.timeout,
                val_items=val_items,
                bootstrap_lock=bootstrap_lock,
                retriever=retriever,
                retrieval_mode=args.retrieval_mode,
            )
        print(
            json.dumps(
                {
                    "slug": case.slug,
                    "status": metrics["status"],
                    "iterations": metrics["iterations"],
                    "llm_calls": metrics["llm_calls"],
                    "estimated_inference_cost_usd": metrics.get("estimated_inference_cost_usd"),
                }
            ),
            flush=True,
        )
        return index, metrics

    metrics_by_index: dict[int, dict[str, Any]] = {}
    max_workers = max(1, args.max_workers)
    if max_workers == 1:
        for index, case in enumerate(cases, start=1):
            finished_index, metrics = run_indexed_case(index, case)
            metrics_by_index[finished_index] = metrics
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(run_indexed_case, index, case): index
                for index, case in enumerate(cases, start=1)
            }
            for future in concurrent.futures.as_completed(futures):
                index = futures[future]
                try:
                    finished_index, metrics = future.result()
                except Exception as exc:
                    case = cases[index - 1]
                    run_dir = output_root / case.slug
                    metrics = metrics_for_run(
                        case=case,
                        run_dir=run_dir,
                        command_result=None,
                        repo_commands=[],
                        dry_run=args.dry_run,
                        run_verify=args.run_verify,
                        python_bin=args.python_bin,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                    finished_index = index
                metrics_by_index[finished_index] = metrics

    metrics_rows = [metrics_by_index[index] for index in range(1, len(cases) + 1)]
    report = aggregate_report(metrics_rows, output_root=output_root, dry_run=args.dry_run)
    print(json.dumps(report, indent=2))
    return 0 if report["manual_intervention"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
