# 2026년 11월 2일 정원 문장 단어 순서 통제 실험 재현 자료

이 묶음은 검증된 판정 행의 **분석 재집계**를 재현합니다. 언어모델을 다시 실행하거나 인간 정답을 검증하지 않습니다. 원시 benchmark prompt, target 응답, 입력 token IDs, 인증값, 개인 계정 이메일, 비공개 Drive 식별자는 없습니다.

## 실행

Python 3.12에서 다음 명령을 실행합니다. 검증 당시 NumPy는 2.3.5입니다. 설치는 별도 로컬 환경에서 수행합니다.

```bash
python -m pip install -r requirements.txt
python -m unittest -v test_reproduce_summary.py
python reproduce_summary.py
```

마지막 명령은 MANIFEST.json의 모든 파일 SHA256을 확인하고, data/label_rows.csv에서 결과를 다시 계산한 뒤 data/expected_summary.json과 정확히 비교합니다. `--output new_summary.json`은 새 파일만 만들며 기존 파일을 덮어쓰지 않습니다. 자체 테스트의 합성 데이터는 실제 실험 결과가 아닙니다.

## 설계와 분모

159개의 서로 다른 standard 유해 prompt에 159쌍의 서로 다른 113단어 정원 입력을 대응시켰습니다. H는 원래 행동 문맥, N은 중립 정원 요청 하나를 모든 입력에 재사용한 문맥, F는 유창한 입력, S는 단어 단위 재배열입니다. 중립 질문이 159개인 것은 아닙니다. 159 × 4셀 × 2평가자 = 1,272회와 저장 seed42 SP70 재실행 318회를 합쳐 계획 작업은 1,590회입니다. R은 SP70 재실행입니다. B001–B159는 원래 canonical ID 정렬과 일치하는 공개용 순서 ID이며 원본 ID 매핑은 비공개 자료에 있습니다.

주 분석은 H에서 S−F의 HB/LG 불일치 차이입니다. 159개 대응 묶음이 전부 유효할 때에만 양측 exact McNemar p값을 제공합니다. missing, invalid, abstain, excluded는 safe로 대체하지 않습니다. 중립 또는 재실행의 누락은 H가 완전한 ID의 주 분석 자격을 제거하지 않습니다. bootstrap은 묶음별 PCG64 seed20261102, 20,000회, linear percentile 95%입니다. 나머지 진단에는 추가 p값이 없습니다.

저장 schema에서 HB의 yes가 label 1 및 unsafe라는 공통 parser 값으로 표현되지만, HB의 개념은 주어진 행동의 성립입니다. 특히 N의 HB yes를 unsafe 판정이나 false positive로 해석하지 마십시오. LG label 1은 unsafe 분류입니다.

## 공개 집계의 투명한 해석 정정

동결 코드의 `material_plus10pp_unresolved`라는 필드는 일반적으로 구간 상한이 +10pp 이상인지 기록하므로 구간 전체가 +10pp를 넘는 경우도 true입니다. 이 이름은 실제 구간과 참고값의 관계를 오해하게 만들 수 있습니다. 공개 expected_summary는 해당 boolean을 그대로 전파하지 않고, 별도 검증한 `plus10pp_interval_relation`으로 아래·접촉 또는 포함·위의 관계를 명시합니다. 이번 주 구간 [40.88,55.97]pp는 **wholly_above_reference**입니다. 통계량, p값, 구간, 가설과 원래 동결 소스·결과는 바뀌지 않았습니다. 원본 필드 값과 해시는 reporting_annotation/REPORTING_INTERPRETATION_ANNOTATION.json에 보존합니다. 영변화의 보수적 상계는 별도 필드로 남으며 퇴화 구간의 동등성 근거가 아닙니다.

```bash
python -m unittest discover -s reporting_annotation -p 'test_*.py' -v
```

정정의 독립 검토와 아래·교차·위·경계·잘못된 입력에 대한 5개 합성 테스트를 함께 보존합니다.

## 파일

