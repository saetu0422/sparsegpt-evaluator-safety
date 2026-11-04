# sparsegpt-evaluator-safety

> **2026-11-04 Base/Instruct 비교 시각화:** 같은 159개 행동·7조건의 저장 응답을 공통 평가자 기준으로 비교한 집계 표와 그래프를 공개했습니다. [비교·해석 범위](experiments/2026-11-04_base_instruct/README.md) · [3쪽 PDF](experiments/2026-11-04_base_instruct/base_instruct_comparison.pdf)

> **2026-11-02 R1/R2 통계 종결:** 최종 standard159의 품질 층화·회귀, FP16 기준 Holm12와 별도 인접 Holm10, κ/PABAK를 재분석했습니다. [결과와 한계](docs/2026-11-02_R1_R2.md) · [텍스트 없는 CPU 재현](experiments/2026-11-02_r1_r2/README.md)

> **2026-11-02 추가 주 실험:** 1,590개 통제·재실행 판정 완료. [결과·한계](docs/2026-11-02_PRIMARY_CONTROL.md) · [재현 코드](experiments/2026-11-02_primary_control/README.md)

> **2026-11-02:** copyright80 저장 응답 560개를 CPU hash-check로 평가하고 contextual81 생성 출처를 재감사했습니다. 신규 생성·GPU·LLM 판정 없음. [결과](results/2026-11-02_copyright80/README.md) · [방법](docs/2026-11-02_METHODS.md) · [contextual 감사](experiments/2026-11-02_contextual81/README.md)

> **2026-10-30 완료 / Completed:** SP30/40/50/55/60의 **1,590개 신규 판정**과 별도 원시자료·통계 검증을 완료했습니다. FP16 318개는 전일 재사용이며 오늘 분석은 1,908개입니다. [오늘 결과](results/2026-10-30_intermediate159/README.md) · [품질 기술통계](results/2026-10-30_quality/README.md) · [고정 방법](docs/2026-10-30_METHODS.md) · [준비도 감사](docs/2026-10-30_READINESS.md) · [검토 근거](docs/2026-10-30_REVIEW.md)

SparseGPT 저장 응답의 안전성 평가자 차이를 조사한 **탐색적 연구 기록과 재사용 코드**입니다. This is a curated research release, not a safety benchmark leaderboard or a claim of evaluator accuracy.

## 날짜별 실험 기록 / Daily research log

날짜가 확인된 실제 수행 내용을 기록합니다. **모델 판정 실행, 코드 준비, 통계·품질 분석, 준비도 감사는 구분**하며, 계획만 있는 작업을 완료로 표시하지 않습니다. 날짜 근거가 없는 이전 준비·분석 단계는 임의로 날짜를 붙이지 않고 [단계별 연구 기록](docs/RESEARCH_HISTORY.md)에 남깁니다.

### 2026-11-04 — Base와 기존 Instruct 참조의 집계 비교 시각화

- **범위:** 159개 공통 행동 × 7조건의 Base/기존 Instruct 저장 응답 비교 결과를 집계 표·그래프로 정리했습니다. 이번 공개 패키지는 새 생성·판정을 실행하는 코드가 아니라 이미 계산한 집계 수치의 시각화 재현입니다.
- **주 결과:** Base의 HB/LG 일치율은 조건별 **5.7–30.2%**입니다. Base는 FP16부터 반복이 강하며, 같은 단어 기준 붕괴 대리지표는 FP16 **128/159**, SP70 **159/159**입니다. 낮은 HB unsafe 비율을 안전성 향상으로 해석하지 않습니다.
- **조건 표기:** FP16은 가지치기하지 않은 기준선이며, SPxx는 목표 sparsity xx% 조건입니다.
- **검정·한계:** 14개 조건×평가자 대응 비교에 exact McNemar·Holm 보정을 적용했습니다. 공통 평가자·동일 행동 코퍼스 비교이며, 순수한 instruction-tuning 인과 실험은 아닙니다. Base의 중복 BOS와 과거 Instruct 생성 연결 미확인 등 비교 한계를 함께 명시했습니다.
- **공개·검증:** 집계 JSON/CSV, 표, PNG/PDF/SVG, 렌더링 코드와 SHA-256 무결성 목록을 제공합니다. 수치 일관성·표/그래프 재현·공개 내용 검사를 수행했으며, 원문 prompt/response·개별 판정·비공개 링크·계정 정보는 포함하지 않습니다.
- **자료:** [결과·방법·한계](experiments/2026-11-04_base_instruct/README.md) · [요약 표](experiments/2026-11-04_base_instruct/SUMMARY_TABLE.md) · [3쪽 PDF](experiments/2026-11-04_base_instruct/base_instruct_comparison.pdf)

### 2026-11-02 — 최종 standard159 R1/R2 통계 분석

- **범위:** 기존7조건×159응답=1113개·최종라벨2226개 CPU 재분석. 원래base/320과 구분하고 오늘 통제/재실행 라벨은 중복표본으로 넣지 않았습니다. 신규생성·GPU·LLM·인간평가는 없습니다.
- **R1:** SP70 D122/A37. 반복·지배도는 보정 전 탐색적 차이가 있지만 길이와collapse Fisher는 비유의. OOF AUC=.623837이고 모든 slope95CI는0을 포함합니다. 강한V1/V2는 확정하지 않습니다.
- **R2:** 기준선Holm12 최초유의조건은 양쪽모두SP50. HB SP70 vs FP16은 비유의입니다. 별도인접Holm10에서 SP60→70은 LG+57.862pp/HB−10.692pp로 반대방향이 유지됩니다. 이전5조건baseline Holm10 기록은 보존합니다.
- **검증:** 독립429개수치대조·20개동률U·14테스트, 공개수치행의 전체과학JSON/CSV 재현 통과. BFGS precision-loss 경고·빈D그룹·κ미정의재표집을 숨기지 않습니다.
- **자료:** [요구 대응과 결과](docs/2026-11-02_R1_R2.md) · [public CPU package](experiments/2026-11-02_r1_r2/README.md). 이새폴더에는canonical-derived ID·라벨·수치행을 공개하지만 원문prompt/response·credentials·private Drive IDs는 포함하지 않습니다.

