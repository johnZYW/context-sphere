# Context Sphere v3

Role-Conditioned Temporal Folding is a research prototype for testing whether
agent role can change useful software-project context geometry.

This package follows the strict v3 handoff in:

- `docs/research_questions/context_sphere_v3_strict_package/context_sphere_v3_codex_goal_pursuit_handoff_STRICT.md`
- `docs/research_questions/context_sphere_v3_strict_package/Context_Sphere_Hypothesis_v3_STRICT_Implementation_Benchmarking.tex`

## Slice Status

Current status: Slices 0-8 complete for scaffold/prototype handoff maturity.

Implemented now:

- fixed roles: `pm`, `worker`, `reviewer`
- documented batch schema
- shape-safe batch validation helper
- evaluation configuration and SWE-bench prediction row interfaces
- toy data, overfit, memory, role-separation, and toy agent-pipeline probes
- vectorized role-conditioned triangular update with reference tests
- SWE-bench Lite 10-instance scaffold and visible-source log
- fair local baseline accounting for Full Context, Standard RAG, and Context Sphere v3
- cloud/provider handoff rows and readiness artifacts

Not implemented yet:

- provider-backed SWE-bench patch generation
- official Docker SWE-bench execution
- fresh novelty review for any paper claim

No official benchmark or novelty claim should be made from the local scaffolds alone.
