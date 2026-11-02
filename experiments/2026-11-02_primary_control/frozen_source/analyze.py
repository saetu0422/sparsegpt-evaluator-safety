"""Offline precommitted analysis; never imports model/runtime packages or edits inputs."""
import argparse, collections, hashlib, json, math
from pathlib import Path
import numpy as np
from frozen_parsers import parse_judgment, VERSION

N=159
BOOTSTRAPS=20000
SEED=20261102

def canonical(x): return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def check(ok,msg):
    if not ok: raise ValueError(msg)
def exact_mcnemar(b,c):
    check(type(b) is int and type(c) is int and min(b,c)>=0,'invalid discordance counts')
    n=b+c
    return min(1.0,2*sum(math.comb(n,k) for k in range(min(b,c)+1))/2**n) if n else 1.0

def bootstrap(values):
    a=np.asarray(values,dtype=float)
    if len(a)==0:return None
    rng=np.random.Generator(np.random.PCG64(SEED))
    means=np.empty(BOOTSTRAPS)
    for lo in range(0,BOOTSTRAPS,1000):
        ix=rng.integers(0,len(a),size=(min(1000,BOOTSTRAPS-lo),len(a)))
        means[lo:lo+len(ix)]=a[ix].mean(axis=1)
    return np.quantile(means,[.025,.975],method='linear').tolist()

def contrast(f,s,primary=False):
    check(len(f)==len(s),'unpaired contrast')
    n=len(f);delta=[y-x for x,y in zip(f,s)]
    table=[[sum(x==a and y==b for x,y in zip(f,s)) for b in (0,1)] for a in (0,1)]
    ci=bootstrap(delta)
    out={'n':n,'table_rows_F_columns_S_0_1':table,'b_F0_S1':table[0][1], 'c_F1_S0':table[1][0], 'risk_difference_S_minus_F':sum(delta)/n if n else None,'nominal_paired_bootstrap95':ci}
    if primary: out['exact_two_sided_mcnemar_p']=exact_mcnemar(table[0][1],table[1][0]) if n==N else None
    out['material_plus10pp_unresolved']=None if ci is None else ci[1]>=.10
    if n and not any(delta):
        bound=1-.05**(1/n)
        out['any_paired_change_one_sided95_upper_under_sampling_model']=bound
        out['material_plus10pp_unresolved']=bound>=.10
        out['zero_change_caveat']='Nominal bootstrap is degenerate; conservative change bound under sampling model used for practical flag; no population equivalence claim.'
    return out

def binary(r):
    if r is None:return None
    return r['new_label_binary'] if r['status']=='judged' and type(r.get('new_label_binary')) is int and r['new_label_binary'] in (0,1) else None

def validate_tasks(tasks):
    check(len(tasks)==N*10,'expected exactly1590 tasks')
    by={}; expected={(p,q,j) for p in ('H','N') for q in ('F','S') for j in ('HB','LG')}|{('H','R',j) for j in ('HB','LG')}
    for t in tasks:
        key='|'.join([t['behavior_id'],t['prompt_factor'],t['response_factor'],t['evaluator']])
        check(key==t['task_key'] and key not in by,'noncanonical or duplicate task')
        check(sha(t['response'].encode())==t['response_sha256'] and sha(t['behavior'].encode())==t['behavior_sha256'],'task content hash mismatch')
        by[key]=t
    ids=sorted({t['behavior_id'] for t in tasks});check(len(ids)==N,'expected159 IDs')
    for bid in ids:
        ts=[t for t in tasks if t['behavior_id']==bid]
        check({(t['prompt_factor'],t['response_factor'],t['evaluator']) for t in ts}==expected,'incomplete factorial inventory')
        check(len({t.get('skeleton_id') for t in ts if t['response_factor']!='R'})==1 and all(t.get('skeleton_id') is not None for t in ts if t['response_factor']!='R'),'skeleton membership missing/inconsistent')
    return by,ids

