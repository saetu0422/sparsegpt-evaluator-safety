# sparsegpt-evaluator-safety

> **2026-10-30 완료 / Completed:** SP30/40/50/55/60의 **1,590개 신규 판정**과 별도 원시자료·통계 검증을 완료했습니다. FP16 318개는 전일 재사용이며 오늘 분석은 1,908개입니다. [오늘 결과](results/2026-10-30_intermediate159/README.md) · [품질 기술통계](results/2026-10-30_quality/README.md) · [고정 방법](docs/2026-10-30_METHODS.md) · [준비도 감사](docs/2026-10-30_READINESS.md) · [검토 근거](docs/2026-10-30_REVIEW.md)

SparseGPT 저장 응답의 안전성 평가자 차이를 조사한 **탐색적 연구 기록과 재사용 코드**입니다. This is a curated research release, not a safety benchmark leaderboard or a claim of evaluator accuracy.

## 2026-10-30 — 중간 조건 / Intermediate conditions

**All 1,590 new labels are valid binary**, with no missing, invalid, abstaining or excluded records. The same 159 standard saved responses per condition were rejudged with HB/LG; no target generation or human rating collection was added.

| Condition | HB unsafe /159 | LG unsafe /159 | HB/LG disagreement /159 |
|---|---:|---:|---:|
| FP16 (reused October29) | 5 (3.14%) | 3 (1.89%) | 2 |
| SP30 | 9 (5.66%) | 5 (3.14%) | 4 |
| SP40 | 14 (8.81%) | 11 (6.92%) | 5 |
| SP50 | 17 (10.69%) | 17 (10.69%) | 6 |
| SP55 | 27 (16.98%) | 29 (18.24%) | 10 |
| SP60 | 23 (14.47%) | 36 (22.64%) | 21 |

- **One fixed Holm10 family versus reused FP16**: seven rejections at .05 (HB SP40/50/55/60; LG SP50/55/60). Full paired cells, exact p-values, adjusted p-values and nominal bootstrap intervals are in the [dated results](results/2026-10-30_intermediate159/README.md). These are not adjacent-condition or evaluator-difference tests.
- **1,584/1,590** new labels matched legacy labels; six changed unsafe→safe. This is agreement, not accuracy. HB and LG measure different constructs.
- HB decreases from SP55 to SP60, so no general monotonicity or pruning-threshold claim is made. No causal effect or human-ground-truth conclusion is established.
- [Descriptive quality reconstruction v2](results/2026-10-30_quality/README.md) covers seven saved conditions, explicitly distinguishes legacy/new disagreement, and omits the unavailable refusal regex. It is a new implementation, not recovery of original code.
- Contextual81 and copyright80 remain **unscored** here. Their [readiness audit](docs/2026-10-30_READINESS.md) found provenance/dependency boundaries, not new outcome scores.

## 2026-10-29 — 이전 결과 / Previous dated result

**2026-10-29: standard 159개 × FP16/SP70 × HB/LG = 636개 신규 판정을 완료했습니다.** 같은 seed 42의 저장 응답을 재판정했으며 타깃 모델을 새로 실행하지 않았습니다. 대상은 **Meta-Llama-3-8B-Instruct**이지 Base 모델이 아닙니다.

| Evaluator | FP16 unsafe | SP70 unsafe | SP70 − FP16 | Nominal 95% paired-bootstrap CI | Holm-adjusted p |
|---|---:|---:|---:|---:|---:|
| HarmBench classifier (HB) | 5/159 (3.14%) | 6/159 (3.77%) | +0.63 pp | −3.14 to +5.03 pp | 1.0 |
| Llama Guard 3 (LG) | 3/159 (1.89%) | 128/159 (80.50%) | +78.62 pp | +71.70 to +84.91 pp | 3.009 × 10⁻³⁶ |

- **636/636 valid binary labels**, with no missing, invalid, abstaining or excluded records.
- New labels matched all 636 legacy labels. Agreement is **not accuracy** and does not prove the historical evaluation procedure was reproduced.
- HB/LG disagreement was **2/159 (FP16)** versus **122/159 (SP70)**. The evaluators apply different criteria; disagreement alone does not identify which is correct.
- Primary tests: paired exact two-sided McNemar, Holm correction across the fixed two-evaluator family. Intervals use 20,000 paired bootstrap draws and are **not multiplicity-adjusted**.

### 해석 제한 / What this does not establish

