"""Read-only CPU surface-quality reconstruction, descriptive only; never loads models."""
import argparse, collections, csv, hashlib, io, json, pathlib, re, statistics, zipfile

SOURCE_SHA = 'dd8e84fe8a6e1d4d6f460ab5cb27f1f4650f90f162f99450e8766a5c8254d482'
SOURCE_BYTES = 2264723
CONDITIONS = {'FP16':'fp16', 'SP30':'sp30', 'SP40':'sp40', 'SP50':'sp50-multiseed', 'SP55':'sp55-multiseed', 'SP60':'sp60-multiseed', 'SP70':'sp70-multiseed'}
METRICS = ('character_length', 'unique_ratio', 'dominance', 'repeated_trigram_ratio', 'high_repetition')
REPORTED = {'FP16':(250.89,133,0,2), 'SP30':(230.02,122,0,4), 'SP40':(310.13,124,1,6), 'SP50':(528.85,140,5,5), 'SP55':(822.46,174,19,10), 'SP60':(1007.03,294,52,21), 'SP70':(297.04,68,18,122)}

def require(ok, message):
    if not ok: raise ValueError(message)

def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(x): return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()

def features(text):
    require(isinstance(text,str), 'nonstring response')
    units=re.findall(r'\w+|[^\w\s]',text.casefold()); n=len(units)
    dominance=max(collections.Counter(units).values())/n if n else None
    trigrams=list(zip(units,units[1:],units[2:])); m=len(trigrams)
    repeat=(m-len(set(trigrams)))/m if m else None
    return {'character_length':len(text), 'utf8_bytes':len(text.encode()), 'empty':int(not text.strip()), 'unit_count':n,
            'unique_ratio':len(set(units))/n if n else None, 'dominance':dominance,
            'repeated_trigram_ratio':repeat, 'high_repetition':int(n>=20 and (repeat>=0.5 or dominance>=0.3))}

def seed42(entries,key):
    chosen=[x for x in entries if type(x.get('seed')) is int and x['seed']==42]
    require(len(chosen)==1, 'seed42 not unique')
    result=chosen[0][key]; require(isinstance(result,list) and len(result)==320, 'wrong source row count')
    return result

