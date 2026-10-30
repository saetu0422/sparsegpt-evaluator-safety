# October30 descriptive surface-quality reconstruction

The seven-condition table covers **1,113 stored standard159 responses**, seed42. The judge-group join uses **2,226 labels**: 1,590 new October30 labels plus 636 October29 FP16/SP70 labels. FP16 appears once, not twice. Including prior SP70 here is descriptive and does **not** add SP70 to the primary Holm10 family.

This is **quality-reconstruction-v2**, a new implementation of metric definitions transcribed from the preserved stage4 report. The original implementation was not recovered. Twenty-eight previous reported aggregate values match at their disclosed precision, but that does not establish original-code equivalence. Exact refusal-prefix regex was unavailable, so no refusal proxy is reconstructed.

| Condition | Mean characters | Median characters | High-repetition count /159 | Verified HB/LG disagreement /159 |
|---|---:|---:|---:|---:|
| FP16 | 250.89 | 133 | 0 | 2 |
| SP30 | 230.02 | 122 | 0 | 4 |
| SP40 | 310.13 | 124 | 1 | 5 |
| SP50 | 528.85 | 140 | 5 | 6 |
| SP55 | 822.46 | 174 | 19 | 10 |
| SP60 | 1007.03 | 294 | 52 | 21 |
| SP70 | 297.04 | 68 | 18 | 122 |

## Definitions

- Character length: Python Unicode-codepoint length of the original response, not model-token count. No response is empty after whitespace stripping in this subset.
- Units: case-folded regex `\w+|[^\w\s]`; punctuation is a unit.
- Unique ratio: distinct units / all units; null for no units.
- Dominance: largest unit frequency / all units; null for no units.
- Repeated-trigram ratio: `(number of overlapping trigrams − number of distinct trigrams) / number of trigrams`; null for fewer than three units.
- High repetition: at least 20 units and (repeated-trigram ratio ≥ .5 or dominance ≥ .3).

These are surface-string proxies, **not** semantic quality, human-rated usefulness, refusal truth or safety accuracy. Means/medians are descriptive; no p-values, confidence intervals, trend tests, adjusted models or threshold search were added.

## Read the label columns carefully

`condition_quality.csv` retains **historical** `legacy_disagreement_n` to check the previous report: SP40=6 and SP50=5. Those are not today's rejudged disagreement counts. `quality_by_judge_agreement.csv` uses the independently verified labels: SP40=5 and SP50=6, as shown in the table above. FP16/SP70 labels date to October29; SP30/40/50/55/60 date to October30.

The group CSV has 105 rows: seven conditions × agree/disagree/nonbinary-or-missing groups × five metrics. `group_n` counts responses; `valid_n` is the metric-specific denominator. Empty groups retain rows with blank/null summary values. `small_group_warning` marks groups below ten; do not treat small-group means as stable findings. The groups are defined by evaluator agreement, not by an externally established correctness class, and associations are not causes.

## Review and reproducibility

Independent review reconstructed all 1,113 feature rows and 2,226 response/seed-bound labels, matched all 105 group rows and 28 earlier values, passed 22 synthetic tests and obtained six byte-identical outputs on a separate CPU rerun. Raw and per-ID files remain private. The two public CSVs are byte-identical to the reviewed aggregate files. See [code, tests and safe private-use instructions](../../experiments/2026-10-30_quality/README.md) and [source/public provenance](../../experiments/2026-10-30_quality/CODE_PROVENANCE.json).

길이·반복 지표와 평가자 불일치는 기술통계일 뿐입니다. 인간 검증이 없으므로 품질·안전성 정확도나 프루닝의 인과효과로 해석하지 않습니다. 과거 라벨 불일치와 새 검증 라벨 불일치를 구분해야 합니다.
