# reproduce.py report

## Checksums
- ✓ every file in results/SHA256SUMS matches

## Core experiment (Sections 5.1–5.2)

| quantity | paper | recomputed | |
|---|---|---|---|
| runs | 360 | 360 | ✓ |
| contaminated | 0 | 0 | ✓ |
| rate.A_prompt | 60.0 | 60.0 | ✓ |
| rate.A_know | 58.3 | 58.333 | ✓ |
| rate.A_retry | 63.3 | 63.333 | ✓ |
| rate.B_generic | 68.3 | 68.333 | ✓ |
| rate.C_domain | 66.7 | 66.667 | ✓ |
| rate.C_know | 73.3 | 73.333 | ✓ |
| rate_within_40.A_prompt | 60.0 | 60.0 | ✓ |
| rate_within_40.A_know | 58.3 | 58.333 | ✓ |
| rate_within_40.A_retry | 60.0 | 60.0 | ✓ |
| rate_within_40.B_generic | 63.3 | 63.333 | ✓ |
| rate_within_40.C_domain | 58.3 | 58.333 | ✓ |
| rate_within_40.C_know | 68.3 | 68.333 | ✓ |
| runs_past_40.A_prompt | 0 | 0 | ✓ |
| runs_past_40.A_know | 0 | 0 | ✓ |
| runs_past_40.A_retry | 11 | 11 | ✓ |
| runs_past_40.B_generic | 12 | 12 | ✓ |
| runs_past_40.C_domain | 19 | 19 | ✓ |
| runs_past_40.C_know | 14 | 14 | ✓ |
| resolved_after_40.A_retry | 2 | 2 | ✓ |
| resolved_after_40.B_generic | 3 | 3 | ✓ |
| resolved_after_40.C_domain | 5 | 5 | ✓ |
| resolved_after_40.C_know | 3 | 3 | ✓ |
| noise_floor_pp | 9.0 | 9.045 | ✓ |
| pooled_seed_sd_pct | 5.65 | 5.652 | ✓ |
| contrasts.C_know vs A_know.diff | 15.0 | 15.0 | ✓ |
| contrasts.C_know vs A_know.ci[0] | 3.3 | 3.333 | ✓ |
| contrasts.C_know vs A_know.ci[1] | 26.7 | 26.667 | ✓ |
| contrasts.C_know vs A_know.prereg_p | 0.015 | 0.015 | ✓ |
| contrasts.C_know vs A_know.task_p | 0.023 | 0.023 | ✓ |
| contrasts.C_know vs A_know.tasks_plus | 9 | 9 | ✓ |
| contrasts.C_know vs A_know.tasks_minus | 2 | 2 | ✓ |
| contrasts.C_domain vs B_generic.diff | -1.7 | -1.667 | ✓ |
| contrasts.C_domain vs B_generic.ci[0] | -10.0 | -10.0 | ✓ |
| contrasts.C_domain vs B_generic.ci[1] | 6.7 | 6.667 | ✓ |
| contrasts.C_domain vs B_generic.prereg_p | 0.81 | 0.812 | ✓ |
| contrasts.C_domain vs B_generic.task_p | 0.75 | 0.75 | ✓ |
| contrasts.C_domain vs A_retry.diff | 3.3 | 3.333 | ✓ |
| contrasts.C_domain vs A_retry.ci[0] | -3.3 | -3.333 | ✓ |
| contrasts.C_domain vs A_retry.ci[1] | 10.0 | 10.0 | ✓ |
| contrasts.C_domain vs A_retry.prereg_p | 0.34 | 0.341 | ✓ |
| contrasts.C_domain vs A_retry.task_p | 0.31 | 0.312 | ✓ |
| contrasts.B_generic vs A_retry.diff | 5.0 | 5.0 | ✓ |
| contrasts.B_generic vs A_retry.ci[0] | -3.3 | -3.333 | ✓ |
| contrasts.B_generic vs A_retry.ci[1] | 16.7 | 16.667 | ✓ |
| contrasts.B_generic vs A_retry.prereg_p | 0.22 | 0.224 | ✓ |
| contrasts.B_generic vs A_retry.task_p | 0.38 | 0.375 | ✓ |
| contrasts.A_know vs A_prompt.diff | -1.7 | -1.667 | ✓ |
| contrasts.A_know vs A_prompt.ci[0] | -11.7 | -11.667 | ✓ |
| contrasts.A_know vs A_prompt.ci[1] | 8.3 | 8.333 | ✓ |
| contrasts.A_know vs A_prompt.prereg_p | 0.77 | 0.765 | ✓ |
| contrasts.A_know vs A_prompt.task_p | 0.73 | 0.734 | ✓ |
| contrasts.A_retry vs A_prompt.diff | 3.3 | 3.333 | ✓ |
| contrasts.A_retry vs A_prompt.ci[0] | -5.0 | -5.0 | ✓ |
| contrasts.A_retry vs A_prompt.ci[1] | 11.7 | 11.667 | ✓ |
| contrasts.A_retry vs A_prompt.prereg_p | 0.35 | 0.353 | ✓ |
| contrasts.A_retry vs A_prompt.task_p | 0.34 | 0.344 | ✓ |
| primary_within_40.diff | 10.0 | 10.0 | ✓ |
| primary_within_40.task_p | 0.074 | 0.074 | ✓ |
| primary_within_40.tasks_plus | 7 | 7 | ✓ |
| primary_within_40.tasks_minus | 2 | 2 | ✓ |
| interaction.diff | 8.3 | 8.333 | ✓ |
| interaction.ci[0] | -5.0 | -5.0 | ✓ |
| interaction.ci[1] | 21.7 | 21.667 | ✓ |
| interaction.task_p_two_sided | 0.37 | 0.369 | ✓ |
| primary_discordant.x_only | 11 | 11 | ✓ |
| primary_discordant.y_only | 2 | 2 | ✓ |
| primary_discordant.x_only_seeds_0_1 | 8 | 8 | ✓ |
| primary_discordant.x_only_seed_2 | 3 | 3 | ✓ |
| primary_discordant.y_only_seeds_0_1 | 1 | 1 | ✓ |
| primary_discordant.y_only_seed_2 | 1 | 1 | ✓ |
| primary_x_only_past_40 | 3 | 3 | ✓ |
| seed2_counterfactual.A_retry.rescued | 0 | 0 | ✓ |
| seed2_counterfactual.A_retry.harmed | 0 | 0 | ✓ |
| seed2_counterfactual.B_generic.rescued | 1 | 1 | ✓ |
| seed2_counterfactual.B_generic.harmed | 0 | 0 | ✓ |
| seed2_counterfactual.C_domain.rescued | 2 | 2 | ✓ |
| seed2_counterfactual.C_domain.harmed | 0 | 0 | ✓ |
| seed2_counterfactual.C_know.rescued | 2 | 2 | ✓ |
| seed2_counterfactual.C_know.harmed | 0 | 0 | ✓ |
| seed2_first_submit_resolved.C_know | 13 | 13 | ✓ |
| seed2_first_submit_resolved.A_know_final | 13 | 13 | ✓ |

