# Reproducibility and safe operation

## 1. Public aggregate check (stdlib only)

From the repository root:

```bash
python tools/check_aggregate_results.py
```

This independently recomputes count consistency, paired risk differences, exact McNemar p-values and the fixed two-test Holm correction from public aggregate cells. It checks descriptive agreement totals. It **does not** recreate bootstrap intervals, item-level bindings or model outputs: exact frozen bootstrap replication uses the private, sorted paired records.

## 2. Offline public code tests

Use Python 3.12 and NumPy 2.3.5 for the recorded analysis environment. In a suitable isolated environment, install the dependency explicitly if needed, then run:

```bash
python -m pip install -r code/requirements-test.txt
cd code
python verify_release.py
python -m unittest discover -v
```

Dependency installation may use the network; **the tests themselves are offline** and use neutral synthetic tasks, fake model/tokenizer objects and temporary files. They do not read a real secret or download a model. Synthetic tests exercise implementation and failure paths; their labels are not research results. Public test receipts are summarized in `docs/REVIEW_STATUS.md`.

The source filename `colab_smoke.py` is historical. Its included scientific implementation is the completed **standard159/636** runner; it is not restricted to the 12-judgment smoke task count.

## 3. Authorized verification of the completed private run

The historical runner, parser, analyzer, plan and template are retained unchanged in this release; storage configuration/setup and exporter dependency pins are sanitized. `code/CODE_PROVENANCE.json` distinguishes original and public bytes. The original wrapper hash in a private historical run must **not** be replaced with the public wrapper's hash merely to pass a check.

An authorized custodian with the verified input ZIP and extracted completed run can run the unchanged offline analyzer:

```bash
python code/analysis.py \
  --run-dir /path/to/private/verified/run \
  --zip /path/to/private/verified_inputs.zip \
  --runner code/colab_smoke.py \
  --runner-sha256 d56b4e1a67b2f0b801ba98f46e65e4052e1e60217ea102d037520b455eb353ee \
  --parser-sha256 6616ea2e9fd27ced56a6e00bc73340bfa6e92cb0c6ee5a213382b6732bd0cbc8 \
  --out /path/to/new/private/analysis
```

The input ZIP is SHA/size-pinned. The analyzer rebuilds all tasks, verifies protocol/record/parser/code bindings, and requires all 636 records by default. Output must be new or empty. `--allow-incomplete` is an explicitly provisional diagnostic, not the completed-run analysis. Never publish its per-record outputs without a separate privacy/safety review.

The raw package, stored responses, per-item outputs and private linkage material are intentionally not included. Missing source material is a reproducibility boundary, not permission to fabricate data, drop assertions, silently alter pins or claim full public replication.

## 4. New GPU invocation: explicit operator action only

No new GPU experiment was run to prepare this public release. The sanitized storage wrapper remains a **hash-bound continuation workflow**, not an arbitrary-dataset evaluation framework. It still requires the original authorized source artifacts and exact source checkpoint hashes. A different dataset or protocol requires a separately versioned research plan and review.

Before importing code in a fresh Colab runtime, an authorized operator must explicitly configure:

| Environment variable | Meaning |
|---|---|
| `SPARSEGPT_CODE_DIR` | Local directory holding the reviewed public code |
| `SPARSEGPT_DRIVE_PARENT` | Existing authorized mounted project directory |
| `SPARSEGPT_DRIVE_FOLDER_ID` | Operator-supplied ID which must match the mount path and source identity |
| `SPARSEGPT_SOURCE_HB_RUN_ID` | Name of the exact private historical HB source run |
| `SPARSEGPT_SOURCE_LG_RUN_ID` | Name of the exact private historical LG source run |
| `SPARSEGPT_FULL159_RUN_ID` | Fresh `full159_YYYYMMDDTHHMMSSZ_<12 lowercase hex>` identifier |

Do not commit these private settings. Missing or mismatched configuration fails closed. The setup cell prepares `HB_ARGS` and `LG_ARGS` without reading credentials or executing models. The runtime must already have an authorized mount and appropriate software/GPU. It does not install packages, mount Drive or log in.

Run HB explicitly and inspect its complete checkpoint before a separate authorized LG invocation. LG requires appropriate upstream model access and the `HF_TOKEN` Colab Secret; the placeholder name is not a token value. The launcher reads it only after preflight and forwards it in memory. Do not paste tokens into source, command arguments, environment dumps, logs, notebooks committed to Git, or repository issues.

The completed environment used torch 2.11.0+cu130, transformers 5.20.2, accelerate 1.15.0 and CUDA 13.0 on A100-SXM4-40GB. These are observed versions, not a promise that future installations or hardware will be equivalent. Model execution and package setup are outside the offline test guarantee.

After a completed new invocation, the V2 exporter validates local/remote snapshots and all record/protocol/checkpoint bindings. A mounted filesystem readback is not backend durability evidence: separately retrieve and verify the backend artifact before declaring it stored. Keep raw archives private. Do not automatically remove stale locks or retry after an uncertain write.
