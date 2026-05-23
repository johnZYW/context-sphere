# Context Sphere 100-Case Retrieval Ablation Report

Generated from local artifacts in `outputs/ablation_100_vector/`, `outputs/ablation_100_context/`, and `outputs/ablation_100_hybrid/`.

Important caveat: this report summarizes the current PASS_TO_PASS smoke/regression verifier, not strict SWE-bench Verified FAIL_TO_PASS scoring. One generated test command contains an unmatched quote, so each run produced 99/100 metrics and crashed on `verified_django_16801` before aggregate `benchmark_summary.json` was written.

## Executive Summary

| Method | Metrics Written | Verified Passes | Manual/Failed/Crash Cases | LLM Calls | Est. Cost USD |
|---|---:|---:|---:|---:|---:|
| Vector | 99/100 | 36 | 64 | 491 | 7.311314 |
| Context Sphere | 99/100 | 41 | 59 | 484 | 8.202211 |
| Hybrid | 99/100 | 39 | 61 | 457 | 8.228887 |

Headline: Context Sphere has the most verified passes on the 99 completed cases, with Hybrid second and dense Vector third. Hybrid did not dominate because dense-vector-first ordering sometimes displaced the Context Sphere files that were useful on Context-only wins.

## Pass Overlap

- Passed by all three methods: 25
- Passed by at least one method: 51
- Vector only: 4
- Context Sphere only: 5
- Hybrid only: 2
- Vector + Context Sphere only: 3
- Vector + Hybrid only: 4
- Context Sphere + Hybrid only: 8

### Unique Pass Lists

