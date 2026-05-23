from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_run_benchmarks_module():
    path = ROOT / "scripts" / "run_benchmarks.py"
    spec = importlib.util.spec_from_file_location("run_benchmarks_script", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_test_command_registry_uses_repo_specific_commands() -> None:
    module = load_run_benchmarks_module()

    by_slug = {case.slug: case for case in module.BATCH_CASES}

    assert module.test_command_for_case(by_slug["easy_numpy_22533"]) == (
        "python -m pytest numpy/core/tests/test_overrides.py -q"
    )
    assert module.normalize_test_command(
        module.test_command_for_case(by_slug["easy_numpy_22533"]),
        python_bin="/repo/.venv/bin/python",
    ) == "/repo/.venv/bin/python -m pytest numpy/core/tests/test_overrides.py -q"
    assert module.test_command_for_case(by_slug["arch_wagtail_1120"]) == ".venv/bin/python runtests.py"
    assert module.test_command_for_case(by_slug["arch_pip_7319"]) == "python -m pytest tests/unit -q"
    assert module.TEST_COMMAND_REGISTRY["psf/requests"] == "python -m pytest tests -q"
    assert module.TEST_COMMAND_REGISTRY["django/django"] == "python tests/runtests.py --verbosity 1"
    assert module.bootstrap_commands_for_case(by_slug["arch_wagtail_1120"]) == []
    assert module.normalize_shell_command(
        "python -m pip install -e .",
        python_bin="/repo/.venv/bin/python",
    ) == ["/repo/.venv/bin/python", "-m", "pip", "install", "-e", "."]
    assert "fallback" in module.MODEL_STRATEGIES
    assert sum(1 for case in module.BATCH_CASES if not case.control) == 15


def test_load_cases_file_accepts_benchmark_case_schema(tmp_path: Path) -> None:
    module = load_run_benchmarks_module()
    cases_file = tmp_path / "cases.json"
    cases_file.write_text(
        (
            '[{"slug":"verified_requests_7188","category":"pure_python_verified",'
            '"instance_id":"psf__requests-7188","issue":"psf/requests#7188",'
            '"repo":"psf/requests","base_commit":"abc123","reason":"sample",'
            '"problem_statement":"sample problem","test_cmd":"python -m pytest tests/test_requests.py -q"}]\n'
        ),
        encoding="utf-8",
    )

    cases = module.load_cases_file(cases_file)

    assert len(cases) == 1
    assert cases[0].slug == "verified_requests_7188"
    assert cases[0].control is False
    assert cases[0].problem_statement == "sample problem"
    assert module.test_command_for_case(cases[0]) == "python -m pytest tests/test_requests.py -q"
    assert module.bootstrap_commands_for_case(cases[0]) == ["python -m pip install -e ."]


def test_benchmark_metrics_record_verify_mode_and_test_cmd(tmp_path: Path) -> None:
    module = load_run_benchmarks_module()
    case = module.BATCH_CASES[0]
    run_dir = tmp_path / case.slug
    run_dir.mkdir()
    (run_dir / "resolution_summary.json").write_text(
        (
            '{"approved": true, "attempts": [{"iteration": 1}], "tests_passed": true, '
            '"model_strategy": "heterogeneous", "estimated_inference_cost_usd": 0.42, '
            '"model_usage": {"estimated_inference_cost_usd": 0.42}}\n'
        ),
        encoding="utf-8",
    )

    metrics = module.metrics_for_run(
        case=case,
        run_dir=run_dir,
        command_result={"returncode": 0, "elapsed_seconds": 1.0},
        repo_commands=[],
        dry_run=False,
        run_verify=True,
        python_bin="/repo/.venv/bin/python",
        error=None,
    )

    assert metrics["run_verify"] is True
    assert metrics["tests_passed"] is True
    assert metrics["test_cmd"] == "/repo/.venv/bin/python -m pytest numpy/core/tests/test_overrides.py -q"
    assert metrics["model_strategy"] == "heterogeneous"
    assert metrics["estimated_inference_cost_usd"] == 0.42

    report = module.aggregate_report([metrics], output_root=tmp_path, dry_run=False)
    assert report["tests_passed"] == 1
    assert report["tests_failed"] == 0
    assert report["tests_not_run"] == 0
    assert report["estimated_inference_cost_usd"] == 0.42
    assert report["mean_estimated_inference_cost_usd"] == 0.42
    assert report["internal_approvals_per_dollar"] == 2.38095238
    assert report["verified_efficacy_per_dollar"] == 2.38095238
    assert report["by_category"][case.category]["estimated_inference_cost_usd"] == 0.42


def test_baseline_retriever_flag_is_passed_to_inference(tmp_path: Path, monkeypatch) -> None:
    module = load_run_benchmarks_module()
    case = module.BenchmarkCase(
        slug="demo",
        category="pure_python_verified",
        instance_id="demo__repo-1",
        issue="demo/repo#1",
        repo="demo/repo",
        base_commit="abc",
        reason="unit",
        problem_statement="bug in target",
    )
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "target.py").write_text("print('x')\n", encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    captured = {}

    def fake_run_command(command, *, cwd, timeout=None):
        captured["command"] = command
        out_path = Path(command[command.index("--out") + 1])
        out_path.write_text('{"top_files": [], "top_chunks": []}\n', encoding="utf-8")
        return {"returncode": 0, "stdout": "", "stderr": "", "elapsed_seconds": 0.0, "command": command}

    monkeypatch.setattr(module, "run_command", fake_run_command)

    module.build_local_selector_output(
        case=case,
        repo_path=repo_path,
        run_dir=run_dir,
        python_bin="/python",
        val_items={},
        timeout=10,
        retriever="baseline",
    )

    assert "--retriever" in captured["command"]
    assert captured["command"][captured["command"].index("--retriever") + 1] == "baseline"
    assert captured["command"][captured["command"].index("--repo-path") + 1] == str(repo_path)


def test_hybrid_retriever_flag_is_passed_to_inference(tmp_path: Path, monkeypatch) -> None:
    module = load_run_benchmarks_module()
    case = module.BenchmarkCase(
        slug="demo",
        category="pure_python_verified",
        instance_id="demo__repo-1",
        issue="demo/repo#1",
        repo="demo/repo",
        base_commit="abc",
        reason="unit",
        problem_statement="bug in target",
    )
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "target.py").write_text("print('x')\n", encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    captured = {}

    def fake_run_command(command, *, cwd, timeout=None):
        captured["command"] = command
        out_path = Path(command[command.index("--out") + 1])
        out_path.write_text('{"top_files": [], "top_chunks": []}\n', encoding="utf-8")
        return {"returncode": 0, "stdout": "", "stderr": "", "elapsed_seconds": 0.0, "command": command}

    monkeypatch.setattr(module, "run_command", fake_run_command)

    module.build_local_selector_output(
        case=case,
        repo_path=repo_path,
        run_dir=run_dir,
        python_bin="/python",
        val_items={},
        timeout=10,
        retriever="hybrid",
    )

    assert captured["command"][captured["command"].index("--retriever") + 1] == "hybrid"
