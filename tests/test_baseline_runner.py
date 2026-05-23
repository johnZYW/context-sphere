from __future__ import annotations

import json
from pathlib import Path

from context_sphere_v3.baselines import METHOD_CONTEXT_SPHERE_V3
from context_sphere_v3.baselines import METHOD_FULL_CONTEXT
from context_sphere_v3.baselines import METHOD_STANDARD_RAG
from context_sphere_v3.baselines import METHODS
from context_sphere_v3.baselines import TOKEN_COUNT_POLICY
from context_sphere_v3.baselines import run_fair_baseline_comparison
from context_sphere_v3.swebench_scaffold import write_jsonl


def write_scaffold(tmp_path: Path) -> Path:
    scaffold = tmp_path / "swebench"
    scaffold.mkdir()
    instance_ids = ("demo__repo-1", "demo__repo-2")
    (scaffold / "subset.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dataset_name": "princeton-nlp/SWE-bench_Lite",
                "dataset_card_url": "https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite",
                "swebench_dataset_guide_url": "https://www.swebench.com/SWE-bench/guides/datasets/",
                "seed": 5,
                "count": 2,
                "instance_ids": list(instance_ids),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (scaffold / "evaluation_config.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "instance_ids": list(instance_ids),
                "agent_model": "MiniMax-M2.7",
                "temperature": 0.0,
                "max_generation_tokens": 1200,
                "visible_repo_state": "swebench_lite_base_commit_only",
                "prompt_template_id": "context_sphere_v3_pm_worker_reviewer_scaffold_v1",
                "seed": 20260522,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    write_jsonl(
        scaffold / "visible_sources.jsonl",
        [
            {
                "instance_id": "demo__repo-1",
                "repo": "demo/repo",
                "base_commit": "a" * 40,
                "problem_statement": (
                    "JSON field isnull bug\n\n"
                    "The query should only match objects that do not have the key.\n\n"
                    "Edit tests for value__j__isnull and inspect SQLite behavior.\n\n"
                    "The current implementation returns JSON null rows, which is wrong."
                ),
            },
            {
                "instance_id": "demo__repo-2",
                "repo": "demo/repo",
                "base_commit": "b" * 40,
                "problem_statement": (
                    "Migration command wraps SQL in transaction\n\n"
                    "sqlmigrate should respect connection.features.can_rollback_ddl.\n\n"
                    "Add a test that mocks can_rollback_ddl to False.\n\n"
                    "The command currently emits BEGIN and COMMIT incorrectly."
                ),
            },
        ],
    )
    return scaffold


def test_run_fair_baseline_comparison_writes_report_and_context_rows(tmp_path: Path) -> None:
    scaffold = write_scaffold(tmp_path)
    report_path = tmp_path / "report.json"
    contexts_path = tmp_path / "contexts.jsonl"
    report = run_fair_baseline_comparison(
        scaffold_dir=scaffold,
        report_path=report_path,
        contexts_path=contexts_path,
        max_context_tokens=20,
    )

    assert report["passed"] is True
    assert report["non_selector_config_equal"] is True
    assert report["official_pass_at_1_claimed"] is False
    assert report["official_swebench_harness_run"] is False
    assert report["methods"] == list(METHODS)
    assert report["token_count_policy"] == TOKEN_COUNT_POLICY
    assert len(report["method_rows"]) == 2 * len(METHODS)
    assert report_path.exists()
    assert len(contexts_path.read_text(encoding="utf-8").splitlines()) == 2 * len(METHODS)


def test_baseline_methods_share_config_and_prompt_shell_but_change_context(tmp_path: Path) -> None:
    report = run_fair_baseline_comparison(
        scaffold_dir=write_scaffold(tmp_path),
        report_path=tmp_path / "report.json",
        max_context_tokens=20,
    )
    grouped = {}
    for row in report["method_rows"]:
        grouped.setdefault(row["instance_id"], {})[row["method"]] = row

    for rows in grouped.values():
        full = rows[METHOD_FULL_CONTEXT]
        rag = rows[METHOD_STANDARD_RAG]
        sphere = rows[METHOD_CONTEXT_SPHERE_V3]
        assert full["evaluation_config"] == rag["evaluation_config"] == sphere["evaluation_config"]
        assert full["prompt_shell_sha256"] == rag["prompt_shell_sha256"] == sphere["prompt_shell_sha256"]
        assert full["token_count_policy"] == rag["token_count_policy"] == sphere["token_count_policy"]
        assert full["selected_context_tokens"] >= rag["selected_context_tokens"]
        assert full["selected_context_tokens"] >= sphere["selected_context_tokens"]
        assert set(sphere["role_sections"]) == {"pm", "worker", "reviewer"}


def test_context_sphere_v3_report_keeps_no_evidence_boundary(tmp_path: Path) -> None:
    report = run_fair_baseline_comparison(
        scaffold_dir=write_scaffold(tmp_path),
        report_path=tmp_path / "report.json",
        max_context_tokens=20,
    )
    sphere_rows = [row for row in report["method_rows"] if row["method"] == METHOD_CONTEXT_SPHERE_V3]
    assert sphere_rows
    assert all(row["status"] == "prepared_not_executed" for row in sphere_rows)
    assert "not official SWE-bench scoring" in report["claim_boundary"]
    assert report["aggregate"][METHOD_CONTEXT_SPHERE_V3]["all_statuses"] == ["prepared_not_executed"]
