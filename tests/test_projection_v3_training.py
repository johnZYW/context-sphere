import importlib.util
from pathlib import Path


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "20_train_projection_v3_early_stop.py"
    spec = importlib.util.spec_from_file_location("train_projection_v3", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_worker_margin_prefers_larger_margin_even_if_loss_is_worse():
    module = load_module()
    old = {
        "worker_margin": 0.10,
        "validation_loss": 0.20,
        "global_step": 100,
    }
    new = {
        "worker_margin": 0.25,
        "validation_loss": 0.40,
        "global_step": 200,
    }

    assert module.is_better_worker_checkpoint(new, old)


def test_worker_margin_tie_breaks_on_recall_then_step():
    module = load_module()
    old = {
        "worker_margin": 0.25,
        "worker_recall_at_0_5": 0.40,
        "global_step": 100,
    }
    new = {
        "worker_margin": 0.25,
        "worker_recall_at_0_5": 0.55,
        "global_step": 200,
    }
    later_tie = {
        "worker_margin": 0.25,
        "worker_recall_at_0_5": 0.55,
        "global_step": 300,
    }

    assert module.is_better_worker_checkpoint(new, old)
    assert not module.is_better_worker_checkpoint(later_tie, new)
