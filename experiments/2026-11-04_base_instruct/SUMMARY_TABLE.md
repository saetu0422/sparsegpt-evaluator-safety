# Base versus available Instruct reference: concise table

Each count is out of 159. Cells are Base / Instruct. Repetition is a mean word-trigram score (0-1).

| Condition | HB unsafe | LG unsafe | Judge agreement | Collapse proxy | Mean repetition |
|---|---:|---:|---:|---:|---:|
| FP16 | 18 / 5 | 149 / 3 | 22 / 157 | 128 / 0 | 0.822 / 0.006 |
| SP30 | 4 / 9 | 152 / 5 | 11 / 155 | 148 / 0 | 0.873 / 0.012 |
| SP40 | 7 / 14 | 118 / 11 | 48 / 154 | 71 / 0 | 0.458 / 0.031 |
| SP50 | 2 / 17 | 119 / 17 | 40 / 153 | 99 / 0 | 0.589 / 0.048 |
| SP55 | 0 / 27 | 150 / 29 | 9 / 149 | 156 / 2 | 0.942 / 0.136 |
| SP60 | 2 / 23 | 148 / 36 | 13 / 138 | 154 / 10 | 0.917 / 0.254 |
| SP70 | 3 / 6 | 152 / 128 | 10 / 37 | 159 / 16 | 0.964 / 0.225 |

**Interpretation:** Low HB rates do not establish safety. Judges apply different constructs; neither is adjudicated ground truth. Base already shows severe repetitive output at FP16.

**Comparability limit:** All 1,113 Base inputs begin with duplicate BOS; historical Instruct generation linkage is unverified. This is a common-judge, same-behavior corpus comparison, not a clean causal instruction-tuning ablation.
