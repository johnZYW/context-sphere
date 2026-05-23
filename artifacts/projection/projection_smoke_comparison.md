# Projection v3 10-Case Smoke Comparison

Source cohort: first 10 cases that passed in `outputs/ablation_100_context/`, selected into `outputs/projection_smoke_context_passed_10.json`.

## Summary

- `case_count`: `10`
- `baseline_passes`: `10`
- `projection_passes`: `6`
- `baseline_tokens_total`: `2090215`
- `projection_tokens_total`: `695158`
- `token_reduction_pct`: `66.7423`
- `baseline_input_tokens_total`: `2078983`
- `projection_input_tokens_total`: `656282`
- `input_token_reduction_pct`: `68.4325`
- `baseline_cost_total`: `0.5737`
- `projection_cost_total`: `0.2435`
- `cost_delta`: `-0.3301`
- `baseline_context_chars_total`: `8483908`
- `projection_context_chars_total`: `1450033`
- `context_char_reduction_pct`: `82.9084`

## Per Case

| Case | Baseline pass | Projection pass | Baseline tokens | Projection tokens | Token delta | Input reduction | Context char reduction | Baseline cost | Projection cost | Projection selected nodes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| verified_django_10914 | yes | yes | 82032 | 35675 | -46357 | 62.4% | 81.3% | $0.02275 | $0.01528 | pm=1, worker=11, reviewer=0 |
| verified_django_11138 | yes | no | 208989 | 179110 | -29879 | 15.7% | 69.2% | $0.05763 | $0.05745 | pm=5, worker=20, reviewer=0 |
| verified_django_11179 | yes | yes | 225654 | 18767 | -206887 | 92.5% | 92.5% | $0.06158 | $0.00733 | pm=0, worker=2, reviewer=0 |
| verified_django_11206 | yes | no | 22727 | 12564 | -10163 | 50.4% | 83.1% | $0.00710 | $0.00545 | pm=0, worker=1, reviewer=0 |
| verified_django_11211 | yes | yes | 340601 | 95192 | -245409 | 74.2% | 72.9% | $0.09299 | $0.03551 | pm=0, worker=11, reviewer=0 |
| verified_django_11239 | yes | yes | 98419 | 15916 | -82503 | 86.7% | 93.9% | $0.02773 | $0.00752 | pm=0, worker=3, reviewer=0 |
| verified_django_11276 | yes | yes | 76963 | 21485 | -55478 | 75.0% | 75.3% | $0.02170 | $0.00870 | pm=1, worker=9, reviewer=0 |
| verified_django_11299 | yes | no | 323656 | 158669 | -164987 | 52.4% | 83.4% | $0.08851 | $0.05232 | pm=0, worker=5, reviewer=0 |
| verified_django_11433 | yes | no | 552089 | 139174 | -412915 | 75.7% | 88.7% | $0.15006 | $0.04671 | pm=0, worker=7, reviewer=0 |
| verified_django_11880 | yes | yes | 159085 | 18606 | -140479 | 89.4% | 89.0% | $0.04363 | $0.00726 | pm=0, worker=3, reviewer=0 |

## Notes

- Projection preserved 6/10 verified passes on this smoke cohort, down from 10/10 because the cohort was chosen from baseline Context Sphere successes.
- Total assembled sphere characters dropped sharply, which confirms context bloat reduction at the prompt-construction layer.
- Total API tokens did not uniformly drop because failed/manual trajectories often used more iterations; token efficiency should be interpreted with pass-rate and loop-count together.
- All live calls used MiniMax fallback after DeepSeek returned insufficient balance; cost accounting reflects the fallback pricing profile recorded in `model_usage.events`.
