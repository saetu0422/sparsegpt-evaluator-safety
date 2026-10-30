# Intermediate sparsity extension — 2026-10-30

## 한국어 요약

이 폴더는 **SP30·SP40·SP50·SP55·SP60**의 저장 응답을 다시 판정하는 코드와,
개인 데이터 없이 실행할 수 있는 합성 회귀 테스트를 보존합니다. 실제 결과나 원시
프롬프트·응답을 포함하지 않습니다.

- 새 판정: 159개 standard 항목 × 5조건 × HB/LG = **1,590개**.
- 비교 기준: 이전 날짜의 FP16 판정 **318개를 재사용**. 분석 행은 총 **1,908개**.
- 5개의 실행 폴더는 운영상 분할일 뿐입니다. 통계 검정은 **하나의 고정된 Holm 10개 검정군**입니다.
- 이전 SP70 결과는 이번 검정군에서 제외합니다. seed 42만 평가하며 인간 검증은 보류 상태입니다.
- `analysis_plan.public.json`은 설명용 삭제본입니다. 원본 계획과 바이트가 다르므로
  실행 입력으로 대체할 수 없습니다.

## What this release contains

The scientific runner, judgment parser, exact experimental HB template, secret launcher,
analyzer and baseline validator retain their approved source bytes. The deployment wrapper
uses explicitly supplied private identifiers rather than publishing a personal Drive folder
or historical run identifier. `CODE_PROVENANCE.json` distinguishes original hashes from
public-copy hashes. Neither a hash manifest nor this README alone proves independent review.

This is a **historical, scope-bound research apparatus**, not a general new-experiment launcher.
The original execution cutoff remains `2026-10-30T08:00:00+00:00`; it has not been extended or
removed. Do not interpret publication as authorization for additional inference, paid runtime
use, credential access or changes to the frozen analysis plan.

## Run the public tests

From the repository root, with Python 3.12 and NumPy 2.3.5 available:

```sh
python -m pip install -r experiments/2026-10-30_intermediate159/requirements-test.txt
python experiments/2026-10-30_intermediate159/verify_release.py
python -m unittest discover -s experiments/2026-10-30_intermediate159 -p 'test_*.py' -v
```

The test suite uses neutral generated texts, visibly synthetic IDs, fake model libraries,
temporary local directories and a noncredential sentinel. It does not load models, request
Colab Secrets, mount Drive, call external services, or consume the private research archives.
Test discovery should run in a separate Python process from the earlier `code/` suite because
both snapshots intentionally retain the historical module names.

The full repository is needed: baseline tests reuse the unchanged prior runner/template and
public plan in `../../code/`. Do not copy this folder alone and call missing dependencies a
successful reproduction.

### What is mocked, and what is exercised

- Source ZIP loading and the private current plan are replaced **inside tests only** with
  explicitly labeled synthetic inputs. All production SHA guards remain active and unchanged.
- The baseline archive fixtures contain only generated neutral data. Their test-specific
  checksums are explicitly substituted in test contexts; no production checksum is bypassed.
- Real code checks task/condition membership, canonical binding, hashes, parsers, protocol
  equality, checkpoints, missing/nonbinary accounting, baseline selection, immutable outputs,
  mounted-filesystem failure handling, authorization cutoff behavior, and secret suppression.
- Full fake-model processing covers all 1,590 new task keys. Offline analysis covers all 1,908
  aligned rows, ten contrast-specific bootstrap streams and a fixed ten-test Holm family.
- Setup success-path tests explicitly mock only the synthetic private-plan digest; separate
  tests prove unapproved plan bytes and the public projection are rejected without that test
  mock. Helper tests use generated complete temporary code bundles and mocked stages, not real runs.
  Their success path temporarily overrides only the neutral plan marker's expected digest.
  Omitted members, helper-only ZIPs, wrong/public plans and rehashed scientific/auth code
  variants must still fail before a write. Exporter tests apply the same bounded plan override.
- Export tests explicitly mock the private source/plan/baseline-lineage dependencies and
  use neutral archive stand-ins. Real full/partial scope checks, record/protocol validation,
  mirroring, immutable archive creation, CRC/member verification and failure paths execute.
- These tests are **not** a replay of GPU inference or independent cloud-backend persistence.

## Private reproduction dependencies

A clean public checkout deliberately lacks the exact current `analysis_plan.json`, raw input
ZIP, baseline archive, baseline extracted run, current run outputs and credentials. Therefore
it cannot independently reproduce the observed research labels from public files alone.

