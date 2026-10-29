# Research history / 연구 진행 기록

This is a sanitized synthesis of preserved stage reports and the completed run receipts. Earlier reports described the state **at that stage**, not the final state. Stage test counts below are historical, non-additive evidence and are not claims about the public release test suite.

## 1 — Input and evaluation-condition audit

The verified input archive contained 25 ZIP members and a 24-file manifest (22 raw files plus two verification reports). The canonical behavior table had 320 rows/IDs and 317 unique behavior texts. Equal texts were not merged across distinct rows.

Seven saved conditions were inspected: FP16, SP30, SP40, SP50, SP55, SP60 and SP70, using seed 42 only. The audit verified 2,240 responses and 4,480 legacy labels by row index, behavior text, semantic category, response bytes and hashes. The response files lacked native BehaviorIDs, so canonical CSV row binding is an explicit limitation.

Functional groups were standard 159, contextual 81, book/hash-check 40 and lyrics/hash-check 40. Context fields existed for the contextual rows, but evidence that they reached the historical generation prompt was missing. Copyright cases require a different hash-check path and references. The new classifier-only run therefore selected standard 159 only.

At the end of this audit, the input was intact but execution contracts were unresolved: “0 ready” meant protocol prerequisites were missing, not that the dataset was damaged. Twelve new audit tests were reported passed. Historical raw judge completions were absent, so old invalid/abstain rates and the impact of old parsing rules cannot be reconstructed.

## 2 — Preparation, then a distinct 12-judgment smoke run

CPU preparation selected three standard IDs deterministically and formed 12 tasks from two conditions and two evaluators. Twenty-three new preparation tests were reported passed. This stage initially had no actual model run and only an in-memory ledger; it must not be confused with the later implemented disk/Drive wrapper.

Subsequent work pinned model/tokenizer revisions, template hashes and tokenization policies; added immutable persistence, mount checks, stage gates and an in-memory secret launcher; and completed the 12-judgment smoke run. The original partial HB checkpoint and later complete smoke archive were preserved. The smoke was an operational check, not a representative safety estimate.

## 3 — Human pilot prepared, not conducted

A 24-ID / 48-response paired pilot with two separately ordered blinded forms was prepared. Nineteen new preparation tests were reported passed. Sampling keys and linking material remained private; neither those keys nor the forms are included here.

Two independent human ratings per response and adjudication were planned, not performed. There were zero collected ratings and zero external packet distributions. Human accuracy, inter-rater agreement and human causal/quality conclusions are unavailable.

## 4 — Saved-response quality proxies

The analysis used Unicode character counts, lexical-unit diversity/dominance, repeated trigrams, a fixed high-repetition proxy and a fixed English refusal-prefix proxy. Twenty new tests were reported passed; repeated execution reproduced 12 machine-readable output hashes.

For standard159 FP16→SP70, character-length medians were 133→68, while the **paired median change was −62**. Mean length was 250.89→297.04: the tail and the typical response must not be conflated. High repetition was 0/159→18/159; the English refusal-prefix proxy was 152/159→0/159. Zero prefix hits do not mean zero real refusals. `results/stage4_reported_proxies.csv` contains report-transcribed aggregates, not a fresh rerun of the original quality code.

Those quality intervals used 5,000 paired bootstrap draws and separate proxy-specific streams. Their two binary-proxy tests formed a separate two-test family, not the later full159 evaluator family. MMLU comparability was unverified. No MMLU score was inferred from string proxies.

## Full159 — Completed new evaluator procedure

The exploratory plan was locally frozen at **2026-10-29 07:24 UTC**, before viewing the new 636 outputs, but after prior corpus/smoke exploration. It is not preregistration.

- 159 standard IDs × 2 conditions × 2 evaluators = **636 new judgments**; no imported smoke labels and no new target generation.
- Both evaluators used fp16, deterministic generation and seed 42 on an A100 runtime. Actual revisions and environment are recorded in `results/scientific_provenance.json`.
- HB completed 318 records, then LG completed 318. All were valid binary; no invalid, abstain, excluded or missing records.
- The complete private archive had 1,975 ZIP members; all 1,974 manifest entries passed size/hash verification. Tasks were rebuilt and matched in full ordered content; record, protocol and completion-marker bindings were checked.
- The original exporter incorrectly rejected legitimate local-root/Drive mount nesting. Exporter V2 corrected actual mount/run/archive separation checks without changing inference, protocols or raw judgments. No model rerun was needed.
- GPU release was confirmed at **08:23 UTC**. Independent raw-artifact verification completed at 08:26 UTC and the statistical review at 08:29 UTC.

All 636 new labels equaled the legacy labels. This establishes agreement on these saved examples under the new procedure, **not** identical historical execution, human correctness, absence of historical parser issues, or a causal effect of pruning.

## Still open

Human validation; authentic target-generation/checkpoint provenance; contextual-generation prompt evidence; a separate authorized copyright/hash-check protocol; additional seeds or external populations; and any MMLU comparison. None is represented as completed by this release.
