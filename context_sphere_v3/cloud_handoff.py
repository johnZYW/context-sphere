"""Cloud execution handoff artifacts for Context Sphere v3."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from context_sphere_v3.baselines import METHOD_CONTEXT_SPHERE_V3
from context_sphere_v3.baselines import METHOD_FULL_CONTEXT
from context_sphere_v3.baselines import METHOD_STANDARD_RAG
from context_sphere_v3.baselines import build_context_section
from context_sphere_v3.baselines import build_prompt_shell
from context_sphere_v3.baselines import load_json
from context_sphere_v3.baselines import load_jsonl


MINIMAX_BASE_URL = "https://api.minimaxi.com/v1"
MINIMAX_CHAT_COMPLETIONS_URL = f"{MINIMAX_BASE_URL}/chat/completions"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_CHAT_COMPLETIONS_URL = f"{DEEPSEEK_BASE_URL}/chat/completions"
PROVIDER_REQUEST_SCHEMA_VERSION = 1
PROVIDER_REQUEST_METHODS = (METHOD_FULL_CONTEXT, METHOD_STANDARD_RAG, METHOD_CONTEXT_SPHERE_V3)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_env_file_keys(path: str | Path) -> set[str]:
    env_path = Path(path)
    if not env_path.exists():
        return set()
    keys = set()
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() and value.strip():
            keys.add(key.strip())
    return keys


def provider_visibility(*, env_file: str | Path = ".env.local") -> dict[str, Any]:
    env_keys = {key for key in ("MINIMAX_API_KEY", "DEEPSEEK_API_KEY") if os.environ.get(key)}
    file_keys = parse_env_file_keys(env_file)
    return {
        "env_file": str(env_file),
        "minimax_key_visible": "MINIMAX_API_KEY" in env_keys or "MINIMAX_API_KEY" in file_keys,
        "deepseek_key_visible": "DEEPSEEK_API_KEY" in env_keys or "DEEPSEEK_API_KEY" in file_keys,
        "visible_key_sources": {
            "MINIMAX_API_KEY": "shell_or_env_file" if "MINIMAX_API_KEY" in env_keys or "MINIMAX_API_KEY" in file_keys else "missing",
            "DEEPSEEK_API_KEY": "shell_or_env_file" if "DEEPSEEK_API_KEY" in env_keys or "DEEPSEEK_API_KEY" in file_keys else "missing",
        },
        "secret_values_logged": False,
    }


def select_provider(visibility: dict[str, Any]) -> dict[str, Any]:
    if visibility["minimax_key_visible"]:
        return {
            "provider": "minimax",
            "fallback_provider": "deepseek" if visibility["deepseek_key_visible"] else None,
            "base_url": MINIMAX_BASE_URL,
            "chat_completions_url": MINIMAX_CHAT_COMPLETIONS_URL,
            "api_key_env": "MINIMAX_API_KEY",
            "model": "MiniMax-M2.7",
        }
    if visibility["deepseek_key_visible"]:
        return {
            "provider": "deepseek",
            "fallback_provider": None,
            "base_url": DEEPSEEK_BASE_URL,
            "chat_completions_url": DEEPSEEK_CHAT_COMPLETIONS_URL,
            "api_key_env": "DEEPSEEK_API_KEY",
            "model": "deepseek-v4-pro",
        }
    return {
        "provider": "blocked",
        "fallback_provider": None,
        "base_url": None,
        "chat_completions_url": None,
        "api_key_env": None,
        "model": None,
    }


def visible_source_by_id(scaffold_dir: str | Path) -> dict[str, dict[str, Any]]:
    return {
        str(row["instance_id"]): row
        for row in load_jsonl(Path(scaffold_dir) / "visible_sources.jsonl")
    }


def request_messages(prompt: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "You are a careful software-maintenance agent. Use only visible issue context.",
        },
        {"role": "user", "content": prompt},
    ]


def build_provider_request_rows(report: dict[str, Any], scaffold_dir: str | Path) -> list[dict[str, Any]]:
    sources = visible_source_by_id(scaffold_dir)
    rows: list[dict[str, Any]] = []
    for method_row in report["method_rows"]:
        method = str(method_row["method"])
        if method not in PROVIDER_REQUEST_METHODS:
            raise ValueError(f"unexpected method {method!r}")
        instance_id = str(method_row["instance_id"])
        source_row = sources[instance_id]
        selection = {
            "selected_chunks": method_row["selected_chunks"],
            "role_sections": method_row["role_sections"],
        }
        context_section = build_context_section(method, selection)
        prompt = build_prompt_shell(source_row, context_section)
        rows.append(
            {
                "schema_version": PROVIDER_REQUEST_SCHEMA_VERSION,
                "custom_id": f"context_sphere_v3::{method}::{instance_id}",
                "instance_id": instance_id,
                "method": method,
                "model": method_row["evaluation_config"]["agent_model"],
                "temperature": method_row["evaluation_config"]["temperature"],
                "max_tokens": method_row["evaluation_config"]["max_generation_tokens"],
                "messages": request_messages(prompt),
                "prompt_shell_id": method_row["prompt_shell_id"],
                "prompt_shell_sha256": method_row["prompt_shell_sha256"],
                "context_row_sha256": sha256_text(json.dumps(method_row, sort_keys=True, ensure_ascii=False)),
                "selected_chunk_ids": method_row["selected_chunk_ids"],
                "token_count_policy": method_row["token_count_policy"],
                "not_model_evidence": True,
                "claim_boundary": "Provider request row only; no model call or benchmark evaluation has run.",
            }
        )
    return rows


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def check_swebench_runtime() -> dict[str, Any]:
    swebench_available = False
    try:
        import swebench  # type: ignore  # noqa: F401

        swebench_available = True
    except ModuleNotFoundError:
        swebench_available = False
    docker_path = shutil.which("docker")
    return {
        "docker_path": docker_path,
        "swebench_package_available": swebench_available,
        "official_evaluation_ready": bool(docker_path and swebench_available),
        "official_pass_at_1_claimed": False,
    }


def prepare_cloud_handoff(
    *,
    scaffold_dir: str | Path = "outputs/swebench_lite_10",
    baseline_report_path: str | Path = "outputs/reports/context_sphere_v3_baseline_comparison.json",
    out_dir: str | Path = "outputs/context_sphere_v3_cloud_handoff",
    env_file: str | Path = ".env.local",
) -> dict[str, Any]:
    scaffold_path = Path(scaffold_dir)
    report_path = Path(baseline_report_path)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    report = load_json(report_path)
    if not report.get("passed"):
        raise ValueError(f"baseline report is not passing: {report_path}")
    request_rows = build_provider_request_rows(report, scaffold_path)
    expected_rows = len(report["instance_ids"]) * len(PROVIDER_REQUEST_METHODS)
    if len(request_rows) != expected_rows:
        raise ValueError(f"expected {expected_rows} provider rows, observed {len(request_rows)}")

    requests_path = out_path / "provider_requests.jsonl"
    write_jsonl(requests_path, request_rows)

    visibility = provider_visibility(env_file=env_file)
    selected_provider = select_provider(visibility)
    runtime = check_swebench_runtime()
    commands = {
        "provider_generation": [
            "Use provider_requests.jsonl with an OpenAI-compatible chat-completions client.",
            f"Preferred MiniMax endpoint: {MINIMAX_CHAT_COMPLETIONS_URL}",
            "Fallback DeepSeek endpoint only if MiniMax budget/access is blocked.",
        ],
        "local_official_swebench_eval": [
            "python",
            "-m",
            "swebench.harness.run_evaluation",
            "--dataset_name",
            "princeton-nlp/SWE-bench_Lite",
            "--predictions_path",
            "outputs/swebench_lite_10/predictions.jsonl",
            "--run_id",
            "context_sphere_v3_cloud_handoff",
        ],
    }
    manifest = {
        "schema_version": 1,
        "handoff": "context_sphere_v3_cloud_handoff",
        "baseline_report_path": str(report_path),
        "baseline_report_sha256": sha256_file(report_path),
        "provider_requests_path": str(requests_path),
        "provider_requests_sha256": sha256_file(requests_path),
        "provider_request_count": len(request_rows),
        "methods": list(PROVIDER_REQUEST_METHODS),
        "instance_ids": report["instance_ids"],
        "provider_preference": ["MiniMax", "DeepSeek fallback if MiniMax is unavailable or budget-limited"],
        "selected_provider": selected_provider,
        "credential_visibility": visibility,
        "runtime": runtime,
        "commands": commands,
        "handoff_ready": True,
        "provider_execution_ready": selected_provider["provider"] != "blocked",
        "official_evaluation_ready": runtime["official_evaluation_ready"],
        "official_pass_at_1_claimed": False,
        "claim_boundary": (
            "Cloud handoff only. Provider request rows are not model outputs, and local official "
            "SWE-bench evaluation remains unavailable unless Docker and the swebench package are present."
        ),
    }
    manifest_path = out_path / "handoff_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    readiness = {
        "schema_version": 1,
        "handoff_manifest": str(manifest_path),
        "handoff_ready": manifest["handoff_ready"],
        "provider_execution_ready": manifest["provider_execution_ready"],
        "official_evaluation_ready": manifest["official_evaluation_ready"],
        "provider_request_count": manifest["provider_request_count"],
        "expected_provider_request_count": expected_rows,
        "selected_provider": selected_provider["provider"],
        "blockers": [
            blocker
            for blocker, blocked in (
                ("provider_key_missing", not manifest["provider_execution_ready"]),
                ("official_swebench_runtime_missing", not manifest["official_evaluation_ready"]),
            )
            if blocked
        ],
        "research_regression_state": (
            "cloud_handoff_ready_but_not_benchmark_evidence"
            if manifest["handoff_ready"]
            else "cloud_handoff_blocked"
        ),
        "official_pass_at_1_claimed": False,
    }
    readiness_path = out_path / "readiness.json"
    readiness_path.write_text(json.dumps(readiness, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest["readiness_path"] = str(readiness_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest
