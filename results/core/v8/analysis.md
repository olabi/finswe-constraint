valid runs: 120

| condition | runs | tasks | seeds | resolve rate | 95% CI (task bootstrap) |
|---|---|---|---|---|---|
| A_know | 20 | 20 | 1 | 65.0% | 45.0% – 85.0% |
| A_prompt | 20 | 20 | 1 | 65.0% | 45.0% – 85.0% |
| A_retry | 20 | 20 | 1 | 65.0% | 45.0% – 85.0% |
| B_generic | 20 | 20 | 1 | 75.0% | 55.0% – 95.0% |
| C_domain | 20 | 20 | 1 | 75.0% | 55.0% – 90.0% |
| C_know | 20 | 20 | 1 | 75.0% | 55.0% – 95.0% |

noise floor (min readable delta): n/a (single seed)

| contrast | role | pairs | diff | 95% CI | X-only / Y-only | placebo p | Holm p | verdict |
|---|---|---|---|---|---|---|---|---|
| C_know vs A_know | PRIMARY | 20 | +10.0% | -10.0% – +30.0% | 3 / 1 | 0.311 | – | no noise floor yet (need ≥ 2 seeds) — descriptive only |
| C_domain vs B_generic | secondary | 20 | +0.0% | -15.0% – +15.0% | 1 / 1 | 0.754 | 1.000 | no noise floor yet (need ≥ 2 seeds) — descriptive only |
| C_domain vs A_retry | secondary | 20 | +10.0% | +0.0% – +25.0% | 2 / 0 | 0.243 | 1.000 | no noise floor yet (need ≥ 2 seeds) — descriptive only |
| B_generic vs A_retry | secondary | 20 | +10.0% | +0.0% – +25.0% | 2 / 0 | 0.248 | 1.000 | no noise floor yet (need ≥ 2 seeds) — descriptive only |
| A_know vs A_prompt | secondary | 20 | +0.0% | -15.0% – +15.0% | 1 / 1 | 0.742 | 1.000 | no noise floor yet (need ≥ 2 seeds) — descriptive only |
| A_retry vs A_prompt | secondary | 20 | +0.0% | -15.0% – +15.0% | 1 / 1 | 0.753 | 1.000 | no noise floor yet (need ≥ 2 seeds) — descriptive only |