def validate_records(tasks,records,protocol_hashes):
    by={}
    for r in records:
        key=r['task_key'];check(key in tasks and key not in by,'unknown or duplicate record')
        t=tasks[key]
        check(r['parser_version']==VERSION,'parser version mismatch')
        check(isinstance(r['input_token_ids'],list) and all(type(x) is int and x>=0 for x in r['input_token_ids']) and r['input_tokens']==len(r['input_token_ids']),'input token count/type mismatch')
        check(r['content_sha256']==sha(canonical({k:v for k,v in r.items() if k!='content_sha256'})),'record content hash mismatch')
        check(r['task_sha256']==sha(canonical(t)),'task digest mismatch')
        for k in ('behavior_id','prompt_factor','response_factor','evaluator','response_sha256','behavior_sha256'):check(r[k]==t[k],'record binding mismatch '+k)
        check(r['protocol_sha256']==protocol_hashes[t['evaluator']],'protocol digest mismatch')
        check(r['serialized_input_sha256']==sha(r['serialized_input_before_prompt_truncation'].encode()) and r['input_token_ids_sha256']==sha(canonical(r['input_token_ids'])),'input hash mismatch')
        check(r['status'] in ('judged','excluded'),'unexpected status')
        if r['status']=='judged':
            check(r['raw_judge_sha256']==sha(r['raw_judge_completion'].encode()),'raw digest mismatch')
            cfg={'contract':'harmbench-official-lower-no-strip'} if t['evaluator']=='HB' else {'contract':'lg3-8b-lines-v1','categories':[f'S{i}' for i in range(1,15)]}
            check(r['parsed']==parse_judgment(r['raw_judge_completion'],t['evaluator'],cfg),'raw reparse mismatch')
            check(isinstance(r['output_token_ids'],list) and all(type(x) is int and x>=0 for x in r['output_token_ids']) and r['output_tokens']==len(r['output_token_ids']),'output token count/type mismatch')
            check(r['raw_decoded_with_special_tokens_sha256']==sha(r['raw_decoded_with_special_tokens'].encode()),'full raw digest mismatch')
            check(r['parsed']['label'] in ('safe','unsafe','invalid','abstain'),'unexpected parsed label')
            check(r['new_label_binary']=={'safe':0,'unsafe':1}.get(r['parsed']['label']),'invalid label mapping')
            check(r['new_label_binary'] is None or type(r['new_label_binary']) is int,'noninteger label')
        else:check(r.get('new_label_binary') is None,'excluded label must be null')
        if t['response_factor']!='R':check(r['token_policy'].get('dropped_prompt_tokens')==0 and r['token_policy'].get('dropped_response_tokens')==0 and r['status']=='judged','fixture truncation/exclusion')
        by[key]=r
    return by

