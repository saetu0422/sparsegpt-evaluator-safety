# standard159 R1 R2 CPU reproduction

2026-11-02 exploratory reanalysis of **1,113 stored responses, 2,226 final judge labels, standard159, seven conditions, seed42**. The target evaluation contract identifies Meta-Llama-3-8B-Instruct. This is not a reproduction of the original base/320 manuscript population, and no new generation, GPU inference or human evaluation was added.

## Main results

- **R1, SP70:** directional D = LG1/HB0 has 122 responses; A = all other pairs has 37. Reverse disagreement is zero here. D has higher repetition and dominance in unadjusted exploratory tests; length p=.468280 and collapse Fisher p=.120872. Apparent AUC=.636354, pooled fivefold OOF AUC=.623837. All three slope Wald intervals include zero. Do not force V1/V2 or treat non-significance as proof of independence.
- **R2 baseline12:** FP16 versus SP30/40/50/55/60/70 × LG/HB, one Holm family of12. Both judges first meet .05 at SP50. FP16→SP70: LG+78.616pp, Holm p=1.806e-35; HB+.629pp, Holm p=1. This is not a significant HB decrease from FP16.
- **Separate adjacent10:** SP30→40→50→55→60→70 × LG/HB. SP60→70: LG+57.862pp (Holm p=6.454e-21), HB−10.692pp (Holm p=.020841). Do not mix this family with baseline12.
- **SP70 agreement:** 37/159=23.270%; κ=.018816; PABAK=−.534591. Neither is evaluator accuracy. κ-undefined bootstrap replicates: FP16 130/20000, SP30 1/20000, other conditions0.

## Reproduce on CPU

Python3.12 was used. Install the pinned numerical packages once, then the tests/replay run without GPU, network, model weights, account credentials or private text. Package installation itself requires an available package index or a preloaded wheel cache.

```bash
python -m venv .venv
# macOS/Linux
. .venv/bin/activate
# Windows PowerShell alternative: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python verify_manifest.py
python -m unittest test_analysis -v
python analyze.py --metrics results/response_metrics_labels.csv --out replay
python verify_replay.py --replay replay
```

The default uses 20,000 bootstrap replicates and deterministic seed42. Public metrics are read with round-trip float parsing. Expected CSVs are byte-identical in the documented environment; all scientific JSON sections match exactly. Input-mode/hash metadata differs because public numeric rows are not the private text input. Cross-platform numerical-library differences may require the explicit floating tolerance supported by `verify_replay.py`; such a tolerance result is not byte-identical verification. Figures are regenerated but PDF timestamps are not a scientific equality criterion.

`verify_manifest.py` verifies package inputs before replay. The package manifest intentionally does not include itself, generated replay directories, or Python cache files. Do not overwrite `results/`; place new results in a separate directory.

## Files

- `results/response_metrics_labels.csv`:1113 numeric rows with condition, canonical-derived behavior ID, response SHA256, LG/HB binary labels and whitespace-token features. **No prompt or response strings.**
- `results/results.json`: full science results, bootstrap intervals, optimizer diagnostics, fold assignments and OOF predictions.
- `results/r1_SP70_table.csv`, `r1_summaries.csv`, `r1_tests.csv`, `logistic_coefficients.csv`, `logistic_oof.csv`: R1 tables and supplemental strata.
- `results/r2_baseline12.csv`, `adjacent10.csv`, `agreement.csv`: paired cells, rates, p-values, intervals and agreement.
- `results/figure*.png` / `.pdf`, `FIGURE_CAPTIONS.md`: three statistical figures and definitions.
- `METHODS_FROZEN.md`: exploratory specification frozen before this analysis run, **not preregistration**.
- `EXECUTION_NOTES.md`: implementation boundaries and Korean findings; `test_analysis.py` contains14 CPU tests.
- `verification/`: independent final receipt, source-verification projection and hash summary. Private source paths are withheld, not silently changed into public locations.

## Scientific caveats

A is **the remainder**, not always agreement: reverse disagreement can occur at lower conditions. D is empty in both FP16 and SP30; unavailable comparisons are null, not p1 or zero-valued quality. Small D groups (SP40=1, SP50=3, SP55=6) cannot establish a reliable mechanism trend.

Whitespace R1 metrics and the recovered original collapse thresholds differ from the October30 regex-quality reconstruction. Primary repetition is zero below6 words; the preserved legacy metric begins at3. The original collapse proxy requires ≥50 words with unique ratio<.10 or repetition≥.80, or ≥20 words with dominance≥.30. Short/long flags are not collapse criteria.

The full BFGS fit and four folds returned precision-loss warnings. They passed the recorded small-score/positive-information/non-separation criteria and independent score-root validation; the raw warning flags remain visible. All bootstrap intervals are nominal and non-simultaneous. R1 tests are unadjusted exploratory comparisons. Human-ground-truth accuracy, FPR, causality, safety improvement and generalization across seeds/models are unvalidated.

The original October29 Holm2 and October30 five-condition baseline Holm10 remain historical analyses. The larger current baseline12 family changes adjusted p-values legitimately and does not retroactively alter those results. November2 control/replay labels were not added to this sample.

## Provenance and privacy boundary

Canonical IDs were assigned from verified CSV row/content correspondence, not native IDs retained in generation files. Source SHA/protocol consistency is not tokenizer inference replay or complete historical checkpoint identity proof. Numeric replay from public rows does not regenerate their features from raw text. Raw harmful prompts, target responses, raw judge outputs, model weights, credentials, private Drive identifiers and financial account data are excluded.

Existing project license status is unchanged; no new project-wide license is asserted. The upstream benchmark/model terms remain applicable to separately obtained resources.
