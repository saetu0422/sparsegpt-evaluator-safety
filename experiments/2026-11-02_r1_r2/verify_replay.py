#!/usr/bin/env python3
"""Compare a public CPU replay with the frozen results; no private files needed."""
from pathlib import Path
import argparse,json,math
ROOT=Path(__file__).resolve().parent

def same(a,b,tol):
 if isinstance(a,dict):return isinstance(b,dict) and a.keys()==b.keys() and all(same(a[k],b[k],tol) for k in a)
 if isinstance(a,list):return isinstance(b,list) and len(a)==len(b) and all(same(x,y,tol) for x,y in zip(a,b))
 if isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool):return a==b if tol==0 else math.isclose(a,b,rel_tol=tol,abs_tol=tol)
 return a==b

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--replay',type=Path,required=True);ap.add_argument('--tolerance',type=float,default=0);args=ap.parse_args()
 if args.tolerance<0:raise ValueError('Tolerance must be nonnegative')
 a=json.loads((ROOT/'results/results.json').read_text());b=json.loads((args.replay/'results.json').read_text())
 for k in ['input_mode','input_sha256','environment']:a.pop(k,None);b.pop(k,None)
 assert same(a,b,args.tolerance),'Scientific JSON mismatch'
 mismatches=[p.name for p in (ROOT/'results').glob('*.csv') if not (args.replay/p.name).is_file() or p.read_bytes()!=(args.replay/p.name).read_bytes()]
 if args.tolerance==0:assert not mismatches, 'CSV byte mismatch: '+', '.join(mismatches)
 print(json.dumps({'status':'PASS','scientific_json_exact':args.tolerance==0,'tolerance':args.tolerance,'all_csv_byte_identical':not mismatches,'csv_byte_mismatches':mismatches,'excluded_metadata':['input_mode','input_sha256','environment']},indent=2))