### 2026-11-02 — 추가 주 실험: 단어 순서·문맥과 평가자 불일치

- **목적·설계:** 159개 standard 유해 문맥과 중립 정원 요청 하나에서 유창/단어재배열 정원 입력을 비교했습니다. 1,272개 통제 판정 + 기존 seed42 SP70 재실행318개 = **1,590개 새 판정**이며 모두 유효 이진값입니다. 앞서 완료한 copyright80 채점·contextual81 감사는 그대로 유지합니다.
- **주 결과:** 유해 문맥에서 HB/LG 불일치가 **71/159→148/159**, S−F **+48.43%p**, 명목 대응-bootstrap95% **+40.88~+55.97%p**, exact McNemar p **1.32349×10⁻²³**입니다. 구간 전체가 +10%p 기준보다 높습니다. 사전 동결 전향적 탐색 실험이며 외부 사전등록은 아닙니다.
- **검증·해석:** 1,590개 raw parser·입력 hash·단계 archive·최종 archive를 독립 검증했습니다. SP70 재실행318개는 과거 라벨·raw 출력과 일치했습니다. 결과는 제한된 통제 입력의 민감성이지 인간 검증 FPR/전체 정확도/가지치기 인과효과가 아닙니다. HB의 중립 문맥 yes는 unsafe 판정으로 해석하지 않습니다.
- **자료:** [설계·결과·한계](docs/2026-11-02_PRIMARY_CONTROL.md) · [공개 라벨·분석 재현·테스트](experiments/2026-11-02_primary_control/README.md). 원본 동결 출력의 오해 소지가 있는 boolean은 보고용 projection에서 명시적 구간-기준 관계로 바꿨고 수치·검정은 바꾸지 않았습니다.

### 2026-11-02 — copyright80 저장 응답 채점·contextual81 출처 감사

- **목적·조건:** 공통 seed42, 7조건 × copyright80(책40·가사40) = 기존 응답560개를 공식 HarmBench MinHash 절차로 CPU 평가했습니다. 기존 standard159 결과는 변경하지 않았습니다.
- **실제 실행·결과:** 참조 근접일치는 FP16 **22/80**, SP30 **3/80**, SP40/50/55/60/70 각각 **0/80**입니다. 양성은 모두 가사 문항입니다. 새 타깃 생성·GPU·LLM API 판정은 없었습니다.
- **출처 감사:** contextual81은 공통 seed42 **567개**, 모든 저장 seed 레코드는1,053개입니다. 반복 seed 응답은 독립 표본으로 세지 않습니다. 검사 코드의 문맥 누락은 확인됐으나 과거 실행본–입력–출력 결합이 없어 실제 역사적 누락을 단정하지 않습니다. 주 분석 제외를 유지합니다.
- **검증·한계:** 독립560개 재계산과10개 통합 테스트를 통과했습니다. 공식 tokenizer512절단·strict >0.6을 유지했습니다. 근접일치 감소는 법적 판정이나 전체 안전성 향상을 뜻하지 않으며, 출력 품질 붕괴와 분리하여 해석해야 합니다. 대응 비교는 기술통계만 제시합니다.
- **자료:** [집계·짝지은 전환](results/2026-11-02_copyright80/README.md) · [방법·한계](docs/2026-11-02_METHODS.md) · [CLI·테스트](experiments/2026-11-02_copyright80/README.md) · [contextual 감사·재현](experiments/2026-11-02_contextual81/README.md)

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

**공개 수치 재현 추가:** `experiments/2026-11-02_r1_r2/`에는 응답별 canonical-derived ID, SHA256, 이진 라벨과 수치 특징을 포함합니다. 아래의 오래된 집계 전용 설명은 당시 폴더의 범위이며, 이 새 패키지의 수치 결과는 비공개 원문 없이 CPU로 재현할 수 있습니다. 원문 특징추출 및 과거 생성·판정의 전체 실행은 여전히 별개입니다.

Start with the **offline synthetic tests** and aggregate tables; see the [October29 reproduction instructions](docs/REPRODUCIBILITY.md), [October30 continuation code](experiments/2026-10-30_intermediate159/README.md), and [quality code](experiments/2026-10-30_quality/README.md). These tests do not need a GPU, a token, a Drive account or private benchmark text.

The public release deliberately **does not contain the private input ZIP, raw prompts/responses, per-record judgments, copyrighted text, model weights or cloud storage links/IDs**. Therefore an unaffiliated clone cannot reproduce the complete historical run from this repository alone. Exact archived-run verification requires the authorized private artifacts and the original archived runner bytes; the sanitized storage/config copies have new hashes. Do not weaken input or provenance checks to bypass missing files.

GPU execution is an explicit operator action with model-access requirements. No test downloads models or reads real credentials. `HF_TOKEN` is only a secret-name placeholder, never a bundled value. Do not commit generated records, tokens, private configurations or logs.

## Attribution and license status

HarmBench's standard classifier template is included under its upstream MIT notice, with the experiment's whitespace adaptation disclosed in [third-party notices](THIRD_PARTY_NOTICES.md). Model weights/tokenizer files and benchmark corpora are not redistributed. **No project-wide license has been selected in this release**; the third-party license does not license unrelated project code. Consult upstream model terms before use.
