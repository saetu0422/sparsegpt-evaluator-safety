# Base versus available Instruct reference

Public, aggregate-only figures for a saved-corpus comparison of seven conditions, with 159 shared behaviors per condition. Prepared 2026-11-04.

## Comparability clarification (2026-11-04)

**Pruning calibration selection and target-generation execution have not been established as matched.** These results describe the saved corpora and must not be treated as an identical-condition comparison or an estimate of instruction-tuning effects. This clarification does not change the reported counts, rates or paired-test calculations.

## Main findings

- Base judge agreement is 5.7-30.2% across conditions. Across the seven repeated measurements, 956 responses are LG-unsafe/HB-not-unsafe versus four in the reverse direction. These are not 1,113 independent behaviors.
- Base output is strongly repetitive before pruning: mean word-trigram repetition is 0.822 at FP16, and 128/159 responses trigger the heuristic collapse proxy. At SP70, the values are 0.964 and 159/159. The Instruct reference values are 0.006 and 0/159 at FP16, and 0.225 and 16/159 at SP70.
- With exact two-sided McNemar tests and Holm correction over 14 condition-by-judge comparisons, LG labels Base unsafe more often at every condition. HB is higher for Base at FP16 and lower at SP50/SP55/SP60. HB differences at SP30/SP40/SP70 do not survive correction.
- Pruning calibration and target generation are not established as matched. The available v2 pruning sources use a different calibration selection path from Base01; their linkage to the compared historical checkpoints is incomplete. Base generation uses a rewritten runner, not original02 unchanged. All 1,113 Base inputs begin with duplicate beginning-of-sequence (BOS) tokens. None of these observations establishes a cause of the outcome differences.

## Deliverables

- `base_instruct_comparison.pdf`: three-page, vector-text comparison.
- `figures/figure1_judge_rates.{png,pdf,svg}`: per-judge unsafe rates, using the same 0-100% scale.
- `figures/figure2_disagreement_quality.{png,pdf,svg}`: joint judge labels and common word-based quality metrics.
- `figures/figure3_summary_table.{png,pdf,svg}`: concise counts, paired-test interpretation, and comparability boundary.
- `SUMMARY_TABLE.md` and `summary_table.csv`: short readable table and full-precision long-form data.
- `data/aggregate_metrics.json`: public aggregate input; no response-level records.
- `render_figures.py`: reproducible rendering and numeric consistency checks.
- `verify_bundle.py` and `MANIFEST.json`: integrity and public-content checks.

## Reproduce

Use Python 3.11 or later:

```bash
python -m pip install -r requirements.txt
python verify_bundle.py
python render_figures.py
```

The script validates denominators, joint-label marginal counts, count-to-rate differences, all 14 exact McNemar p-values from discordant-pair counts, and their Holm adjustments before rendering. No network, credentials, model weights, raw prompts, generated responses, or original judge outputs are needed. The default output directory is the script's directory; `--input` and `--out` can override it.

**Reproduction scope:** these files reproduce the public tables and figures from the supplied aggregate data. They do not reproduce model generation, label adjudication, record-level pairing, source-hash validation, or the original raw-data analysis. The supplied paired bootstrap intervals are retained in the aggregate input for traceability but are not plotted; they are descriptive, not simultaneous intervals.

## Provenance and comparability

The upstream comparison binds 159 canonical shared behaviors across seven conditions, producing 1,113 response pairs and 2,226 paired judge labels. The Instruct reference uses original Oct 29 FP16/SP70 and Oct 30 SP30-SP60 rejudgments, not legacy labels or a new November replay. The upstream analysis reports that all reference labels and response hashes matched the original judged records, and that all 1,113 reference texts and word-based metrics were reconstructed from the corresponding saved seed-42 generation. Its error list was empty. The SHA-256 of that upstream aggregate comparison JSON is recorded in `data/aggregate_metrics.json`; the original non-public artifacts are not included or linked.

The upstream protocol comparison reports matching **rejudgment** model/revision/tokenizer identities, templates, active decoding settings, parser hash, package versions, and intended token policies. Hardware differs, and the new adapter is not byte-identical to the historical pipeline. Matching the compared rejudgment protocol does not establish matching pruning or target generation.

**Pruning calibration provenance.** Multiple candidate historical pruning implementations are available, including non-v2 SP30/SP40 sources. No executed-source hash binds one of these candidates to each compared historical checkpoint. Archived Instruct SP30/SP40/SP50 metadata names the v2 pruning route, whose source uses shuffled streaming C4 training data. The Base 01 route samples random documents/windows from the first C4 training shard. This is a substantive source/metadata provenance mismatch. **Checkpoint-specific linkage differs:** the archived SP30/SP40 folders have v2 suffixes, but the corresponding saved-response `model_dir` fields name non-v2 folders. SP50 names a v2 folder in both places, which is path agreement rather than checkpoint-hash or executed-code proof. Thus the archived v2 route must not be attributed to the historical SP30/SP40 response runs as a verified fact. No per-checkpoint executed-source hash or calibration-token record establishes exactly which samples produced each historical checkpoint; the metadata/source difference is not proof that the actual historical samples differed. Do not extend the SP30/SP40/SP50 metadata finding to other conditions without evidence.

