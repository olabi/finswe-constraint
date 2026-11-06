valid runs: 126

| condition | runs | tasks | seeds | resolve rate | 95% CI (task bootstrap) |
|---|---|---|---|---|---|
| A_enforce | 63 | 21 | 3 | 60.3% | 42.9% – 76.2% |
| C_enforce | 63 | 21 | 3 | 74.6% | 58.7% – 87.3% |

noise floor (min readable delta): 13.9% (pooled seed sd 8.7%, 3 seeds)
  A_enforce: seed rates [0.667, 0.524, 0.619], tasks flipping across seeds 7
  C_enforce: seed rates [0.667, 0.857, 0.714], tasks flipping across seeds 7

| contrast | role | pairs | diff | 95% CI | X-only / Y-only | placebo p | Holm p | verdict |
|---|---|---|---|---|---|---|---|---|
| C_know vs A_know | PRIMARY | 0 | – | – | – | – | – | not run |
| C_domain vs B_generic | secondary | 0 | – | – | – | – | – | not run |
| C_domain vs A_retry | secondary | 0 | – | – | – | – | – | not run |
| B_generic vs A_retry | secondary | 0 | – | – | – | – | – | not run |
| A_know vs A_prompt | secondary | 0 | – | – | – | – | – | not run |
| A_retry vs A_prompt | secondary | 0 | – | – | – | – | – | not run |