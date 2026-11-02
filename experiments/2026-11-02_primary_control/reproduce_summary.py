"""Reaggregate text-free PRIMARY labels. No model, network, or raw text access.

This is a reporting replay, not a rerun of judge inference. Statistical choices
mirror the prospectively frozen analysis; the row parser is independently built.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math
from collections import Counter
from pathlib import Path
import numpy as np
from reporting_annotation.reference_interpretation import interval_relation

N = 159
SEED = 20261102
DRAWS = 20000
GRID = {(p,q,j) for p in ('H','N') for q in ('F','S') for j in ('HB','LG')} | {('H','R',j) for j in ('HB','LG')}
FIELDS = ('cluster_id','skeleton_id','context','response','judge','status','label','historical_raw636_label')
STATUSES = {'safe','unsafe','invalid','abstain','excluded','missing'}

def require(ok, message):
    if not ok: raise ValueError(message)

def exact_mcnemar(b, c):
    require(type(b) is int and type(c) is int and b >= 0 and c >= 0, 'invalid counts')
    n = b + c
    return min(1.0, sum(math.comb(n,k) for k in range(min(b,c)+1)) * 2 / 2**n) if n else 1.0

def interval(values):
    if not values: return None
    rng = np.random.Generator(np.random.PCG64(SEED))
    x = np.asarray(values, dtype=float)
    means = np.empty(DRAWS)
    for start in range(0, DRAWS, 1000):
        draws = rng.integers(0, len(x), size=(min(1000, DRAWS-start), len(x)))
        means[start:start+len(draws)] = x[draws].mean(axis=1)
    return np.quantile(means, [0.025,0.975], method='linear').tolist()

def paired(f, s, primary=False):
    require(len(f)==len(s), 'unpaired inputs')
    n = len(f)
    table = [[0,0],[0,0]]
    for a,b in zip(f,s):
        require(type(a) is int and type(b) is int and a in (0,1) and b in (0,1), 'nonbinary pair')
        table[a][b] += 1
    delta = [b-a for a,b in zip(f,s)]
    ci = interval(delta)
    out = {'n':n,'table_rows_F_columns_S_0_1':table,'b_F0_S1':table[0][1],'c_F1_S0':table[1][0],
           'risk_difference_S_minus_F':sum(delta)/n if n else None,'nominal_paired_bootstrap95':ci,
           'plus10pp_interval_relation':interval_relation(ci)}
    if primary: out['exact_two_sided_mcnemar_p'] = exact_mcnemar(table[0][1],table[1][0]) if n==N else None
    if n and not any(delta):
        upper = 1-.05**(1/n)
        out['any_paired_change_one_sided95_upper_under_sampling_model'] = upper
    return out

def load_rows(path):
    with Path(path).open(newline='',encoding='utf-8') as f:
        reader=csv.DictReader(f)
        require(tuple(reader.fieldnames or ())==FIELDS, 'unexpected columns')
        rows=[]
        for row in reader:
            require(row['status'] in STATUSES, 'unknown status')
            for name in ('label','historical_raw636_label'):
                require(row[name] in ('','0','1'), 'invalid binary field')
                row[name] = None if row[name]=='' else int(row[name])
            require(row['label']=={'safe':0,'unsafe':1}.get(row['status']), 'status/label mismatch')
            rows.append(row)
    return rows

def aggregate(rows):
    require(len(rows)==N*10, 'expected 1590 planned rows including missing statuses')
    keyed={}
    for r in rows:
        require(set(r)==set(FIELDS), 'unexpected row fields')
        require(r['status'] in STATUSES, 'unknown status')
        require(r['label']=={'safe':0,'unsafe':1}.get(r['status']), 'status/label mismatch')
        require(r['label'] is None or type(r['label']) is int, 'label must be integer')
        require(len(r['cluster_id'])==4 and r['cluster_id'].startswith('B') and r['cluster_id'][1:].isdigit(), 'invalid opaque cluster ID')
        k=(r['cluster_id'],r['context'],r['response'],r['judge'])
        require(k not in keyed, 'duplicate row')
        require(k[1:] in GRID, 'unexpected factorial cell')
        keyed[k]=r
    ids=sorted({r['cluster_id'] for r in rows})
    require(ids==[f'B{i:03d}' for i in range(1,N+1)], 'canonical opaque ID inventory mismatch')
    skeleton={}
    for bid in ids:
        group=[r for r in rows if r['cluster_id']==bid]
        require({(r['context'],r['response'],r['judge']) for r in group}==GRID, 'incomplete grid')
        s={r['skeleton_id'] for r in group if r['response']!='R'}
        require(len(s)==1 and next(iter(s))!='', 'inconsistent skeleton')
        skeleton[bid]=next(iter(s))
    def y(b,p,q,j): return keyed[b,p,q,j]['label']
    def valid(p): return [b for b in ids if all(y(b,p,q,j) is not None for q in ('F','S') for j in ('HB','LG'))]
    def d(b,p,q): return int(y(b,p,q,'HB')!=y(b,p,q,'LG'))
    hi=valid('H');ni=valid('N');both=sorted(set(hi)&set(ni))
    out={'schema':'primary-control-public-replay-v1','planned_clusters':N,'planned_tasks':N*10,
         'record_count':sum(r['status']!='missing' for r in rows), 'status_counts':dict(sorted(Counter(r['status'] for r in rows).items())),
         'primary_status':'complete_prespecified_exploratory' if len(hi)==N else 'INCOMPLETE_NONCONFIRMATORY_DESCRIPTIVE_ONLY',
         'primary_missing_or_invalid_cluster_ids':sorted(set(ids)-set(hi)),
         'primary':paired([d(b,'H','F') for b in hi],[d(b,'H','S') for b in hi],True),
         'neutral':paired([d(b,'N','F') for b in ni],[d(b,'N','S') for b in ni]),
         'cells':{},'judge_quality_contrasts':{},'skeletons':{},'replay':{}}
    did=[d(b,'H','S')-d(b,'H','F')-d(b,'N','S')+d(b,'N','F') for b in both]
    out['context_disagreement_difference_in_differences']={'n':len(both),'H_minus_N':float(np.mean(did)) if did else None,'nominal_descriptive_bootstrap95':interval(did)}
    for p in ('H','N'):
        for q in ('F','S'):
            table=[[0,0],[0,0]]
            for b in ids:
                a,c=y(b,p,q,'HB'),y(b,p,q,'LG')
                if a is not None and c is not None: table[a][c]+=1
            n=sum(map(sum,table))
            cell={'paired_n':n,'HB_rows_LG_columns_0_1':table,'disagreement_rate':(table[0][1]+table[1][0])/n if n else None}
            for j in ('HB','LG'):
                v=[y(b,p,q,j) for b in ids if y(b,p,q,j) is not None]
                cell[j]={'valid_n':len(v),'unsafe_count':sum(v),'unsafe_rate':sum(v)/len(v) if v else None}
            out['cells'][p+q]=cell
        for j in ('HB','LG'):
            ok=[b for b in ids if all(y(b,p,q,j) is not None for q in ('F','S'))]
            out['judge_quality_contrasts'][p+j]=paired([y(b,p,'F',j) for b in ok],[y(b,p,'S',j) for b in ok])
        ok=valid(p)
        values=[y(b,p,'S','LG')-y(b,p,'F','LG')-y(b,p,'S','HB')+y(b,p,'F','HB') for b in ok]
        out['judge_quality_contrasts'][p+'_LG_minus_HB']={'n':len(ok),'difference':sum(values)/len(ok) if ok else None,'nominal_descriptive_bootstrap95':interval(values)}
    for s in sorted(set(skeleton.values()),key=str):
        members=[b for b in ids if skeleton[b]==s];ok=[b for b in members if b in hi]
        out['skeletons'][s]={'planned_n':len(members),'eligible_n':len(ok),'H_disagreement_difference':sum(d(b,'H','S')-d(b,'H','F') for b in ok)/len(ok) if ok else None}
    for j in ('HB','LG'):
        group=[r for r in rows if r['response']=='R' and r['judge']==j]
        valid_pairs=[r for r in group if r['label'] is not None and r['historical_raw636_label'] is not None]
        table=[[sum(r['historical_raw636_label']==a and r['label']==b for r in valid_pairs) for b in (0,1)] for a in (0,1)]
        out['replay'][j]={'planned_n':len(group),'valid_pair_n':len(valid_pairs),'historical_rows_new_columns_0_1':table,'label_match_n':table[0][0]+table[1][1]}
    return out

def verify_manifest(root):
    root=Path(root);m=json.loads((root/'MANIFEST.json').read_text())
    for rel,digest in m['files'].items():
        p=root/rel
        require(not Path(rel).is_absolute() and '..' not in Path(rel).parts and not p.is_symlink(), 'unsafe manifest path')
        require(hashlib.sha256(p.read_bytes()).hexdigest()==digest, 'manifest mismatch: '+rel)
    freeze_path=root/'frozen_source/ANALYSIS_FREEZE.json'
    if freeze_path.exists():
        freeze=json.loads(freeze_path.read_text())
        for rel,digest in freeze['files'].items():
            p=freeze_path.parent/rel
            require(not Path(rel).is_absolute() and '..' not in Path(rel).parts and not p.is_symlink(), 'unsafe frozen path')
            require(hashlib.sha256(p.read_bytes()).hexdigest()==digest,'public derivative integrity mismatch: '+rel)
    return len(m['files'])

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rows',default='data/label_rows.csv')
    ap.add_argument('--expected',default='data/expected_summary.json')
    ap.add_argument('--output')
    ap.add_argument('--skip-manifest',action='store_true')
    a=ap.parse_args()
    if not a.skip_manifest: verify_manifest(Path(__file__).resolve().parent)
    got=aggregate(load_rows(a.rows));want=json.loads(Path(a.expected).read_text())
    require(got==want, 'reaggregation differs from verified expected summary')
    if a.output:
        with Path(a.output).open('x',encoding='utf-8') as f: json.dump(got,f,ensure_ascii=False,indent=2);f.write('\n')
    print('PASS: file hashes and text-free row aggregation match the verified summary.')

if __name__=='__main__': main()
