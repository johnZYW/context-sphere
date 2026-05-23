from __future__ import annotations

import json
from pathlib import Path

from context_sphere_v3.assembler import assemble_context_sphere
from context_sphere_v3.assembler import parse_python_imports
from context_sphere_v3.assembler import resolve_import_to_file


def write_demo_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    package = repo / "src" / "demo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "core.py").write_text(
        "\n".join(
            [
                "import os",
                "from .helper import normalize",
                "from demo.config import SETTINGS",
                "",
                "def run(value):",
                "    return normalize(value) + SETTINGS['suffix']",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (package / "helper.py").write_text(
        "def normalize(value):\n    return value.strip().lower()\n",
        encoding="utf-8",
    )
    (package / "config.py").write_text(
        "SETTINGS = {'suffix': '-ok'}\n",
        encoding="utf-8",
    )
    return repo


def selector_output() -> dict[str, object]:
    return {
        "schema_version": 1,
        "issue": {"source": "unit-test", "title": "Demo failure"},
        "top_files": [{"path": "src/demo/core.py", "score": 0.9}],
        "top_chunks": [{"chunk_id": "problem_chunk_00", "score": 0.8, "text": "core.py fails"}],
    }


def test_parse_and_resolve_python_imports(tmp_path: Path) -> None:
    repo = write_demo_repo(tmp_path)
    core = repo / "src" / "demo" / "core.py"

    modules = parse_python_imports(core, repo_path=repo)

    assert "os" in modules
    assert "demo.helper" in modules
    assert "demo.config" in modules
    assert resolve_import_to_file("os", importing_file=core, repo_path=repo) is None
    assert resolve_import_to_file("demo.helper", importing_file=core, repo_path=repo) == "src/demo/helper.py"
    assert resolve_import_to_file("demo.config", importing_file=core, repo_path=repo) == "src/demo/config.py"


def test_assemble_context_sphere_worker_lens(tmp_path: Path) -> None:
    repo = write_demo_repo(tmp_path)

    result = assemble_context_sphere(
        selector_output=selector_output(),
        repo_path=repo,
        target_persona="WORKER",
        max_file_chars=1000,
    )
    markdown = str(result["markdown"])

    assert result["core_files"] == ["src/demo/core.py"]
    assert set(result["neighborhood_files"]) == {"src/demo/helper.py", "src/demo/config.py"}
    assert "## Persona Instructions: Worker Lens" in markdown
    assert "## Core Evidence" in markdown
    assert "## Neighborhood" in markdown
    assert "src/demo/core.py" in markdown
    assert "src/demo/helper.py" in markdown
    assert "src/demo/config.py" in markdown


def test_assemble_context_sphere_can_disable_neighborhood(tmp_path: Path) -> None:
    repo = write_demo_repo(tmp_path)

    result = assemble_context_sphere(
        selector_output=selector_output(),
        repo_path=repo,
        target_persona="WORKER",
        max_neighborhood_files=0,
    )

    assert result["core_files"] == ["src/demo/core.py"]
    assert result["neighborhood_files"] == []
    assert "No one-level local import dependencies were resolved" in str(result["markdown"])


def test_assembler_cli_writes_markdown_and_json(tmp_path: Path) -> None:
    repo = write_demo_repo(tmp_path)
    selector_path = tmp_path / "selector.json"
    selector_path.write_text(json.dumps(selector_output()), encoding="utf-8")
    out_path = tmp_path / "sphere.md"
    json_out = tmp_path / "sphere.json"

    import subprocess
    import sys

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/assembler.py",
            str(selector_path),
            str(repo),
            "REVIEWER",
            "--out",
            str(out_path),
            "--json-out",
            str(json_out),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout == ""
    assert "Reviewer Lens" in out_path.read_text(encoding="utf-8")
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["target_persona"] == "reviewer"
    assert payload["core_file_count"] == 1
    assert payload["neighborhood_file_count"] == 2