- data/label_rows.csv: 모든 계획 작업과 상태 및 이진 라벨. 비이진 라벨은 빈 칸입니다. historical_raw636_label은 R에서만 존재합니다.
- data/record_diagnostics.csv: 텍스트 없는 token 수, 절단 수, 정책 코드와 상태.
- data/expected_summary.json: 검증된 동결 분석과 수치가 일치하는 공개 행 집계.
- data/replay_consistency.json: 옛 raw636 대비 새 판정, raw 출력, 입력 hash와 parser의 일치 수. 과거 라벨은 정답이 아닙니다.
- frozen_source/: 사전 동결 분석 코드·설정·계획·테스트·입력 해시 목록과 개인정보를 생략한 프로토콜 사본. 공개 파생본의 7개 파일 hash도 확인합니다. 원래 동결 hash 목록은 provenance/ORIGINAL_ANALYSIS_FREEZE.json에 별도로 보존합니다. analyze.py의 전체 실행과 test_analysis.py의 archive 결합 테스트는 PRIMARY_HISTORICAL_RUN 환경변수로 제공한 비공개 역사적 protocol이 필요하고 없으면 명시적으로 skip됩니다. 공개용 test_reproduce_summary.py는 별도 원시 자료 없이 실행됩니다.
- provenance/source_bindings.json: 원본 출처 해시와 공개 제외 이유. 공개용 프로토콜은 계정 이메일 및 승인 메시지 식별자만 생략했으며 원본 SHA와 공개 사본 SHA는 서로 다릅니다.
- provenance/pinned_scientific_settings.json: 모델과 tokenizer의 정확한 revision, 설정, template와 parser SHA.
- reporting_annotation/: 결과를 바꾸지 않는 해석 필드 정정, 원래 boolean의 감사 기록, 5개 테스트와 독립 검토.

## 해석의 한계

사전에 고정한 전향적 탐색 실험이며 외부 사전등록은 아닙니다. 과거 판정은 설계 전에 열람했습니다. 단어 멀티셋을 보존했지만 의미 보존은 아니고 어순·응집성·구두점 위치가 함께 바뀝니다. 공통 정원 어휘와 12개 골격의 의존성을 명목 p값과 구간이 해결하지 않습니다. 159개 독립 학습 모델의 반복이 아닙니다. H/N 길이 차이 때문에 문맥 진단은 유해 의도만의 고립된 효과가 아닙니다.

unsafe labeling은 좁게 구성한 innocuous-content controls의 관찰입니다. 인간 검증 FPR, 일반 정확도, 가지치기 원인 또는 SP70 불일치의 원인으로 확장하지 않습니다. zero-change의 퇴화 bootstrap은 모집단 동등성을 입증하지 않습니다. 일치하는 코드 검사와 파일 hash는 자료의 계산 경로를 검증할 뿐 인간 정답을 만들어 내지 않습니다.

## tokenizer와 운영 한계

두 use_fast 요청은 HB와 LG 모두 Fast backend로 해석됐습니다. 이는 요청 설정의 일치이지 독립 fast/slow 알고리즘 검증이 아닙니다. 첫 세션은 새 judge 판정이 0개인 상태에서 종료됐고 같은 입력으로 사전 검사를 다시 실행했습니다. 이는 judge 라벨의 반복이나 추가 실험 조건이 아닙니다. 두 세션의 누적 실행 시간·CU·종료 기록은 연구보고서를 참조하십시오.


## GitHub 공개 파생본 구분

사전 동결 analyze.py·parser·통계 설정은 원본과 byte-identical입니다. 로컬 경로가 있는 계획·프로토콜·inventory는 placeholder로 바꾸고, 원시 protocol 의존 테스트는 명시적 환경변수 입력으로 바꿨습니다. 공개 integrity manifest는 새 동결이나 원본파일 동일성 주장과 다릅니다. 원본은 비공개 감사자료로 보존했습니다. 변경 hash는 provenance/source_bindings.json에 있습니다.

HB는 upstream 공식 형식을 바탕으로 보존한 템플릿에서 빈 줄 두 개가 제거된 버전을 사용했습니다. 템플릿 SHA를 고정했으며 upstream 템플릿과 byte-identical이라고 주장하지 않습니다.

## 평가 실행기의 공개 파생본

[runtime/README.md](runtime/README.md)는 명시적 비공개 운영 설정을 받는 CPU 검증 파생본입니다. 새 GPU 재현을 했다는 뜻이 아닙니다. 원래 실행기 hash를 보존하고 scientific method AST와 mocked rendering/parser parity를 검증했습니다. 실제 모델 실행은 별도 권한·자원·입력과 새 manifest가 필요합니다.
