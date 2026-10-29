# Review status / 검증 상태

## Completed historical experiment

The 636-judgment experiment completed on 2026-10-29. The private artifact review verified 1,975 archive members and all 1,974 manifest entries, rebuilt all tasks exactly, and checked all 636 record/content/task/protocol/raw/parser/token bindings and completion checkpoints. It did not rerun a tokenizer or model.

An independent technical/statistical audit reconstructed raw labels, paired cells, exact McNemar tests, the fixed-family Holm adjustment, the frozen PCG64 20,000-pair bootstrap intervals and descriptive tables. Those checks passed. All protected source/plan/raw/output bytes remained unchanged during that audit.

Historical reviewer-executed test evidence was: core persistence suite 56, separate CLI/launcher checks 2, analyzer synthetic suite 25, exporter V1 suite 9 and exporter V2 suite 11. An exact-McNemar oracle comparison covered 12,879 discordance combinations. These scopes overlap, were run at different stages and **must not be summed into a single independent test total**. The author later added another V2 test; it was not represented as rerun by that historical reviewer.

These were independent AI-assisted technical reviews, not human subject evaluation, outside peer review or a guarantee of scientific validity. No human ratings were collected. Accuracy and causal claims remain unsupported.

## Public code release checks

The public packaging copies were tested separately after sanitization:

- **90/90 offline synthetic tests passed, zero skips.** Tests cover neutral 320-row/636-task fixtures, strict parsing, tokenization contracts, statistical methods, immutable mirroring/recovery, fake-model full636 integration, secret hygiene, exporter corruption/isolation/write failures and explicit deployment-config guards.
- Python compilation passed.
- `code/verify_release.py` verified 21 payload files against `code/CODE_PROVENANCE.json`; the provenance file is not self-hashed.
- `tools/check_aggregate_results.py` independently passed aggregate counts, marginal totals, paired risk differences, exact McNemar, Holm and agreement checks. It does not reproduce the private ordered-pair bootstrap.
- Private archive/model tests were **not** run as part of public packaging. No new model invocation, human rating or GPU experiment occurred.

The scientific runner, parser, analyzer, frozen plan, HB template and secret launcher remain byte-identical to their preserved originals. Deployment wrapper/setup configuration and exporter wrapper pins differ and have **new hashes**. The public wrapper/exporter cannot claim the original storage-code review SHA or silently resume/export a run bound to different wrapper bytes.

## Publication boundary

The intended public payload is text-only code, documentation, upstream notice and aggregate numeric results. Private input/output archives, row-level IDs/text, model weights, authentication material, personal cloud identifiers and human-pilot keys are excluded. A full-tree secret/privacy scan and independent publication review are recorded separately by the release custodian; they are not a claim of human validation or perfect leak detection.

Scientific and implementation limitations are documented in the README and methods. Code correctness checks do not convert evaluator labels into ground truth.