## FinSWE-21 (Section 5.4)

| quantity | paper | recomputed | |
|---|---|---|---|
| runs | 72 | 72 | ✓ |
| contaminated | 0 | 0 | ✓ |
| resolved.v10.A_prompt | 1 | 1 | ✓ |
| resolved.v10.A_know | 2 | 2 | ✓ |
| resolved.v10.A_retry | 0 | 0 | ✓ |
| resolved.v10.B_generic | 0 | 0 | ✓ |
| resolved.v10.C_domain | 3 | 3 | ✓ |
| resolved.v10.C_know | 3 | 3 | ✓ |
| resolved.v11.A_prompt | 2 | 2 | ✓ |
| resolved.v11.A_know | 2 | 2 | ✓ |
| resolved.v11.A_retry | 1 | 1 | ✓ |
| resolved.v11.B_generic | 1 | 1 | ✓ |
| resolved.v11.C_domain | 1 | 1 | ✓ |
| resolved.v11.C_know | 3 | 3 | ✓ |
| resolved.v12.A_prompt | 2 | 2 | ✓ |
| resolved.v12.A_know | 1 | 1 | ✓ |
| resolved.v12.A_retry | 1 | 1 | ✓ |
| resolved.v12.B_generic | 0 | 0 | ✓ |
| resolved.v12.C_domain | 2 | 2 | ✓ |
| resolved.v12.C_know | 3 | 3 | ✓ |
| resolved.v13.A_prompt | 1 | 1 | ✓ |
| resolved.v13.A_know | 1 | 1 | ✓ |
| resolved.v13.A_retry | 2 | 2 | ✓ |
| resolved.v13.B_generic | 2 | 2 | ✓ |
| resolved.v13.C_domain | 3 | 3 | ✓ |
| resolved.v13.C_know | 2 | 2 | ✓ |
| within_40.A_prompt | 6 | 6 | ✓ |
| within_40.A_know | 6 | 6 | ✓ |
| within_40.A_retry | 4 | 4 | ✓ |
| within_40.B_generic | 3 | 3 | ✓ |
| within_40.C_domain | 8 | 8 | ✓ |
| within_40.C_know | 6 | 6 | ✓ |
| rescued.A_retry | 0 | 0 | ✓ |
| rescued.B_generic | 0 | 0 | ✓ |
| rescued.C_domain | 6 | 6 | ✓ |
| rescued.C_know | 5 | 5 | ✓ |
| harmed.A_retry | 0 | 0 | ✓ |
| harmed.B_generic | 0 | 0 | ✓ |
| harmed.C_domain | 0 | 0 | ✓ |
| harmed.C_know | 0 | 0 | ✓ |
| gate_passed.B_generic | 10 | 10 | ✓ |
| gate_passed.C_domain | 9 | 9 | ✓ |
| gate_passed.C_know | 11 | 11 | ✓ |
| gate_passed_hidden_failed.B_generic | 7 | 7 | ✓ |
| gate_passed_hidden_failed.C_domain | 0 | 0 | ✓ |
| gate_passed_hidden_failed.C_know | 0 | 0 | ✓ |
| noise_floor_pp | 37.0 | 36.962 | ✓ |
| primary.diff | 41.7 | 41.667 | ✓ |
| primary.placebo_p | 0.034 | 0.034 | ✓ |
| primary.x_only | 5 | 5 | ✓ |
| primary.y_only | 0 | 0 | ✓ |
| primary_within_40.diff | 0.0 | 0.0 | ✓ |
| primary_within_40.placebo_p | 0.657 | 0.657 | ✓ |
| c_domain_vs_b_generic.diff | 50.0 | 50.0 | ✓ |
| c_domain_vs_b_generic.placebo_p | 0.019 | 0.019 | ✓ |
| c_domain_vs_b_generic.holm_p | 0.098 | 0.098 | ✓ |

## Figures
- redrawn: paper/figures/fig1–fig4 (.svg)

**ALL MATCH**