**All three (25)**
- `verified_django_10914` (django/django#10914)
- `verified_django_11138` (django/django#11138)
- `verified_django_11206` (django/django#11206)
- `verified_django_11239` (django/django#11239)
- `verified_django_11276` (django/django#11276)
- `verified_django_11433` (django/django#11433)
- `verified_django_11880` (django/django#11880)
- `verified_django_11964` (django/django#11964)
- `verified_django_12050` (django/django#12050)
- `verified_django_12308` (django/django#12308)
- `verified_django_12741` (django/django#12741)
- `verified_django_13121` (django/django#13121)
- `verified_django_13128` (django/django#13128)
- `verified_django_13279` (django/django#13279)
- `verified_django_13449` (django/django#13449)
- `verified_django_13516` (django/django#13516)
- `verified_django_13569` (django/django#13569)
- `verified_django_13590` (django/django#13590)
- `verified_django_13786` (django/django#13786)
- `verified_django_14017` (django/django#14017)
- `verified_django_14140` (django/django#14140)
- `verified_django_14580` (django/django#14580)
- `verified_django_15315` (django/django#15315)
- `verified_django_15380` (django/django#15380)
- `verified_django_15851` (django/django#15851)

**Vector only (4)**
- `verified_django_12262` (django/django#12262)
- `verified_django_14053` (django/django#14053)
- `verified_django_15695` (django/django#15695)
- `verified_sphinx_10673` (sphinx-doc/sphinx#10673)

**Context Sphere only (5)**
- `verified_django_14771` (django/django#14771)
- `verified_requests_1142` (psf/requests#1142)
- `verified_requests_1766` (psf/requests#1766)
- `verified_requests_1921` (psf/requests#1921)
- `verified_sphinx_11445` (sphinx-doc/sphinx#11445)

**Hybrid only (2)**
- `verified_django_13551` (django/django#13551)
- `verified_django_13964` (django/django#13964)

**Vector + Context Sphere only (3)**
- `verified_django_11299` (django/django#11299)
- `verified_django_13933` (django/django#13933)
- `verified_django_16315` (django/django#16315)

**Vector + Hybrid only (4)**
- `verified_django_11141` (django/django#11141)
- `verified_django_12663` (django/django#12663)
- `verified_django_15252` (django/django#15252)
- `verified_django_15375` (django/django#15375)

**Context Sphere + Hybrid only (8)**
- `verified_django_11179` (django/django#11179)
- `verified_django_11211` (django/django#11211)
- `verified_django_11951` (django/django#11951)
- `verified_django_13023` (django/django#13023)
- `verified_django_13513` (django/django#13513)
- `verified_django_14351` (django/django#14351)
- `verified_django_15467` (django/django#15467)
- `verified_django_15569` (django/django#15569)

## Failure Buckets

| Method | PASS | PATCH_APPLY_FAILED | TEST_FAILED | RUNNER/NO_VERIFY/NO_METRICS | Other |
|---|---:|---:|---:|---:|---:|
| Vector | 36 | 31 | 23 | 10 | 0 |
| Context Sphere | 41 | 27 | 24 | 8 | 0 |
| Hybrid | 39 | 24 | 23 | 14 | 0 |

## Case-by-Case Matrix

Legend: `V` = dense Vector baseline, `C` = Context Sphere, `H` = Hybrid. `-` means no method passed. The notes emphasize why the case is interesting or where failures occurred.

| # | Case | Repo | Issue | Passed By | Vector | Context | Hybrid | Notes |
|---:|---|---|---|---|---|---|---|---|
| 1 | `verified_django_10914` | `django/django` | django/django#10914 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 2 | `verified_django_11138` | `django/django` | django/django#11138 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 3 | `verified_django_11141` | `django/django` | django/django#11141 | `VH` | PASS | PATCH_APPLY_FAILED | PASS | Passed by Vector, Hybrid only. Failures: Context Sphere: PATCH_APPLY_FAILED. |
| 4 | `verified_django_11149` | `django/django` | django/django#11149 | `-` | PATCH_APPLY_FAILED | TEST_FAILED | PATCH_APPLY_FAILED | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (2/3). |
| 5 | `verified_django_11163` | `django/django` | django/django#11163 | `-` | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (3/3). |
| 6 | `verified_django_11179` | `django/django` | django/django#11179 | `CH` | PATCH_APPLY_FAILED | PASS | PASS | Passed by Context Sphere, Hybrid only. Failures: Vector: PATCH_APPLY_FAILED. |
| 7 | `verified_django_11206` | `django/django` | django/django#11206 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 8 | `verified_django_11211` | `django/django` | django/django#11211 | `CH` | PATCH_APPLY_FAILED | PASS | PASS | Passed by Context Sphere, Hybrid only. Failures: Vector: PATCH_APPLY_FAILED. |
| 9 | `verified_django_11239` | `django/django` | django/django#11239 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 10 | `verified_django_11276` | `django/django` | django/django#11276 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 11 | `verified_django_11299` | `django/django` | django/django#11299 | `VC` | PASS | PASS | PATCH_APPLY_FAILED | Passed by Vector, Context Sphere only. Failures: Hybrid: PATCH_APPLY_FAILED. |
| 12 | `verified_django_11433` | `django/django` | django/django#11433 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 13 | `verified_django_11880` | `django/django` | django/django#11880 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 14 | `verified_django_11951` | `django/django` | django/django#11951 | `CH` | PATCH_APPLY_FAILED | PASS | PASS | Passed by Context Sphere, Hybrid only. Failures: Vector: PATCH_APPLY_FAILED. |
| 15 | `verified_django_11964` | `django/django` | django/django#11964 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 16 | `verified_django_12050` | `django/django` | django/django#12050 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 17 | `verified_django_12143` | `django/django` | django/django#12143 | `-` | TEST_FAILED | PATCH_APPLY_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (2/3). |
| 18 | `verified_django_12262` | `django/django` | django/django#12262 | `V` | PASS | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | Passed by Vector only. Failures: Context Sphere: PATCH_APPLY_FAILED, Hybrid: PATCH_APPLY_FAILED. |
| 19 | `verified_django_12273` | `django/django` | django/django#12273 | `-` | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (3/3). |
| 20 | `verified_django_12308` | `django/django` | django/django#12308 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 21 | `verified_django_12325` | `django/django` | django/django#12325 | `-` | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (3/3). |
| 22 | `verified_django_12406` | `django/django` | django/django#12406 | `-` | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (3/3). |
| 23 | `verified_django_12663` | `django/django` | django/django#12663 | `VH` | PASS | TEST_FAILED | PASS | Passed by Vector, Hybrid only. Failures: Context Sphere: TEST_FAILED. |
| 24 | `verified_django_12741` | `django/django` | django/django#12741 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 25 | `verified_django_12754` | `django/django` | django/django#12754 | `-` | TEST_FAILED | TEST_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (3/3). |
| 26 | `verified_django_13023` | `django/django` | django/django#13023 | `CH` | PATCH_APPLY_FAILED | PASS | PASS | Passed by Context Sphere, Hybrid only. Failures: Vector: PATCH_APPLY_FAILED. |
| 27 | `verified_django_13028` | `django/django` | django/django#13028 | `-` | PATCH_APPLY_FAILED | TEST_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (2/3). |
| 28 | `verified_django_13089` | `django/django` | django/django#13089 | `-` | TEST_FAILED | TEST_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (3/3). |
| 29 | `verified_django_13121` | `django/django` | django/django#13121 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 30 | `verified_django_13128` | `django/django` | django/django#13128 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 31 | `verified_django_13279` | `django/django` | django/django#13279 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 32 | `verified_django_13315` | `django/django` | django/django#13315 | `-` | PATCH_APPLY_FAILED | TEST_FAILED | PATCH_APPLY_FAILED | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (2/3). |
| 33 | `verified_django_13344` | `django/django` | django/django#13344 | `-` | TEST_FAILED | TEST_FAILED | PATCH_APPLY_FAILED | No retriever passed. Dominant failure: TEST_FAILED (2/3). |
| 34 | `verified_django_13449` | `django/django` | django/django#13449 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 35 | `verified_django_13513` | `django/django` | django/django#13513 | `CH` | PATCH_APPLY_FAILED | PASS | PASS | Passed by Context Sphere, Hybrid only. Failures: Vector: PATCH_APPLY_FAILED. |
| 36 | `verified_django_13516` | `django/django` | django/django#13516 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 37 | `verified_django_13551` | `django/django` | django/django#13551 | `H` | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | PASS | Passed by Hybrid only. Failures: Vector: PATCH_APPLY_FAILED, Context Sphere: PATCH_APPLY_FAILED. |
| 38 | `verified_django_13569` | `django/django` | django/django#13569 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 39 | `verified_django_13590` | `django/django` | django/django#13590 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 40 | `verified_django_13786` | `django/django` | django/django#13786 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 41 | `verified_django_13933` | `django/django` | django/django#13933 | `VC` | PASS | PASS | PATCH_APPLY_FAILED | Passed by Vector, Context Sphere only. Failures: Hybrid: PATCH_APPLY_FAILED. |
| 42 | `verified_django_13964` | `django/django` | django/django#13964 | `H` | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | PASS | Passed by Hybrid only. Failures: Vector: PATCH_APPLY_FAILED, Context Sphere: PATCH_APPLY_FAILED. |
| 43 | `verified_django_14007` | `django/django` | django/django#14007 | `-` | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (3/3). |
| 44 | `verified_django_14017` | `django/django` | django/django#14017 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 45 | `verified_django_14053` | `django/django` | django/django#14053 | `V` | PASS | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | Passed by Vector only. Failures: Context Sphere: PATCH_APPLY_FAILED, Hybrid: PATCH_APPLY_FAILED. |
| 46 | `verified_django_14122` | `django/django` | django/django#14122 | `-` | TEST_FAILED | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (2/3). |
| 47 | `verified_django_14140` | `django/django` | django/django#14140 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 48 | `verified_django_14351` | `django/django` | django/django#14351 | `CH` | PATCH_APPLY_FAILED | PASS | PASS | Passed by Context Sphere, Hybrid only. Failures: Vector: PATCH_APPLY_FAILED. |
| 49 | `verified_django_14580` | `django/django` | django/django#14580 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 50 | `verified_django_14608` | `django/django` | django/django#14608 | `-` | TEST_FAILED | TEST_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (3/3). |
| 51 | `verified_django_14765` | `django/django` | django/django#14765 | `-` | PATCH_APPLY_FAILED | TEST_FAILED | PATCH_APPLY_FAILED | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (2/3). |
| 52 | `verified_django_14771` | `django/django` | django/django#14771 | `C` | PATCH_APPLY_FAILED | PASS | PATCH_APPLY_FAILED | Passed by Context Sphere only. Failures: Vector: PATCH_APPLY_FAILED, Hybrid: PATCH_APPLY_FAILED. |
| 53 | `verified_django_14787` | `django/django` | django/django#14787 | `-` | TEST_FAILED | PATCH_APPLY_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (2/3). |
| 54 | `verified_django_15022` | `django/django` | django/django#15022 | `-` | PATCH_APPLY_FAILED | TEST_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (2/3). |
| 55 | `verified_django_15252` | `django/django` | django/django#15252 | `VH` | PASS | PATCH_APPLY_FAILED | PASS | Passed by Vector, Hybrid only. Failures: Context Sphere: PATCH_APPLY_FAILED. |
| 56 | `verified_django_15278` | `django/django` | django/django#15278 | `-` | TEST_FAILED | TEST_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (3/3). |
| 57 | `verified_django_15315` | `django/django` | django/django#15315 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 58 | `verified_django_15375` | `django/django` | django/django#15375 | `VH` | PASS | PATCH_APPLY_FAILED | PASS | Passed by Vector, Hybrid only. Failures: Context Sphere: PATCH_APPLY_FAILED. |
| 59 | `verified_django_15380` | `django/django` | django/django#15380 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 60 | `verified_django_15467` | `django/django` | django/django#15467 | `CH` | PATCH_APPLY_FAILED | PASS | PASS | Passed by Context Sphere, Hybrid only. Failures: Vector: PATCH_APPLY_FAILED. |
| 61 | `verified_django_15554` | `django/django` | django/django#15554 | `-` | TEST_FAILED | TEST_FAILED | PATCH_APPLY_FAILED | No retriever passed. Dominant failure: TEST_FAILED (2/3). |
| 62 | `verified_django_15563` | `django/django` | django/django#15563 | `-` | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | TEST_FAILED | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (2/3). |
| 63 | `verified_django_15569` | `django/django` | django/django#15569 | `CH` | PATCH_APPLY_FAILED | PASS | PASS | Passed by Context Sphere, Hybrid only. Failures: Vector: PATCH_APPLY_FAILED. |
| 64 | `verified_django_15629` | `django/django` | django/django#15629 | `-` | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (3/3). |
| 65 | `verified_django_15695` | `django/django` | django/django#15695 | `V` | PASS | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | Passed by Vector only. Failures: Context Sphere: PATCH_APPLY_FAILED, Hybrid: PATCH_APPLY_FAILED. |
| 66 | `verified_django_15731` | `django/django` | django/django#15731 | `-` | PATCH_APPLY_FAILED | TEST_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (2/3). |
| 67 | `verified_django_15814` | `django/django` | django/django#15814 | `-` | TEST_FAILED | PATCH_APPLY_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (2/3). |
| 68 | `verified_django_15851` | `django/django` | django/django#15851 | `VCH` | PASS | PASS | PASS | All retrievers solved this case; likely easy under current smoke tests. |
| 69 | `verified_django_15930` | `django/django` | django/django#15930 | `-` | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (3/3). |
| 70 | `verified_django_15987` | `django/django` | django/django#15987 | `-` | PATCH_APPLY_FAILED | TEST_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (2/3). |
| 71 | `verified_django_16255` | `django/django` | django/django#16255 | `-` | TEST_FAILED | TEST_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (3/3). |
| 72 | `verified_django_16263` | `django/django` | django/django#16263 | `-` | TEST_FAILED | TEST_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (3/3). |
| 73 | `verified_django_16315` | `django/django` | django/django#16315 | `VC` | PASS | PASS | PATCH_APPLY_FAILED | Passed by Vector, Context Sphere only. Failures: Hybrid: PATCH_APPLY_FAILED. |
| 74 | `verified_django_16662` | `django/django` | django/django#16662 | `-` | RUNNER_ERROR | RUNNER_ERROR | RUNNER_ERROR | No retriever passed. Dominant failure: RUNNER_ERROR (3/3). |
| 75 | `verified_django_16667` | `django/django` | django/django#16667 | `-` | RUNNER_ERROR | RUNNER_ERROR | RUNNER_ERROR | No retriever passed. Dominant failure: RUNNER_ERROR (3/3). |
| 76 | `verified_django_16801` | `django/django` | django/django#16801 | `-` | NO_METRICS | NO_METRICS | NO_METRICS | No retriever passed. Dominant failure: NO_METRICS (3/3). |
| 77 | `verified_django_16899` | `django/django` | django/django#16899 | `-` | RUNNER_ERROR | RUNNER_ERROR | RUNNER_ERROR | No retriever passed. Dominant failure: RUNNER_ERROR (3/3). |
| 78 | `verified_django_16938` | `django/django` | django/django#16938 | `-` | RUNNER_ERROR | RUNNER_ERROR | RUNNER_ERROR | No retriever passed. Dominant failure: RUNNER_ERROR (3/3). |
| 79 | `verified_django_17029` | `django/django` | django/django#17029 | `-` | RUNNER_ERROR | RUNNER_ERROR | RUNNER_ERROR | No retriever passed. Dominant failure: RUNNER_ERROR (3/3). |
| 80 | `verified_django_17084` | `django/django` | django/django#17084 | `-` | RUNNER_ERROR | RUNNER_ERROR | RUNNER_ERROR | No retriever passed. Dominant failure: RUNNER_ERROR (3/3). |
| 81 | `verified_django_17087` | `django/django` | django/django#17087 | `-` | RUNNER_ERROR | RUNNER_ERROR | RUNNER_ERROR | No retriever passed. Dominant failure: RUNNER_ERROR (3/3). |
| 82 | `verified_flask_5014` | `pallets/flask` | pallets/flask#5014 | `-` | TEST_FAILED | TEST_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (3/3). |
| 83 | `verified_requests_1142` | `psf/requests` | psf/requests#1142 | `C` | RUNNER_ERROR | PASS | RUNNER_ERROR | Passed by Context Sphere only. Failures: Vector: RUNNER_ERROR, Hybrid: RUNNER_ERROR. |
| 84 | `verified_requests_1766` | `psf/requests` | psf/requests#1766 | `C` | RUNNER_ERROR | PASS | RUNNER_ERROR | Passed by Context Sphere only. Failures: Vector: RUNNER_ERROR, Hybrid: RUNNER_ERROR. |
| 85 | `verified_requests_1921` | `psf/requests` | psf/requests#1921 | `C` | PATCH_APPLY_FAILED | PASS | PATCH_APPLY_FAILED | Passed by Context Sphere only. Failures: Vector: PATCH_APPLY_FAILED, Hybrid: PATCH_APPLY_FAILED. |
| 86 | `verified_pytest_10081` | `pytest-dev/pytest` | pytest-dev/pytest#10081 | `-` | TEST_FAILED | PATCH_APPLY_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (2/3). |
| 87 | `verified_pytest_10356` | `pytest-dev/pytest` | pytest-dev/pytest#10356 | `-` | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | TEST_FAILED | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (2/3). |
| 88 | `verified_pytest_7521` | `pytest-dev/pytest` | pytest-dev/pytest#7521 | `-` | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (3/3). |
| 89 | `verified_pytest_7982` | `pytest-dev/pytest` | pytest-dev/pytest#7982 | `-` | TEST_FAILED | TEST_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (3/3). |
| 90 | `verified_sphinx_10673` | `sphinx-doc/sphinx` | sphinx-doc/sphinx#10673 | `V` | PASS | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | Passed by Vector only. Failures: Context Sphere: PATCH_APPLY_FAILED, Hybrid: PATCH_APPLY_FAILED. |
| 91 | `verified_sphinx_11445` | `sphinx-doc/sphinx` | sphinx-doc/sphinx#11445 | `C` | TEST_FAILED | PASS | PATCH_APPLY_FAILED | Passed by Context Sphere only. Failures: Vector: TEST_FAILED, Hybrid: PATCH_APPLY_FAILED. |
| 92 | `verified_sphinx_7440` | `sphinx-doc/sphinx` | sphinx-doc/sphinx#7440 | `-` | PATCH_APPLY_FAILED | PATCH_APPLY_FAILED | TEST_FAILED | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (2/3). |
| 93 | `verified_sphinx_7910` | `sphinx-doc/sphinx` | sphinx-doc/sphinx#7910 | `-` | TEST_FAILED | PATCH_APPLY_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (2/3). |
| 94 | `verified_sphinx_7985` | `sphinx-doc/sphinx` | sphinx-doc/sphinx#7985 | `-` | TEST_FAILED | TEST_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (3/3). |
| 95 | `verified_sphinx_8265` | `sphinx-doc/sphinx` | sphinx-doc/sphinx#8265 | `-` | TEST_FAILED | TEST_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (3/3). |
| 96 | `verified_sphinx_8593` | `sphinx-doc/sphinx` | sphinx-doc/sphinx#8593 | `-` | TEST_FAILED | PATCH_APPLY_FAILED | TEST_FAILED | No retriever passed. Dominant failure: TEST_FAILED (2/3). |
| 97 | `verified_sphinx_8721` | `sphinx-doc/sphinx` | sphinx-doc/sphinx#8721 | `-` | PATCH_APPLY_FAILED | TEST_FAILED | NO_VERIFY | No retriever passed. Dominant failure: PATCH_APPLY_FAILED (1/3). |
| 98 | `verified_sphinx_9258` | `sphinx-doc/sphinx` | sphinx-doc/sphinx#9258 | `-` | TEST_FAILED | TEST_FAILED | NO_VERIFY | No retriever passed. Dominant failure: TEST_FAILED (2/3). |
| 99 | `verified_sphinx_9367` | `sphinx-doc/sphinx` | sphinx-doc/sphinx#9367 | `-` | TEST_FAILED | TEST_FAILED | NO_VERIFY | No retriever passed. Dominant failure: TEST_FAILED (2/3). |
| 100 | `verified_sphinx_9461` | `sphinx-doc/sphinx` | sphinx-doc/sphinx#9461 | `-` | TEST_FAILED | TEST_FAILED | NO_VERIFY | No retriever passed. Dominant failure: TEST_FAILED (2/3). |

## Detailed Failure Notes

### `verified_django_10914` (django/django#10914)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.02950896
  - Top files: `django/core/files/uploadhandler.py`, `django/core/files/uploadedfile.py`, `tests/file_storage/models.py`, `django/core/files/temp.py`, `tests/file_storage/tests.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.02275454
  - Top files: `django/core/files/storage.py`, `docs/howto/custom-file-storage.txt`, `django/middleware/security.py`, `docs/topics/http/file-uploads.txt`, `docs/ref/files/uploads.txt`
- **Hybrid:** PASS; iterations=2; calls=5; cost=0.03809624
  - Top files: `django/core/files/uploadhandler.py`, `django/core/files/uploadedfile.py`, `tests/file_storage/models.py`, `django/core/files/storage.py`, `docs/howto/custom-file-storage.txt`

### `verified_django_11138` (django/django#11138)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.01028681
  - Top files: `django/db/backends/postgresql/utils.py`, `django/utils/timezone.py`, `django/contrib/admin/migrations/0002_logentry_remove_auto_add.py`, `tests/utils_tests/test_timezone.py`, `django/templatetags/tz.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.05762887
  - Top files: `django/db/backends/mysql/operations.py`, `django/db/backends/oracle/operations.py`, `django/contrib/gis/db/backends/oracle/operations.py`, `django/contrib/gis/db/backends/mysql/operations.py`, `docs/ref/models/querysets.txt`
- **Hybrid:** PASS; iterations=2; calls=5; cost=0.0785366
  - Top files: `django/db/backends/postgresql/utils.py`, `django/utils/timezone.py`, `django/contrib/admin/migrations/0002_logentry_remove_auto_add.py`, `django/db/backends/mysql/operations.py`, `django/db/backends/oracle/operations.py`

### `verified_django_11141` (django/django#11141)

Passed by: `VH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.02675695
  - Top files: `django/db/migrations/loader.py`, `django/utils/module_loading.py`, `django/db/migrations/questioner.py`, `django/db/migrations/__init__.py`, `django/db/migrations/migration.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=5; cost=0.00247378
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/migrations/faulty_migrations/namespace/foo/__init__.py`, `tests/migrations/__init__.py`, `tests/files/__init__.py`, `tests/sites_framework/migrations/__init__.py`, `tests/postgres_tests/migrations/__init__.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.02292553
  - Top files: `django/db/migrations/loader.py`, `django/utils/module_loading.py`, `django/db/migrations/questioner.py`, `tests/migrations/faulty_migrations/namespace/foo/__init__.py`, `tests/migrations/__init__.py`

### `verified_django_11149` (django/django#11149)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.10087979
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/admin_inlines/tests.py`, `django/contrib/admin/actions.py`, `tests/schema/fields.py`, `tests/admin_widgets/widgetadmin.py`, `tests/admin_inlines/admin.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.12555314
  - Detail: ModuleNotFoundError: No module named 'Regression' ====================================================================== ERROR: for (unittest.loader._FailedTest) ------------------
  - Top files: `django/contrib/admin/models.py`, `tests/view_tests/models.py`, `tests/validation/models.py`, `tests/utils_tests/models.py`, `tests/user_commands/models.py`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.11489026
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/admin_inlines/tests.py`, `django/contrib/admin/actions.py`, `tests/schema/fields.py`, `django/contrib/admin/models.py`, `tests/view_tests/models.py`

### `verified_django_11163` (django/django#11163)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.1434872
  - Detail: ValueError: SEARCH block matched 2 times exactly; expected one unique match
  - Top files: `tests/empty/models.py`, `django/contrib/postgres/fields/hstore.py`, `django/db/migrations/operations/utils.py`, `django/db/migrations/operations/fields.py`, `tests/model_meta/tests.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.1537512
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `django/db/models/fields/files.py`, `django/forms/fields.py`, `django/views/generic/list.py`, `django/core/files/utils.py`, `django/core/files/uploadhandler.py`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.17152331
  - Detail: ValueError: SEARCH block matched 2 times exactly; expected one unique match
  - Top files: `tests/empty/models.py`, `django/contrib/postgres/fields/hstore.py`, `django/db/migrations/operations/utils.py`, `django/db/models/fields/files.py`, `django/forms/fields.py`

### `verified_django_11179` (django/django#11179)

Passed by: `CH`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.03458002
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/migrations/migrations_test_apps/unmigrated_app_syncdb/models.py`, `django/contrib/admin/actions.py`, `tests/migrations/test_migrations_no_changes/0003_third.py`, `tests/schema/models.py`, `tests/serializers/models/natural.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.06157564
  - Top files: `django/db/models/deletion.py`, `tests/update/models.py`, `tests/delete/models.py`, `django/forms/models.py`, `docs/ref/models/instances.txt`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.01475965
  - Top files: `tests/migrations/migrations_test_apps/unmigrated_app_syncdb/models.py`, `django/contrib/admin/actions.py`, `tests/migrations/test_migrations_no_changes/0003_third.py`, `django/db/models/deletion.py`, `tests/update/models.py`

### `verified_django_11206` (django/django#11206)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.02528202
  - Top files: `tests/utils_tests/test_numberformat.py`, `django/utils/numberformat.py`, `tests/db_functions/math/test_exp.py`, `tests/model_fields/test_decimalfield.py`, `tests/template_tests/filter_tests/test_floatformat.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.00709826
  - Top files: `django/utils/numberformat.py`, `django/utils/xmlutils.py`, `django/utils/version.py`, `django/utils/tree.py`, `django/utils/topological_sort.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.01460248
  - Top files: `tests/utils_tests/test_numberformat.py`, `django/utils/numberformat.py`, `tests/db_functions/math/test_exp.py`, `django/utils/xmlutils.py`, `django/utils/version.py`

### `verified_django_11211` (django/django#11211)

Passed by: `CH`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.08672486
  - Detail: RuntimeError: Search/Replace blocks produced no staged changes
  - Top files: `tests/serializers/models/natural.py`, `tests/delete/models.py`, `django/contrib/contenttypes/fields.py`, `tests/indexes/models.py`, `tests/generic_inline_admin/models.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.09298732
  - Top files: `django/db/models/fields/related.py`, `tests/prefetch_related/models.py`, `django/template/library.py`, `django/template/engine.py`, `django/forms/models.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.08452135
  - Top files: `tests/serializers/models/natural.py`, `tests/delete/models.py`, `django/contrib/contenttypes/fields.py`, `django/db/models/fields/related.py`, `tests/prefetch_related/models.py`

### `verified_django_11239` (django/django#11239)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.03311014
  - Top files: `django/db/backends/postgresql/base.py`, `tests/postgres_tests/integration_settings.py`, `django/core/management/commands/dbshell.py`, `django/db/__init__.py`, `django/contrib/gis/db/backends/postgis/base.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.02773181
  - Top files: `django/db/backends/postgresql/schema.py`, `django/db/backends/postgresql/client.py`, `django/db/backends/sqlite3/schema.py`, `django/db/backends/sqlite3/client.py`, `django/db/backends/postgresql/utils.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.04926623
  - Top files: `django/db/backends/postgresql/base.py`, `tests/postgres_tests/integration_settings.py`, `django/core/management/commands/dbshell.py`, `django/db/backends/postgresql/schema.py`, `django/db/backends/postgresql/client.py`

### `verified_django_11276` (django/django#11276)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.02494226
  - Top files: `django/utils/html.py`, `django/utils/safestring.py`, `tests/utils_tests/test_safestring.py`, `django/views/csrf.py`, `tests/i18n/commands/__init__.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.0217038
  - Top files: `django/forms/templates/django/forms/widgets/text.html`, `django/utils/version.py`, `django/utils/text.py`, `django/utils/html.py`, `django/views/templates/technical_500.html`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.01896107
  - Top files: `django/utils/html.py`, `django/utils/safestring.py`, `tests/utils_tests/test_safestring.py`, `django/forms/templates/django/forms/widgets/text.html`, `django/utils/version.py`

### `verified_django_11299` (django/django#11299)

Passed by: `VC`
- **Vector:** PASS; iterations=1; calls=3; cost=0.02814271
  - Top files: `django/db/models/constraints.py`, `django/db/models/indexes.py`, `tests/postgres_tests/test_constraints.py`, `tests/constraints/tests.py`, `django/contrib/sites/managers.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.08851094
  - Top files: `django/db/models/sql/query.py`, `django/db/migrations/operations/models.py`, `django/db/migrations/operations/fields.py`, `django/db/models/query.py`, `django/db/models/constraints.py`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.16998078
  - Detail: RuntimeError: Search/Replace blocks produced no staged changes
  - Top files: `django/db/models/constraints.py`, `django/db/models/indexes.py`, `tests/postgres_tests/test_constraints.py`, `django/db/models/sql/query.py`, `django/db/migrations/operations/models.py`

### `verified_django_11433` (django/django#11433)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.03126648
  - Top files: `tests/save_delete_hooks/models.py`, `tests/model_fields/test_filefield.py`, `tests/forms_tests/widget_tests/test_fileinput.py`, `tests/model_formsets/test_uuid.py`, `tests/model_formsets_regress/tests.py`
- **Context Sphere:** PASS; iterations=2; calls=5; cost=0.15005837
  - Top files: `django/db/models/fields/files.py`, `Django.egg-info/requires.txt`, `docs/howto/custom-model-fields.txt`, `django/forms/fields.py`, `django/core/files/utils.py`
- **Hybrid:** PASS; iterations=2; calls=5; cost=0.05911797
  - Top files: `tests/save_delete_hooks/models.py`, `tests/model_fields/test_filefield.py`, `tests/forms_tests/widget_tests/test_fileinput.py`, `django/db/models/fields/files.py`, `Django.egg-info/requires.txt`

### `verified_django_11880` (django/django#11880)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.03971423
  - Top files: `tests/validation/__init__.py`, `django/forms/forms.py`, `django/forms/formsets.py`, `tests/forms_tests/field_tests/test_charfield.py`, `django/contrib/postgres/forms/array.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.04363106
  - Top files: `django/forms/fields.py`, `django/forms/forms.py`, `django/contrib/gis/forms/fields.py`, `django/contrib/flatpages/forms.py`, `django/contrib/contenttypes/forms.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.04224316
  - Top files: `tests/validation/__init__.py`, `django/forms/forms.py`, `django/forms/formsets.py`, `django/forms/fields.py`, `django/contrib/gis/forms/fields.py`

### `verified_django_11951` (django/django#11951)

Passed by: `CH`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.09378816
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/backends/oracle/test_operations.py`, `django/db/backends/sqlite3/operations.py`, `tests/force_insert_update/models.py`, `tests/requests/test_data_upload_settings.py`, `tests/queries/test_bulk_update.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.08114456
  - Top files: `django/db/models/query.py`, `django/db/models/sql/query.py`, `tests/bulk_create/models.py`, `django/forms/models.py`, `django/db/models/utils.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.07721452
  - Top files: `tests/backends/oracle/test_operations.py`, `django/db/backends/sqlite3/operations.py`, `tests/force_insert_update/models.py`, `django/db/models/query.py`, `django/db/models/sql/query.py`

### `verified_django_11964` (django/django#11964)

Passed by: `VCH`
- **Vector:** PASS; iterations=2; calls=5; cost=0.03691153
  - Top files: `django/db/models/enums.py`, `tests/forms_tests/field_tests/test_typedmultiplechoicefield.py`, `tests/forms_tests/field_tests/test_typedchoicefield.py`, `tests/serializers/models/base.py`, `tests/model_regress/models.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.03507129
  - Top files: `tests/str/tests.py`, `tests/str/models.py`, `django/test/utils.py`, `tests/i18n/sampleproject/manage.py`, `django/utils/translation/trans_real.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.02989784
  - Top files: `django/db/models/enums.py`, `tests/forms_tests/field_tests/test_typedmultiplechoicefield.py`, `tests/forms_tests/field_tests/test_typedchoicefield.py`, `tests/str/tests.py`, `tests/str/models.py`

### `verified_django_12050` (django/django#12050)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.04676628
  - Top files: `django/contrib/postgres/search.py`, `django/contrib/postgres/lookups.py`, `django/db/backends/base/introspection.py`, `tests/queries/test_query.py`, `django/db/models/query_utils.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.07039177
  - Top files: `tests/queries/tests.py`, `tests/queries/test_query.py`, `tests/queries/test_qs_combinators.py`, `tests/queries/test_q.py`, `tests/queries/test_iterator.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.06220051
  - Top files: `django/contrib/postgres/search.py`, `django/contrib/postgres/lookups.py`, `django/db/backends/base/introspection.py`, `tests/queries/tests.py`, `tests/queries/test_query.py`

### `verified_django_12143` (django/django#12143)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.07933408
  - Detail: ModuleNotFoundError: No module named '{%' ====================================================================== ERROR: get_admin_log (unittest.loader._FailedTest) ----------------
  - Top files: `django/utils/regex_helper.py`, `django/contrib/gis/geometry.py`, `tests/template_tests/filter_tests/test_stringformat.py`, `django/utils/http.py`, `django/contrib/contenttypes/forms.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.19275694
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `django/contrib/admin/options.py`, `django/contrib/gis/admin/options.py`, `docs/topics/forms/formsets.txt`, `django/contrib/admin/forms.py`, `docs/internals/contributing/writing-code/working-with-git.txt`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.19956995
  - Detail: ModuleNotFoundError: No module named '{%' ====================================================================== ERROR: get_admin_log (unittest.loader._FailedTest) ----------------
  - Top files: `django/utils/regex_helper.py`, `django/contrib/gis/geometry.py`, `tests/template_tests/filter_tests/test_stringformat.py`, `django/contrib/admin/options.py`, `django/contrib/gis/admin/options.py`

### `verified_django_12262` (django/django#12262)

Passed by: `V`
- **Vector:** PASS; iterations=1; calls=3; cost=0.04390174
  - Top files: `tests/template_tests/templatetags/bad_tag.py`, `tests/template_tests/syntax_tests/test_with.py`, `django/template/defaulttags.py`, `tests/template_tests/syntax_tests/test_include.py`, `tests/template_tests/syntax_tests/test_autoescape.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.03183183
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `docs/howto/custom-template-tags.txt`, `tests/admin_scripts/custom_templates/project_template/ticket-18091-non-ascii-template.txt`, `tests/pagination/custom.py`, `tests/auth_tests/common-passwords-custom.txt`, `docs/ref/template-response.txt`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.10960148
  - Detail: RuntimeError: Search/Replace blocks produced no staged changes
  - Top files: `tests/template_tests/templatetags/bad_tag.py`, `tests/template_tests/syntax_tests/test_with.py`, `django/template/defaulttags.py`, `docs/howto/custom-template-tags.txt`, `tests/admin_scripts/custom_templates/project_template/ticket-18091-non-ascii-template.txt`

### `verified_django_12273` (django/django#12273)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.13932358
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/force_insert_update/tests.py`, `tests/serializers/models/natural.py`, `tests/model_formsets/test_uuid.py`, `tests/serializers/test_natural.py`, `tests/invalid_models_tests/test_ordinary_fields.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=6; cost=0.11938503
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `django/forms/models.py`, `docs/ref/models/class.txt`, `docs/ref/class-based-views/mixins-single-object.txt`, `docs/ref/class-based-views/mixins-multiple-object.txt`, `django/db/models/utils.py`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.13317295
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/force_insert_update/tests.py`, `tests/serializers/models/natural.py`, `tests/model_formsets/test_uuid.py`, `django/forms/models.py`, `docs/ref/models/class.txt`

### `verified_django_12308` (django/django#12308)

Passed by: `VCH`
- **Vector:** PASS; iterations=2; calls=5; cost=0.04731729
  - Top files: `django/contrib/postgres/forms/hstore.py`, `django/contrib/postgres/fields/jsonb.py`, `django/db/models/fields/json.py`, `django/contrib/postgres/forms/jsonb.py`, `tests/forms_tests/field_tests/test_jsonfield.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.03175247
  - Top files: `django/contrib/admin/utils.py`, `django/contrib/staticfiles/utils.py`, `django/contrib/sites/admin.py`, `django/contrib/redirects/admin.py`, `django/contrib/postgres/utils.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.05084503
  - Top files: `django/contrib/postgres/forms/hstore.py`, `django/contrib/postgres/fields/jsonb.py`, `django/db/models/fields/json.py`, `django/contrib/admin/utils.py`, `django/contrib/staticfiles/utils.py`

### `verified_django_12325` (django/django#12325)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.03197931
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/mutually_referential/models.py`, `tests/generic_relations_regress/models.py`, `tests/order_with_respect_to/models.py`, `tests/m2o_recursive/models.py`, `tests/string_lookup/models.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.1449567
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `django/core/exceptions.py`, `tests/ordering/models.py`, `django/urls/exceptions.py`, `django/template/exceptions.py`, `django/forms/models.py`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.05450462
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/mutually_referential/models.py`, `tests/generic_relations_regress/models.py`, `tests/order_with_respect_to/models.py`, `django/core/exceptions.py`, `tests/ordering/models.py`

### `verified_django_12406` (django/django#12406)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.03262517
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/forms_tests/widget_tests/test_nullbooleanselect.py`, `tests/forms_tests/field_tests/test_nullbooleanfield.py`, `tests/model_fields/tests.py`, `tests/forms_tests/widget_tests/test_checkboxinput.py`, `tests/forms_tests/widget_tests/test_fileinput.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.06890895
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `docs/howto/custom-model-fields.txt`, `tests/serializers/models/data.py`, `docs/ref/models/meta.txt`, `docs/ref/models/fields.txt`, `docs/ref/models/class.txt`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.06605455
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/forms_tests/widget_tests/test_nullbooleanselect.py`, `tests/forms_tests/field_tests/test_nullbooleanfield.py`, `tests/model_fields/tests.py`, `docs/howto/custom-model-fields.txt`, `tests/serializers/models/data.py`

### `verified_django_12663` (django/django#12663)

Passed by: `VH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.04279449
  - Top files: `tests/queries/models.py`, `tests/nested_foreign_keys/tests.py`, `tests/queries/test_explain.py`, `tests/model_meta/tests.py`, `tests/custom_managers/tests.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.25672753
  - Detail: Traceback (most recent call last):
  - Top files: `django/db/models/sql/query.py`, `django/db/models/fields/__init__.py`, `django/db/models/query.py`, `django/db/models/lookups.py`, `django/contrib/gis/db/models/sql/__init__.py`
- **Hybrid:** PASS; iterations=3; calls=7; cost=0.18186313
  - Top files: `tests/queries/models.py`, `tests/nested_foreign_keys/tests.py`, `tests/queries/test_explain.py`, `django/db/models/sql/query.py`, `django/db/models/fields/__init__.py`

### `verified_django_12741` (django/django#12741)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.01821396
  - Top files: `django/core/management/commands/sqlflush.py`, `django/contrib/gis/db/backends/utils.py`, `django/core/management/commands/sqlsequencereset.py`, `django/core/management/sql.py`, `django/contrib/gis/db/backends/postgis/base.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.00265301
  - Top files: `docs/internals/contributing/bugs-and-features.txt`, `tests/template_tests/templates/template_tests/using.html`, `tests/template_tests/recursive_templates/fs/self.html`, `tests/template_tests/jinja2/template_tests/using.html`, `tests/syndication_tests/templates/syndication/description.html`
- **Hybrid:** PASS; iterations=3; calls=7; cost=0.01954074
  - Top files: `django/core/management/commands/sqlflush.py`, `django/contrib/gis/db/backends/utils.py`, `django/core/management/commands/sqlsequencereset.py`, `docs/internals/contributing/bugs-and-features.txt`, `tests/template_tests/templates/template_tests/using.html`

### `verified_django_12754` (django/django#12754)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.01373562
  - Detail: ModuleNotFoundError: No module named 'Test' ====================================================================== ERROR: change (unittest.loader._FailedTest) ---------------------
  - Top files: `tests/migration_test_data_persistence/migrations/0001_initial.py`, `tests/migrations/test_migrations_non_atomic/0001_initial.py`, `tests/migrations/migrations_test_apps/conflicting_app_with_dependencies/migrations/0002_second.py`, `tests/migrations/models.py`, `tests/migrations2/test_migrations_2_first/0002_second.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.16582364
  - Detail: ModuleNotFoundError: No module named 'Test' ====================================================================== ERROR: change (unittest.loader._FailedTest) ---------------------
  - Top files: `django/core/exceptions.py`, `django/db/models/base.py`, `django/core/serializers/base.py`, `django/core/management/base.py`, `django/core/handlers/base.py`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.14185414
  - Detail: ModuleNotFoundError: No module named 'Test' ====================================================================== ERROR: change (unittest.loader._FailedTest) ---------------------
  - Top files: `tests/migration_test_data_persistence/migrations/0001_initial.py`, `tests/migrations/test_migrations_non_atomic/0001_initial.py`, `tests/migrations/migrations_test_apps/conflicting_app_with_dependencies/migrations/0002_second.py`, `django/core/exceptions.py`, `django/db/models/base.py`

### `verified_django_13023` (django/django#13023)

Passed by: `CH`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.05933161
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/forms_tests/field_tests/test_decimalfield.py`, `tests/model_fields/test_decimalfield.py`, `django/contrib/gis/db/models/functions.py`, `tests/db_functions/math/test_ceil.py`, `tests/db_functions/math/test_asin.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.07424535
  - Top files: `docs/howto/custom-model-fields.txt`, `django/forms/fields.py`, `django/core/handlers/exception.py`, `django/contrib/contenttypes/fields.py`, `django/db/models/fields/reverse_related.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.05245949
  - Top files: `tests/forms_tests/field_tests/test_decimalfield.py`, `tests/model_fields/test_decimalfield.py`, `django/contrib/gis/db/models/functions.py`, `docs/howto/custom-model-fields.txt`, `django/forms/fields.py`

### `verified_django_13028` (django/django#13028)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.06716613
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/constraints/models.py`, `tests/queries/models.py`, `tests/postgres_tests/models.py`, `django/contrib/admin/exceptions.py`, `django/contrib/admin/filters.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.17315838
  - Detail: ModuleNotFoundError: No module named '#13227' ====================================================================== ERROR: If (unittest.loader._FailedTest) -----------------------
  - Top files: `django/db/models/sql/query.py`, `django/db/models/query.py`, `django/db/models/manager.py`, `django/utils/timezone.py`, `tests/serializers/models/data.py`
- **Hybrid:** TEST_FAILED; iterations=3; calls=6; cost=0.15345848
  - Detail: ModuleNotFoundError: No module named '#13227' ====================================================================== ERROR: If (unittest.loader._FailedTest) -----------------------
  - Top files: `tests/constraints/models.py`, `tests/queries/models.py`, `tests/postgres_tests/models.py`, `django/db/models/sql/query.py`, `django/db/models/query.py`

### `verified_django_13089` (django/django#13089)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.05682247
  - Detail: ModuleNotFoundError: No module named 'If' ====================================================================== ERROR: None (unittest.loader._FailedTest) -------------------------
  - Top files: `django/core/management/commands/createcachetable.py`, `django/db/utils.py`, `django/core/cache/backends/memcached.py`, `django/templatetags/cache.py`, `django/contrib/sessions/backends/cached_db.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.07924751
  - Detail: ModuleNotFoundError: No module named 'If' ====================================================================== ERROR: None (unittest.loader._FailedTest) -------------------------
  - Top files: `django/core/handlers/base.py`, `django/core/cache/backends/db.py`, `django/utils/decorators.py`, `django/utils/cache.py`, `django/template/response.py`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.06696742
  - Detail: ModuleNotFoundError: No module named 'If' ====================================================================== ERROR: None (unittest.loader._FailedTest) -------------------------
  - Top files: `django/core/management/commands/createcachetable.py`, `django/db/utils.py`, `django/core/cache/backends/memcached.py`, `django/core/handlers/base.py`, `django/core/cache/backends/db.py`

### `verified_django_13121` (django/django#13121)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.08099733
  - Top files: `django/db/backends/sqlite3/operations.py`, `tests/expressions/tests.py`, `django/db/backends/oracle/operations.py`, `django/db/models/expressions.py`, `tests/queries/tests.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.08275898
  - Top files: `django/db/models/sql/compiler.py`, `django/db/backends/base/operations.py`, `django/db/models/query.py`, `tests/expressions/tests.py`, `django/db/models/sql/query.py`
- **Hybrid:** PASS; iterations=2; calls=5; cost=0.14764435
  - Top files: `django/db/backends/sqlite3/operations.py`, `tests/expressions/tests.py`, `django/db/backends/oracle/operations.py`, `django/db/models/sql/compiler.py`, `django/db/backends/base/operations.py`

### `verified_django_13128` (django/django#13128)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.04867608
  - Top files: `django/db/backends/oracle/functions.py`, `django/db/models/functions/datetime.py`, `tests/forms_tests/field_tests/test_durationfield.py`, `tests/forms_tests/tests/test_input_formats.py`, `django/utils/dateparse.py`
- **Context Sphere:** PASS; iterations=2; calls=5; cost=0.1208512
  - Top files: `django/core/exceptions.py`, `django/db/models/functions/datetime.py`, `django/urls/exceptions.py`, `django/template/exceptions.py`, `django/forms/models.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.03374017
  - Top files: `django/db/backends/oracle/functions.py`, `django/db/models/functions/datetime.py`, `tests/forms_tests/field_tests/test_durationfield.py`, `django/core/exceptions.py`, `django/urls/exceptions.py`

### `verified_django_13279` (django/django#13279)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.03058267
  - Top files: `tests/test_client_regress/session.py`, `tests/sessions_tests/tests.py`, `django/contrib/auth/hashers.py`, `django/contrib/sessions/exceptions.py`, `django/contrib/sessions/backends/base.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.01361152
  - Top files: `django/contrib/messages/storage/session.py`, `django/shortcuts.py`, `django/__main__.py`, `django/__init__.py`, `Django.egg-info/top_level.txt`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.03094381
  - Top files: `tests/test_client_regress/session.py`, `tests/sessions_tests/tests.py`, `django/contrib/auth/hashers.py`, `django/contrib/messages/storage/session.py`, `django/shortcuts.py`

### `verified_django_13315` (django/django#13315)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.04649947
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/null_queries/models.py`, `tests/model_fields/test_textfield.py`, `tests/order_with_respect_to/tests.py`, `tests/model_fields/tests.py`, `tests/forms_tests/field_tests/test_choicefield.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.08096418
  - Detail: ModuleNotFoundError: No module named 'Regression' ====================================================================== ERROR: for (unittest.loader._FailedTest) ------------------
  - Top files: `docs/topics/conditional-view-processing.txt`, `docs/ref/models/options.txt`, `docs/ref/class-based-views/mixins-single-object.txt`, `docs/ref/class-based-views/mixins-multiple-object.txt`, `django/db/models/options.py`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.04434686
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/null_queries/models.py`, `tests/model_fields/test_textfield.py`, `tests/order_with_respect_to/tests.py`, `docs/topics/conditional-view-processing.txt`, `docs/ref/models/options.txt`

### `verified_django_13344` (django/django#13344)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.05970185
  - Detail: ModuleNotFoundError: No module named 'Nonexistent' ====================================================================== ERROR: keys (unittest.loader._FailedTest) ----------------
  - Top files: `tests/middleware_exceptions/middleware.py`, `tests/urlpatterns_reverse/middleware.py`, `tests/utils_tests/test_decorators.py`, `django/core/handlers/base.py`, `tests/middleware/test_security.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.09145032
  - Detail: ModuleNotFoundError: No module named 'Nonexistent' ====================================================================== ERROR: keys (unittest.loader._FailedTest) ----------------
  - Top files: `django/core/handlers/asgi.py`, `django/middleware/security.py`, `django/middleware/http.py`, `django/http/response.py`, `django/http/request.py`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.05394025
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/middleware_exceptions/middleware.py`, `tests/urlpatterns_reverse/middleware.py`, `tests/utils_tests/test_decorators.py`, `django/core/handlers/asgi.py`, `django/middleware/security.py`

### `verified_django_13449` (django/django#13449)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.06568892
  - Top files: `django/db/models/expressions.py`, `django/db/backends/base/operations.py`, `django/contrib/gis/db/models/functions.py`, `django/db/models/functions/mixins.py`, `tests/expressions/tests.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.07810389
  - Top files: `django/db/models/sql/query.py`, `django/db/models/sql/compiler.py`, `django/db/backends/sqlite3/base.py`, `django/template/backends/utils.py`, `django/template/backends/base.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.08270989
  - Top files: `django/db/models/expressions.py`, `django/db/backends/base/operations.py`, `django/contrib/gis/db/models/functions.py`, `django/db/models/sql/query.py`, `django/db/models/sql/compiler.py`

### `verified_django_13513` (django/django#13513)

Passed by: `CH`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.05648788
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/queries/test_deprecation.py`, `django/views/generic/base.py`, `django/conf/global_settings.py`, `django/template/context_processors.py`, `tests/urlpatterns_reverse/urls_error_handlers_callables.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.03929214
  - Top files: `django/views/debug.py`, `django/views/decorators/debug.py`, `django/views/static.py`, `django/views/i18n.py`, `django/views/defaults.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.04384078
  - Top files: `tests/queries/test_deprecation.py`, `django/views/generic/base.py`, `django/conf/global_settings.py`, `django/views/debug.py`, `django/views/decorators/debug.py`

### `verified_django_13516` (django/django#13516)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.04718532
  - Top files: `django/db/migrations/executor.py`, `django/core/management/commands/migrate.py`, `django/db/migrations/loader.py`, `django/core/management/sql.py`, `django/core/management/commands/makemigrations.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.04439895
  - Top files: `django/core/management/commands/migrate.py`, `django/core/management/commands/flush.py`, `docs/ref/migration-operations.txt`, `docs/howto/custom-management-commands.txt`, `django/db/migrations/migration.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.0462306
  - Top files: `django/db/migrations/executor.py`, `django/core/management/commands/migrate.py`, `django/db/migrations/loader.py`, `django/core/management/commands/flush.py`, `docs/ref/migration-operations.txt`

### `verified_django_13551` (django/django#13551)

Passed by: `H`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.04171437
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `django/contrib/auth/base_user.py`, `tests/auth_tests/models/with_custom_email_field.py`, `tests/auth_tests/models/invalid_models.py`, `tests/auth_tests/models/custom_user.py`, `tests/test_client_regress/models.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.11651075
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `docs/topics/email.txt`, `docs/ref/request-response.txt`, `docs/howto/custom-model-fields.txt`, `docs/howto/auth-remote-user.txt`, `django/http/request.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.03838664
  - Top files: `django/contrib/auth/base_user.py`, `tests/auth_tests/models/with_custom_email_field.py`, `tests/auth_tests/models/invalid_models.py`, `docs/topics/email.txt`, `docs/ref/request-response.txt`

### `verified_django_13569` (django/django#13569)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.05576432
  - Top files: `tests/queries/models.py`, `django/db/models/sql/compiler.py`, `tests/null_fk_ordering/models.py`, `tests/queries/test_explain.py`, `tests/ordering/models.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.06838891
  - Top files: `django/db/models/sql/where.py`, `django/db/models/sql/query.py`, `django/db/models/sql/compiler.py`, `tests/ordering/models.py`, `tests/expressions/models.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.07108943
  - Top files: `tests/queries/models.py`, `django/db/models/sql/compiler.py`, `tests/null_fk_ordering/models.py`, `django/db/models/sql/where.py`, `django/db/models/sql/query.py`

### `verified_django_13590` (django/django#13590)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.07967731
  - Top files: `django/db/models/lookups.py`, `django/db/models/query_utils.py`, `tests/model_regress/tests.py`, `tests/queries/test_query.py`, `django/db/models/sql/compiler.py`
- **Context Sphere:** PASS; iterations=2; calls=5; cost=0.12281241
  - Top files: `django/db/models/sql/query.py`, `django/db/models/query.py`, `django/db/models/lookups.py`, `django/db/models/sql/where.py`, `django/db/models/sql/subqueries.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.07758408
  - Top files: `django/db/models/lookups.py`, `django/db/models/query_utils.py`, `tests/model_regress/tests.py`, `django/db/models/sql/query.py`, `django/db/models/query.py`

### `verified_django_13786` (django/django#13786)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.03079504
  - Top files: `tests/migrations/test_optimizer.py`, `tests/migrations/test_deprecated_fields.py`, `tests/contenttypes_tests/test_operations.py`, `tests/migrations/test_fake_initial_case_insensitive/initial/0001_initial.py`, `tests/model_options/test_default_pk.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.08086793
  - Top files: `django/db/migrations/operations/models.py`, `tests/migrations/models.py`, `django/forms/models.py`, `django/db/models/options.py`, `django/contrib/sites/models.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.08306926
  - Top files: `tests/migrations/test_optimizer.py`, `tests/migrations/test_deprecated_fields.py`, `tests/contenttypes_tests/test_operations.py`, `django/db/migrations/operations/models.py`, `tests/migrations/models.py`

### `verified_django_13933` (django/django#13933)

Passed by: `VC`
- **Vector:** PASS; iterations=2; calls=5; cost=0.0243601
  - Top files: `tests/forms_tests/field_tests/test_choicefield.py`, `tests/forms_tests/field_tests/test_multiplechoicefield.py`, `tests/forms_tests/field_tests/test_typedmultiplechoicefield.py`, `tests/forms_tests/field_tests/test_typedchoicefield.py`, `tests/model_fields/tests.py`
- **Context Sphere:** PASS; iterations=3; calls=7; cost=0.10381558
  - Top files: `tests/validation/tests.py`, `tests/validation/test_validators.py`, `tests/validation/test_unique.py`, `tests/validation/test_picklable.py`, `tests/validation/test_error_messages.py`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.03790329
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/forms_tests/field_tests/test_choicefield.py`, `tests/forms_tests/field_tests/test_multiplechoicefield.py`, `tests/forms_tests/field_tests/test_typedmultiplechoicefield.py`, `tests/validation/tests.py`, `tests/validation/test_validators.py`

### `verified_django_13964` (django/django#13964)

Passed by: `H`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.01983464
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/serializers/models/natural.py`, `tests/serializers/test_natural.py`, `tests/null_fk_ordering/models.py`, `tests/string_lookup/models.py`, `tests/serializers/models/multi_table.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.03297305
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/empty/models.py`, `tests/serializers/models/data.py`, `docs/ref/models/class.txt`, `docs/ref/class-based-views/mixins-single-object.txt`, `docs/ref/class-based-views/mixins-multiple-object.txt`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.01718955
  - Top files: `tests/serializers/models/natural.py`, `tests/serializers/test_natural.py`, `tests/null_fk_ordering/models.py`, `tests/empty/models.py`, `tests/serializers/models/data.py`

### `verified_django_14007` (django/django#14007)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.06486868
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/model_fields/test_autofield.py`, `tests/postgres_tests/models.py`, `django/db/models/functions/comparison.py`, `tests/field_subclassing/fields.py`, `tests/custom_pk/fields.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.0681494
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/from_db_value/models.py`, `tests/bulk_create/models.py`, `tests/backends/models.py`, `docs/ref/models/instances.txt`, `docs/ref/models/database-functions.txt`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.07669616
  - Detail: RuntimeError: Search/Replace blocks produced no staged changes
  - Top files: `tests/model_fields/test_autofield.py`, `tests/postgres_tests/models.py`, `django/db/models/functions/comparison.py`, `tests/from_db_value/models.py`, `tests/bulk_create/models.py`

### `verified_django_14017` (django/django#14017)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.09986331
  - Top files: `django/db/models/__init__.py`, `tests/get_object_or_404/models.py`, `django/db/models/sql/query.py`, `tests/queries/test_query.py`, `tests/queries/test_q.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.02409234
  - Top files: `django/db/models/query_utils.py`, `django/db/models/utils.py`, `django/db/models/expressions.py`, `tests/expressions/models.py`, `tests/empty/models.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.09858678
  - Top files: `django/db/models/__init__.py`, `tests/get_object_or_404/models.py`, `django/db/models/sql/query.py`, `django/db/models/query_utils.py`, `django/db/models/utils.py`

### `verified_django_14053` (django/django#14053)

Passed by: `V`
- **Vector:** PASS; iterations=1; calls=3; cost=0.0527921
  - Top files: `tests/staticfiles_tests/test_storage.py`, `django/http/request.py`, `tests/file_uploads/views.py`, `django/core/cache/backends/filebased.py`, `django/contrib/staticfiles/storage.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.02495249
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `django/contrib/admin/static/admin/css/base.css`, `django/contrib/admin/static/admin/css/dashboard.css`, `django/contrib/admin/static/admin/css/widgets.css`, `django/contrib/admin/static/admin/css/rtl.css`, `django/contrib/admin/static/admin/css/responsive_rtl.css`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.12539537
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/staticfiles_tests/test_storage.py`, `django/http/request.py`, `tests/file_uploads/views.py`, `django/contrib/admin/static/admin/css/base.css`, `django/contrib/admin/static/admin/css/dashboard.css`

### `verified_django_14122` (django/django#14122)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.18669294
  - Detail: ModuleNotFoundError: No module named 'By' ====================================================================== ERROR: default, (unittest.loader._FailedTest) ---------------------
  - Top files: `tests/ordering/models.py`, `tests/null_fk_ordering/models.py`, `tests/order_with_respect_to/tests.py`, `django/db/models/sql/compiler.py`, `django/db/models/fields/proxy.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.16090168
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `django/test/utils.py`, `django/test/testcases.py`, `django/test/signals.py`, `django/test/selenium.py`, `django/test/runner.py`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.12437426
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/ordering/models.py`, `tests/null_fk_ordering/models.py`, `tests/order_with_respect_to/tests.py`, `django/test/utils.py`, `django/test/testcases.py`

### `verified_django_14140` (django/django#14140)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.09595877
  - Top files: `django/db/models/__init__.py`, `tests/queries/models.py`, `django/db/models/constraints.py`, `tests/queries/test_q.py`, `django/db/backends/mysql/compiler.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.04135728
  - Top files: `django/contrib/auth/models.py`, `django/db/models/expressions.py`, `django/contrib/sites/models.py`, `django/contrib/sessions/models.py`, `django/contrib/redirects/models.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.10571471
  - Top files: `django/db/models/__init__.py`, `tests/queries/models.py`, `django/db/models/constraints.py`, `django/contrib/auth/models.py`, `django/db/models/expressions.py`

### `verified_django_14351` (django/django#14351)

Passed by: `CH`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.06681705
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `django/db/backends/mysql/compiler.py`, `django/db/backends/mysql/features.py`, `django/db/models/sql/datastructures.py`, `tests/db_functions/text/test_substr.py`, `tests/queries/test_q.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.07891332
  - Top files: `django/db/models/sql/query.py`, `django/db/backends/utils.py`, `django/db/utils.py`, `django/db/models/sql/compiler.py`, `django/test/utils.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.06329007
  - Top files: `django/db/backends/mysql/compiler.py`, `django/db/backends/mysql/features.py`, `django/db/models/sql/datastructures.py`, `django/db/models/sql/query.py`, `django/db/backends/utils.py`

### `verified_django_14580` (django/django#14580)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.03379347
  - Top files: `django/core/management/commands/makemigrations.py`, `tests/backends/base/app_unmigrated/migrations/0001_initial.py`, `tests/admin_scripts/another_app_waiting_migration/migrations/0001_initial.py`, `tests/migrations/test_migrations_no_default/0001_initial.py`, `tests/migrations/test_migrations_conflict/0002_conflicting_second.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.02935902
  - Top files: `django/db/migrations/operations/models.py`, `tests/migrations/test_fake_initial_case_insensitive/initial/0001_initial.py`, `django/db/migrations/operations/fields.py`, `django/contrib/sites/migrations/0001_initial.py`, `django/contrib/sessions/migrations/0001_initial.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.05248471
  - Top files: `django/core/management/commands/makemigrations.py`, `tests/backends/base/app_unmigrated/migrations/0001_initial.py`, `tests/admin_scripts/another_app_waiting_migration/migrations/0001_initial.py`, `django/db/migrations/operations/models.py`, `tests/migrations/test_fake_initial_case_insensitive/initial/0001_initial.py`

### `verified_django_14608` (django/django#14608)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.1307377
  - Detail: ModuleNotFoundError: No module named 'all_valid()' ====================================================================== ERROR: validates (unittest.loader._FailedTest) -----------
  - Top files: `django/forms/forms.py`, `django/forms/__init__.py`, `django/forms/formsets.py`, `tests/admin_views/forms.py`, `django/forms/models.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.09662257
  - Detail: ModuleNotFoundError: No module named 'all_valid()' ====================================================================== ERROR: validates (unittest.loader._FailedTest) -----------
  - Top files: `django/forms/formsets.py`, `docs/topics/forms/formsets.txt`, `docs/ref/forms/formsets.txt`, `django/contrib/admin/static/admin/css/forms.css`, `tests/timezones/forms.py`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.13313737
  - Detail: ModuleNotFoundError: No module named 'all_valid()' ====================================================================== ERROR: validates (unittest.loader._FailedTest) -----------
  - Top files: `django/forms/forms.py`, `django/forms/__init__.py`, `django/forms/formsets.py`, `docs/topics/forms/formsets.txt`, `docs/ref/forms/formsets.txt`

### `verified_django_14765` (django/django#14765)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.00467528
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/apps/explicit_default_config_without_apps/__init__.py`, `tests/admin_scripts/custom_templates/project_template/project_name/settings.py`, `tests/apps/explicit_default_config_mismatch_app/not_apps.py`, `tests/apps/explicit_default_config_empty_apps/__init__.py`, `tests/apps/explicit_default_config_mismatch_app/apps.py`
- **Context Sphere:** TEST_FAILED; iterations=0; calls=3; cost=0.0
  - Detail: ValueError: Available apps isn't a subset of installed apps, extra apps: empty_models ====================================================================== ERROR: test_sqlsequence
  - Top files: `django/__init__.py`, `django/views/__init__.py`, `django/utils/__init__.py`, `django/urls/__init__.py`, `django/test/__init__.py`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.01746556
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/apps/explicit_default_config_without_apps/__init__.py`, `tests/admin_scripts/custom_templates/project_template/project_name/settings.py`, `tests/apps/explicit_default_config_mismatch_app/not_apps.py`, `django/__init__.py`, `django/views/__init__.py`

### `verified_django_14771` (django/django#14771)

Passed by: `C`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.04476637
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/i18n/sampleproject/manage.py`, `django/apps/config.py`, `tests/model_options/apps.py`, `django/core/management/commands/shell.py`, `django/apps/registry.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.04317773
  - Top files: `docs/ref/models/options.txt`, `docs/ref/models/database-functions.txt`, `docs/ref/models/class.txt`, `django/db/models/options.py`, `django/contrib/syndication/apps.py`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.07107912
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/i18n/sampleproject/manage.py`, `django/apps/config.py`, `tests/model_options/apps.py`, `docs/ref/models/options.txt`, `docs/ref/models/database-functions.txt`

### `verified_django_14787` (django/django#14787)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.02932769
  - Detail: ModuleNotFoundError: No module named 'Ensures' ====================================================================== ERROR: @xframe_options_deny (unittest.loader._FailedTest) ----
  - Top files: `django/utils/decorators.py`, `django/utils/deconstruct.py`, `django/views/decorators/debug.py`, `tests/utils_tests/test_lazyobject.py`, `tests/template_tests/test_logging.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.02663345
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `docs/ref/class-based-views/mixins-single-object.txt`, `docs/ref/class-based-views/mixins-multiple-object.txt`, `tests/str/tests.py`, `tests/str/models.py`, `tests/str/__init__.py`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.03593193
  - Detail: ModuleNotFoundError: No module named 'Ensures' ====================================================================== ERROR: @xframe_options_deny (unittest.loader._FailedTest) ----
  - Top files: `django/utils/decorators.py`, `django/utils/deconstruct.py`, `django/views/decorators/debug.py`, `docs/ref/class-based-views/mixins-single-object.txt`, `docs/ref/class-based-views/mixins-multiple-object.txt`

### `verified_django_15022` (django/django#15022)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=6; cost=0.01356651
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/foreign_object/models/customers.py`, `tests/string_lookup/models.py`, `tests/distinct_on_fields/models.py`, `tests/model_options/models/default_related_name.py`, `tests/queries/models.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.31145193
  - Detail: ModuleNotFoundError: No module named '{%' ====================================================================== ERROR: get_admin_log (unittest.loader._FailedTest) ----------------
  - Top files: `django/db/models/sql/query.py`, `django/db/models/query.py`, `django/db/models/options.py`, `django/contrib/admin/options.py`, `django/contrib/admin/models.py`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.18310221
  - Detail: ModuleNotFoundError: No module named '{%' ====================================================================== ERROR: get_admin_log (unittest.loader._FailedTest) ----------------
  - Top files: `tests/foreign_object/models/customers.py`, `tests/string_lookup/models.py`, `tests/distinct_on_fields/models.py`, `django/db/models/sql/query.py`, `django/db/models/query.py`

### `verified_django_15252` (django/django#15252)

Passed by: `VH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.0457634
  - Top files: `tests/migrations/test_multidb.py`, `tests/migrations/test_loader.py`, `tests/check_framework/test_multi_db.py`, `tests/migrations/test_base.py`, `tests/migrations/test_executor.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.11669438
  - Detail: RuntimeError: Search/Replace blocks produced no staged changes
  - Top files: `django/test/runner.py`, `django/db/migrations/recorder.py`, `django/db/migrations/executor.py`, `django/db/backends/sqlite3/creation.py`, `django/db/backends/postgresql/creation.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.05238525
  - Top files: `tests/migrations/test_multidb.py`, `tests/migrations/test_loader.py`, `tests/check_framework/test_multi_db.py`, `django/test/runner.py`, `django/db/migrations/recorder.py`

### `verified_django_15278` (django/django#15278)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=0; calls=3; cost=0.0
  - Detail: ValueError: Available apps isn't a subset of installed apps, extra apps: empty_models ====================================================================== ERROR: test_sqlsequence
  - Top files: `tests/backends/sqlite/tests.py`, `django/db/backends/sqlite3/base.py`, `django/db/backends/oracle/features.py`, `tests/model_regress/tests.py`, `tests/migrations/test_state.py`
- **Context Sphere:** TEST_FAILED; iterations=0; calls=3; cost=0.0
  - Detail: ValueError: Available apps isn't a subset of installed apps, extra apps: empty_models ====================================================================== ERROR: test_sqlsequence
  - Top files: `django/db/backends/sqlite3/base.py`, `django/contrib/gis/db/backends/base/models.py`, `django/template/backends/utils.py`, `django/template/backends/base.py`, `django/db/models/utils.py`
- **Hybrid:** TEST_FAILED; iterations=0; calls=3; cost=0.0
  - Detail: ValueError: Available apps isn't a subset of installed apps, extra apps: empty_models ====================================================================== ERROR: test_sqlsequence
  - Top files: `tests/backends/sqlite/tests.py`, `django/db/backends/sqlite3/base.py`, `django/db/backends/oracle/features.py`, `django/contrib/gis/db/backends/base/models.py`, `django/template/backends/utils.py`

### `verified_django_15315` (django/django#15315)

Passed by: `VCH`
- **Vector:** PASS; iterations=2; calls=5; cost=0.03803835
  - Top files: `tests/raw_query/models.py`, `tests/field_deconstruction/tests.py`, `django/utils/hashable.py`, `tests/model_fields/test_uuid.py`, `django/db/models/fields/proxy.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.0460255
  - Top files: `django/forms/models.py`, `docs/ref/models/class.txt`, `docs/ref/class-based-views/mixins-single-object.txt`, `docs/ref/class-based-views/mixins-multiple-object.txt`, `django/db/models/utils.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.05957173
  - Top files: `tests/raw_query/models.py`, `tests/field_deconstruction/tests.py`, `django/utils/hashable.py`, `django/forms/models.py`, `docs/ref/models/class.txt`

### `verified_django_15375` (django/django#15375)

Passed by: `VH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.0903665
  - Top files: `django/db/models/aggregates.py`, `tests/raw_query/models.py`, `django/db/models/__init__.py`, `django/contrib/gis/db/models/aggregates.py`, `django/contrib/postgres/aggregates/general.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.12030884
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `django/db/backends/sqlite3/base.py`, `django/db/backends/postgresql/base.py`, `django/core/mail/backends/base.py`, `django/core/cache/backends/base.py`, `django/template/backends/base.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.09999576
  - Top files: `django/db/models/aggregates.py`, `tests/raw_query/models.py`, `django/db/models/__init__.py`, `django/db/backends/sqlite3/base.py`, `django/db/backends/postgresql/base.py`

### `verified_django_15380` (django/django#15380)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.07597306
  - Top files: `django/core/management/commands/migrate.py`, `django/core/management/commands/makemigrations.py`, `django/contrib/contenttypes/management/__init__.py`, `tests/migrations/test_base.py`, `tests/migrations/test_state.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.05135904
  - Top files: `django/core/management/commands/makemigrations.py`, `django/core/management/base.py`, `django/core/management/__init__.py`, `django/db/migrations/autodetector.py`, `django/core/management/commands/__init__.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.05160814
  - Top files: `django/core/management/commands/migrate.py`, `django/core/management/commands/makemigrations.py`, `django/contrib/contenttypes/management/__init__.py`, `django/core/management/base.py`, `django/core/management/__init__.py`

### `verified_django_15467` (django/django#15467)

Passed by: `CH`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.11805227
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `django/contrib/contenttypes/forms.py`, `tests/admin_widgets/widgetadmin.py`, `django/contrib/gis/admin/options.py`, `django/forms/models.py`, `tests/model_options/apps.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.07609799
  - Top files: `django/contrib/admin/options.py`, `django/contrib/gis/admin/options.py`, `django/db/models/options.py`, `django/contrib/sites/admin.py`, `django/contrib/redirects/admin.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.06042585
  - Top files: `django/contrib/contenttypes/forms.py`, `tests/admin_widgets/widgetadmin.py`, `django/contrib/gis/admin/options.py`, `django/contrib/admin/options.py`, `django/db/models/options.py`

### `verified_django_15554` (django/django#15554)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.24242598
  - Detail: ModuleNotFoundError: No module named \'filtered_relation()\'\n') Unfortunately, tracebacks cannot be pickled, making it impossible for the parallel test runner to handle this excep
  - Top files: `tests/queries/test_q.py`, `django/db/models/__init__.py`, `tests/defer_regress/models.py`, `tests/constraints/models.py`, `django/db/backends/mysql/features.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.21582887
  - Detail: Creating test database for alias 'default'...
  - Top files: `django/db/models/sql/query.py`, `django/db/models/query.py`, `django/db/models/sql/where.py`, `django/db/models/sql/subqueries.py`, `django/db/models/sql/datastructures.py`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.26582348
  - Detail: RuntimeError: Search/Replace blocks produced no staged changes
  - Top files: `tests/queries/test_q.py`, `django/db/models/__init__.py`, `tests/defer_regress/models.py`, `django/db/models/sql/query.py`, `django/db/models/query.py`

### `verified_django_15563` (django/django#15563)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.03315561
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/update/models.py`, `tests/model_inheritance/models.py`, `tests/queries/models.py`, `tests/serializers/models/natural.py`, `tests/select_related/models.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.19836951
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `docs/ref/class-based-views/mixins-multiple-object.txt`, `django/db/models/query.py`, `django/db/models/base.py`, `django/db/models/sql/where.py`, `django/db/models/sql/query.py`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.22549251
  - Detail: ModuleNotFoundError: No module named \'verbose_name_plural\'\n') Unfortunately, tracebacks cannot be pickled, making it impossible for the parallel test runner to handle this excep
  - Top files: `tests/update/models.py`, `tests/model_inheritance/models.py`, `tests/queries/models.py`, `docs/ref/class-based-views/mixins-multiple-object.txt`, `django/db/models/query.py`

### `verified_django_15569` (django/django#15569)

Passed by: `CH`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.1312118
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/update/tests.py`, `tests/db_functions/text/test_sha384.py`, `tests/backends/test_ddl_references.py`, `tests/queries/test_query.py`, `tests/db_functions/text/test_sha256.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.01503733
  - Top files: `django/db/models/query_utils.py`, `tests/schema/models.py`, `tests/lookup/models.py`, `tests/cache/models.py`, `tests/xor_lookups/models.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.03251958
  - Top files: `tests/update/tests.py`, `tests/db_functions/text/test_sha384.py`, `tests/backends/test_ddl_references.py`, `django/db/models/query_utils.py`, `tests/schema/models.py`

### `verified_django_15629` (django/django#15629)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.01105891
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/indexes/models.py`, `tests/serializers/models/natural.py`, `tests/null_fk_ordering/models.py`, `tests/string_lookup/models.py`, `tests/inspectdb/models.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.14193948
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `django/db/models/sql/where.py`, `tests/queries/models.py`, `docs/ref/models/class.txt`, `django/db/models/sql/subqueries.py`, `django/db/models/sql/query.py`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.07080384
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/indexes/models.py`, `tests/serializers/models/natural.py`, `tests/null_fk_ordering/models.py`, `django/db/models/sql/where.py`, `tests/queries/models.py`

### `verified_django_15695` (django/django#15695)

Passed by: `V`
- **Vector:** PASS; iterations=1; calls=3; cost=0.04375462
  - Top files: `tests/backends/test_ddl_references.py`, `tests/deprecation/tests.py`, `django/contrib/contenttypes/management/__init__.py`, `tests/migrations/test_base.py`, `django/db/migrations/operations/__init__.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.1427264
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/migrations/test_operations.py`, `tests/backends/postgresql/test_operations.py`, `tests/postgres_tests/test_operations.py`, `tests/contenttypes_tests/test_operations.py`, `django/utils/deconstruct.py`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.13510734
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/backends/test_ddl_references.py`, `tests/deprecation/tests.py`, `django/contrib/contenttypes/management/__init__.py`, `tests/migrations/test_operations.py`, `tests/backends/postgresql/test_operations.py`

### `verified_django_15731` (django/django#15731)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.06281809
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `django/contrib/admindocs/views.py`, `tests/db_functions/text/test_sha256.py`, `tests/db_functions/text/test_sha384.py`, `tests/raw_query/models.py`, `tests/db_functions/text/test_sha224.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.18006851
  - Detail: ModuleNotFoundError: No module named \'You\'\n') Unfortunately, tracebacks cannot be pickled, making it impossible for the parallel test runner to handle this exception cleanly. In
  - Top files: `django/db/models/manager.py`, `tests/bulk_create/models.py`, `django/utils/inspect.py`, `django/forms/models.py`, `tests/foreign_object/models/person.py`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.18343956
  - Detail: Creating test database for alias 'default'...
  - Top files: `django/contrib/admindocs/views.py`, `tests/db_functions/text/test_sha256.py`, `tests/db_functions/text/test_sha384.py`, `django/db/models/manager.py`, `tests/bulk_create/models.py`

### `verified_django_15814` (django/django#15814)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.19977939
  - Detail: ModuleNotFoundError: No module named \'Creating\'\n') Unfortunately, tracebacks cannot be pickled, making it impossible for the parallel test runner to handle this exception cleanl
  - Top files: `tests/queries/models.py`, `django/db/__init__.py`, `django/contrib/gis/db/models/fields.py`, `django/test/runner.py`, `tests/queries/test_query.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.18590093
  - Detail: RuntimeError: Search/Replace blocks produced no staged changes
  - Top files: `django/db/models/sql/query.py`, `django/core/management/commands/__init__.py`, `django/core/management/base.py`, `django/core/management/__init__.py`, `django/db/models/sql/__init__.py`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.21336866
  - Detail: Creating test database for alias 'default'...
  - Top files: `tests/queries/models.py`, `django/db/__init__.py`, `django/contrib/gis/db/models/fields.py`, `django/db/models/sql/query.py`, `django/core/management/commands/__init__.py`

### `verified_django_15851` (django/django#15851)

Passed by: `VCH`
- **Vector:** PASS; iterations=1; calls=3; cost=0.04090733
  - Top files: `django/db/backends/postgresql/base.py`, `django/contrib/gis/db/backends/postgis/base.py`, `tests/dbshell/test_postgresql.py`, `django/core/management/commands/dbshell.py`, `django/db/backends/postgresql/creation.py`
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.01209928
  - Top files: `tests/i18n/sampleproject/manage.py`, `tests/dbshell/tests.py`, `tests/dbshell/test_sqlite.py`, `tests/dbshell/test_postgresql.py`, `tests/dbshell/test_oracle.py`
- **Hybrid:** PASS; iterations=1; calls=3; cost=0.041692
  - Top files: `django/db/backends/postgresql/base.py`, `django/contrib/gis/db/backends/postgis/base.py`, `tests/dbshell/test_postgresql.py`, `tests/i18n/sampleproject/manage.py`, `tests/dbshell/tests.py`

### `verified_django_15930` (django/django#15930)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.02657126
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/db_functions/text/test_lower.py`, `tests/db_functions/text/test_substr.py`, `tests/db_functions/text/test_left.py`, `tests/db_functions/text/test_right.py`, `tests/db_functions/text/test_length.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.01648698
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `docs/howto/error-reporting.txt`, `docs/howto/auth-remote-user.txt`, `tests/view_tests/media/long-line.txt`, `tests/staticfiles_tests/urls/default.py`, `tests/multiple_database/fixtures/multidb.default.json`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.03750199
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/db_functions/text/test_lower.py`, `tests/db_functions/text/test_substr.py`, `tests/db_functions/text/test_left.py`, `docs/howto/error-reporting.txt`, `docs/howto/auth-remote-user.txt`

### `verified_django_15987` (django/django#15987)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.10680576
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/auth_tests/__init__.py`, `tests/fixtures_regress/tests.py`, `tests/fixtures_model_package/tests.py`, `tests/model_fields/test_filepathfield.py`, `tests/distinct_on_fields/tests.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.10149552
  - Detail: Creating test database for alias 'default'...
  - Top files: `tests/fixtures_regress/fixtures/path.containing.dots.json`, `tests/fixtures_regress/fixtures/big-fixture.json`, `docs/ref/models/instances.txt`, `tests/syndication_tests/templates/syndication/description.html`, `django/core/management/commands/loaddata.py`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.08085043
  - Detail: ModuleNotFoundError: No module named \'Natural\'\n') Unfortunately, tracebacks cannot be pickled, making it impossible for the parallel test runner to handle this exception cleanly
  - Top files: `tests/auth_tests/__init__.py`, `tests/fixtures_regress/tests.py`, `tests/fixtures_model_package/tests.py`, `tests/fixtures_regress/fixtures/path.containing.dots.json`, `tests/fixtures_regress/fixtures/big-fixture.json`

### `verified_django_16255` (django/django#16255)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.13532624
  - Detail: Traceback (most recent call last):
  - Top files: `tests/sitemaps_tests/test_http.py`, `tests/urlpatterns_reverse/views_broken.py`, `django/views/generic/base.py`, `django/contrib/sitemaps/views.py`, `django/template/engine.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.06236086
  - Detail: Traceback (most recent call last):
  - Top files: `django/core/handlers/exception.py`, `django/core/handlers/base.py`, `django/contrib/sitemaps/views.py`, `django/contrib/sitemaps/__init__.py`, `django/utils/decorators.py`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.10446123
  - Detail: Traceback (most recent call last):
  - Top files: `tests/sitemaps_tests/test_http.py`, `tests/urlpatterns_reverse/views_broken.py`, `django/views/generic/base.py`, `django/core/handlers/exception.py`, `django/core/handlers/base.py`

### `verified_django_16263` (django/django#16263)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.24702292
  - Detail: Creating test database for alias 'default'...
  - Top files: `django/db/models/sql/query.py`, `tests/queries/test_explain.py`, `django/db/models/sql/subqueries.py`, `django/db/models/query.py`, `tests/queries/models.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.24058612
  - Detail: Creating test database for alias 'default'...
  - Top files: `django/db/models/sql/query.py`, `django/db/models/query.py`, `django/core/management/sql.py`, `django/contrib/postgres/operations.py`, `django/contrib/admin/filters.py`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.24829232
  - Detail: Creating test database for alias 'default'...
  - Top files: `django/db/models/sql/query.py`, `tests/queries/test_explain.py`, `django/db/models/sql/subqueries.py`, `django/db/models/query.py`, `django/core/management/sql.py`

### `verified_django_16315` (django/django#16315)

Passed by: `VC`
- **Vector:** PASS; iterations=2; calls=5; cost=0.03522907
  - Top files: `django/db/backends/oracle/features.py`, `tests/migrations/test_fake_initial_case_insensitive/fake_initial/0001_initial.py`, `tests/postgres_tests/test_bulk_update.py`, `tests/admin_changelist/models.py`, `tests/bulk_create/tests.py`
- **Context Sphere:** PASS; iterations=3; calls=7; cost=0.04357016
  - Top files: `tests/update/models.py`, `tests/bulk_create/models.py`, `docs/howto/custom-model-fields.txt`, `tests/serializers/models/data.py`, `docs/ref/models/meta.txt`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.04224598
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `django/db/backends/oracle/features.py`, `tests/migrations/test_fake_initial_case_insensitive/fake_initial/0001_initial.py`, `tests/postgres_tests/test_bulk_update.py`, `tests/update/models.py`, `tests/bulk_create/models.py`

### `verified_django_16662` (django/django#16662)

Passed by: `-`
- **Vector:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'

- **Context Sphere:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'

- **Hybrid:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'


### `verified_django_16667` (django/django#16667)

Passed by: `-`
- **Vector:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'

- **Context Sphere:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'

- **Hybrid:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'


### `verified_django_16801` (django/django#16801)

Passed by: `-`
- **Vector:** NO_METRICS; iterations=None; calls=None; cost=None
  - Detail: Run crashed before writing metrics; known malformed generated test_cmd caused shlex ValueError: No closing quotation.
- **Context Sphere:** NO_METRICS; iterations=None; calls=None; cost=None
  - Detail: Run crashed before writing metrics; known malformed generated test_cmd caused shlex ValueError: No closing quotation.
- **Hybrid:** NO_METRICS; iterations=None; calls=None; cost=None
  - Detail: Run crashed before writing metrics; known malformed generated test_cmd caused shlex ValueError: No closing quotation.

### `verified_django_16899` (django/django#16899)

Passed by: `-`
- **Vector:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'

- **Context Sphere:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'

- **Hybrid:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'


### `verified_django_16938` (django/django#16938)

Passed by: `-`
- **Vector:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'

- **Context Sphere:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'

- **Hybrid:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'


### `verified_django_17029` (django/django#17029)

Passed by: `-`
- **Vector:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'

- **Context Sphere:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'

- **Hybrid:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'


### `verified_django_17084` (django/django#17084)

Passed by: `-`
- **Vector:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'

- **Context Sphere:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'

- **Hybrid:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'


### `verified_django_17087` (django/django#17087)

Passed by: `-`
- **Vector:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'

- **Context Sphere:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'

- **Hybrid:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: bootstrap failed for django/django: ERROR: Package 'django' requires a different Python: 3.9.6 not in '>=3.10'


### `verified_flask_5014` (pallets/flask#5014)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.14619431
  - Detail: EEE                                                                      [100%]
  - Top files: `src/flask/debughelpers.py`, `src/flask/blueprints.py`, `tests/test_apps/blueprintapp/__init__.py`, `src/flask/signals.py`, `src/flask/config.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.14156951
  - Detail: EEE                                                                      [100%]
  - Top files: `docs/blueprints.rst`, `src/flask/blueprints.py`, `tox.ini`, `pyproject.toml`, `README.rst`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.14288752
  - Detail: EEE                                                                      [100%]
  - Top files: `src/flask/debughelpers.py`, `src/flask/blueprints.py`, `tests/test_apps/blueprintapp/__init__.py`, `docs/blueprints.rst`, `tox.ini`

### `verified_requests_1142` (psf/requests#1142)

Passed by: `C`
- **Vector:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: local selector generation failed for verified_requests_1142: Traceback (most recent call last):
  File "<LOCAL_REPO_ROOT>/scripts/inference
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.02047576
  - Top files: `requests/packages/urllib3/request.py`, `requests/utils.py`, `requests/structures.py`, `requests/status_codes.py`, `requests/sessions.py`
- **Hybrid:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: local selector generation failed for verified_requests_1142: Traceback (most recent call last):
  File "<LOCAL_REPO_ROOT>/scripts/inference

### `verified_requests_1766` (psf/requests#1766)

Passed by: `C`
- **Vector:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: local selector generation failed for verified_requests_1766: No sentence-transformers model found with name sentence-transformers/all-MiniLM-L6-v2. Creating a new one
- **Context Sphere:** PASS; iterations=1; calls=3; cost=0.01119811
  - Top files: `docs/user/authentication.rst`, `requests/auth.py`, `docs/user/quickstart.rst`, `docs/user/intro.rst`, `docs/user/install.rst`
- **Hybrid:** RUNNER_ERROR; iterations=0; calls=0; cost=0.0
  - Detail: RuntimeError: local selector generation failed for verified_requests_1766: No sentence-transformers model found with name sentence-transformers/all-MiniLM-L6-v2. Creating a new one

### `verified_requests_1921` (psf/requests#1921)

Passed by: `C`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.06183468
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `requests/cookies.py`, `requests/api.py`, `requests/packages/urllib3/request.py`, `requests/auth.py`, `test_requests.py`
- **Context Sphere:** PASS; iterations=3; calls=7; cost=0.02503157
  - Top files: `docs/user/advanced.rst`, `docs/user/quickstart.rst`, `docs/user/intro.rst`, `docs/user/install.rst`, `docs/user/authentication.rst`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.03857685
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `requests/cookies.py`, `requests/api.py`, `requests/packages/urllib3/request.py`, `docs/user/advanced.rst`, `docs/user/quickstart.rst`

### `verified_pytest_10081` (pytest-dev/pytest#10081)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.17252728
  - Detail: ERROR: <LOCAL_REPO_ROOT>/outputs/benchmark_repos/pytest-dev__pytest/pyproject.toml: 'minversion' requires pytest-2.0, actual pytest-0.1.dev1+gda9a2b584'
  - Top files: `testing/test_setupplan.py`, `testing/test_unittest.py`, `testing/test_mark.py`, `testing/test_unraisableexception.py`, `testing/test_pluginmanager.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.00816603
  - Detail: RuntimeError: Search/Replace blocks produced no staged changes
  - Top files: `scripts/update-plugin-list.py`, `bench/skip.py`, `testing/plugins_integration/pytest.ini`, `testing/example_scripts/pytest.ini`, `src/pytest/__main__.py`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.14043731
  - Detail: ERROR: <LOCAL_REPO_ROOT>/outputs/benchmark_repos/pytest-dev__pytest/pyproject.toml: 'minversion' requires pytest-2.0, actual pytest-0.1.dev1+gda9a2b584'
  - Top files: `testing/test_setupplan.py`, `testing/test_unittest.py`, `testing/test_mark.py`, `scripts/update-plugin-list.py`, `bench/skip.py`

### `verified_pytest_10356` (pytest-dev/pytest#10356)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.25207128
  - Detail: RuntimeError: Search/Replace blocks produced no staged changes
  - Top files: `testing/test_mark.py`, `testing/python/integration.py`, `testing/test_monkeypatch.py`, `testing/test_skipping.py`, `testing/python/metafunc.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=5; cost=0.01481217
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `changelog/README.rst`, `README.rst`, `testing/plugins_integration/README.rst`, `testing/example_scripts/README.rst`, `doc/en/example/markers.rst`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.18751097
  - Detail: ERROR: <LOCAL_REPO_ROOT>/outputs/benchmark_repos/pytest-dev__pytest/pyproject.toml: 'minversion' requires pytest-2.0, actual pytest-0.1.dev1+g3c1534944'
  - Top files: `testing/test_mark.py`, `testing/python/integration.py`, `testing/test_monkeypatch.py`, `changelog/README.rst`, `README.rst`

### `verified_pytest_7521` (pytest-dev/pytest#7521)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.16558391
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `testing/acceptance_test.py`, `testing/test_main.py`, `testing/test_pytester.py`, `testing/code/test_excinfo.py`, `testing/test_helpconfig.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=6; cost=0.17184075
  - Detail: RuntimeError: Search/Replace blocks produced no staged changes
  - Top files: `testing/python/show_fixtures_per_test.py`, `testing/python/raises.py`, `testing/python/metafunc.py`, `testing/python/integration.py`, `testing/python/fixtures.py`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.23582602
  - Detail: ValueError: SEARCH block matched 2 times exactly; expected one unique match
  - Top files: `testing/test_capture.py`, `testing/python/approx.py`, `testing/io/test_terminalwriter.py`, `testing/python/show_fixtures_per_test.py`, `testing/python/raises.py`

### `verified_pytest_7982` (pytest-dev/pytest#7982)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.23421694
  - Detail: ImportError: cannot import name 'Testdir' from '_pytest.pytester' (<LOCAL_REPO_ROOT>/.venv/lib/python3.9/site-packages/_pytest/pytester.py) =============
  - Top files: `testing/example_scripts/collect/package_infinite_recursion/conftest.py`, `testing/acceptance_test.py`, `testing/test_pathlib.py`, `testing/test_collection.py`, `src/_pytest/tmpdir.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.27144993
  - Detail: ImportError: cannot import name 'Testdir' from '_pytest.pytester' (<LOCAL_REPO_ROOT>/.venv/lib/python3.9/site-packages/_pytest/pytester.py) =============
  - Top files: `testing/plugins_integration/pytest.ini`, `testing/example_scripts/pytest.ini`, `src/pytest/collect.py`, `src/pytest/__main__.py`, `src/pytest/__init__.py`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.16534373
  - Detail: ImportError: cannot import name 'Testdir' from '_pytest.pytester' (<LOCAL_REPO_ROOT>/.venv/lib/python3.9/site-packages/_pytest/pytester.py) =============
  - Top files: `testing/example_scripts/collect/package_infinite_recursion/conftest.py`, `testing/acceptance_test.py`, `testing/test_pathlib.py`, `testing/plugins_integration/pytest.ini`, `testing/example_scripts/pytest.ini`

### `verified_sphinx_10673` (sphinx-doc/sphinx#10673)

Passed by: `V`
- **Vector:** PASS; iterations=1; calls=3; cost=0.04168626
  - Top files: `tests/test_environment_indexentries.py`, `tests/test_search.py`, `tests/test_directive_other.py`, `sphinx/search/__init__.py`, `sphinx/environment/adapters/toctree.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.00440369
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/roots/test-build-html-theme-having-multiple-stylesheets/index.rst`, `tests/roots/test-toctree-glob/bar/index.rst`, `tests/roots/test-toctree-glob/bar/bar_4/index.rst`, `tests/roots/test-toctree-maxdepth/index.rst`, `tests/roots/test-transforms-post_transforms-missing-reference/index.rst`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.03583773
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/test_environment_indexentries.py`, `tests/test_search.py`, `tests/test_directive_other.py`, `tests/roots/test-build-html-theme-having-multiple-stylesheets/index.rst`, `tests/roots/test-toctree-glob/bar/index.rst`

### `verified_sphinx_11445` (sphinx-doc/sphinx#11445)

Passed by: `C`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.1774462
  - Detail: Traceback (most recent call last):
  - Top files: `sphinx/directives/other.py`, `sphinx/util/nodes.py`, `sphinx/parsers.py`, `tests/test_util_nodes.py`, `tests/test_domain_rst.py`
- **Context Sphere:** PASS; iterations=2; calls=5; cost=0.00289893
  - Top files: `tests/roots/test-api-set-translator/index.rst`, `tests/roots/test-toctree-domain-objects/index.rst`, `tests/roots/test-build-html-translator/index.rst`, `tests/roots/test-build-html-theme-having-multiple-stylesheets/index.rst`, `tests/roots/test-toctree/index.rst`
- **Hybrid:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.14694961
  - Detail: RuntimeError: Search/Replace blocks produced no staged changes
  - Top files: `sphinx/directives/other.py`, `sphinx/util/nodes.py`, `sphinx/parsers.py`, `tests/roots/test-api-set-translator/index.rst`, `tests/roots/test-toctree-domain-objects/index.rst`

### `verified_sphinx_7440` (sphinx-doc/sphinx#7440)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.0846197
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `sphinx/builders/qthelp.py`, `sphinx/builders/devhelp.py`, `tests/roots/test-setup/doc/conf.py`, `sphinx/builders/applehelp.py`, `sphinx/config.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=6; cost=0.01197041
  - Detail: RuntimeError: Search/Replace blocks produced no staged changes
  - Top files: `doc/glossary.rst`, `.travis.yml`, `doc/man/sphinx-quickstart.rst`, `doc/man/sphinx-build.rst`, `doc/man/sphinx-autogen.rst`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.08091659
  - Detail: ImportError: cannot import name 'environmentfilter' from 'jinja2' (<LOCAL_REPO_ROOT>/.venv/lib/python3.9/site-packages/jinja2/__init__.py) The above exce
  - Top files: `sphinx/builders/qthelp.py`, `sphinx/builders/devhelp.py`, `tests/roots/test-setup/doc/conf.py`, `doc/glossary.rst`, `.travis.yml`

### `verified_sphinx_7910` (sphinx-doc/sphinx#7910)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.18535076
  - Detail: ImportError: cannot import name 'environmentfilter' from 'jinja2' (<LOCAL_REPO_ROOT>/.venv/lib/python3.9/site-packages/jinja2/__init__.py) The above exce
  - Top files: `tests/roots/test-ext-autodoc/target/need_mocks.py`, `tests/test_ext_napoleon.py`, `tests/test_ext_napoleon_docstring.py`, `sphinx/util/compat.py`, `sphinx/builders/latex/util.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=6; cost=0.11308933
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `sphinx/environment/__init__.py`, `sphinx/environment/collectors/__init__.py`, `sphinx/environment/adapters/__init__.py`, `sphinx/__init__.py`, `doc/contents.rst`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.27770024
  - Detail: ImportError: cannot import name 'environmentfilter' from 'jinja2' (<LOCAL_REPO_ROOT>/.venv/lib/python3.9/site-packages/jinja2/__init__.py) The above exce
  - Top files: `tests/roots/test-ext-autodoc/target/need_mocks.py`, `tests/test_ext_napoleon.py`, `tests/test_ext_napoleon_docstring.py`, `sphinx/environment/__init__.py`, `sphinx/environment/collectors/__init__.py`

### `verified_sphinx_7985` (sphinx-doc/sphinx#7985)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.23850948
  - Detail: ImportError: cannot import name 'environmentfilter' from 'jinja2' (<LOCAL_REPO_ROOT>/.venv/lib/python3.9/site-packages/jinja2/__init__.py) The above exce
  - Top files: `sphinx/ext/linkcode.py`, `sphinx/builders/linkcheck.py`, `sphinx/ext/intersphinx.py`, `tests/roots/test-ext-viewcode/conf.py`, `tests/test_build_linkcheck.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.00468854
  - Detail: ImportError: cannot import name 'environmentfilter' from 'jinja2' (<LOCAL_REPO_ROOT>/.venv/lib/python3.9/site-packages/jinja2/__init__.py) The above exce
  - Top files: `tests/roots/test-nested-enumerated-list/index.rst`, `tests/roots/test-build-html-translator/index.rst`, `tests/roots/test-gettext-template/index.rst`, `tests/roots/test-ext-autosummary-template/index.rst`, `doc/usage/index.rst`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.18614687
  - Detail: ImportError: cannot import name 'environmentfilter' from 'jinja2' (<LOCAL_REPO_ROOT>/.venv/lib/python3.9/site-packages/jinja2/__init__.py) The above exce
  - Top files: `sphinx/ext/linkcode.py`, `sphinx/builders/linkcheck.py`, `sphinx/ext/intersphinx.py`, `tests/roots/test-nested-enumerated-list/index.rst`, `tests/roots/test-build-html-translator/index.rst`

### `verified_sphinx_8265` (sphinx-doc/sphinx#8265)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.22022508
  - Detail: ERROR: not found: <LOCAL_REPO_ROOT>/outputs/benchmark_repos/sphinx-doc__sphinx/tests/test_pycode_ast.py::test_unparse[a (no match in any of [<Module test
  - Top files: `tests/test_templating.py`, `tests/test_docutilsconf.py`, `tests/test_theming.py`, `tests/test_build_changes.py`, `tests/test_build_html.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.24045558
  - Detail: ImportError: cannot import name 'environmentfilter' from 'jinja2' (<LOCAL_REPO_ROOT>/.venv/lib/python3.9/site-packages/jinja2/__init__.py) The above exce
  - Top files: `sphinx/ext/napoleon/docstring.py`, `sphinx/ext/autodoc/typehints.py`, `sphinx/ext/autodoc/type_comment.py`, `sphinx/ext/autodoc/mock.py`, `sphinx/ext/autodoc/importer.py`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.22051649
  - Detail: ImportError: cannot import name 'environmentfilter' from 'jinja2' (<LOCAL_REPO_ROOT>/.venv/lib/python3.9/site-packages/jinja2/__init__.py) The above exce
  - Top files: `tests/test_templating.py`, `tests/test_docutilsconf.py`, `tests/test_theming.py`, `sphinx/ext/napoleon/docstring.py`, `sphinx/ext/autodoc/typehints.py`

### `verified_sphinx_8593` (sphinx-doc/sphinx#8593)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.19540214
  - Detail: ImportError: cannot import name 'environmentfilter' from 'jinja2' (<LOCAL_REPO_ROOT>/.venv/lib/python3.9/site-packages/jinja2/__init__.py) The above exce
  - Top files: `tests/test_ext_autodoc_configs.py`, `tests/test_ext_autodoc.py`, `tests/test_ext_autodoc_autodata.py`, `tests/test_ext_autodoc_autoclass.py`, `tests/test_ext_autodoc_autofunction.py`
- **Context Sphere:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.00468145
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `tests/roots/test-ext-doctest-with-autodoc/index.rst`, `tests/roots/test-ext-autosectionlabel-prefix-document/index.rst`, `tests/roots/test-ext-autodoc/index.rst`, `tests/roots/test-ext-viewcode/index.rst`, `tests/roots/test-ext-viewcode-find/index.rst`
- **Hybrid:** TEST_FAILED; iterations=3; calls=7; cost=0.19014522
  - Detail: ImportError: cannot import name 'environmentfilter' from 'jinja2' (<LOCAL_REPO_ROOT>/.venv/lib/python3.9/site-packages/jinja2/__init__.py) The above exce
  - Top files: `tests/test_ext_autodoc_configs.py`, `tests/test_ext_autodoc.py`, `tests/test_ext_autodoc_autodata.py`, `tests/roots/test-ext-doctest-with-autodoc/index.rst`, `tests/roots/test-ext-autosectionlabel-prefix-document/index.rst`

### `verified_sphinx_8721` (sphinx-doc/sphinx#8721)

Passed by: `-`
- **Vector:** PATCH_APPLY_FAILED; iterations=3; calls=7; cost=0.1614976
  - Detail: ValueError: SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks
  - Top files: `sphinx/builders/epub3.py`, `tests/roots/test-ext-viewcode-find/conf.py`, `tests/test_ext_viewcode.py`, `sphinx/builders/_epub_base.py`, `doc/conf.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.19764862
  - Detail: ImportError: cannot import name 'environmentfilter' from 'jinja2' (<LOCAL_REPO_ROOT>/.venv/lib/python3.9/site-packages/jinja2/__init__.py) The above exce
  - Top files: `sphinx/ext/viewcode.py`, `sphinx/themes/epub/layout.html`, `sphinx/themes/epub/epub-cover.html`, `sphinx/ext/autosummary/templates/autosummary/module.rst`, `Sphinx.egg-info/top_level.txt`
- **Hybrid:** NO_VERIFY; iterations=0; calls=0; cost=0.0
  - Detail: Traceback (most recent call last):
  - Top files: `sphinx/builders/epub3.py`, `tests/roots/test-ext-viewcode-find/conf.py`, `tests/test_ext_viewcode.py`, `sphinx/ext/viewcode.py`, `sphinx/themes/epub/layout.html`

### `verified_sphinx_9258` (sphinx-doc/sphinx#9258)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.08345565
  - Detail: .EE                                                                      [100%]
  - Top files: `tests/roots/test-ext-autosummary-filename-map/autosummary_dummy_module.py`, `tests/roots/test-ext-autosummary/autosummary_dummy_module.py`, `tests/roots/test-ext-autodoc/target/classes.py`, `tests/test_util_typing.py`, `tests/roots/test-ext-autodoc/target/pep604.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.26187183
  - Detail: .EE                                                                      [100%]
  - Top files: `sphinx/writers/text.py`, `sphinx/writers/html.py`, `sphinx/testing/restructuredtext.py`, `sphinx/builders/text.py`, `doc/_templates/indexsidebar.html`
- **Hybrid:** NO_VERIFY; iterations=0; calls=0; cost=0.0
  - Detail: Traceback (most recent call last):
  - Top files: `tests/roots/test-ext-autosummary-filename-map/autosummary_dummy_module.py`, `tests/roots/test-ext-autosummary/autosummary_dummy_module.py`, `tests/roots/test-ext-autodoc/target/classes.py`, `sphinx/writers/text.py`, `sphinx/writers/html.py`

### `verified_sphinx_9367` (sphinx-doc/sphinx#9367)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.04402874
  - Detail: ERROR: not found: <LOCAL_REPO_ROOT>/outputs/benchmark_repos/sphinx-doc__sphinx/tests/test_pycode_ast.py::test_unparse[a (no match in any of [<Module test
  - Top files: `sphinx/pycode/__init__.py`, `tests/test_transforms_post_transforms_code.py`, `sphinx/pycode/ast.py`, `tests/test_util.py`, `tests/test_directive_patch.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.01900015
  - Detail: ERROR: not found: <LOCAL_REPO_ROOT>/outputs/benchmark_repos/sphinx-doc__sphinx/tests/test_pycode_ast.py::test_unparse[a (no match in any of [<Module test
  - Top files: `tests/test_pycode_ast.py`, `doc/man/sphinx-quickstart.rst`, `doc/man/sphinx-build.rst`, `doc/man/sphinx-autogen.rst`, `doc/man/sphinx-apidoc.rst`
- **Hybrid:** NO_VERIFY; iterations=0; calls=0; cost=0.0
  - Detail: Traceback (most recent call last):
  - Top files: `sphinx/pycode/__init__.py`, `tests/test_transforms_post_transforms_code.py`, `sphinx/pycode/ast.py`, `tests/test_pycode_ast.py`, `doc/man/sphinx-quickstart.rst`

### `verified_sphinx_9461` (sphinx-doc/sphinx#9461)

Passed by: `-`
- **Vector:** TEST_FAILED; iterations=3; calls=7; cost=0.22588408
  - Detail: .EE                                                                      [100%]
  - Top files: `tests/roots/test-ext-inheritance_diagram/example/sphinx.py`, `tests/roots/test-ext-autodoc/target/need_mocks.py`, `sphinx/ext/autodoc/deprecated.py`, `sphinx/util/typing.py`, `sphinx/util/compat.py`
- **Context Sphere:** TEST_FAILED; iterations=3; calls=7; cost=0.34407853
  - Detail: .EE                                                                      [100%]
  - Top files: `tests/roots/test-ext-autodoc/target/methods.py`, `sphinx/ext/autosummary/templates/autosummary/class.rst`, `sphinx/ext/autosummary/generate.py`, `sphinx/ext/autosummary/__init__.py`, `sphinx/ext/autodoc/typehints.py`
- **Hybrid:** NO_VERIFY; iterations=0; calls=0; cost=0.0
  - Detail: Traceback (most recent call last):
  - Top files: `tests/roots/test-ext-inheritance_diagram/example/sphinx.py`, `tests/roots/test-ext-autodoc/target/need_mocks.py`, `sphinx/ext/autodoc/deprecated.py`, `tests/roots/test-ext-autodoc/target/methods.py`, `sphinx/ext/autosummary/templates/autosummary/class.rst`

## Immediate Methodological Notes

- The 99/100 crash is not a model failure. It is a benchmark harness quoting bug in generated `test_cmd`; fix by storing test commands as argv arrays or by quoting test labels with `shlex.join()` at generation time.
- Current PASS_TO_PASS verification mostly measures whether the agent preserves existing behavior after an internally approved patch. For publication-quality SWE-bench Verified claims, add leakage-safe `test_patch` application inside `State_VERIFY` and run FAIL_TO_PASS tests without exposing test_patch to PM/Worker/Reviewer context.
- Hybrid underperformed Context Sphere in this run despite using more retrieval signal. The current merge policy is dense-first; testing Context-first or score-normalized interleaving is a natural next ablation.
- Patch application remains a major bottleneck across all methods. Improvements to Search/Replace anchoring may raise every retriever, so separate retriever quality from patch formatting quality in the paper.
