# Surface-quality reconstruction v2 (descriptive only)

This is a **new implementation of preserved report definitions**, not recovery of the original quality program or byte-identical historical replication. It measures length and repetition proxies, not human quality, refusal truth or safety accuracy. Exact original refusal-prefix regex was unavailable, so that proxy is **omitted**, not guessed.

`quality.py` and its 22 neutral synthetic tests are byte-identical to the independently reviewed reconstruction sources. `methods.json` changes only its provenance text to withhold one private Library identifier; the original and public hashes are disclosed in [CODE_PROVENANCE.json](CODE_PROVENANCE.json). Runtime output provenance therefore reports the public method-file hash, not the original one. No metric or scientific method was changed by packaging.

## Offline tests

From this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest -v test_quality
```

Standard library only; no model, GPU, authentication, network or private input is needed for tests.

## Authorized private-data use

The actual reconstruction requires the exactly pinned private input ZIP and independently verified item-level analyzer CSVs. They are deliberately not provided in this public repository. For an authorized operator, the interface is:

```sh
python quality.py --zip "$PRIVATE_INPUT_ZIP" \
  --new-labels "$VERIFIED_OCT30_RECORD_CSV" \
  --prior-labels "$VERIFIED_OCT29_RECORD_CSV" \
  --out "$PRIVATE_OUTPUT_DIRECTORY"
```

The output directory must be empty. **The program writes private per-item CSVs containing row-derived IDs and response hashes. It is not a public-output sanitizer.** Keep every generated output outside the repository and publish only separately reviewed aggregate projections. The program checks source/response/seed/label joins; it expects prior independent analyzer/backend validation and does not itself revalidate the entire judgment archive.

Methods, scope and the distinction between historical and new judge disagreement are summarized with the [aggregate results](../../results/2026-10-30_quality/README.md). Human validation remains deferred; no inferential quality/subgroup tests are performed.
