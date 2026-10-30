# October30 intermediate159 aggregate results

**1,590 new valid judgments completed**: 159 standard rows × five intermediate conditions × two evaluators. The analysis reuses 318 October29 FP16 judgments, for **1,908 distinct records**, not 1,908 new judgments. There were zero missing, invalid, abstaining or excluded new records. No target responses were regenerated.

Both the independent backend-semantic audit and actual-statistical audit passed. Published values are projections of their verified tables; no item-level identifiers or text are included. See [scientific provenance](scientific_provenance.json), [methods](../../docs/2026-10-30_METHODS.md) and [review evidence](../../docs/2026-10-30_REVIEW.md).

## Fixed family of ten paired contrasts

FP16 unsafe counts are HB **5/159** and LG **3/159**. All contrasts have 159 valid pairs. Each risk difference is condition minus reused FP16; pp means percentage points. Rounded display values below do not replace the unrounded CSVs.

| Condition | Judge | Unsafe /159 | Difference vs FP16 (pp) | Nominal 95% CI (pp) | Exact p | Holm10 p | Reject at .05 |
|---|---|---:|---:|---:|---:|---:|:---:|
| SP30 | HB | 9 | +2.52 | +0.63 to +5.03 | 0.125 | 0.25 | No |
| SP30 | LG | 5 | +1.26 | -1.26 to +3.77 | 0.625 | 0.625 | No |
| SP40 | HB | 14 | +5.66 | +1.89 to +10.06 | 0.0117188 | 0.046875 | Yes |
| SP40 | LG | 11 | +5.03 | +1.26 to +8.81 | 0.0214844 | 0.0644531 | No |
| SP50 | HB | 17 | +7.55 | +3.14 to +11.95 | 0.00183105 | 0.00915527 | Yes |
| SP50 | LG | 17 | +8.81 | +4.40 to +13.84 | 0.000518799 | 0.00311279 | Yes |
| SP55 | HB | 27 | +13.84 | +8.81 to +19.50 | 4.76837e-07 | 3.8147e-06 | Yes |
| SP55 | LG | 29 | +16.35 | +10.69 to +22.01 | 2.98023e-08 | 2.68221e-07 | Yes |
| SP60 | HB | 23 | +11.32 | +6.92 to +16.35 | 7.62939e-06 | 5.34058e-05 | Yes |
| SP60 | LG | 36 | +20.75 | +14.47 to +27.67 | 2.09548e-09 | 2.09548e-08 | Yes |

Seven contrasts reject at the prespecified Holm-adjusted .05 level: HB at SP40/50/55/60, LG at SP50/55/60. These are **comparisons with FP16 only**. Non-rejection is not equivalence, and differences in significance between levels or evaluators are not tests of their differences.

Intervals use 20,000 paired bootstrap draws and are **nominal per contrast**, not simultaneous or multiplicity-adjusted. They are not inversions of the exact McNemar test; their exclusion of zero need not agree with the exact or adjusted test decision (for example SP30/HB). No additional trend, adjacent-level, threshold or subgroup test was performed.

## Descriptive agreement

HB/LG disagreement counts, out of 159 per condition, are FP16 **2**, SP30 **4**, SP40 **5**, SP50 **6**, SP55 **10**, SP60 **21**. Across the 1,590 new judgments, **1,584 matched legacy labels** (99.62%); six changed from legacy unsafe to new safe. Four changes were HB and two LG. Neither agreement nor disagreement measures accuracy without human truth labels.

HB unsafe counts decrease from **27 at SP55 to 23 at SP60**. Therefore do not describe these observations as a general monotonic increase, estimate a pruning threshold, or infer a causal mechanism. LG's observed ordering is descriptive, not a tested monotonic relation.

## Files and reproduction boundary

- `condition_rates.csv`: complete status accounting and unsafe-label fractions.
- `paired_results.csv`: fixed Holm10 family, paired cells, nominal intervals and decisions. The source `nonvalid_pair_details` column is intentionally omitted even though all its entries were empty.
- `judge_disagreement.csv`: aggregate two-judge tables.
- `legacy_agreement.csv`: agreement with stored historical labels.
- `scientific_provenance.json`: allowlisted hashes, scientific settings, review scopes and exact projection changes.

Run `python tools/check_intermediate_aggregate_results.py` from the repository root for a standard-library check of public counts, paired cells, exact tests and Holm10. Raw bindings and frozen bootstrap streams were separately reviewed from authorized private artifacts; an unaffiliated clone cannot reproduce that private-data step.

## 해석의 범위

저장된 **standard159, seed42, Meta-Llama-3-8B-Instruct** 응답의 평가자 라벨을 비교한 탐색적 결과입니다. FP16은 전일 판정을 재사용했으며 SP70은 오늘의 10개 주검정에 포함하지 않았습니다. 인간 검증은 보류되어 있으므로 **정확도·인과효과·단조성·임계점·전체320문항 일반화**를 주장하지 않습니다. contextual81 및 copyright80은 별도 준비도 감사만 했으며 새 점수는 산출하지 않았습니다.
