"""SWE-bench Lite scaffold utilities for Context Sphere v3."""

from __future__ import annotations

import json
import random
import shutil
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from context_sphere_v3.evaluation import EvaluationConfig
from context_sphere_v3.evaluation import SwebenchPredictionRow


DATASET_NAME = "princeton-nlp/SWE-bench_Lite"
DATASET_SPLIT = "test"
DATASET_CONFIG = "default"
DATASET_ROWS_URL = "https://datasets-server.huggingface.co/rows"
DATASET_CARD_URL = "https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite"
SWEBENCH_DATASET_GUIDE_URL = "https://www.swebench.com/SWE-bench/guides/datasets/"
FORBIDDEN_CONTEXT_FIELDS = (
    "patch",
    "test_patch",
    "FAIL_TO_PASS",
    "PASS_TO_PASS",
)
ALLOWED_VISIBLE_FIELDS = (
    "instance_id",
    "repo",
    "base_commit",
    "problem_statement",
)


def _fetch_rows_page(*, split: str, offset: int, length: int) -> tuple[list[dict[str, Any]], int | None]:
    params = urllib.parse.urlencode(
        {
            "dataset": DATASET_NAME,
            "config": DATASET_CONFIG,
            "split": split,
            "offset": offset,
            "length": length,
        }
    )
    with urllib.request.urlopen(f"{DATASET_ROWS_URL}?{params}", timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    rows = []
    for item in payload.get("rows", []):
        row = item.get("row")
        if isinstance(row, dict):
            rows.append(row)
    total = payload.get("num_rows_total")
    total_int = int(total) if isinstance(total, int) else None
    return rows, total_int


def fetch_swebench_lite_rows(*, split: str = DATASET_SPLIT, offset: int = 0, length: int = 300) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page_size = min(100, max(1, length))
    current_offset = offset
    total_rows: int | None = None
    while len(rows) < length:
        page, total = _fetch_rows_page(split=split, offset=current_offset, length=min(page_size, length - len(rows)))
        if total is not None:
            total_rows = total
        if not page:
            break
        rows.extend(page)
        current_offset += len(page)
        if total_rows is not None and current_offset >= total_rows:
            break
    if not rows:
        raise RuntimeError(f"no rows returned from {DATASET_NAME}/{split}")
    return rows


def select_instance_subset(rows: list[dict[str, Any]], *, seed: int, count: int = 10) -> list[dict[str, Any]]:
    if len(rows) < count:
        raise ValueError(f"need at least {count} rows, observed {len(rows)}")
    candidates = sorted(rows, key=lambda row: str(row.get("instance_id", "")))
    rng = random.Random(seed)
    selected_indices = sorted(rng.sample(range(len(candidates)), count))
    return [candidates[index] for index in selected_indices]


def visible_source_log_row(row: dict[str, Any]) -> dict[str, Any]:
    visible = {field: row.get(field, "") for field in ALLOWED_VISIBLE_FIELDS}
    visible["visible_field_names"] = list(ALLOWED_VISIBLE_FIELDS)
    visible["excluded_forbidden_fields"] = [field for field in FORBIDDEN_CONTEXT_FIELDS if field in row]
    visible["no_leakage_boundary"] = (
        "Only instance_id, repo, base_commit, and problem_statement are exposed in this scaffold. "
        "Gold patches, test patches, and test labels are not exposed as context."
    )
    return visible


def scaffold_prediction_for_instance(instance_id: str) -> SwebenchPredictionRow:
    model_patch = (
        "diff --git a/context_sphere_v3_scaffold.txt b/context_sphere_v3_scaffold.txt\n"
        "new file mode 100644\n"
        "index 0000000..1111111\n"
        "--- /dev/null\n"
        "+++ b/context_sphere_v3_scaffold.txt\n"
        "@@ -0,0 +1 @@\n"
        "+Context Sphere v3 scaffold patch; not an official SWE-bench solution.\n"
    )
    return SwebenchPredictionRow(
        instance_id=instance_id,
        model_name_or_path="context-sphere-v3-worker",
        model_patch=model_patch,
    )


def docker_harness_status(predictions_path: str) -> dict[str, Any]:
    docker_path = shutil.which("docker")
    swebench_available = False
    try:
        import swebench  # type: ignore  # noqa: F401

        swebench_available = True
    except ModuleNotFoundError:
        swebench_available = False
    command = [
        "python",
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        DATASET_NAME,
        "--predictions_path",
        predictions_path,
        "--max_workers",
        "8",
        "--run_id",
        "context_sphere_v3_local_debug",
    ]
    if docker_path and swebench_available:
        status = "ready_not_run"
        reason = "Docker and swebench package appear available; run command manually for official scoring."
    elif not docker_path:
        status = "not_run"
        reason = "SWE-bench harness not run: Docker unavailable."
    else:
        status = "not_run"
        reason = "SWE-bench harness not run: swebench package unavailable."
    return {
        "schema_version": 1,
        "official_pass_at_1_claimed": False,
        "status": status,
        "reason": reason,
        "docker_path": docker_path,
        "swebench_package_available": swebench_available,
        "official_harness_command": command,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def prepare_swebench_lite_scaffold(
    *,
    out_dir: str | Path = "outputs/swebench_lite_10",
    seed: int = 20260522,
    count: int = 10,
) -> dict[str, Any]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rows = fetch_swebench_lite_rows(length=300)
    selected = select_instance_subset(rows, seed=seed, count=count)
    selected_ids = [str(row["instance_id"]) for row in selected]

    subset_payload = {
        "schema_version": 1,
        "dataset_name": DATASET_NAME,
        "dataset_card_url": DATASET_CARD_URL,
        "swebench_dataset_guide_url": SWEBENCH_DATASET_GUIDE_URL,
        "dataset_config": DATASET_CONFIG,
        "split": DATASET_SPLIT,
        "seed": seed,
        "count": count,
        "instance_ids": selected_ids,
        "claim_boundary": "Subset selection scaffold only. This is not an official SWE-bench evaluation.",
    }
    subset_path = out_path / "subset.json"
    subset_path.write_text(json.dumps(subset_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    visible_rows = [visible_source_log_row(row) for row in selected]
    visible_sources_path = out_path / "visible_sources.jsonl"
    write_jsonl(visible_sources_path, visible_rows)

    prediction_rows = [scaffold_prediction_for_instance(instance_id).as_json_dict() for instance_id in selected_ids]
    predictions_path = out_path / "predictions.jsonl"
    write_jsonl(predictions_path, prediction_rows)

    eval_config = EvaluationConfig(
        instance_ids=tuple(selected_ids),
        agent_model="MiniMax-M2.7",
        temperature=0.0,
        max_generation_tokens=1200,
        visible_repo_state="swebench_lite_base_commit_only",
        prompt_template_id="context_sphere_v3_pm_worker_reviewer_scaffold_v1",
        seed=seed,
    ).validate()
    config_payload = {
        "schema_version": 1,
        "config_id": "context_sphere_v3_swebench_lite_10_scaffold",
        "dataset_name": DATASET_NAME,
        "dataset_card_url": DATASET_CARD_URL,
        "swebench_dataset_guide_url": SWEBENCH_DATASET_GUIDE_URL,
        "instance_ids": list(eval_config.instance_ids),
        "agent_model": eval_config.agent_model,
        "temperature": eval_config.temperature,
        "max_generation_tokens": eval_config.max_generation_tokens,
        "visible_repo_state": eval_config.visible_repo_state,
        "prompt_template_id": eval_config.prompt_template_id,
        "seed": eval_config.seed,
        "provider_preference": ["MiniMax", "DeepSeek fallback"],
        "claim_boundary": "Configuration scaffold only. No provider calls were made.",
    }
    config_path = out_path / "evaluation_config.json"
    config_path.write_text(json.dumps(config_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    harness_payload = docker_harness_status(str(predictions_path))
    harness_path = out_path / "harness_status.json"
    harness_path.write_text(json.dumps(harness_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "schema_version": 1,
        "scaffold": "context_sphere_v3_swebench_lite_10",
        "passed": (
            len(selected_ids) == count
            and predictions_path.exists()
            and visible_sources_path.exists()
            and harness_payload["official_pass_at_1_claimed"] is False
        ),
        "dataset_name": DATASET_NAME,
        "dataset_card_url": DATASET_CARD_URL,
        "swebench_dataset_guide_url": SWEBENCH_DATASET_GUIDE_URL,
        "seed": seed,
        "count": count,
        "artifacts": {
            "subset": str(subset_path),
            "visible_sources": str(visible_sources_path),
            "predictions": str(predictions_path),
            "evaluation_config": str(config_path),
            "harness_status": str(harness_path),
        },
        "official_pass_at_1_claimed": False,
        "claim_boundary": "SWE-bench scaffold only. Predictions are patch-format placeholders and are not official benchmark results.",
    }
    summary_path = out_path / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary
