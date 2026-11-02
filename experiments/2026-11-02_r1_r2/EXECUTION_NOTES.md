# Execution notes and Korean findings

## 재현 범위와 검증
- 최종 분석은 Instruct 응답의 standard159, seed42만 사용했다. 원지시서의 base/320 수치는 재사용하지 않았다.
- 7조건×159응답=1,113행, 두 판정자=2,226라벨; 원본 ZIP SHA 및 24개 manifest 항목, backend export 7,060개 항목을 검증했다. canonical CSV 행과 원문 내용의 정확한 대응으로 ID를 부여했으며, 생성 원본의 native ID가 존재한다는 주장은 하지 않는다.
- 6개 legacy 라벨 차이를 검증했으며, 최종 라벨은 검증된 backend 재판정값이다. 11월2일 SP70 재실행은 추가 표본으로 포함하지 않았다.
- 응답/프롬프트 원문은 `input_verification/joined_private_inputs.json`에만 보관하며 공개 대상이 아니다. `results/`는 라벨·수치·그림만 포함한다. 모델/토크나이저 추론을 CPU에서 재실행한 것이 아니라 저장된 기록과 해시/프로토콜을 검증했다.

## R1 핵심 결과: 강한 V1 또는 V2로 확정하지 않음
SP70 D=122(LG1/HB0), A=37. 역방향 불일치는0.
- 길이 중위값[Q1,Q3]: D11[10,15], A14[10,15]; MWU p=.468280, r=−.077758. D가 유의하게 짧다는 주장은 성립하지 않는다. D의 긴 꼬리 때문에 평균 길이는 오히려 더 크다.
- trigram 반복률 평균: D.261510 vs A.103681; bootstrap95 CI 각각[.204075,.320760], [.040610,.178502]. MWU p=.005401, r=.270270.
- 단일어 지배도 평균: D.175841 vs A.149337; bootstrap95 CI[.164377,.187596], [.134212,.165622]. MWU p=.014060, r=.263181.
- 원래 collapse proxy: D15/122(12.30%), A1/37(2.70%). Wilson95 각각[7.59%,19.30%], [.48%,13.82%]. Fisher exact p=.120872; 참고용 binary-MWU p=.091090. 작은 셀(1건)이 있으므로 odds ratio5.05를 유의한 효과로 해석하지 않는다.
- 비벌점 로지스틱: apparent AUC=.636354; 층화5-fold OOF AUC=.623837. 길이·반복률·지배도 세 기울기의 Wald95 CI는 모두0을 포함한다. 반복/지배도 단변량 차이는 있으나 강한 설명력 또는 생성붕괴의 인과적 설명으로 확정할 수 없다. 또한 비유의성을 ‘무관/독립’의 증명으로 해석하지 않는다.

## R2와 일치도
- FP16 대비 별도 Holm12에서 두 판정자 모두 처음 유의한 수준은 SP50이다: LG+8.805pp, pHolm=.003632; HB+7.547pp, pHolm=.010986.
- FP16→SP70: LG+78.616pp(pHolm=1.806e−35), HB+.629pp(pHolm=1). HB가 FP16보다 유의하게 낮아졌다는 주장은 불가능하다.
- 인접 별도 Holm10의 SP60→70: LG b99/c7, +57.862pp(pHolm=6.454e−21), HB b6/c23, −10.692pp(pHolm=.020841). 이 전이에서 반대 방향의 유의한 변화는 유지된다.
- SP70 원일치37/159=23.270%, κ=.018816, PABAK=−.534591. κ와 PABAK는 다른 기준선 보정을 사용하므로 서로 바꾸어 부르지 않는다.

## 계획 실행의 명시적 세부사항
고정 METHODS_FROZEN.md SHA는 그대로 유지한다. 이하 내용은 결과를 선택하기 위한 방법 변경이 아니라 경계값/수치상태의 명시적 처리다.
- FP16에서는 방향성 D가0이다. 빈 그룹 요약은 n0, MWU/Fisher는 unavailable/null이며 p1이나0으로 대체하지 않는다. 작은 D 집단의 추가 수준 비교는 탐색적이다.
- SP70 실제 길이는 최소6이어서 primary와 legacy trigram 값이 동일하다. 전체 자료에는 두 정의를 모두 저장했다. collapse proxy는 반복 임계조건 n>=50이므로 두 trigram 정의의 영향을 받지 않는다.
- SciPy BFGS 전체 적합은 `precision loss` 종료 메시지와 optimizer_success=false를 반환했다. 이는 숨기지 않는다. 미리 정한 score 기준(maxabs<1e−6)과 양의 정부호 information을 통과했고 전체 score maxabs=1.02e−7, Hessian 조건수13.41이며 strict/quasi separation 없음이다. 따라서 inference_status=ok로 표시하되 optimizer flag와 함께 읽는다. 독립 검토자의 score-root 해와 계수가 약1e−7 수준에서 일치했다. fold별 모든 진단은 results.json에 보존했다.
- Bootstrap percentile 구간은 비동시·기술적 구간이다. 특히 희소 discordance에서 CI가0을 제외해도 exact McNemar가 비유의일 수 있다. 유의성 판단은 각 가족의 Holm p에 따른다.
- exploratory R1 다중 비교는 보정하지 않았으며 재현된 유의성은 확증적/인과적 결론이 아니다. 단일 seed의 불확실성은 평가 응답 표집에 관한 것이며 seed/model 간 변동이 아니다.
- 공개 metric CSV는 float round-trip parsing으로 읽어 private-text 분석과 동일한 수치를 재현한다. 텍스트 없이 원문에서 metric 자체를 재추출할 수 있다고 주장하지 않는다.

## CLI
```bash
python -m unittest test_analysis -v
python analyze.py --metrics results/response_metrics_labels.csv --out replay
# private source route (never publish joined_private_inputs.json)
python analyze.py --input input_verification/joined_private_inputs.json --out results
```
필요 패키지와 실행 버전은 results.json.environment 및 requirements.txt에 기록했다. GPU/네트워크/계정 자격증명 불필요. 결과 재현에는 원문이 필요 없다. 원문 metric 추출/해시 재검증에는 별도의 비공개 입력이 필요하다.
