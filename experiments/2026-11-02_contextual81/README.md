# Contextual81 provenance audit (2026-11-02)

## Finding
No new binding between historical target-generation inputs, executed source version, and selected saved responses was established. Three inspected candidate source versions omit `ContextString` in their generation prompt path. That demonstrates omission in the inspected code, **not proof of omission in every historical run**. Retain contextual81 outside the primary protocol-aligned analysis. Adding context only to a judge input cannot retrospectively establish the target generation input.

Verified source dataset: 81 contextual items, all with nonempty context. Selected seed-42 set: **567 condition–item pairs (7 × 81)**. All stored seed records: **1,053 entries (13 × 81)**; repeated vectors at 50%, 55%, 60% sparsity are identical and must not be counted as independent observations. All 2,240 saved item entries match the canonical CSV by index, behavior, and category.

The 56 relevant notebook cells have no saved outputs; relevant code cells have null execution counts. The restored 636 input-token/serialized-input records are October 29 standard159 **judge** records, with zero contextual IDs, not historical contextual target-generation records. No new generation or scoring was performed.

## Reproduce privately
Python 3 standard library only. Supply the original private artifacts yourself; they are deliberately not included. The prior audit must be the original structured audit containing the archive SHA-256, `generator_sources`, and `response_schema_audit`. Three distinct candidate scripts must match its source hash set. The restored directory must contain `HB_protocol.json`, `LG_protocol.json`, and `records/*.json`.

```sh
python audit_contextual.py \
  --archive INPUTS.zip \
  --prior-audit PRIOR_AUDIT.json \
  --candidate-source CURRENT_GENERATOR.py \
  --candidate-source BACKUP_GENERATOR.py \
  --candidate-source LOGS_GENERATOR.py \
  --notebook NOTEBOOK.ipynb \
  --restored-run RESTORED_RUN_DIRECTORY \
  --log HISTORICAL_LOG.txt \
  --output OUTPUT_DIRECTORY
```

Run without Python's `-O` or `-OO` options: assertions are validation gates. Missing arguments, missing files, mismatched hash sets, incomplete record counts, unexpected categories, or non-identical repeat vectors fail instead of producing a successful inventory. This is a frozen audit of these inputs, not a general-purpose inference that arbitrary data establish historical omission. Source/log evidence interpretations are bounded manual conclusions, not a parser proving absence from all possible artifacts.

The supplied `verified_output/evidence_inventory.json` contains only scientific identifiers, structural facts, hashes, and limits. It contains no absolute local paths, Drive identifiers, raw contexts, raw model responses, or rendered prompts. Its record hash inventory permits equivalence checks while leaving the underlying data private. The CLI reads inputs and writes only its requested output; it never executes inspected source, unpickles data, loads models, uses a network, or uploads artifacts.

## Limitations
This was a targeted local audit, not an exhaustive search of all storage. Failure to locate historical input evidence is not proof it does not exist. Filenames are not evidence that researcher-reported common v2 conditions differed. Releasing this candidate requires separate publication authorization.
