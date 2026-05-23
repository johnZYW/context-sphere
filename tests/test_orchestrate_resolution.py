from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from tests.test_context_sphere_assembler import selector_output
from tests.test_context_sphere_assembler import write_demo_repo


ROOT = Path(__file__).resolve().parents[1]


def init_git_repo(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def load_orchestrator_module():
    path = ROOT / "scripts" / "orchestrate_resolution.py"
    spec = importlib.util.spec_from_file_location("orchestrate_resolution_script", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_default_routing_profiles_record_cost_scenario_coefficients(monkeypatch) -> None:
    module = load_orchestrator_module()
    for key in (
        "CONTEXT_SPHERE_MONOLITHIC_INPUT_USD_PER_1M",
        "CONTEXT_SPHERE_MONOLITHIC_OUTPUT_USD_PER_1M",
        "CONTEXT_SPHERE_LONG_CONTEXT_INPUT_USD_PER_1M",
        "CONTEXT_SPHERE_LONG_CONTEXT_OUTPUT_USD_PER_1M",
        "CONTEXT_SPHERE_REASONING_INPUT_USD_PER_1M",
        "CONTEXT_SPHERE_REASONING_OUTPUT_USD_PER_1M",
        "CONTEXT_SPHERE_WORKER_INPUT_USD_PER_1M",
        "CONTEXT_SPHERE_WORKER_OUTPUT_USD_PER_1M",
        "CONTEXT_SPHERE_FALLBACK_INPUT_USD_PER_1M",
        "CONTEXT_SPHERE_FALLBACK_OUTPUT_USD_PER_1M",
    ):
        monkeypatch.delenv(key, raising=False)

    monolithic = module.build_routing_profile(strategy="monolithic", base_url="https://example.test", model="deepseek-chat")
    assert monolithic["pm"]["provider"] == "deepseek"
    assert monolithic["pm"]["api_key_env"] == "DEEPSEEK_API_KEY"
    assert monolithic["pm"]["pricing"]["input_usd_per_1m_tokens"] == 0.27
    assert monolithic["pm"]["pricing"]["output_usd_per_1m_tokens"] == 1.10

    heterogeneous = module.build_routing_profile(
        strategy="heterogeneous",
        base_url="https://example.test",
        model="MiniMax-M2.7",
    )
    assert heterogeneous["locator"]["pricing"]["input_usd_per_1m_tokens"] == 1.25
    assert heterogeneous["locator"]["pricing"]["output_usd_per_1m_tokens"] == 5.00
    assert heterogeneous["pm"]["pricing"]["input_usd_per_1m_tokens"] == 3.00
    assert heterogeneous["pm"]["pricing"]["output_usd_per_1m_tokens"] == 15.00
    assert heterogeneous["worker"]["pricing"]["input_usd_per_1m_tokens"] == 5.00
    assert heterogeneous["worker"]["pricing"]["output_usd_per_1m_tokens"] == 25.00

    fallback = module.build_routing_profile(strategy="fallback", base_url="https://deepseek.example", model="deepseek-chat")
    assert fallback["pm"]["provider"] == "deepseek"
    assert fallback["pm"]["model"] == "deepseek-chat"
    assert fallback["pm"]["secondary"]["provider"] == "minimax"
    assert fallback["pm"]["secondary"]["model"] == "MiniMax-M2.7"
    assert fallback["pm"]["secondary"]["pricing"]["input_usd_per_1m_tokens"] == 0.30
    assert fallback["pm"]["secondary"]["pricing"]["output_usd_per_1m_tokens"] == 1.20


def test_routed_text_hot_swaps_to_minimax_on_provider_failure(tmp_path: Path, monkeypatch) -> None:
    module = load_orchestrator_module()
    monkeypatch.setenv("MINIMAX_API_KEY", "fake-minimax-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-deepseek-key")
    profile = module.build_routing_profile(strategy="fallback", base_url="https://deepseek.example", model="deepseek-chat")[
        "worker"
    ]
    calls = []

    def fake_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("DeepSeek request failed with HTTP 429: rate limit")
        return {
            "choices": [{"message": {"content": "diff --git a/a.py b/a.py\n"}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
        }

    monkeypatch.setattr(module, "chat_completion", fake_chat_completion)
    usage_events = []
    provider_swaps = []

    text = module.routed_text(
        role="worker",
        profile=profile,
        attempt_index=2,
        system_prompt="system",
        user_prompt="user",
        max_tokens=100,
        temperature=0.0,
        timeout=1,
        raw_out=tmp_path / "patch.raw.json",
        usage_events=usage_events,
        provider_swaps=provider_swaps,
    )

    assert text.startswith("diff --git")
    assert len(calls) == 2
    assert calls[0]["base_url"] == "https://deepseek.example"
    assert calls[1]["base_url"] == "https://api.minimaxi.com/v1"
    assert provider_swaps[0]["attempt_index"] == 2
    assert provider_swaps[0]["from_provider"] == "deepseek"
    assert provider_swaps[0]["to_provider"] == "minimax"
    assert usage_events[0]["provider"] == "minimax"
    assert usage_events[0]["estimated_cost_usd"] == 0.0009


def test_orchestrate_resolution_dry_run_loop(tmp_path: Path) -> None:
    repo = write_demo_repo(tmp_path)
    selector_path = tmp_path / "selector_output.json"
    selector_path.write_text(json.dumps(selector_output()), encoding="utf-8")
    out_dir = tmp_path / "resolution_history"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/orchestrate_resolution.py",
            "demo/repo#1",
            str(repo),
            "--selector-output",
            str(selector_path),
            "--out-dir",
            str(out_dir),
            "--dry-run",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    run_dir = Path(payload["run_dir"])
    assert payload["status"] == "approved"
    assert payload["approved"] is True
    assert (run_dir / "selector_output.json").exists()
    assert (run_dir / "pm_sphere.md").exists()
    assert (run_dir / "worker_sphere.md").exists()
    assert (run_dir / "reviewer_sphere.md").exists()
    assert (run_dir / "constraints.json").exists()
    assert (run_dir / "constraints_after_review_v1.json").exists()
    assert (run_dir / "patch_v1.blocks.md").exists()
    assert (run_dir / "patch_v2.blocks.md").exists()
    assert (run_dir / "review_v1.md").read_text(encoding="utf-8").startswith("REJECTED")
    assert (run_dir / "review_v2.md").read_text(encoding="utf-8").startswith("APPROVED")
    assert (run_dir / "final_patch.diff").exists()

    constraints = json.loads((run_dir / "constraints.json").read_text(encoding="utf-8"))
    assert constraints["reviewer_feedback"]
    summary = json.loads((run_dir / "resolution_summary.json").read_text(encoding="utf-8"))
    assert summary["final_state"] == "State_DONE"
    assert len(summary["attempts"]) == 2
    assert summary["model_strategy"] == "monolithic"
    assert summary["routing_profile"]["pm"]["model"] == "deepseek-chat"
    assert summary["estimated_inference_cost_usd"] == 0.0


def test_search_replace_block_parser_and_applicator_commits_clean_patch(tmp_path: Path) -> None:
    module = load_orchestrator_module()
    repo = write_demo_repo(tmp_path)
    init_git_repo(repo)
    block_path = tmp_path / "patch.blocks.md"
    block_path.write_text(
        "\n".join(
            [
                "FILE: src/demo/core.py",
                "<<<<<<< SEARCH",
                "def run(value):",
                "    return normalize(value) + SETTINGS['suffix']",
                "=======",
                "def run(value):",
                "    cleaned = normalize(value)",
                "    return cleaned + SETTINGS['suffix']",
                ">>>>>>> REPLACE",
                "",
            ]
        ),
        encoding="utf-8",
    )

    changes = module.parse_search_replace_blocks(block_path.read_text(encoding="utf-8"), repo_path=repo)
    assert changes[0]["file_path"] == "src/demo/core.py"

    result = module.apply_search_replace_blocks_to_repo(repo, block_path, attempt=1)

    assert result["returncode"] == 0
    assert result["format"] == "search_replace_blocks"
    assert result["changed_files"] == ["src/demo/core.py"]
    assert result["commit"]
    assert "cleaned = normalize(value)" in (repo / "src" / "demo" / "core.py").read_text(encoding="utf-8")


def test_search_replace_applicator_uses_whitespace_normalized_fallback(tmp_path: Path) -> None:
    module = load_orchestrator_module()
    repo = write_demo_repo(tmp_path)
    core = repo / "src" / "demo" / "core.py"
    core.write_text(
        "def run(value):  \n"
        "\n"
        "    cleaned = value.strip()   \n"
        "    return cleaned\n",
        encoding="utf-8",
    )
    init_git_repo(repo)
    block_path = tmp_path / "patch.blocks.md"
    block_path.write_text(
        "\n".join(
            [
                "FILE: src/demo/core.py",
                "<<<<<<< SEARCH",
                "def run(value):",
                "    cleaned = value.strip()",
                "=======",
                "def run(value):",
                "    cleaned = value.strip().lower()",
                "    return cleaned",
                ">>>>>>> REPLACE",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = module.apply_search_replace_blocks_to_repo(repo, block_path, attempt=1)

    assert result["returncode"] == 0
    assert result["applied_changes"][0]["match_mode"] == "normalized_whitespace"
    assert "strip().lower()" in core.read_text(encoding="utf-8")


def test_search_replace_applicator_uses_unique_signature_anchor(tmp_path: Path) -> None:
    module = load_orchestrator_module()
    repo = write_demo_repo(tmp_path)
    core = repo / "src" / "demo" / "core.py"
    core.write_text(
        "def run(value):\n"
        "    cleaned = value.strip()\n"
        "    return cleaned\n",
        encoding="utf-8",
    )
    init_git_repo(repo)
    block_path = tmp_path / "patch.blocks.md"
    block_path.write_text(
        "\n".join(
            [
                "FILE: src/demo/core.py",
                "<<<<<<< SEARCH",
                "def run(value):",
                "    cleaned = value.strip()",
                "    missing_line = cleaned",
                "=======",
                "def run(value):",
                "    cleaned = value.strip().lower()",
                ">>>>>>> REPLACE",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = module.apply_search_replace_blocks_to_repo(repo, block_path, attempt=1)

    assert result["returncode"] == 0
    assert result["applied_changes"][0]["match_mode"] == "signature_anchor"
    updated = core.read_text(encoding="utf-8")
    assert "strip().lower()" in updated
    assert "return cleaned" in updated


def test_patch_target_preflight_rejects_nonexistent_file(tmp_path: Path) -> None:
    module = load_orchestrator_module()
    repo = write_demo_repo(tmp_path)
    patch_text = "\n".join(
        [
            "FILE: doc/source/reference/array_interface.rst",
            "<<<<<<< SEARCH",
            "placeholder",
            "=======",
            "replacement",
            ">>>>>>> REPLACE",
            "",
        ]
    )

    result = module.validate_patch_target_files(repo, patch_text, attempt=2)

    assert result["valid"] is False
    assert result["kind"] == "invalid_target_file"
    assert result["invalid_target_files"] == ["doc/source/reference/array_interface.rst"]
    assert "does not exist" in result["worker_message"]


def test_patch_target_preflight_reports_malformed_block_structure(tmp_path: Path) -> None:
    module = load_orchestrator_module()
    repo = write_demo_repo(tmp_path)
    patch_text = "\n".join(
        [
            "FILE: src/demo/core.py",
            "def run(value):",
            "    return value",
            "",
        ]
    )

    result = module.validate_patch_target_files(repo, patch_text, attempt=1)

    assert result["valid"] is False
    assert result["kind"] == "malformed_block_structure"
    assert result["worker_message"] == module.PREFLIGHT_MALFORMED_BLOCK


def test_patch_target_preflight_reports_truncated_payload(tmp_path: Path) -> None:
    module = load_orchestrator_module()
    repo = write_demo_repo(tmp_path)
    patch_text = "\n".join(
        [
            "FILE: src/demo/core.py",
            "<<<<<<< SEARCH",
            "def run(value):",
            "=======",
            "def run(value):",
            "    return value",
            "",
        ]
    )

    result = module.validate_patch_target_files(repo, patch_text, attempt=1)

    assert result["valid"] is False
    assert result["kind"] == "truncated_payload"
    assert result["worker_message"] == module.PREFLIGHT_TRUNCATED_PAYLOAD


def test_run_verification_rebuilds_for_setup_py_change(tmp_path: Path) -> None:
    module = load_orchestrator_module()
    repo = write_demo_repo(tmp_path)
    (repo / "setup.py").write_text(
        "from distutils.core import setup\n"
        "setup(name='demo', version='0.1')\n",
        encoding="utf-8",
    )
    init_git_repo(repo)
    block_path = tmp_path / "patch.blocks.md"
    block_path.write_text(
        "\n".join(
            [
                "FILE: setup.py",
                "<<<<<<< SEARCH",
                "setup(name='demo', version='0.1')",
                "=======",
                "setup(name='demo', version='0.2')",
                ">>>>>>> REPLACE",
                "",
            ]
        ),
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    result = module.run_verification(
        repo_path=repo,
        patch_blocks_path=block_path,
        test_cmd=f"{sys.executable} -c 'print(\"ok\")'",
        run_dir=run_dir,
        attempt=1,
        python_bin=sys.executable,
    )

    assert result["patch_apply"]["returncode"] == 0
    assert result["requires_rebuild"] is True
    assert result["build_cache_purge"]["path"].endswith(".eggs")
    assert result["build_result"]["command"] == [sys.executable, "setup.py", "build_ext", "--inplace"]
    assert result["build_result"]["returncode"] == 0
    assert result["tests_passed"] is True
    assert (run_dir / "verify_v1.build.stdout").exists()


def test_header_files_trigger_rebuild() -> None:
    module = load_orchestrator_module()

    assert module.changed_files_require_rebuild(["pandas/src/ujson/python/py_defines.h"]) is True
    assert module.changed_files_require_rebuild(["include/demo.hpp"]) is True


def test_purge_egg_cache_removes_existing_directory(tmp_path: Path) -> None:
    module = load_orchestrator_module()
    repo = tmp_path / "repo"
    egg_cache = repo / ".eggs" / "numpy.egg"
    egg_cache.mkdir(parents=True)
    (egg_cache / "marker.txt").write_text("stale", encoding="utf-8")

    result = module.purge_egg_cache(repo)

    assert result["existed"] is True
    assert result["removed"] is True
    assert not (repo / ".eggs").exists()


def test_search_replace_block_parser_rejects_raw_unified_diff(tmp_path: Path) -> None:
    module = load_orchestrator_module()
    repo = write_demo_repo(tmp_path)

    try:
        module.parse_search_replace_blocks("diff --git a/src/demo/core.py b/src/demo/core.py\n", repo_path=repo)
    except ValueError as exc:
        assert "No Search/Replace blocks found" in str(exc)
    else:
        raise AssertionError("raw unified diff should be rejected")


def test_orchestrate_resolution_manual_intervention_after_budget(tmp_path: Path) -> None:
    repo = write_demo_repo(tmp_path)
    selector_path = tmp_path / "selector_output.json"
    selector_path.write_text(json.dumps(selector_output()), encoding="utf-8")
    out_dir = tmp_path / "resolution_history"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/orchestrate_resolution.py",
            "demo/repo#1",
            str(repo),
            "--selector-output",
            str(selector_path),
            "--out-dir",
            str(out_dir),
            "--dry-run",
            "--max-attempts",
            "1",
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    run_dir = Path(payload["run_dir"])
    assert payload["status"] == "manual_intervention"
    assert (run_dir / "manual_intervention.md").exists()
    assert not (run_dir / "final_patch.diff").exists()


def test_orchestrate_resolution_accepts_exact_run_dir(tmp_path: Path) -> None:
    repo = write_demo_repo(tmp_path)
    selector_path = tmp_path / "selector_output.json"
    selector_path.write_text(json.dumps(selector_output()), encoding="utf-8")
    run_dir = tmp_path / "exact_run"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/orchestrate_resolution.py",
            "demo/repo#1",
            str(repo),
            "--selector-output",
            str(selector_path),
            "--run-dir",
            str(run_dir),
            "--dry-run",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert Path(payload["run_dir"]) == run_dir
    assert (run_dir / "resolution_summary.json").exists()


def test_orchestrate_resolution_heterogeneous_strategy_records_role_routes(tmp_path: Path) -> None:
    repo = write_demo_repo(tmp_path)
    selector_path = tmp_path / "selector_output.json"
    selector_path.write_text(json.dumps(selector_output()), encoding="utf-8")
    run_dir = tmp_path / "heterogeneous_run"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/orchestrate_resolution.py",
            "demo/repo#1",
            str(repo),
            "--selector-output",
            str(selector_path),
            "--run-dir",
            str(run_dir),
            "--dry-run",
            "--model-strategy",
            "heterogeneous",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    summary = json.loads((run_dir / "resolution_summary.json").read_text(encoding="utf-8"))
    assert payload["status"] == "approved"
    assert summary["model_strategy"] == "heterogeneous"
    assert summary["routing_profile"]["locator"]["provider_class"] == "long_context"
    assert summary["routing_profile"]["pm"]["provider_class"] == "elite_reasoning"
    assert summary["routing_profile"]["reviewer"]["provider_class"] == "elite_reasoning"
    assert summary["routing_profile"]["worker"]["provider_class"] == "implementation"
    assert summary["model_usage"]["estimated_inference_cost_usd"] == 0.0


def test_orchestrate_resolution_verify_passes_with_test_cmd(tmp_path: Path) -> None:
    repo = write_demo_repo(tmp_path)
    init_git_repo(repo)
    selector_path = tmp_path / "selector_output.json"
    selector_path.write_text(json.dumps(selector_output()), encoding="utf-8")
    run_dir = tmp_path / "verify_pass"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/orchestrate_resolution.py",
            "demo/repo#1",
            str(repo),
            "--selector-output",
            str(selector_path),
            "--run-dir",
            str(run_dir),
            "--dry-run",
            "--test-cmd",
            f"{sys.executable} -c 'print(\"ok\")'",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    summary = json.loads((run_dir / "resolution_summary.json").read_text(encoding="utf-8"))
    assert payload["status"] == "approved"
    assert summary["tests_passed"] is True
    assert summary["final_state"] == "State_DONE"
    assert (run_dir / "verify_v2.json").exists()
    assert (run_dir / "final_patch.diff").exists()


def test_orchestrate_resolution_verify_failure_routes_back_to_worker(tmp_path: Path) -> None:
    repo = write_demo_repo(tmp_path)
    init_git_repo(repo)
    selector_path = tmp_path / "selector_output.json"
    selector_path.write_text(json.dumps(selector_output()), encoding="utf-8")
    run_dir = tmp_path / "verify_fail"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/orchestrate_resolution.py",
            "demo/repo#1",
            str(repo),
            "--selector-output",
            str(selector_path),
            "--run-dir",
            str(run_dir),
            "--dry-run",
            "--max-attempts",
            "2",
            "--test-cmd",
            f"{sys.executable} -c 'import sys; print(\"bad\"); sys.exit(3)'",
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    summary = json.loads((run_dir / "resolution_summary.json").read_text(encoding="utf-8"))
    assert payload["status"] == "manual_intervention"
    assert summary["tests_passed"] is False
    assert summary["final_state"] == "State_MANUAL_INTERVENTION"
    assert (run_dir / "constraints_after_verify_v2.json").exists()
    constraints = json.loads((run_dir / "constraints.json").read_text(encoding="utf-8"))
    assert any(item.get("source") == "State_VERIFY" for item in constraints["reviewer_feedback"])


def test_orchestrate_resolution_expands_context_from_verify_failure_trace(tmp_path: Path) -> None:
    repo = write_demo_repo(tmp_path)
    (repo / "src" / "demo" / "extra.py").write_text(
        "from .deep import explain\n\n"
        "def fail_path():\n"
        "    return explain()\n",
        encoding="utf-8",
    )
    (repo / "src" / "demo" / "deep.py").write_text(
        "def explain():\n"
        "    return 'expanded dependency'\n",
        encoding="utf-8",
    )
    init_git_repo(repo)
    selector_path = tmp_path / "selector_output.json"
    selector_path.write_text(json.dumps(selector_output()), encoding="utf-8")
    run_dir = tmp_path / "verify_expand"
    failing_test = (
        f"{sys.executable} -c "
        "'import sys; "
        'sys.stderr.write(\"Traceback (most recent call last):\\n'
        '  File \\\\\\\"src/demo/extra.py\\\\\\\", line 3, in fail_path\\n'
        'ModuleNotFoundError: No module named \\\\\\\"demo.extra\\\\\\\"\\n\"); '
        "sys.exit(3)'"
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/orchestrate_resolution.py",
            "demo/repo#1",
            str(repo),
            "--selector-output",
            str(selector_path),
            "--run-dir",
            str(run_dir),
            "--dry-run",
            "--max-attempts",
            "2",
            "--test-cmd",
            failing_test,
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    selector = json.loads((run_dir / "selector_output.json").read_text(encoding="utf-8"))
    top_file_paths = {row["path"] for row in selector["top_files"]}
    assert "src/demo/extra.py" in top_file_paths
    assert selector["active_sub_centroids"][0]["path"] == "src/demo/extra.py"

    worker_sphere = (run_dir / "worker_sphere.md").read_text(encoding="utf-8")
    reviewer_sphere = (run_dir / "reviewer_sphere.md").read_text(encoding="utf-8")
    assert "## Recursive Verification Context Expansion" in worker_sphere
    assert "src/demo/extra.py" in worker_sphere
    assert "src/demo/deep.py" in worker_sphere
    assert "src/demo/extra.py" in reviewer_sphere
    assert "src/demo/deep.py" in reviewer_sphere

    constraints = json.loads((run_dir / "constraints.json").read_text(encoding="utf-8"))
    expansions = constraints.get("verification_context_expansions", [])
    assert expansions
    assert expansions[0]["sub_centroid_files"] == ["src/demo/extra.py"]
    assert expansions[0]["token_bounds"]["worker_sphere_chars_after"] >= expansions[0]["token_bounds"]["worker_sphere_chars_before"]
