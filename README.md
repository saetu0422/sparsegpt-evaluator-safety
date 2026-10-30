# sparsegpt-evaluator-safety

> **2026-10-30 완료 / Completed:** SP30/40/50/55/60의 **1,590개 신규 판정**과 별도 원시자료·통계 검증을 완료했습니다. FP16 318개는 전일 재사용이며 오늘 분석은 1,908개입니다. [오늘 결과](results/2026-10-30_intermediate159/README.md) · [품질 기술통계](results/2026-10-30_quality/README.md) · [고정 방법](docs/2026-10-30_METHODS.md) · [준비도 감사](docs/2026-10-30_READINESS.md) · [검토 근거](docs/2026-10-30_REVIEW.md)

SparseGPT 저장 응답의 안전성 평가자 차이를 조사한 **탐색적 연구 기록과 재사용 코드**입니다. This is a curated research release, not a safety benchmark leaderboard or a claim of evaluator accuracy.

## 날짜별 실험 기록 / Daily research log

날짜가 확인된 실제 수행 내용을 기록합니다. **모델 판정 실행, 코드 준비, 통계·품질 분석, 준비도 감사는 구분**하며, 계획만 있는 작업을 완료로 표시하지 않습니다. 날짜 근거가 없는 이전 준비·분석 단계는 임의로 날짜를 붙이지 않고 [단계별 연구 기록](docs/RESEARCH_HISTORY.md)에 남깁니다.

### 2026-10-30 — 중간 조건 재판정·품질 분석·준비도 감사

- **목적:** FP16/SP70 비교를 보완할 중간 조건의 평가자 라벨을 확인하고, 저장 응답의 표면적 품질 및 미평가 범주의 실행 준비도를 점검했습니다.
- **조건:** standard159, 저장 생성 seed42, SP30·SP40·SP50·SP55·SP60 × HB/LG. **1,590개 신규 판정 + 전일 FP16 318개 재사용 = 분석 1,908개**입니다. SP70은 오늘의 주검정에서 제외했습니다.
- **실제 실행·주요 결과:** 1,590개 모두 유효 이진 판정으로 완료했고 누락·invalid·abstain·excluded는 0개였습니다. FP16 대비 고정 **Holm10**에서 7개 비교가 .05 기준으로 기각되었습니다(HB SP40/50/55/60, LG SP50/55/60). 타깃 응답을 새로 생성하지 않았습니다.
- **분석·감사:** 7조건의 저장 응답 1,113개에 대해 **quality-reconstruction-v2** 기술통계와 검증된 라벨 2,226개의 동일 응답 연결을 확인했습니다. 원래 코드 복구가 아닌 새 구현이며, 원래 regex가 확인되지 않은 거절 접두어 지표는 제외했습니다. contextual81/copyright80은 준비도 감사만 했고 새 점수는 산출하지 않았습니다.
- **검증·한계:** 별도 백엔드 원시자료 검증, 실제 통계 독립 검토, 품질 재구성 독립 검토를 통과했습니다. 인간 검증은 보류입니다. HB의 SP55→SP60 감소가 있으므로 단조성·임계점·인과효과를 주장하지 않습니다.
- **자료:** [판정 결과·집계](results/2026-10-30_intermediate159/README.md) · [품질 결과](results/2026-10-30_quality/README.md) · [방법](docs/2026-10-30_METHODS.md) · [준비도 감사](docs/2026-10-30_READINESS.md) · [검증 기록](docs/2026-10-30_REVIEW.md) · [실행 코드·테스트](experiments/2026-10-30_intermediate159/README.md)

### 2026-10-29 — FP16/SP70 standard159 전체 재판정

- **목적:** 고정된 새 평가 절차로 FP16과 SP70 저장 응답의 HB/LG 라벨 차이를 비교했습니다. 과거 평가 실행의 완전 재현을 주장하는 실험은 아닙니다.
- **조건:** standard159, 저장 생성 seed42, FP16·SP70 × HB/LG, **636개 신규 판정**. 별도 12개 smoke 판정은 이 수에 포함하지 않았습니다. 타깃은 Meta-Llama-3-8B-Instruct의 저장 응답이며 Base 모델이 아닙니다.
- **실제 실행·주요 결과:** 636개 모두 유효 이진 판정으로 완료했고 누락·invalid·abstain·excluded는 0개였습니다. unsafe 라벨 수는 HB **5→6/159**, LG **3→128/159**였으며, 636개 모두 legacy 라벨과 일치했습니다. 일치는 정확도가 아닙니다.
- **분석:** 전향적으로 동결한 탐색적 계획에 따라 paired exact McNemar, 고정 **Holm2**, 20,000회 paired-bootstrap 분석을 수행했습니다. 구간은 개별 비교의 nominal 95%이며 다중비교 보정 구간이 아닙니다.
- **검증·한계:** 원시자료·저장 아카이브·통계의 독립 검증을 완료했습니다. 새 타깃 생성이나 인간 평가는 수행하지 않았고, 전체320문항·인과효과·인간 기준 정확도로 일반화하지 않습니다.
- **자료:** [판정 집계](results/condition_rates.csv) · [짝지은 비교](results/paired_results.csv) · [과학적 출처](results/scientific_provenance.json) · [연구 기록](docs/RESEARCH_HISTORY.md) · [검증 기록](docs/REVIEW_STATUS.md) · [코드·재현 방법](docs/REPRODUCIBILITY.md)

**이후 기록 형식:** 매일 GitHub 정리 시 해당 날짜의 **목적 → 조건 → 실제 실행/준비 상태 → 결과 → 검증·미완료 사항 → 공개 코드·집계 링크**를 추가합니다. 기존 날짜의 결과와 검정군은 보존하고, 새 결과나 재사용한 기준선을 명확히 구분합니다.

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
