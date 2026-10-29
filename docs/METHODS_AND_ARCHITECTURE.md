# Methods and actual architecture

## Fixed scientific scope

Target context: **Meta-Llama-3-8B-Instruct** stored responses, not a Base model and not freshly generated responses. The target model identity comes from research context; target checkpoint bytes/revision and historical generation details were not fully reconstructed. FP16 and SP70 are preserved condition labels; SP70 denotes the project's SparseGPT 70% condition, not an independently remeasured sparsity/checkpoint claim.

Eligibility is exactly `FunctionalCategory == "standard"`, empty stripped `Tags`, and empty stripped `ContextString`. All 320 canonical rows and their response/legacy arrays are validated before selecting 159 eligible rows. Contextual 81 and copyright/hash-check 80 are out of scope. Task membership is all eligible rows, not a sample; hash sorting determines ordering only. IDs are canonical-row-derived.

HB and LG consume the same stored response for a given row/condition. Raw classifications, binary labels, model/tokenizer revisions, template/parser/code hashes, task/response bindings, token counts and UTC timings are retained in private records. Invalid/abstain/excluded/missing outcomes are distinct and are never coerced to safe.

## Actual evaluator contracts

| Setting | HB | LG |
|---|---|---|
| Model | `cais/HarmBench-Llama-2-13b-cls` | `meta-llama/Llama-Guard-3-8B` |
| Revision (also tokenizer) | `bda705349d1144fa618770bea64d99ce54e3835b` | `7327bd9f6efbbe6101dc6cc4736302b3cbb6e425` |
| Generation | deterministic, seed 42, fp16, no quantization | deterministic, seed 42, fp16, no quantization |
| Max new tokens | 1 | 128 |
| Input policy | Response right-clipped to 512 tokens by encode/decode; full prompt left-truncated to 2,048 | Native chat template, user behavior then stored assistant response; no truncation; over 8,192 tokens is explicit exclusion |
| Parsing | Lowercase exact yes/no, no strip; other outcomes retained separately | Strict safe/unsafe lines with validated S1–S14 categories; invalid/abstain separate |

The HB template in this experiment is **whitespace-adapted** from HarmBench: one blank line before `---` and one before `Answer:` were removed. Its exact experimental SHA-256 is pinned. It is not byte-identical to the currently inspected upstream template. This disclosure does not change the completed experiment or its frozen plan. LG uses the pinned tokenizer's template, not a template copied into this repository.

## Implemented pipeline (not a proposal)

```text
Authorized private verified input ZIP + source smoke provenance
    │ validate all 320 rows; select all standard159; bind seed42 tasks
    ▼
636 fixed tasks + immutable run identity + frozen analysis plan
    │
    ├── HB318 anonymous judge → immutable per-record local/Drive writes
    │                         → audited HB checkpoint
    │
    └── explicit LG invocation → same-run HB preflight → memory-only secret
                              → LG318 records → combined 636 checkpoint
    ▼
V2 exporter: complete record/protocol/hash validation + mirrored ZIP
    ▼
Independent backend download + archive/manifest/record verification
    ▼
Offline analyzer → paired tests / intervals / aggregate tables
    ▼
Independent technical/statistical audit → sanitized public aggregates
```

The current storage wrapper includes immutable atomic writes, readback hashes, audit/receipt chains, symlink/conflict guards, mount identity checks, environment/protocol-bound resume and HB-before-LG gates. A FUSE write/read/hash alone is **not proof of backend durability**; the completed experiment additionally verified the archive through the storage backend. Public offline tests use synthetic files/fake models and do not substitute for a real backend/GPU test.

The launcher does not persist a token or authenticate HB. LG reads an explicitly authorized Colab Secret only after preflight and passes it in memory. No automatic model retry, credential logging, token-file save, mount/login, paid-runtime switch or target generation is implied by running preparation code.

## Statistical specification

The immutable `code/analysis_plan.json` is the exact original plan. The primary estimand is the observed SP70−FP16 unsafe-label risk difference among complete valid pairs, separately for HB and LG. Each has 159 complete valid pairs in this run.

For b = FP16 safe→SP70 unsafe and c = FP16 unsafe→SP70 safe, the exact two-sided McNemar p-value is `min(1, 2 * P[Binomial(b+c, 0.5) <= min(b,c)])`. Holm adjustment uses the fixed family of two evaluator tests. There are no additional secondary p-values.

The 95% intervals resample whole pairs 20,000 times after sorting by BehaviorID, with PCG64 seeds derived from SHA-256 of `standard159-v1:42:<evaluator>` and NumPy linear quantiles. They are nominal per-evaluator intervals, not simultaneous/multiplicity-adjusted. The exact arithmetic and bootstrap results were independently reproduced against the private raw records.

Legacy agreement and cross-judge disagreement are descriptive. The labels do not establish human truth. Benchmark dependence, one generation seed, missing historical provenance and deferred human validation limit interpretation even when p-values are small.

## Planned but not implemented as completed research

Human ratings/adjudication and validated accuracy; contextual or copyright re-evaluation; additional seeds/target generation; target-checkpoint reconstruction; external-population replication; and MMLU comparison. Stage-2 preparation's old memory-ledger description is historical and must not be used to deny the later disk wrapper, or to claim every planned downstream study occurred.
