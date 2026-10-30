# 2026-10-30 — Contextual / copyright readiness audit

**감사 완료, 신규 평가 점수 없음.** This is an evidence/readiness audit, not a model run or a new safety/copyright result. The standard159 analysis remains separate from the 81 contextual and 80 copyright cases.

## Contextual 81: historical generation remains unverified

- All 81 contextual rows contain a nonempty `ContextString`; the selected seed42 slice across seven conditions contains 567 saved contextual responses.
- Three inspected generator-code variants pass the behavior text, but do not reference or inject `ContextString`. This supports a finding about **those inspected code variants**, not proof that every historical output used those variants.
- The preserved response schema stores row index, behavior, category, seed and response text, but not rendered generation prompts, input-token IDs, context injection evidence or the generation-code hash. All 2,240 saved behavior fields match their canonical CSV rows; that correspondence does not establish context delivery.
- A historical run manifest binding the actual code, model/checkpoint, inputs and outputs is absent. Therefore “context existed in the CSV” must not become “context was used in generation.” Adding it only at judging time would not retroactively establish correct contextual generation.

**Readiness decision:** keep these cases outside the standard159 primary analysis. Seek exact historical prompt/token and code-run provenance; if unavailable, a later explicitly authorized contextual regeneration study should be separate. No contextual outputs were generated or rejudged in this audit.

## Copyright 80: reference metadata found, execution not yet validated

The 40 book and 40 lyrics cases all use the `hash_check` path. At official HarmBench commit `8e1604d1171fe8a48d8febecd22f600e462bdcdd`, metadata exists for **80/80 matching reference files**, with a combined recorded size of **226,753,848 bytes**. The project test CSV's Git blob exactly matches the official CSV at that commit.

This is a metadata-level existence/name/size check. **No reference PKL was downloaded, deserialized, executed or scored.** Reference-content integrity, dependency compatibility and scoring behavior are not established merely by finding the files. The scoped project-folder inspection is not a claim that no copies exist anywhere in an account.

HarmBench routes these cases to reference MinHash comparisons, not its ordinary text classifier. Book and lyrics policies differ. These similarity results would not be interchangeable with LG safety labels. See the pinned [evaluation entry point](https://github.com/centerforaisafety/HarmBench/blob/8e1604d1171fe8a48d8febecd22f600e462bdcdd/evaluate_completions.py), [context/hash implementation](https://github.com/centerforaisafety/HarmBench/blob/8e1604d1171fe8a48d8febecd22f600e462bdcdd/eval_utils.py), and [reference directory](https://github.com/centerforaisafety/HarmBench/tree/8e1604d1171fe8a48d8febecd22f600e462bdcdd/data/copyright_classifier_hashes).

**Readiness decision:** a later study needs independently verified pinned reference bytes, safe handling of serialized data, pinned spaCy/datasketch/tokenizer versions, and a separately tested runner preserving the official truncation/window/threshold rules. Synthetic positive/negative and source-compatibility tests should precede scoring the 560 saved seed42 responses (80 × 7 conditions). No copyright scores were computed here.

## Privacy and interpretation

This public summary excludes private storage locations, source-file account identifiers, item IDs, original prompts/responses, reference payloads and participant material. The full private evidence remains separate. These findings clarify evaluation readiness; they do not establish human safety accuracy, a pruning-causal effect, or the missing historical execution provenance.
