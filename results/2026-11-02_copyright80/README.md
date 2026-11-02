# Copyright80 reference-match results — 2026-11-02

These are **reference MinHash match labels**, not LLM safety decisions or legal findings. Existing saved responses only; common seed42; 80 items (40 book, 40 lyrics) in each of seven conditions.

| Condition | All positive /80 | Book /40 | Lyrics /40 |
|---|---:|---:|---:|
| FP16 | 22 (27.5%) | 0 | 22 |
| SP30 | 3 (3.75%) | 0 | 3 |
| SP40 | 0 | 0 | 0 |
| SP50 | 0 | 0 | 0 |
| SP55 | 0 | 0 | 0 |
| SP60 | 0 | 0 | 0 |
| SP70 | 0 | 0 | 0 |

FP16→SP30 has 19 positive-to-negative and zero negative-to-positive transitions. Each other condition has 22 and zero, respectively. Lower match rate is not proof of improved general safety; degraded output quality and this limited fixed sample constrain interpretation. Zero observed positives is not a guarantee for all possible outputs. No pre-registered causal or confirmatory hypothesis test is claimed.

- `results.csv`: 560 item-level labels, similarities, token lengths and response hashes, **no raw text**.
- `summary.csv`: 21 condition/stratum summaries.
- `paired_descriptive.csv`: 18 paired descriptive comparisons. No p-values in the primary table.
- `scientific_provenance.json`: algorithm/environment versions and input hashes; original executed-runner SHA is preserved separately from public CLI source.

[Methods and limitations](../../docs/2026-11-02_METHODS.md) · [Private-input reproduction](../../experiments/2026-11-02_copyright80/README.md). Contextual81 remains excluded from the primary analysis: [audit](../../experiments/2026-11-02_contextual81/README.md).
