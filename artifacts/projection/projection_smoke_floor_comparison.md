# Projection Smoke Test With Top-K Floor

## Summary

- Cases: 10
- Baseline Context Sphere pass rate: 10/10
- Projection without floor pass rate: 6/10
- Projection with min_k=2 floor pass rate: 9/10
- Pass recovery from floor: +3 cases
- Projection floor token reduction vs baseline: 69.21%
- Projection floor input-token reduction vs baseline: 71.48%
- Projection floor context-char reduction vs baseline: 76.66%
- Projection floor cost reduction vs baseline: 58.41%
- Projection floor total estimated cost: $0.23857290
- Mean selected nodes under floor: PM=2.3, Worker=7.3, Reviewer=2
- Failed floor cases: verified_django_11239

## Per-Case Comparison

| Case | Baseline pass | No-floor pass | Floor pass | Floor selected nodes (PM/W/R) | Baseline tokens | Floor tokens | Token savings | Floor cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| verified_django_10914 | Y | Y | Y | 2/11/2 | 82,032 | 22,647 | 72.4% | $0.008886 |
| verified_django_11138 | Y | - | Y | 5/20/2 | 208,989 | 152,478 | 27.0% | $0.053851 |
| verified_django_11179 | Y | Y | Y | 2/2/2 | 225,654 | 24,613 | 89.1% | $0.010367 |
| verified_django_11206 | Y | - | Y | 2/2/2 | 22,727 | 14,344 | 36.9% | $0.009567 |
| verified_django_11211 | Y | Y | Y | 2/11/2 | 340,601 | 117,254 | 65.6% | $0.038547 |
| verified_django_11239 | Y | Y | N | 2/3/2 | 98,419 | 41,319 | 58.0% | $0.018416 |
| verified_django_11276 | Y | Y | Y | 2/9/2 | 76,963 | 30,546 | 60.3% | $0.011976 |
| verified_django_11299 | Y | N | Y | 2/5/2 | 323,656 | 78,650 | 75.7% | $0.026659 |
| verified_django_11433 | Y | N | Y | 2/7/2 | 552,089 | 130,531 | 76.4% | $0.049199 |
| verified_django_11880 | Y | Y | Y | 2/3/2 | 159,085 | 31,130 | 80.4% | $0.011107 |

## Interpretation

The min_k floor fixed the reviewer-starvation failure mode: Reviewer now receives at least two projected nodes per case. The pass rate recovered from 6/10 to 9/10 while preserving a large token and cost reduction versus the full Context Sphere baseline. The remaining failure is verified_django_11239, which reached the maximum repair loop rather than failing because the Reviewer had no context.