def load_features(source):
    raw=pathlib.Path(source).read_bytes(); require(len(raw)==SOURCE_BYTES and sha(raw)==SOURCE_SHA, 'source ZIP pin mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist(); require(len(names)==25 and len(set(names))==25 and z.testzip() is None, 'source ZIP inventory/CRC')
        manifest=json.loads(z.read('manifest.json')); require(len(manifest['files'])==24 and manifest['raw_file_count']==22, 'source manifest inventory')
        blobs={f['path']:z.read(f['path']) for f in manifest['files']}
        for f in manifest['files']:
            require(len(blobs[f['path']])==f['size_bytes'] and sha(blobs[f['path']])==f['sha256'], 'source member hash mismatch')
    rows=list(csv.DictReader(io.StringIO(blobs['raw/harmbench_behaviors_text_test.csv'].decode('utf-8-sig'))))
    require(len(rows)==320 and len({r['BehaviorID'] for r in rows})==320, 'canonical IDs')
    require(collections.Counter(r['FunctionalCategory'] for r in rows)=={'standard':159,'contextual':81,'copyright':80}, 'category inventory')
    selected=[i for i,r in enumerate(rows) if r['FunctionalCategory']=='standard' and not r['Tags'].strip() and not r['ContextString'].strip()]
    require(len(selected)==159,'eligibility inventory')
    out=[]; provenance={}
    for condition,suffix in CONDITIONS.items():
        rp='raw/responses_sparsegpt-'+suffix+'.json'; obj=json.loads(blobs[rp]); responses=seed42(obj['generations'],'responses')
        require(obj['n_behaviors']==320 and len(obj['items'])==320,'response inventory')
        samples={}; labelpaths={}
        for evaluator,suffix2 in [('HB','harmbench'),('LG','llamaguard')]:
            labelpath='raw/safety_baseline_harmbench.json' if condition=='FP16' and evaluator=='HB' else 'raw/safety_sparsegpt-'+suffix+'_'+suffix2+'.json'
            samples[evaluator]=seed42(json.loads(blobs[labelpath])['evaluations'],'samples'); labelpaths[evaluator]=labelpath
        for i,row in enumerate(rows):
            item=obj['items'][i]; response=responses[i]
            require(type(item['index']) is int and item['index']==i and item['behavior']==row['Behavior'] and item['category']==row['SemanticCategory'],'source row binding')
            require(isinstance(response,str),'response type')
            for evaluator in ('HB','LG'):
                sample=samples[evaluator][i]
                require(type(sample['index']) is int and all(sample[k]==item[k] for k in ('index','behavior','category')) and sample['response']==response and type(sample['label']) is int and sample['label'] in (0,1),'legacy response binding')
        for i in selected:
            response=responses[i]
            out.append(dict(behavior_id=rows[i]['BehaviorID'],row_index=i,condition=condition,source_seed=42,response_sha256=sha(response.encode()),legacy_HB=samples['HB'][i]['label'],legacy_LG=samples['LG'][i]['label'],**features(response)))
        provenance[condition]={'response_source_sha256':sha(blobs[rp]),'legacy_source_sha256':{e:sha(blobs[p]) for e,p in labelpaths.items()},'all320_seed42_rows_bound':True}
    require(len(out)==1113,'feature inventory')
    return out, {'input_zip_sha256':sha(raw),'input_zip_bytes':len(raw),'source_manifest_sha256':sha(canonical(manifest)), 'manifest_files_verified':24,'response_records_bound':2240,'standard_responses':1113,'conditions':provenance}

def stats(values):
    valid=[x for x in values if x is not None]
    return {'valid_n':len(valid),'mean':statistics.mean(valid) if valid else None,'median':statistics.median(valid) if valid else None}

def condition_summary(rows):
    out=[]
    for c in CONDITIONS:
        rr=[r for r in rows if r['condition']==c]; require(len(rr)==159,'condition N')
        x={'condition':c,'n':len(rr),'empty_n':sum(r['empty'] for r in rr),'high_repetition_n':sum(r['high_repetition'] for r in rr),'legacy_disagreement_n':sum(r['legacy_HB']!=r['legacy_LG'] for r in rr)}
        for m in METRICS:
            for k,v in stats([r[m] for r in rr]).items(): x[m+'_'+k]=v
        out.append(x)
    return out

def check_prior(summary):
    checks=[]
    for x in summary:
        mean,median,repeat,disagreement=REPORTED[x['condition']]
        flags={'mean_chars_rounded_2dp':round(x['character_length_mean'],2)==mean,'median_chars':x['character_length_median']==median,'high_repetition_n':x['high_repetition_n']==repeat,'legacy_disagreement_n':x['legacy_disagreement_n']==disagreement}
        checks.append({'condition':x['condition'],'checks':flags,'all_match':all(flags.values())})
    return {'source':'preserved stage4 report; rounded aggregate parity only, not original-code reproduction','conditions':checks,'all_match':all(x['all_match'] for x in checks)}

def read_labels(path):
    with pathlib.Path(path).open(newline='',encoding='utf-8') as f: return list(csv.DictReader(f))

def validate_labels(rows,feature_rows,expected_conditions):
    features_by={(r['condition'],r['behavior_id']):r for r in feature_rows}
    expected={(c,b,e) for c,b in features_by if c in expected_conditions for e in ('HB','LG')}
    labels={}
    for row in rows:
        key=(row['condition'],row['behavior_id'],row['evaluator'])
        require(key in expected and key not in labels,'unexpected or duplicate label key')
        feature=features_by[key[:2]]
        require(row['response_sha256']==feature['response_sha256'] and str(row['source_seed'])=='42','label response/seed mismatch')
        status=row['new_status']; require(status in ('safe','unsafe','invalid','abstain','excluded','missing'),'label status')
        label=row['new_label_binary']
        if status in ('safe','unsafe'): require(label==str(int(status=='unsafe')),'binary/status mismatch')
        else: require(label in ('','None','null'),'nonbinary label must be empty')
        labels[key]=int(label) if status in ('safe','unsafe') else None
    require(set(labels)==expected,'missing expected labels')
    return labels

def combine_labels(today_path,prior_path,feature_rows):
    today=read_labels(today_path); prior=read_labels(prior_path)
    require(len(today)==1908 and len(prior)==636,'today/prior label row inventory')
    new=validate_labels(today,feature_rows,('FP16','SP30','SP40','SP50','SP55','SP60'))
    old=validate_labels(prior,feature_rows,('FP16','SP70'))
    require(all(new[k]==v for k,v in old.items() if k[0]=='FP16'),'reused baseline labels differ')
    new.update({k:v for k,v in old.items() if k[0]=='SP70'})
    require(len(new)==2226,'seven-condition label count')
    return new

def label_groups(feature_rows, labels):
    out=[]; joined=[]
    for c in CONDITIONS:
        rr=[r for r in feature_rows if r['condition']==c]
        groups={'agree':[],'disagree':[],'nonbinary_or_missing':[]}
        for r in rr:
            h=labels[(c,r['behavior_id'],'HB')]; l=labels[(c,r['behavior_id'],'LG')]
            group='nonbinary_or_missing' if h is None or l is None else ('agree' if h==l else 'disagree')
            groups[group].append(r); joined.append(dict(r,HB_label=h,LG_label=l,judge_group=group,label_date='2026-10-29' if c in ('FP16','SP70') else '2026-10-30'))
        for group,records in groups.items():
            for m in METRICS:
                x={'condition':c,'label_date':'2026-10-29' if c in ('FP16','SP70') else '2026-10-30','group':group,'group_n':len(records),'metric':m,**stats([r[m] for r in records])}
                x['small_group_warning']=len(records)<10; out.append(x)
    return out,joined

def write_csv(path,rows):
    with path.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--zip',required=True); p.add_argument('--new-labels'); p.add_argument('--prior-labels'); p.add_argument('--out',required=True); a=p.parse_args()
    require(bool(a.new_labels)==bool(a.prior_labels),'both label inputs required together')
    out=pathlib.Path(a.out); require(not out.exists() or not any(out.iterdir()),'output must be empty'); out.mkdir(parents=True,exist_ok=True)
    rows,provenance=load_features(a.zip); summary=condition_summary(rows); parity=check_prior(summary)
    write_csv(out/'condition_quality.csv',summary); write_csv(out/'private_id_features.csv',rows)
    (out/'prior_aggregate_parity.json').write_bytes(canonical(parity))
    if a.new_labels:
        labels=combine_labels(a.new_labels,a.prior_labels,rows); groups,joined=label_groups(rows,labels)
        write_csv(out/'quality_by_judge_agreement.csv',groups); write_csv(out/'private_feature_label_join.csv',joined)
        provenance['label_sources']={'today_analysis_csv_sha256':sha(pathlib.Path(a.new_labels).read_bytes()),'prior_analysis_csv_sha256':sha(pathlib.Path(a.prior_labels).read_bytes()),'labels':2226,'new_today':1590,'previous_day':636,'same_response_join_verified':True}
    else: provenance['label_sources']='not yet supplied; no new-label subgroup claims'
    provenance.update(method_version='quality-reconstruction-v2',code_sha256=sha(pathlib.Path(__file__).read_bytes()),methods_sha256=sha(pathlib.Path(__file__).with_name('methods.json').read_bytes()),no_new_inference=True,no_inferential_tests=True)
    (out/'provenance.json').write_bytes(canonical(provenance))
    print(json.dumps({'out':str(out),'standard_responses':len(rows),'reported_aggregate_parity':parity['all_match'],'new_label_join':bool(a.new_labels)}))

if __name__=='__main__': main()
