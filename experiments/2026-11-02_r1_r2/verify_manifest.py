#!/usr/bin/env python3
"""Verify every declared package file, using only the standard library."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent
if __name__=='__main__':
 m=json.loads((ROOT/'MANIFEST.json').read_text());failed=[]
 for x in m['files']:
  rel=Path(x['path'])
  if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe manifest path')
  p=ROOT/rel
  if not p.is_file() or p.stat().st_size!=x['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=x['sha256']:failed.append(x['path'])
 if failed:raise SystemExit('Manifest mismatch: '+', '.join(failed))
 print('PASS: '+str(len(m['files']))+' package files match SHA256 and byte length')
