"""Read-only local provenance audit. Never executes inspected source or model code."""
import csv,io,json,hashlib,pathlib,zipfile,collections,datetime
import argparse
if not __debug__:
 raise RuntimeError("Validation requires assertions enabled; do not use -O or -OO.")
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--archive',required=True,type=pathlib.Path)
ap.add_argument('--prior-audit',required=True,type=pathlib.Path)
ap.add_argument('--candidate-source',required=True,action='append',type=pathlib.Path,help='Repeat exactly three times for the three previously audited code files.')
ap.add_argument('--notebook',required=True,type=pathlib.Path)
ap.add_argument('--restored-run',required=True,type=pathlib.Path)
ap.add_argument('--log',required=True,type=pathlib.Path)
ap.add_argument('--output',required=True,type=pathlib.Path)
a=ap.parse_args()
if len(a.candidate_source)!=3:ap.error('Exactly three --candidate-source inputs are required.')
a.output.mkdir(parents=True,exist_ok=True)
OUT=a.output
def sha(b):return hashlib.sha256(b).hexdigest()
def entry(p):return {'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}
e={'audit_time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'bounded local historical context provenance; no inference, no external fetch, no source modification','sources':[]}
prior=json.loads(a.prior_audit.read_text());e['prior_audit']=entry(a.prior_audit)
archive=a.archive;e['archive']=entry(archive)
assert e['archive']['sha256']==prior['input_archive_sha256']
with zipfile.ZipFile(archive) as z:
 rows=list(csv.DictReader(io.StringIO(z.read('raw/harmbench_behaviors_text_test.csv').decode('utf-8-sig')))); indices=[i for i,r in enumerate(rows) if r['FunctionalCategory']=='contextual'];assert len(rows)==320 and len({r['BehaviorID'] for r in rows})==320;e['contextual_items']=len(indices);e['contextual_nonempty_context']=sum(bool(rows[i]['ContextString'].strip()) for i in indices)
 e['csv_sha256']=sha(z.read('raw/harmbench_behaviors_text_test.csv'));e['responses']=[]
 for n in z.namelist():
  if not n.startswith('raw/responses_'):continue
  b=z.read(n);d=json.loads(b); gs=d['generations'];its=d['items'];assert len(its)==320 and all(len(g['responses'])==320 for g in gs);assert all(it['index']==i and it['behavior']==rows[i]['Behavior'] and it['category']==rows[i]['SemanticCategory'] for i,it in enumerate(its))
  e['responses'].append({'archive_member':n,'sha256':sha(b),'top_level_keys':sorted(d),'item_keys':sorted(set(k for it in its for k in it)),'generation_keys':sorted(set(k for g in gs for k in g)),'seeds':[g['seed'] for g in gs],'contextual_seed42_count':sum(len(indices) for g in gs if g['seed']==42),'contextual_all_seed_records':sum(len(indices) for g in gs),'all_seed_response_vectors_identical':all(g['responses']==gs[0]['responses'] for g in gs),'all_items_exact_csv_match':True})
 e['contextual_seed42_total']=sum(x['contextual_seed42_count'] for x in e['responses']);e['contextual_all_seed_records_total']=sum(x['contextual_all_seed_records'] for x in e['responses'])
 e['contextual_index_map']=[{'row_index':i,'behavior_id':rows[i]['BehaviorID'],'context_sha256':sha(rows[i]['ContextString'].encode())} for i in indices]
e['candidate_sources']=[]
expected={x['sha256']:x for x in prior['generator_sources']}
assert len(expected)==3, 'Prior audit must contain three distinct source hashes'
assert {sha(p.read_bytes()) for p in a.candidate_source}==set(expected), 'Candidate source inventory differs from prior audit'
for p in a.candidate_source:
 b=p.read_bytes();old=expected[sha(b)];e['candidate_sources'].append({**entry(p),'matches_prior':True,'ContextString_occurrences':b.count(b'ContextString'),'format_prompt_span':old['format_prompt_span'],'generation_lines':old['generation_lines']})
nb=a.notebook;d=json.loads(nb.read_text());cells=[]
for i,c in enumerate(d['cells']):
 s=''.join(c.get('source',[]))
 if '02_eval_safety.py' in s or 'ContextString' in s or 'format_prompt' in s:
  cells.append({'zero_based_index':i,'cell_type':c['cell_type'],'execution_count':c.get('execution_count'),'output_count':len(c.get('outputs',[])),'ContextString_occurrences':s.count('ContextString'),'reuse_responses_flag':'--reuse-responses' in s,'source_sha256':sha(s.encode())})
e['notebook']={**entry(nb),'relevant_cells':cells,'all_relevant_cells_have_no_outputs':all(c['output_count']==0 for c in cells),'all_relevant_code_execution_counts_null':all(c['execution_count'] is None for c in cells if c['cell_type']=='code')}
e['restored_protocols']=[]
for p in sorted(a.restored_run.glob('*_protocol.json')):
 d=json.loads(p.read_text());e['restored_protocols'].append({**entry(p),'scope':d['inputs']['scope'],'excluded_counts':d['inputs']['excluded_counts'],'selected_ids_count':len(d['inputs']['selected_id_order'])})
records=list((a.restored_run/'records').glob('*.json')); cats=collections.Counter();ks=collections.Counter();task_keys=set();contextids={rows[i]['BehaviorID'] for i in indices}
for p in records:
 d=json.loads(p.read_text());assert d['task_key'] not in task_keys;task_keys.add(d['task_key']);cats[d['evaluator']]+=1;ks.update(d.keys());assert d['behavior_id'] not in contextids
# Persist per-file hashes, not prompt contents.
e['restored_records']={'count':len(records),'evaluators':dict(cats),'contextual_record_count':0,'key_counts':dict(ks),'inventory':[entry(p) for p in sorted(records)],'interpretation':'October 29 judge-input evidence for standard159; not historical target-generation input evidence'}
log_text=a.log.read_text()
assert '2026-07-06 17:02:28,144' in log_text and '2026-07-07 06:49:29,242' in log_text, 'Unexpected historical log range'
assert sha(a.log.read_bytes())=='90c5b2665bcc058fc8aed8681484050a8441e4542ca0799e051a1390fb274bef', 'Historical log hash mismatch'
e['log']={**entry(a.log),'first_timestamp':'2026-07-06 17:02:28,144','last_timestamp':'2026-07-07 06:49:29,242','historical_context_code_output_binding_found':False}
e['conclusion']={'new_historical_target_prompt_binding_found':False,'historical_context_omission_proved':False,'inspected_candidate_sources_omit_context':True,'main_analysis_recommendation':'Keep contextual81 excluded; do not retroactively validate generation by changing judge prompt.'}
assert len(e['responses'])==7 and e['contextual_items']==81 and e['contextual_nonempty_context']==81
assert e['contextual_seed42_total']==567 and e['contextual_all_seed_records_total']==1053
assert all(x['all_seed_response_vectors_identical'] for x in e['responses'])
assert {x['sha256'] for x in e['responses']}=={x['sha256'] for x in prior['response_schema_audit']}
assert len(cells)==56 and e['notebook']['all_relevant_cells_have_no_outputs'] and e['notebook']['all_relevant_code_execution_counts_null']
assert len(records)==636 and dict(cats)=={'HB':318,'LG':318}
assert len(e['restored_protocols'])==2 and {p.name for p in a.restored_run.glob('*_protocol.json')}=={'HB_protocol.json','LG_protocol.json'}
assert all(p['selected_ids_count']==159 and p['excluded_counts']=={'contextual':81,'copyright':80} and p['scope']=='new-standard159-v1; all eligible standard IDs; not historical judge reproduction' for p in e['restored_protocols'])
assert all(x['ContextString_occurrences']==0 for x in e['candidate_sources'])
(OUT/'evidence_inventory.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'responses':len(e['responses']),'seed42':e['contextual_seed42_total'],'all_seed_records':e['contextual_all_seed_records_total'],'notebook_relevant_cells':len(cells),'restored_records':len(records),'status':'PASS'},indent=2))
