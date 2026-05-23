# Context Sphere

Artifact repository for the paper:

**Context Sphere: Topology-Aware Context Orchestration for Autonomous Software Engineering**

Context Sphere is an autonomous software-engineering research artifact evaluated on repository-level repair tasks. It combines:

- neural centroid selection over issue text and repository files;
- deterministic Python AST neighborhood expansion;
- a Product Manager--Worker--Reviewer repair loop;
- local `PASS_TO_PASS` verification;
- a preliminary persona-conditioned Context Projection Model for token reduction.

The artifact is intended to support reproduction of the paper's local 100-case retrieval ablation and 10-case projection smoke test. It is not an official SWE-bench leaderboard submission.

## Repository Layout

```text
context_sphere_v3/        Core Python package for assembly, projection, and training utilities.
scripts/                  Entry points for retrieval, orchestration, benchmarking, and projection training.
tests/                    Focused regression tests for the released artifact.
artifacts/cases/          Exact case lists used in the ablation and projection smoke test.
artifacts/results/        100-case comparative report.
artifacts/projection/     Projection smoke-test comparison artifacts.
artifacts/model_reports/  Projection model training reports and threshold calibration.
models/                   Released Context Projection v3 checkpoint and tokenizer files.
paper/                    arXiv LaTeX source and bibliography.
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Provider-backed repair runs require API keys in the shell environment or an ignored `.env.local` file:

```bash
export DEEPSEEK_API_KEY=...
export MINIMAX_API_KEY=...
```

Do not commit `.env.local` or raw provider credentials.

## Reproducing The Case List

The paper's 100-case list is included at:

```text
artifacts/cases/ablation_benchmark_verified_100.json
```

To regenerate a compatible pure-Python SWE-bench Verified case list:

```bash
python scripts/generate_pure_python_verified_ablation.py \
  --out artifacts/cases/ablation_benchmark_verified_100.regenerated.json \
  --sample-size 100 \
  --seed 42
```

## Running The Main Ablation

The exact paper runs used top-5 core files, at most 24 one-hop neighborhood files, a 60,000-character file clamp, and up to 3 Worker--Reviewer repair attempts per case.

Example Context Sphere run:

```bash
python scripts/run_benchmarks.py \
  --cases-file artifacts/cases/ablation_benchmark_verified_100.json \
  --retrieval-mode standard \
  --model-strategy fallback \
  --max-file-chars 60000 \
  --out outputs/ablation_100_context_repro \
  --run-verify
```

Dense-vector and hybrid controls are selected by the retriever settings in `scripts/inference.py` and the benchmark configuration used for the corresponding paper artifacts. See `artifacts/results/ablation_100_comparative_report.md` for the reconstructed aggregate results.

## Projection Smoke Test

The projection smoke cohort is included at:

```text
artifacts/cases/projection_smoke_context_passed_10.json
```

Run projection mode with the `min_k=2` safety floor:

```bash
python scripts/run_benchmarks.py \
  --cases-file artifacts/cases/projection_smoke_context_passed_10.json \
  --retrieval-mode projection \
  --projection-min-k 2 \
  --model-strategy fallback \
  --max-file-chars 60000 \
  --out outputs/projection_smoke_10_floor_repro \
  --run-verify
```

The paper comparison artifacts are under `artifacts/projection/`.

## Paper Results

The paper reports:

- Dense Vector baseline: 36 / 100 local `PASS_TO_PASS` passes.
- Context Sphere: 41 / 100 local `PASS_TO_PASS` passes.
- Hybrid: 39 / 100 local `PASS_TO_PASS` passes.
- Projection smoke test with `min_k=2`: 9 / 10 known Context Sphere successes preserved, with 71.5% input-token reduction and 58.4% estimated cost reduction.

These are local harness results, not official SWE-bench `FAIL_TO_PASS` leaderboard scores.

## Citation

```bibtex
@misc{zhang2026contextsphere,
  title        = {Context Sphere: Topology-Aware Context Orchestration for Cost-Efficient LLM Repository Repair},
  author       = {Zhang, Yuwen},
  year         = {2026},
  eprint       = {TBD},
  archivePrefix = {arXiv},
  primaryClass = {cs.SE}
}
```

## License

Code is released under the MIT License. See `LICENSE`.
