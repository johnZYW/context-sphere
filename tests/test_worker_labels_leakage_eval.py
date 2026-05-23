from __future__ import annotations

import json
from pathlib import Path

from context_sphere_v3.leakage_audit import audit_leakage
from context_sphere_v3.selector_eval import METHOD_STANDARD_BM25
from context_sphere_v3.selector_eval import run_selector_only_evaluation
from context_sphere_v3.worker_labels import build_worker_label_rows
from context_sphere_v3.worker_labels import touched_files_from_patch
from tests.test_baseline_runner import write_scaffold


def source_rows() -> dict[str, dict[str, object]]:
    return {
        "demo__repo-1": {
            "instance_id": "demo__repo-1",
            "patch": (
                "diff --git a/demo/models.py b/demo/models.py\n"
                "--- a/demo/models.py\n"
                "+++ b/demo/models.py\n"
                "@@ -1 +1 @@\n"
                "-old secret implementation line that should not enter input\n"
                "+new secret implementation line that should not enter input\n"
            ),
            "test_patch": (
                "diff --git a/tests/test_models.py b/tests/test_models.py\n"
                "+assert secret behavior\n"
            ),
        },
        "demo__repo-2": {
            "instance_id": "demo__repo-2",
            "patch": (
                "diff --git a/demo/commands.py b/demo/commands.py\n"
                "--- a/demo/commands.py\n"
                "+++ b/demo/commands.py\n"
                "+fix command transaction behavior\n"
            ),
            "test_patch": "diff --git a/tests/test_commands.py b/tests/test_commands.py\n+assert no transaction\n",
        },
    }


def test_touched_files_from_patch_extracts_paths_only() -> None:
    assert touched_files_from_patch(str(source_rows()["demo__repo-1"]["patch"])) == ["demo/models.py"]


def test_worker_labels_and_leakage_audit_pass_without_patch_content(tmp_path: Path, monkeypatch) -> None:
    scaffold = write_scaffold(tmp_path)
    monkeypatch.setattr("context_sphere_v3.worker_labels.fetch_rows_by_instance_id", lambda instance_ids, fetch_length=300: source_rows())
    monkeypatch.setattr("context_sphere_v3.leakage_audit.fetch_rows_by_instance_id", lambda instance_ids, fetch_length=300: source_rows())
    labels_path = tmp_path / "labels.jsonl"

    labels = build_worker_label_rows(scaffold_dir=scaffold, out_path=labels_path)
    assert len(labels) == 2
    assert labels[0]["label_source"] == "gold_patch_touched_file_paths_only"
    assert "old secret implementation" not in labels_path.read_text(encoding="utf-8")

    audit = audit_leakage(
        scaffold_dir=scaffold,
        labels_path=labels_path,
        out_path=tmp_path / "audit.json",
    )
    assert audit["passed"] is True
    assert audit["gold_patch_used_as_model_input"] is False
    assert audit["test_patch_used_as_model_input"] is False


def test_selector_only_eval_reports_required_metrics(tmp_path: Path, monkeypatch) -> None:
    scaffold = write_scaffold(tmp_path)
    monkeypatch.setattr("context_sphere_v3.worker_labels.fetch_rows_by_instance_id", lambda instance_ids, fetch_length=300: source_rows())
    monkeypatch.setattr("context_sphere_v3.leakage_audit.fetch_rows_by_instance_id", lambda instance_ids, fetch_length=300: source_rows())
    labels_path = tmp_path / "labels.jsonl"
    audit_path = tmp_path / "audit.json"
    build_worker_label_rows(scaffold_dir=scaffold, out_path=labels_path)
    audit_leakage(scaffold_dir=scaffold, labels_path=labels_path, out_path=audit_path)

    report = run_selector_only_evaluation(
        scaffold_dir=scaffold,
        labels_path=labels_path,
        leakage_audit_path=audit_path,
        out_path=tmp_path / "eval.json",
        k_values=(1, 3),
    )

    assert report["passed"] is True
    assert METHOD_STANDARD_BM25 in report["methods"]
    first_method = report["rows"][0]["methods"][0]
    metrics = first_method["metrics"]
    assert "file_recall_at_1" in metrics
    assert "chunk_recall_at_3" in metrics
    assert "ndcg" in metrics
    assert "mrr" in metrics
    assert "tokens_to_recover_80pct_files" in metrics
    assert "tokens_to_recover_90pct_files" in metrics
    assert "token_reduction_vs_full_context" in metrics
    serialized = json.dumps(report)
    assert "secret implementation" not in serialized
