# Public-safe evaluator runner derivative

This is a **CPU-tested derivative**, not the exact deployed artifact and not a fresh GPU reproduction. The executed source SHA-256 is `2a23efdacce1507e7bbe5599d2730a42fe5505501a2ce04b476553fc7013aa96`. Private inputs, responses, account identity, folder IDs, run paths, credentials, weights and raw records are not included.

## Preserved scientific behavior

Pinned HB/LG model and tokenizer revisions, package versions, archived official-based templates, response/prompt clipping, sampling settings, raw parser, deterministic task order, invalid-label handling, record persistence and fail-closed stage behavior are unchanged. The historical protocol files here are minimal projections retaining only the fields consumed by the runner; this removes historical task-ID inventories and authorization statements without changing consumed values. `CPU_PARITY.json` records AST parity for every original function and every Session method except its operational constructor. `research_parsers.py` and `HB_standard_template.txt` are byte-identical to the executed archived files. The archived HB official-based template removes two blank lines relative to the upstream template; pinned byte identity is to that executed archived variant, **not** upstream byte identity.

## Operational adaptation

Supply an `OperationalConfig` with your **explicitly authorized** account/folder identity, verified mounted parent, mount root, ephemeral scratch root, original connection time, no-new-run cutoff, hard stop, baseline compute-unit balance and operational stop balance. No private configuration example is shipped. The configuration binds once per Python process and cannot be reset to restart the budget clock. Explicit timezone-aware dates, at most two hours from original connection to hard stop, separate ephemeral storage, and positive finite reserves are required. The runner still stops operationally by connection +110 minutes and retains fresh visible-budget observations, eight-minute stage bounds and create-only record guards. Configure the operational stop balance conservatively below your separately authorized hard expenditure cap; configuration itself is **not authorization**.

A new run ID uses `primarycontrol_YYYYMMDDTHHMMSSZ_<12hex>`. The independently backend-created identity marker must bind your exact destination, owner and newly frozen manifest. Preserve old records. Mounting/authentication, model access and GPU allocation require the operator's appropriate permissions; the code does not obtain permission on their behalf. No automatic connection, installation or inference occurs on import.

## Offline validation and tests

```sh
python -m unittest discover -p 'test_*.py' -v
python check_reference_parity.py --executed-reference /path/to/retained/executed/control_runner.py
python runner_cli.py --operational-config /path/to/private_config.json --manifest /path/to/private_bundle/manifest.json --manifest-sha256 EXPECTED_SHA256
```

The CLI only validates the supplied private bundle; it does not authenticate, allocate compute, load tokenizers/weights or generate labels. The separately retained executed reference is needed only for the optional reference-parity command. Unit tests use synthetic records and mocked tokenizers, not public or private model calls.

For an independently approved replication, build a new manifest binding this derivative (including the active `operational_config.py` source) and all required private inputs, configure once, initialize a fresh Session, execute the all-tokenizer gate, and supply a **fresh actual resource-panel observation before each stage**. Do not use stale example timestamps. Runtime HF authentication uses an ephemeral Colab Secret only for the official pinned matching service. Never print/save the token or invoke credential-persistence login helpers.

A human/browser watchdog must disconnect/delete the runtime on errors or budget/deadline exhaustion. Python timeouts cannot guarantee cancellation of blocked native/FUSE operations or stop billing. Mounted readback can reflect FUSE cache; independently backend-verify stage/final archives before claiming cloud persistence. No zero-loss guarantee is made.
