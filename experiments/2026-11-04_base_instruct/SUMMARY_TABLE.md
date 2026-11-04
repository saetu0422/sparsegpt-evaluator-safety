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

**Comparability limit:** Pruning calibration and target-generation execution have not been established as matched. Multiple candidate historical pruning implementations exist, including non-v2 SP30/SP40 sources, without executed-source linkage to each compared checkpoint. Archived Instruct SP30/SP40/SP50 v2 metadata points to a different calibration route from Base 01; SP30/SP40 saved-response paths do not name those v2 folders, so the historical linkage is unresolved. SP50 path agreement is not checkpoint-hash proof. Base uses a rewritten generation runner. Input selection/batch composition and pad/EOS provision are not a verified replay of original02; historical effective EOS/pad values and actual calibration samples are not asserted to differ. All 1,113 Base inputs begin with duplicate BOS. This is a descriptive saved-corpus comparison, not an identical-condition or causal instruction-tuning ablation.