Authorized custodians can use a **separate private working copy** with the exact retained plan
(SHA-256 `473ecba7402b70a171b0589e8eb761cbe802330bd6de4d717a31e948aa94a5c7`) and other hash-bound
artifacts. The runner expects that private plan alongside its source. The analyzer accepts an
explicit `--plan` path but still requires exact original bytes. Never rename the explanatory
public projection to the private filename or alter the production pins to make it pass.

Private deployment identifiers must be configured before importing the wrapper:

- `SPARSEGPT_DRIVE_FOLDER_ID`: explicitly verified personal destination identifier.
- `SPARSEGPT_BASELINE_RUN_ID`: exact retained historical baseline run identifier.
- `SPARSEGPT_CODE_DIR` / `SPARSEGPT_DRIVE_PARENT`: explicitly chosen private local code and
  ID-bound mounted parent paths, used by `COLAB_SETUP_LEVELS.py`.
- `SPARSEGPT_REVIEWED_BUNDLE_PATH` / `SPARSEGPT_REVIEWED_BUNDLE_SHA256`: path and separately
  reviewed digest of a **private deployment bundle matching these public-copy bytes**, not the
  historical original-wrapper bundle.

The supplied CLI folder identifier must match the configured identifier and the ID-bound
mounted path. Baseline archive, identity, checkpoint, code, package and protocol hashes remain
required; configuration does not make an arbitrary baseline acceptable. Do not place private
configuration values or the original private plan in a public commit.

`COLAB_SETUP_LEVELS.py` only prepares code and arguments. `COLAB_RUN_CONDITION.py` acts on
exactly one explicit condition, verifies the supplied private bundle digest/CRC/manifest and
installed member bytes, mirrors that bundle, then performs input validation, HB and LG stages.
Its private bundle must have the expected `MANIFEST.json` member/size/hash structure and the
exact original private plan, in addition to the reviewed deployment code. `CODE_PROVENANCE.json`
is a publication manifest, **not** a substitute runtime bundle manifest. Both helper and
exporter require at least these eight deployment members before writing an artifact:

- `colab_smoke.py`, `research_parsers.py`, `HB_standard_template.txt`
- `drive_wrapper.py`, `colab_secret_launcher.py`, exact private `analysis_plan.json`
- `COLAB_SETUP_LEVELS.py`, `COLAB_RUN_CONDITION.py`

They check immutable reviewed hashes for the first six files, not merely a self-consistent
operator-supplied ZIP. Setup/helper bytes are bound by the independently reviewed whole-bundle
digest and installed-byte equality, without circular self-hash pins. Every archive member
still requires manifest/hash/installed-byte checks; tiny or incomplete bundles are refused.
No private bundle,
new packager or hard-bound historical ZIP installer is supplied; `verify_release.py` only
checks public file integrity.

The accepted HB→LG handoff is **mounted-filesystem/FUSE readback only**, not an independent
backend-confirmed HB gate. Independent backend verification is still required before the
next condition or runtime release. The helper has no all-condition loop and does not perform
that independent backend check itself. Do not report `condition318_complete` as proof of
backend durability.

`EXPORT_LEVELS_RESULTS.py` is a raw private-archive exporter, separate from statistical
analysis. `export_condition(...)` covers one operational318-task run;
`export_all(...)` retains the five-condition1,590-task scope. Missing or excluded records
require explicit `allow_partial=True` and remain separately counted; partial export never
shrinks the ten-test analysis family. The exporter uses the same explicitly configured
private bundle digest/name and verifies the exact private plan, code bindings, records,
checkpoints, immutable writes and archive members. It performs no model inference or
statistical tests. Its evidence is mounted-filesystem readback, not independent backend
verification.

**Exporter ZIPs and per-record comparison CSVs are private artifacts.** They include raw
research content and the exact private plan/bundle. Never commit them here or treat the
exporter as a public-data sanitizer. Only separately reviewed aggregate tables belong in
the public results directory.

The public wrapper has different bytes from the executed private wrapper. It cannot masquerade
as the original archive's wrapper hash. The public exporter likewise cannot be substituted for the original source archive contract.
Historical offline analysis must use the trusted pins
appropriate to the archived execution, not substitute the public wrapper SHA silently.

## Interpretation and rights

Model-judge labels and agreement are not human-validated accuracy. The fixed standard subset,
one saved generation seed, shared previous-day FP16 baseline and nominal per-contrast intervals
limit interpretation. There is no pruning-causal, population-generalization, change-point or
threshold claim. No additional subgroup or trend tests are introduced here.

The HB template is the exact experimental whitespace-adapted template, not a newly substituted
upstream version. See the repository's `THIRD_PARTY_NOTICES.md` and HarmBench MIT notice. No
model weights, tokenizer files, benchmark corpus or new project-wide license is bundled.