이 결과는 전체 320문항 결과가 아니라 **standard 159문항**의 고정 저장 응답에 관한 것입니다. contextual 81개와 copyright/hash-check 80개는 제외했습니다. ID 연결은 canonical CSV 행에서 파생했으며 원본 생성 파일의 native ID가 아닙니다. 새 평가 계약을 사용했으므로 과거 실행의 완전 재현이 아닙니다. 인간 검증은 보류되어 있습니다. **인간 기준 정확도, 프루닝의 인과적 안전성 영향, 다른 seed·모델·문항 모집단으로의 일반화는 주장하지 않습니다.**

The analysis plan was locally frozen before inspecting the new full-run judgments, but after exploring legacy data and a 12-judgment smoke test. It is **prospective exploratory work, not preregistered or confirmatory research**. The 12 smoke judgments are separate and are not counted among the 636 new judgments.

## 지금까지 한 일 / Work completed

| Stage | Completed work | Boundary |
|---|---|---|
| 1. Input audit | Verified 320 canonical rows, 2,240 saved responses across 7 conditions, and 4,480 stored labels; checked row/content bindings and hashes. | Historical target/checkpoint provenance and contextual prompt injection remain incomplete. |
| 2. Smoke preparation and execution | Prepared strict parsers and fixed evaluator contracts; subsequently completed a separate 3-ID × 2-condition × 2-evaluator = 12-judgment smoke run. | Operational validation, not a representative effect estimate. |
| 3. Human-validation pilot preparation | Prepared blinded forms for 24 paired IDs / 48 responses and separate private mapping material. | **0 human ratings, 0 external distributions**; participants not secured, validation deferred. No forms or mappings are published. |
| 4. Response-quality analysis | Measured length, repetition and English refusal-prefix proxies on saved responses. | String proxies are not semantic quality, refusal truth, MMLU performance or safety accuracy. |
| Full standard159 (October29) | Completed 636 new HB/LG judgments, private archive/backend verification, frozen-plan analysis and independent technical/statistical review. | No new target generation or human adjudication. |
| Intermediate159 (October30) | Completed 1,590 additional judgments, reused 318 FP16 labels, verified all raw records/checkpoints and reproduced the fixed Holm10 analysis. | Five new conditions; previous SP70 excluded from today’s primary family. |
| Quality/readiness (October30) | Reconstructed descriptive quality metrics and verified same-response judge groups; audited contextual generation and copyright-reference readiness. | No extra inferential quality tests, contextual/copyright scores or human truth labels. |

See [research history](docs/RESEARCH_HISTORY.md), [methods and architecture](docs/METHODS_AND_ARCHITECTURE.md), and [review status](docs/REVIEW_STATUS.md).

## Repository map

- `code/`: sanitized copies of the completed judge-only runner, storage wrapper, secret launcher, exporter and offline analyzer, with public synthetic tests.
- `results/`: preserved October29 aggregates plus dated `2026-10-30_intermediate159/` and `2026-10-30_quality/` results; no item-level IDs or text.
- `experiments/`: versioned continuation code/configuration/synthetic tests and the descriptive quality reconstruction.
- `docs/`: methods, timeline, reproducibility boundaries and review evidence.
- `third_party/`: the upstream notice for the attributed HarmBench template.

## Reproduce safely

Start with the **offline synthetic tests** and aggregate tables; see the [October29 reproduction instructions](docs/REPRODUCIBILITY.md), [October30 continuation code](experiments/2026-10-30_intermediate159/README.md), and [quality code](experiments/2026-10-30_quality/README.md). These tests do not need a GPU, a token, a Drive account or private benchmark text.

The public release deliberately **does not contain the private input ZIP, raw prompts/responses, per-record judgments, copyrighted text, model weights or cloud storage links/IDs**. Therefore an unaffiliated clone cannot reproduce the complete historical run from this repository alone. Exact archived-run verification requires the authorized private artifacts and the original archived runner bytes; the sanitized storage/config copies have new hashes. Do not weaken input or provenance checks to bypass missing files.

GPU execution is an explicit operator action with model-access requirements. No test downloads models or reads real credentials. `HF_TOKEN` is only a secret-name placeholder, never a bundled value. Do not commit generated records, tokens, private configurations or logs.

## Attribution and license status

HarmBench's standard classifier template is included under its upstream MIT notice, with the experiment's whitespace adaptation disclosed in [third-party notices](THIRD_PARTY_NOTICES.md). Model weights/tokenizer files and benchmark corpora are not redistributed. **No project-wide license has been selected in this release**; the third-party license does not license unrelated project code. Consult upstream model terms before use.
