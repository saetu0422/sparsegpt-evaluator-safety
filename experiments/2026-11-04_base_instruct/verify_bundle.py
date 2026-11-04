#!/usr/bin/env python3
"""Verify the public figure bundle without raw model or judge data."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent
manifest = json.loads((ROOT / 'MANIFEST.json').read_text())
errors = []
for name, digest in manifest['files_sha256'].items():
    p = ROOT / name
    if not p.is_file():
        errors.append('Missing file: ' + name)
    elif hashlib.sha256(p.read_bytes()).hexdigest() != digest:
        errors.append('Hash mismatch: ' + name)

data = json.loads((ROOT / 'data/aggregate_metrics.json').read_text())
assert set(data) == {'schema_version', 'title', 'analysis_date', 'source_sha256', 'scope', 'conditions', 'agreement', 'cross_model', 'quality_common_word_metrics'}
for row in data['agreement']:
    for key in ['base_agreement', 'instruct_agreement']:
        t = row[key]['table_LGrows_HBcols']
        assert sum(map(sum, t)) == 159
assert len(data['cross_model']) == 14
assert len(data['quality_common_word_metrics']) == 14

# Check literal private domains/paths and common credential formats. This
# complements the deliberately aggregate-only schema; it is not a secret scanner.
patterns = [r'drive\.google\.com', r'/workspace/(?:shared|scratch)/',
            r'/home/agent/', r'gh[pousr]_[A-Za-z0-9]{20,}', r'github_pat_[A-Za-z0-9_]{20,}',
            r'AKIA[0-9A-Z]{16}', r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----']
for name in manifest['files_sha256']:
    if name.endswith(('.json', '.csv', '.md', '.svg', '.txt')):
        body = (ROOT / name).read_text()
        for pattern in patterns:
            if re.search(pattern, body):
                errors.append('Potential private content in ' + name)
if errors:
    raise SystemExit('\n'.join(errors))
print(json.dumps({'integrity': 'pass', 'aggregate_schema': 'pass',
                  'public_content_scan': 'pass', 'files_verified': len(manifest['files_sha256'])}, indent=2))