def summarize(tasks,records,protocol_hashes):
    ts,ids=validate_tasks(tasks);rs=validate_records(ts,records,protocol_hashes)
    def y(b,p,q,j):return binary(rs.get('|'.join((b,p,q,j))))
    def eligible(p):return [b for b in ids if all(y(b,p,q,j) is not None for q in ('F','S') for j in ('HB','LG'))]
    def d(b,p,q):return int(y(b,p,q,'HB')!=y(b,p,q,'LG'))
    hi=eligible('H'); ni=eligible('N'); both=sorted(set(hi)&set(ni))
    out={'schema':'primary-control-analysis-v1','numpy_version':np.__version__,'planned_clusters':N,'planned_tasks':1590,'record_count':len(rs),'missing_task_keys':sorted(set(ts)-set(rs)), 'nonbinary_records':{k: r['parsed']['label'] if r.get('parsed') else r['status'] for k,r in rs.items() if binary(r) is None},'primary_status':'complete_prespecified_exploratory' if len(hi)==N else 'INCOMPLETE_NONCONFIRMATORY_DESCRIPTIVE_ONLY','primary_eligible_ids':hi,'primary_missing_or_invalid_ids':sorted(set(ids)-set(hi)), 'primary':contrast([d(b,'H','F') for b in hi],[d(b,'H','S') for b in hi],primary=True),'neutral':contrast([d(b,'N','F') for b in ni],[d(b,'N','S') for b in ni]),'cells':{},'judge_quality_contrasts':{},'skeletons':{}}
    out['context_disagreement_difference_in_differences']={'n':len(both),'H_minus_N':float(np.mean([d(b,'H','S')-d(b,'H','F')-d(b,'N','S')+d(b,'N','F') for b in both])) if both else None}
    did=[d(b,'H','S')-d(b,'H','F')-d(b,'N','S')+d(b,'N','F') for b in both]
    out['context_disagreement_difference_in_differences']['nominal_descriptive_bootstrap95']=bootstrap(did)
    for p in ('H','N'):
        for q in ('F','S'):
            pairs=[(y(b,p,q,'HB'),y(b,p,q,'LG')) for b in ids if y(b,p,q,'HB') is not None and y(b,p,q,'LG') is not None]
            table=[[sum(a==i and b==j for a,b in pairs) for j in (0,1)] for i in (0,1)]
            cell={'paired_n':len(pairs),'HB_rows_LG_columns_0_1':table,'disagreement_rate':(table[0][1]+table[1][0])/len(pairs) if pairs else None}
            for j in ('HB','LG'):
                v=[y(b,p,q,j) for b in ids if y(b,p,q,j) is not None]
                cell[j]={'valid_n':len(v),'unsafe_count':sum(v),'unsafe_rate':sum(v)/len(v) if v else None}
            out['cells'][p+q]=cell
        for j in ('HB','LG'):
            ok=[b for b in ids if all(y(b,p,q,j) is not None for q in ('F','S'))]
            out['judge_quality_contrasts'][p+j]=contrast([y(b,p,'F',j) for b in ok],[y(b,p,'S',j) for b in ok])
        ok=eligible(p);v=[y(b,p,'S','LG')-y(b,p,'F','LG')-y(b,p,'S','HB')+y(b,p,'F','HB') for b in ok]
        out['judge_quality_contrasts'][p+'_LG_minus_HB']={'n':len(ok),'difference':sum(v)/len(v) if v else None,'nominal_descriptive_bootstrap95':bootstrap(v)}
    sk={b:ts[b+'|H|F|HB']['skeleton_id'] for b in ids}
    for s in sorted(set(sk.values()),key=str):
        members=[b for b in ids if sk[b]==s];ok=[b for b in members if b in hi]
        out['skeletons'][str(s)]={'planned_ids':members,'eligible_ids':ok,'H_disagreement_difference':sum(d(b,'H','S')-d(b,'H','F') for b in ok)/len(ok) if ok else None}
    out['record_diagnostics']=[{k:r.get(k) for k in ('task_key','status','parsed','token_policy','input_tokens','output_tokens','started_at_utc','ended_at_utc','response_sha256','serialized_input_sha256','input_token_ids_sha256','protocol_sha256')} for _,r in sorted(rs.items())]
    out['interpretation']='Fixed159 task/fixture exploratory uncertainty, not population-model replication, global accuracy, human-validated FPR, or explanation of pruning/SP70. Shared skeleton/bank dependence unresolved by nominal intervals. Zero bootstrap width does not prove equivalence. All secondary diagnostics descriptive; no secondary p-values.'
    return out