**Target-generation implementation.** Base generation used a rewritten runner rather than a byte-identical execution of original02. It selects the standard159 subset before batching, whereas original02 selects all 320 non-multimodal behaviors. Both code paths specify batch size 8: 320 versus 159 describes input selection and resulting batch composition, not batch size. These source paths do not hold batch composition constant; historical executed input batches are not independently recorded. The Base runner explicitly supplies a recovered chat template, adds EOS override IDs [128001, 128009], and uses a different device-placement path. The original02 source gets its chat template from the loaded tokenizer and leaves EOS resolution to the loaded generation configuration. A difference in provision or call arguments is not proof of different effective template bytes or EOS IDs in a historical run.

**Pad/EOS and execution linkage.** Both code paths assign padding through tokenizer EOS settings, while the Base generation call explicitly overrides EOS stopping IDs. Historical effective pad/EOS equality is not established by the available run linkage; neither a numerical pad/EOS mismatch nor identical effective values is assumed here. Base uses historical-chat formatting with special tokens enabled, and all 1,113 active Base input sequences start with duplicate BOS. The exact historical Instruct prompt/tokenizer/runtime/checkpoint-to-output linkage remains unverified. The observed differences cannot isolate instruction tuning, calibration selection, generation implementation or any individual configuration as their cause.

HB uses a response right-clip of 512 tokens before a whole-prompt left-clip at 2,048 tokens. LG uses the full serialized input within its cap. In the upstream Base QA, response clipping changed 155, 154, 88, 99, 156, 156 and 159 strings respectively across FP16 through SP70, while no whole HB prompt was left-truncated and LG was not truncated. Different judge rubrics and response windows remain relevant, but these observations do not identify causes of disagreement.

This is a **common-judge, same-behavior corpus comparison**, not a clean single-factor causal instruction-tuning ablation, historical replay proof, multi-seed estimate, or general safety evaluation. Neither judge is adjudicated ground truth. HB detects successful exhibition of the specified behavior; LG classifies unsafe content under its policy. The two unsafe rates are not interchangeable measures.

## Common quality metrics

Words are whitespace-delimited and lowercased. The unique-word ratio is the number of distinct words divided by the word count. Dominance is the most frequent word's count divided by the word count. Word-trigram repetition is one minus the number of distinct contiguous word trigrams divided by all word-trigram positions; responses under six words receive a score of zero.

The collapse proxy flags a response when any of these conditions holds:

1. At least 50 words and unique-word ratio below 0.10.
2. At least 50 words and word-trigram repetition at least 0.80.
3. At least 20 words and dominance at least 0.30.

These are length-sensitive heuristics, not human-adjudicated failure. They use the same definition for both model corpora. They must not be compared directly with a token-fourgram repetition metric from a separate Base QA.

## Figure captions

**Figure 1.** Descriptive unsafe rates among the same 159 behaviors per condition. Base and the available Instruct reference are paired by behavior. Each judge panel shares a 0-100% axis. The figure reports observed rates, not an estimate of between-model or between-seed variability. Pruning calibration and target generation are not established as matched. Low HB labeling rates do not establish safe or useful output.

**Figure 2.** Upper panels partition all 159 responses by joint HB/LG label, with counts inside segments where space permits. “Not unsafe” names a classifier output, not a ground-truth safety conclusion. Lower panels compare identical word-based metrics; connecting lines show condition order, not proportionate sparsity spacing. Base repetition is already pronounced at FP16. Pruning calibration and target generation are not established as matched. No causal link from repetition or duplicate BOS to judge disagreement is established.

**Figure 3.** Summary of unsafe counts, agreement counts, collapse-proxy counts and mean word-trigram repetition. Cells are Base / Instruct. Paired-test statements use a 14-test exploratory Holm family. The interpretation box names unresolved pruning/generation equivalence; neither historical EOS/pad differences nor calibration-sample differences are asserted. SP70 HB difference is -1.887 percentage points, adjusted p=0.533691, which does not support a claim that Base is safer.

## Public-content boundary

Only aggregate metrics, methods, tables, rendering code, and figures are included. The bundle excludes individual behavior IDs, harmful prompts, generated responses, judge raw records, checkpoint/model files, credentials, account information, private links and private filesystem paths. Safe aggregate release does not make the excluded raw artifacts public or grant permission to upload them.
