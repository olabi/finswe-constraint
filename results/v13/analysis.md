valid runs: 18

| condition | runs | tasks | seeds | resolve rate | 95% CI (task bootstrap) |
|---|---|---|---|---|---|
| A_know | 3 | 1 | 3 | 33.3% | 33.3% – 33.3% |
| A_prompt | 3 | 1 | 3 | 33.3% | 33.3% – 33.3% |
| A_retry | 3 | 1 | 3 | 66.7% | 66.7% – 66.7% |
| B_generic | 3 | 1 | 3 | 66.7% | 66.7% – 66.7% |
| C_domain | 3 | 1 | 3 | 100.0% | 100.0% – 100.0% |
| C_know | 3 | 1 | 3 | 66.7% | 66.7% – 66.7% |

noise floor (min readable delta): 84.3% (pooled seed sd 52.7%, 3 seeds)
  A_know: seed rates [0.0, 0.0, 1.0], tasks flipping across seeds 1
  A_prompt: seed rates [1.0, 0.0, 0.0], tasks flipping across seeds 1
  A_retry: seed rates [0.0, 1.0, 1.0], tasks flipping across seeds 1
  B_generic: seed rates [0.0, 1.0, 1.0], tasks flipping across seeds 1
  C_domain: seed rates [1.0, 1.0, 1.0], tasks flipping across seeds 0
  C_know: seed rates [1.0, 0.0, 1.0], tasks flipping across seeds 1

| contrast | role | pairs | diff | 95% CI | X-only / Y-only | placebo p | Holm p | verdict |
|---|---|---|---|---|---|---|---|---|
| C_know vs A_know | PRIMARY | 3 | +33.3% | +33.3% – +33.3% | 1 / 0 | 0.497 | – | below noise floor |
| C_domain vs B_generic | secondary | 3 | +33.3% | +33.3% – +33.3% | 1 / 0 | 0.497 | 1.000 | below noise floor |
| C_domain vs A_retry | secondary | 3 | +33.3% | +33.3% – +33.3% | 1 / 0 | 0.497 | 1.000 | below noise floor |
| B_generic vs A_retry | secondary | 3 | +0.0% | +0.0% – +0.0% | 0 / 0 | 1.000 | 1.000 | below noise floor |
| A_know vs A_prompt | secondary | 3 | +0.0% | +0.0% – +0.0% | 1 / 1 | 0.744 | 1.000 | below noise floor |
| A_retry vs A_prompt | secondary | 3 | +33.3% | +33.3% – +33.3% | 2 / 1 | 0.488 | 1.000 | below noise floor |