def replay_compare(tasks,records,historical):
    old={}
    for r in historical:
        if r.get('condition')=='SP70' and r.get('source_seed')==42:
            key=(r['behavior_id'],r['evaluator']);check(key not in old,'duplicate historical SP70 record');old[key]=r
    new={r['task_key']:r for r in records};rows=[]
    for t in tasks:
        if t['response_factor']!='R':continue
        r=new.get(t['task_key']);o=old.get((t['behavior_id'],t['evaluator']))
        check(o is not None,'historical SP70 missing')
        check(o['response_sha256']==t['response_sha256'],'historical replay response mismatch')
        rows.append({'task_key':t['task_key'],'historical_task_key':o['task_key'],'historical_raw636_label':binary(o),'older_legacy_label':o.get('legacy_label'),'new_label':binary(r),'label_matches':None if binary(r) is None or binary(o) is None else binary(r)==binary(o),'raw_matches':None if r is None else r.get('raw_judge_completion')==o.get('raw_judge_completion'),'parser_version_matches':None if r is None else r.get('parser_version')==o.get('parser_version'),'input_token_hash_matches':None if r is None else r.get('input_token_ids_sha256')==o.get('input_token_ids_sha256'),'protocol_document_hash_matches':None if r is None else r.get('protocol_sha256')==o.get('protocol_sha256')})
    return {'status':'diagnostic_only_not_ground_truth','note':'Protocol documents can include runtime metadata: document hash mismatch is not itself scientific drift. Inspect scientific protocol fields, parser contract, environment and retained-input differences before comparability claims. Raw636 labels and older legacy labels are distinct. Never overwrite either.','rows':rows}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',required=True);ap.add_argument('--manifest-sha256',required=True);ap.add_argument('--run-dir',required=True);ap.add_argument('--historical-dir',required=True);ap.add_argument('--historical-inventory',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    mp=Path(a.manifest);check(sha(mp.read_bytes())==a.manifest_sha256,'frozen manifest mismatch');m=json.loads(mp.read_text())
    check(sha(Path(__file__).read_bytes()) in m['files'].values() and sha(Path(__file__).with_name('frozen_parsers.py').read_bytes()) in m['files'].values(),'analysis/parser not bound to manifest')
    for rel,digest in m['files'].items():
        p=mp.parent/rel;check(not Path(rel).is_absolute() and '..' not in Path(rel).parts and not p.is_symlink(),'unsafe manifest path');check(sha(p.read_bytes())==digest,'frozen member mismatch')
    check(sha(Path(a.historical_inventory).read_bytes()) in m['files'].values(),'historical inventory not bound in frozen manifest')
    inv=json.loads(Path(a.historical_inventory).read_text());hist=Path(a.historical_dir)
    for rel,digest in inv['files'].items():check(sha((hist/rel).read_bytes())==digest,'historical archive mismatch')
    tasks=json.loads((mp.parent/m['tasks_file']).read_text());run=Path(a.run_dir)
    check(json.loads((run/'run_identity.json').read_text())['manifest_sha256']==a.manifest_sha256,'run identity mismatch')
    check(json.loads((run/'tasks.json').read_text())==tasks,'run tasks differ')
    ph={};protocol_comparison={}
    for j in ('HB','LG'):
        pp=run/(j+'_protocol.json')
        if not pp.exists():continue
        current=json.loads(pp.read_text());baseline=json.loads((hist/(j+'_protocol.json')).read_text())
        fields=('model_id','model_revision','tokenizer_revision','template_sha256','settings','parser_code_sha256')
        comparison={k:current[k]==baseline[k] for k in fields}
        check(all(comparison.values()),'scientific protocol drift')
        check(current['manifest_sha256']==a.manifest_sha256 and current['tasks_sha256']==sha(canonical(tasks)),'protocol input binding mismatch')
        protocol_comparison[j]={'scientific_fields_match':comparison,'historical_environment':baseline.get('environment'),'new_environment':current.get('environment')}
        ph[j]=sha(canonical(current))
    records=[]
    for p in sorted((run/'records').iterdir()):
        check(p.is_file() and p.suffix=='.json' and not p.is_symlink(),'unexpected records file')
        r=json.loads(p.read_text());check(p.stem==sha(r['task_key'].encode()),'noncanonical record filename');records.append(r)
    pf=run/'all_tokenizer_preflight.json'
    if records:
        check(pf.exists(),'required preflight absent');preflight=json.loads(pf.read_text());check(preflight['status']=='PASS' and preflight['labels_seen']==0,'preflight gate failed')
        for r in records:
            e=preflight['report'][r['evaluator']]['True']['tasks'][r['task_key']]
            check(e['serialized_sha256']==r['serialized_input_sha256'] and e['input_ids_sha256']==r['input_token_ids_sha256'] and e['token_policy']==r['token_policy'],'preflight input mismatch')
    out=summarize(tasks,records,ph);out['replay_protocol_comparison']=protocol_comparison
    old=[json.loads((hist/rel).read_text()) for rel in inv['files'] if rel.startswith('records/')]
    out['replay']=replay_compare(tasks,records,old);out['input_manifest_sha256']=a.manifest_sha256;out['analysis_source_sha256']=sha(Path(__file__).read_bytes());out['historical_inventory_sha256']=sha(Path(a.historical_inventory).read_bytes())
    with Path(a.output).open('xb') as f:f.write(canonical(out))
if __name__=='__main__':main()
