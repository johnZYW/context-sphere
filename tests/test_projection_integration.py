import json
from pathlib import Path

from context_sphere_v3.projection import apply_persona_thresholds
from context_sphere_v3.projection import python_skeleton


def load_orchestrator_module():
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "scripts" / "orchestrate_resolution.py"
    spec = importlib.util.spec_from_file_location("orchestrate_resolution_script", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_python_skeleton_strips_function_bodies():
    source = """
import os

class Widget:
    def compute(self, value):
        secret = value + 1
        return secret
"""

    skeleton = python_skeleton(source)

    assert "import os" in skeleton
    assert "class Widget:" in skeleton
    assert "def compute(self, value): ..." in skeleton
    assert "secret = value + 1" not in skeleton
    assert "return secret" not in skeleton


def test_apply_persona_thresholds_uses_pm_skeleton_and_worker_full_text(tmp_path: Path):
    thresholds = {
        "persona_thresholds": {
            "PM": {"recommended_threshold": 0.7},
            "WORKER": {"recommended_threshold": 0.2},
            "REVIEWER": {"recommended_threshold": 0.5},
        }
    }
    threshold_path = tmp_path / "thresholds.json"
    threshold_path.write_text(json.dumps(thresholds), encoding="utf-8")
    nodes = [
        {
            "path": "pkg/core.py",
            "source": "core",
            "score": 0.9,
            "content": "def solve(x):\n    hidden_impl = x + 1\n    return hidden_impl\n",
            "projection_scores": {"PM": 0.8, "WORKER": 0.3, "REVIEWER": 0.6},
        },
        {
            "path": "pkg/unused.py",
            "source": "core",
            "score": 0.1,
            "content": "def unused():\n    return None\n",
            "projection_scores": {"PM": 0.1, "WORKER": 0.1, "REVIEWER": 0.1},
        },
    ]

    projected = apply_persona_thresholds(nodes, thresholds)

    pm_node = projected["PM"][0]
    worker_node = projected["WORKER"][0]
    assert len(projected["PM"]) == 1
    assert pm_node["node_text_kind"] == "pm_skeleton"
    assert pm_node["raw_body_chars"] == 0
    assert "hidden_impl" not in pm_node["node_text"]
    assert worker_node["node_text_kind"] == "full_text"
    assert worker_node["raw_body_chars"] > 0
    assert "hidden_impl" in worker_node["node_text"]


def test_apply_persona_thresholds_uses_min_k_floor_when_threshold_starves_persona():
    thresholds = {
        "persona_thresholds": {
            "PM": {"recommended_threshold": 0.7},
            "WORKER": {"recommended_threshold": 0.7},
            "REVIEWER": {"recommended_threshold": 0.95},
        }
    }
    nodes = [
        {
            "path": "pkg/a.py",
            "source": "core",
            "content": "def a():\n    return 1\n",
            "projection_scores": {"PM": 0.1, "WORKER": 0.1, "REVIEWER": 0.40},
        },
        {
            "path": "pkg/b.py",
            "source": "core",
            "content": "def b():\n    return 2\n",
            "projection_scores": {"PM": 0.2, "WORKER": 0.2, "REVIEWER": 0.80},
        },
        {
            "path": "pkg/c.py",
            "source": "core",
            "content": "def c():\n    return 3\n",
            "projection_scores": {"PM": 0.3, "WORKER": 0.3, "REVIEWER": 0.60},
        },
    ]

    projected = apply_persona_thresholds(nodes, thresholds, min_k=2)

    assert [node["path"] for node in projected["REVIEWER"]] == ["pkg/b.py", "pkg/c.py"]
    assert {node["projection_selection_reason"] for node in projected["REVIEWER"]} == {"min_k_floor"}


def test_provider_fallback_treats_insufficient_balance_as_swappable():
    module = load_orchestrator_module()

    assert module.provider_error_is_fallbackable(
        RuntimeError('chat completion request failed with HTTP 402: {"error":{"message":"Insufficient Balance"}}')
    )
