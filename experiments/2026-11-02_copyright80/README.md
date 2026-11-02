# Copyright80 saved-response hash check — 2026-11-02

CPU-only scoring of 560 existing responses (7 conditions × 80 items; common seed42).
No target generation, model weights, GPU, or LLM API is required. These are reference MinHash matches, not HB/LG safety labels, legal determinations, or proof of overall safety improvement.

## Reproduce privately

Use Python 3.12 and the versions in `requirements.lock.txt`. Install the pinned spaCy `en_core_web_sm` model version separately if required. The lock records the executed environment, not a portable cross-platform dependency guarantee. Tokenizer metadata is pinned in `tokenizer_manifest.json`; no model weights are needed.

You must supply your own authorized private inputs. This repository deliberately excludes raw response archives, reference pickles, tokenizer assets, private Drive identifiers and credentials.

- `--archive`: verified saved-response ZIP (expected SHA-256 is pinned in the runner/provenance), containing `raw/harmbench_behaviors_text_test.csv` and seven `raw/responses_*.json` files. Each response file has 320 aligned `items`, `tag`, and `generations` with one seed42 response vector.
- `--input-dir`: `reference_download_manifest.json` with `upstream_commit` and `references` records (`path`, `size`, `git_blob_sha`, `sha256`); `private_references/` contains only the corresponding authorized reference pickle basenames. Also supply `tokenizer_manifest.json` and its verified files under `tokenizer/`.
- `--audit-dir`: pinned upstream `eval_utils.py` and GitHub recursive `upstream_tree.json` from HarmBench commit `8e1604d1171fe8a48d8febecd22f600e462bdcdd`. No arbitrary source is executed: the runner verifies the recorded Git blob and extracts the three scoring/tokenization functions. Supply trusted pinned inputs; integrity checks do not turn untrusted manifests into trusted provenance.
- `--output-dir`: a distinct private output directory. It receives scores, summaries, and provenance, never raw response/reference text.

```bash
python copyright_eval.py --input-dir "$PRIVATE_INPUTS" --audit-dir "$PINNED_UPSTREAM" --archive "$PRIVATE_ARCHIVE" --output-dir "$PRIVATE_OUTPUTS"
python test_copyright_eval.py --input-dir "$PRIVATE_INPUTS" --audit-dir "$PINNED_UPSTREAM" --archive "$PRIVATE_ARCHIVE" --output-dir "$PRIVATE_TEST_OUTPUTS"
python -m unittest -v test_synthetic
```

The five synthetic tests need installed dependencies only, not private inputs or network access. The ten integration tests additionally check upstream window semantics, strict threshold, tokenizer fast/slow parity and private-reference compatibility. Do not run with Python `-O`: validation assertions must remain enabled.

The input archive and manifests intentionally fail closed when bytes differ. This is a reproduction runner for the recorded dataset, not a generic replacement benchmark. Official sources are described in [methods](../../docs/2026-11-02_METHODS.md).

Primary published comparisons are descriptive paired counts. No p-values are included in the primary table; unplanned inferential diagnostics are not presented as confirmatory evidence.
