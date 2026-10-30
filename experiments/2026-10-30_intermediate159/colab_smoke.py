"""Private Colab standard159 five-level judge-only runner; no target model generation or credentials."""
from pathlib import Path
import argparse, collections, csv, datetime, gc, hashlib, importlib.metadata, io, json, os, sys, uuid, zipfile

ZIP_SHA='dd8e84fe8a6e1d4d6f460ab5cb27f1f4650f90f162f99450e8766a5c8254d482'
MODELS={'LG':('meta-llama/Llama-Guard-3-8B','7327bd9f6efbbe6101dc6cc4736302b3cbb6e425'),
        'HB':('cais/HarmBench-Llama-2-13b-cls','bda705349d1144fa618770bea64d99ce54e3835b')}
HB_TEMPLATE_SHA='6e40c2f76a74aa2dc38d83b557220017311e29c249d938a256c3f0a2d87f0cac'
HB_TEMPLATE_PATH=Path(__file__).with_name('HB_standard_template.txt')
HB_TEMPLATE=HB_TEMPLATE_PATH.read_text(encoding='utf8')
ANALYSIS_PLAN_SHA='473ecba7402b70a171b0589e8eb761cbe802330bd6de4d717a31e948aa94a5c7'
ANALYSIS_PLAN_PATH=Path(__file__).with_name('analysis_plan.json')
BASELINE_ARCHIVE_SHA='c97df90714f89e809343c434c474b5a5a15813a0de15e082330353ae3c955957'
BASELINE_FULL_CHECKPOINT_SHA='1cc2e8398a903523ca6c8673cc87e83d3abc3cd1d465b4d335041718d4085569'
BASELINE_PACKAGES={'torch':'2.11.0+cu130','transformers':'5.20.2','accelerate':'1.15.0'}
EXECUTION_CUTOFF_UTC='2026-10-30T08:00:00+00:00'
STANDARD_IDS=159
PER_JUDGE=159
TOTAL_TASKS=318
CONDITIONS={"SP30":"sp30","SP40":"sp40","SP50":"sp50-multiseed","SP55":"sp55-multiseed","SP60":"sp60-multiseed"}
CONTEXT={'stage':'input_validation','judge':None,'model_id':None,'revision':None}

def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(x): return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8')
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p): return json.loads(Path(p).read_text(encoding='utf8'))

def freeze(path,obj):
    """Atomic immutable commit; identical replay skips and any conflict stops."""
    path=Path(path); data=canonical(obj); path.parent.mkdir(parents=True,exist_ok=True)
    guard=path.with_name(path.name+'.commitlock')
    fd=os.open(guard,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.close(fd)
    try:
        if path.exists():
            if path.read_bytes()!=data: raise ValueError('immutable output conflict: '+path.name)
            return False
        temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
        with temp.open('xb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        # Exclusive cooperative commit lock and complete-file atomic replacement.
        # Does not claim protection against unrelated programs ignoring this lock.
        try:
            if path.exists(): raise ValueError('unexpected destination appeared')
            os.replace(temp,path)
        finally:
            if temp.exists():temp.unlink()
    finally:
        guard.unlink()
    return True

def commit_record(path,record):
    record=dict(record,content_sha256=sha(canonical(record)))
    return freeze(path,record)

def verify_record(record,task,protocol_sha):
    content={k:v for k,v in record.items() if k!='content_sha256'}
    if record.get('content_sha256')!=sha(canonical(content)): raise ValueError('stored record checksum mismatch')
    if record['task_sha256']!=sha(canonical(task)) or record['protocol_sha256']!=protocol_sha: raise ValueError('resume task/protocol conflict')
    for k in ('task_key','behavior_id','condition','evaluator','response_sha256','legacy_label'):
        if record[k]!=task[k]:raise ValueError('record task binding mismatch')
    if record['status'] not in ('judged','excluded'):raise ValueError('unexpected record status')
    raw=record.get('raw_judge_completion')
    if raw is not None:
        if sha(raw.encode())!=record['raw_judge_sha256'] or record['parsed']!=parser(raw,task['evaluator']): raise ValueError('stored raw/parser mismatch')
        if sha(record['raw_decoded_with_special_tokens'].encode())!=record['raw_decoded_with_special_tokens_sha256']:raise ValueError('full decoded raw hash mismatch')
        if record['status']!='judged' or len(record['output_token_ids'])!=record['output_tokens']:raise ValueError('judged record schema mismatch')
    elif record['status']!='excluded' or not record['token_policy'].get('exclude_reason'):raise ValueError('excluded record reason missing')

def records_checked(out,tasks):
    expected={sha(t['task_key'].encode())+'.json':t for t in tasks}; result=[]
    for p in sorted((out/'records').glob('*.json')):
        if p.name not in expected:raise ValueError('unexpected result file outside fixed task membership')
        task=expected[p.name]; protocol=read(out/(task['evaluator']+'_protocol.json')); r=read(p)
        verify_record(r,task,sha(canonical(protocol))); result.append(r)
    return result

def seed42(entries,key):
    found=[x for x in entries if type(x.get('seed')) is int and x['seed']==42]
    if len(found)!=1: raise ValueError('missing or duplicate seed42')
    return found[0][key]

class DeadlineReached(RuntimeError):
    """Authorization window ended; preserve in-flight completion, start no new work."""

def execution_utcnow():
    return datetime.datetime.now(datetime.timezone.utc)

def require_before_cutoff(stage):
    if execution_utcnow()>=datetime.datetime.fromisoformat(EXECUTION_CUTOFF_UTC):
        CONTEXT.update(stage='cutoff',blocked_stage=stage)
        raise DeadlineReached('08:00UTC execution cutoff; no new model load or record inference')


def inputs(zip_path,condition):
    if condition not in CONDITIONS: raise ValueError("unknown condition; exactly SP30/SP40/SP50/SP55/SP60 permitted")
    if ANALYSIS_PLAN_SHA is None: raise ValueError("prospective analysis plan not frozen")
    if sha(ANALYSIS_PLAN_PATH.read_bytes())!=ANALYSIS_PLAN_SHA: raise ValueError("prospective analysis plan bytes mismatch")
    if sha(HB_TEMPLATE_PATH.read_bytes())!=HB_TEMPLATE_SHA: raise ValueError('official HB template bytes mismatch')
    data=Path(zip_path).read_bytes()
    if len(data)!=2264723 or sha(data)!=ZIP_SHA: raise ValueError('verified ZIP size/SHA mismatch')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names=z.namelist()
        if len(names)!=25 or len(set(names))!=25: raise ValueError('ZIP inventory mismatch')
        manifest_bytes=z.read('manifest.json');manifest=json.loads(manifest_bytes); files=manifest['files']
        if len(files)!=24 or manifest['raw_file_count']!=22: raise ValueError('manifest inventory mismatch')
        blobs={f['path']:z.read(f['path']) for f in files}
        for f in files:
            if len(blobs[f['path']])!=f['size_bytes'] or sha(blobs[f['path']])!=f['sha256']:
                raise ValueError('manifest hash mismatch')
    rows=list(csv.DictReader(io.StringIO(blobs['raw/harmbench_behaviors_text_test.csv'].decode('utf-8-sig'))))
    if len(rows)!=320 or len({r['BehaviorID'] for r in rows})!=320 or len({r['Behavior'] for r in rows})!=317: raise ValueError('canonical inventory')
    return bind_condition_tasks(rows,blobs,manifest_bytes,manifest,condition)

def bind_condition_tasks(rows,blobs,manifest_bytes,manifest,condition):
    """Verify all320 rows in all five conditions/all available seeds; judge seed42 only."""
    if condition not in CONDITIONS: raise ValueError('unknown condition')
    if len(rows)!=320 or len({r['BehaviorID'] for r in rows})!=320 or len({r['Behavior'] for r in rows})!=317: raise ValueError('canonical inventory')
    categories=collections.Counter(r['FunctionalCategory'] for r in rows)
    shapes=collections.Counter((r['FunctionalCategory'],bool(r['Tags'].strip()),bool(r['ContextString'].strip())) for r in rows)
    if categories!={'standard':159,'contextual':81,'copyright':80} or shapes!={('standard',False,False):159,('contextual',True,True):81,('copyright',True,False):80}:
        raise ValueError('canonical category/exclusion inventory mismatch')
    picked=sorted(((i,row) for i,row in enumerate(rows) if row['FunctionalCategory']=='standard' and not row['Tags'].strip() and not row['ContextString'].strip()),key=lambda x:(sha(('42:'+x[1]['BehaviorID']).encode()),x[1]['BehaviorID']))
    if len(picked)!=STANDARD_IDS: raise ValueError('full standard inventory')
    selected=None; inventories={}
    for current,suffix in CONDITIONS.items():
        expected_seeds=[42] if current in ('SP30','SP40') else [42,123,2024]
        rp='raw/responses_sparsegpt-'+suffix+'.json';obj=json.loads(blobs[rp])
        if len(obj['items'])!=320 or obj['n_behaviors']!=320 or obj['seeds']!=expected_seeds: raise ValueError('response metadata inventory')
        def arrays(entries,key):
            if (len(entries)!=len(expected_seeds) or any(type(x.get('seed')) is not int for x in entries)
                or sorted(x['seed'] for x in entries)!=expected_seeds): raise ValueError('seed inventory mismatch')
            result={x['seed']:x[key] for x in entries}
            if any(not isinstance(a,list) or len(a)!=320 for a in result.values()): raise ValueError('row count mismatch')
            return result
        generations=arrays(obj['generations'],'responses'); samples={}; sources={}
        for evaluator,j in [('LG','llamaguard'),('HB','harmbench')]:
            jp='raw/safety_sparsegpt-'+suffix+'_'+j+'.json'
            samples[evaluator]=arrays(json.loads(blobs[jp])['evaluations'],'samples');sources[evaluator]=jp
        for i,row in enumerate(rows):
            item=obj['items'][i]
            if type(item['index']) is not int or item['index']!=i or item['behavior']!=row['Behavior'] or item['category']!=row['SemanticCategory']: raise ValueError('canonical correspondence')
            for seed in expected_seeds:
                response=generations[seed][i]
                if not isinstance(response,str): raise ValueError('response must be string')
                for evaluator in ('LG','HB'):
                    sample=samples[evaluator][seed][i]
                    if type(sample['index']) is not int or any(sample[k]!=item[k] for k in ('index','behavior','category')) or sample['response']!=response or type(sample['label']) is not int or sample['label'] not in (0,1): raise ValueError('stored label correspondence')
        inventories[current]={'available_seeds':expected_seeds,'evaluated_seed':42,'not_evaluated_seeds':[x for x in expected_seeds if x!=42],'verified_rows_per_seed':320,'response_source_sha256':sha(blobs[rp]),'legacy_source_sha256':{e:sha(blobs[jp]) for e,jp in sources.items()}}
        if current==condition:selected=(rp,generations[42],sources,{e:samples[e][42] for e in ('LG','HB')})
    rp,responses,sources,samples=selected
    tasks=[]
    for i,row in picked:
        response=responses[i]
        for evaluator in ('LG','HB'):
            jp=sources[evaluator];sample=samples[evaluator][i]
            tasks.append({'task_key':'|'.join([row['BehaviorID'],condition,evaluator,'42']),'behavior_id':row['BehaviorID'],'row_index':i,'condition':condition,'evaluator':evaluator,'source_seed':42,'behavior':row['Behavior'],'response':response,'response_sha256':sha(response.encode()),'legacy_label':sample['label'],'legacy_source_sha256':sha(blobs[jp]),'response_source_sha256':sha(blobs[rp])})
    if len(tasks)!=TOTAL_TASKS or len({x['task_key'] for x in tasks})!=TOTAL_TASKS or collections.Counter((x['condition'],x['evaluator']) for x in tasks)!={(condition,e):STANDARD_IDS for e in ('HB','LG')}:
        raise ValueError('condition task inventory')
    return tasks,{'zip_sha256':ZIP_SHA,'source_manifest_bytes_sha256':sha(manifest_bytes),'canonical_manifest_sha256':sha(canonical(manifest)),'raw_files_verified':22,'manifest_files_verified':24,'standard_pool':159,'id_binding':'canonical CSV row-derived; not native source IDs',
        'scope':'new-standard159-levels-v1; one condition per immutable run; not historical judge reproduction','condition':condition,'planned_conditions':list(CONDITIONS),'planned_new_judgments_all_conditions':1590,'canonical_rows':320,'canonical_behavior_unique_texts':317,'category_counts':dict(categories),'excluded_counts':{'contextual':81,'copyright':80},'selected_ids':STANDARD_IDS,'expected_per_judge':PER_JUDGE,'expected_total_tasks':TOTAL_TASKS,'verified_all_conditions_all_available_seeds':inventories,'selection_order':'ascending SHA256(UTF8("42:" + BehaviorID)), then BehaviorID; all159, no sampling','selected_id_order':[row['BehaviorID'] for _,row in picked]}

def parser(raw,e):
    from research_parsers import parse_judgment
    cfg={'contract':'harmbench-official-lower-no-strip'} if e=='HB' else {'contract':'lg3-8b-lines-v1','categories':[f'S{i}' for i in range(1,15)]}
    return parse_judgment(raw,e,cfg)

def gpu_preflight(precision,judges):
    CONTEXT.update(stage='gpu_package_preflight')
    import torch
    packages=['torch','transformers','accelerate']+(['bitsandbytes'] if precision=='nf4' else [])
    versions={p:importlib.metadata.version(p) for p in packages}
    if versions!=BASELINE_PACKAGES: raise RuntimeError('baseline package version drift; stop for reviewed compatibility decision; no installation performed')
    if not torch.cuda.is_available(): raise RuntimeError('CUDA GPU is not connected; no model downloaded')
    free,total=torch.cuda.mem_get_info(); need=(31 if 'HB' in judges else 18) if precision=='fp16' else 11
    CONTEXT.update(required_free_gib=need,observed_free_gib=round(free/1024**3,3))
    if free<need*1024**3: raise RuntimeError(f'insufficient free GPU memory: requires conservative {need} GiB for {precision}; no paid runtime switch or package installation performed')
    return {'packages':versions,'cuda':torch.version.cuda,'device':torch.cuda.get_device_name(0),'total_memory':total,'precision':precision}

def render(task,e,tok):
    if e=='HB':
        tok.truncation_side='right'
        clip_ids=tok.encode(task['response'],max_length=512,truncation=True)
        clipped=tok.decode(clip_ids,skip_special_tokens=True)
        text=HB_TEMPLATE.format(behavior=task['behavior'],generation=clipped)
        tok.truncation_side='left'
        ids=tok.encode(text,max_length=2048,truncation=True)
        return text,ids,{'response_clip_tokens':len(clip_ids),'clipped_response_sha256':sha(clipped.encode()),'full_prompt_left_truncated':len(tok.encode(text))>2048}
    messages=[{'role':'user','content':task['behavior']},{'role':'assistant','content':task['response']}]
    text=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
    ids=tok.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,return_dict=False)
    if type(ids) is not list or not ids or any(type(token_id) is not int or token_id < 0 for token_id in ids):
        raise TypeError('LG tokenizer must return a nonempty flat list of nonnegative integer token IDs')
    if len(ids)>8192: return text,ids,{'exclude_reason':'LG_input_over_8192_no_truncation','apply_chat_template_return_dict':False,'input_ids_contract':'nonempty flat list[int]'}
    return text,ids,{'truncation':'none; conversation user behavior then assistant stored response','apply_chat_template_return_dict':False,'input_ids_contract':'nonempty flat list[int]'}

def inference(args,tasks,provenance,environment,auth_token=None):
    if auth_token is not None and (args.judge != 'LG' or not isinstance(auth_token,str) or not auth_token):
        raise ValueError('explicit nonempty in-memory token is permitted only for LG')
    require_before_cutoff('inference_stage_start')
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer,BitsAndBytesConfig,set_seed
    out=Path(args.out)
    for e in ('HB','LG'):
        if args.judge!='both' and args.judge!=e: continue
        name,revision=MODELS[e]
        CONTEXT.update(stage='tokenizer_load',judge=e,model_id=name,revision=revision)
        require_before_cutoff('tokenizer_load')
        tok=AutoTokenizer.from_pretrained(name,revision=revision,token=(auth_token if e=='LG' and auth_token is not None else False),trust_remote_code=False)
        template=HB_TEMPLATE if e=='HB' else tok.chat_template
        if not isinstance(template,str) or not template: raise ValueError('missing actual tokenizer template')
        from research_parsers import VERSION
        protocol={'baseline_archive_sha256':BASELINE_ARCHIVE_SHA,'baseline_full_checkpoint_sha256':BASELINE_FULL_CHECKPOINT_SHA,'analysis_plan_sha256':ANALYSIS_PLAN_SHA,'analysis_plan_status':'prospective locally frozen exploratory plan; not preregistered','protocol':'new-standard159-levels-v1; not historical judge reproduction','condition':args.condition,'auth_mode':'ephemeral_explicit_read_token' if auth_token is not None else 'anonymous','target_research_model':'Meta-Llama-3-8B-Instruct; saved responses only, not loaded','model_execution_authorized':True,'model_id':name,'model_revision':revision,'tokenizer_revision':revision,'template_sha256':sha(template.encode()),'template':template,'environment':environment,'settings':{'seed':42,'do_sample':False,'temperature_inactive':0,'top_p_inactive':1,'max_new_tokens':1 if e=='HB' else 128,'dtype':'float16','quantization':'none' if args.precision=='fp16' else 'nf4,double_quant,float16_compute'},'token_policy':'HB right clip generation512 encode/decode, full prompt left2048; LG no truncate cap8192','parser_version':VERSION,'parser_code_sha256':sha(Path(__file__).with_name('research_parsers.py').read_bytes()),'runner_code_sha256':sha(Path(__file__).read_bytes()),'inputs':provenance,'tasks_sha256':sha(canonical(tasks)),'judge':e}
        protocol_sha=sha(canonical(protocol)); freeze(out/(e+'_protocol.json'),protocol)
        selected=[t for t in tasks if t['evaluator']==e]; pending=[]
        for t in selected:
            path=out/'records'/(sha(t['task_key'].encode())+'.json')
            if path.exists():
                old=read(path)
                verify_record(old,t,protocol_sha)
                continue
            pending.append((t,path))
        if not pending: continue
        quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.float16) if args.precision=='nf4' else None
        CONTEXT.update(stage='judge_weight_load')
        require_before_cutoff('judge_weight_load')
        model=AutoModelForCausalLM.from_pretrained(name,revision=revision,token=(auth_token if e=='LG' and auth_token is not None else False),trust_remote_code=False,use_safetensors=True,torch_dtype=torch.float16,device_map={'':0},quantization_config=quant)
        loaded_commit=getattr(model.config,'_commit_hash',None)
        if loaded_commit is not None and loaded_commit!=revision:raise ValueError('loaded model commit mismatch')
        model.eval()
        for task,path in pending:
            require_before_cutoff('before_record')
            text,ids,token_policy=render(task,e,tok)
            base={'task_key':task['task_key'],'task_sha256':sha(canonical(task)),'protocol_sha256':protocol_sha,'behavior_id':task['behavior_id'],'condition':task['condition'],'evaluator':e,'source_seed':42,'judge_seed':42,'response_sha256':task['response_sha256'],'legacy_label':task['legacy_label'],'model_revision':revision,'observed_config_commit':loaded_commit,'tokenizer_revision':revision,'template_sha256':protocol['template_sha256'],'serialized_input_before_prompt_truncation':text,'serialized_input_sha256':sha(text.encode()),'input_token_ids':ids,'input_token_ids_sha256':sha(canonical(ids)),'input_tokens':len(ids),'token_policy':token_policy,'parser_version':VERSION}
            if 'exclude_reason' in token_policy:
                commit_record(path,dict(base,status='excluded',raw_judge_completion=None,raw_judge_sha256=None,started_at_utc=None,ended_at_utc=None,output_tokens=0)); continue
            require_before_cutoff('before_generate')
            set_seed(42); tensor=torch.tensor([ids],device='cuda'); started=utc()
            CONTEXT.update(stage='judge_inference')
            with torch.inference_mode():
                result=model.generate(input_ids=tensor,attention_mask=torch.ones_like(tensor),do_sample=False,max_new_tokens=protocol['settings']['max_new_tokens'],pad_token_id=tok.eos_token_id)
            torch.cuda.synchronize(); ended=utc(); continuation=result[0,len(ids):].tolist()
            raw=tok.decode(continuation,skip_special_tokens=True,clean_up_tokenization_spaces=False)
            fullraw=tok.decode(continuation,skip_special_tokens=False,clean_up_tokenization_spaces=False)
            parsed=parser(raw,e);binary={'safe':0,'unsafe':1}.get(parsed['label'])
            commit_record(path,dict(base,status='judged',raw_judge_completion=raw,raw_judge_sha256=sha(raw.encode()),raw_decoded_with_special_tokens=fullraw,raw_decoded_with_special_tokens_sha256=sha(fullraw.encode()),decoder_settings={'parser_input_skip_special_tokens':True,'full_raw_skip_special_tokens':False,'clean_up_tokenization_spaces':False,'strip':False},output_token_ids=continuation,output_tokens=len(continuation),started_at_utc=started,ended_at_utc=ended,parsed=parsed,new_label_binary=binary,legacy_changed=None if binary is None else binary!=task['legacy_label']))
        del model,tok; gc.collect(); torch.cuda.empty_cache()
    CONTEXT.update(stage='final_record_validation')
    records=records_checked(out,tasks)
    selected_records=[r for r in records if args.judge=='both' or r['evaluator']==args.judge]
    counts=collections.Counter(r.get('parsed',{}).get('label',r['status']) for r in selected_records)
    expected_count=TOTAL_TASKS if args.judge=='both' else PER_JUDGE;judged=sum(r['status']=='judged' for r in selected_records);valid=counts['safe']+counts['unsafe']
    freeze(out/('completion_'+args.judge+'.json'),{'task_accounted_complete':len(selected_records)==expected_count,'requested_evaluation_complete':judged==expected_count,'requested_judge':args.judge,'records':len(selected_records),'judged':judged,'valid':valid,'invalid':counts['invalid'],'abstain':counts['abstain'],'excluded':counts['excluded'],'counts':dict(counts),'positive_rate_all_judged':counts['unsafe']/judged if judged else None,'positive_rate_valid':counts['unsafe']/valid if valid else None,'mode':'new raw judging only; legacy labels retained separately'})

def main(auth_token=None):
    p=argparse.ArgumentParser();p.add_argument('--condition',required=True,choices=list(CONDITIONS));p.add_argument('--zip',required=True);p.add_argument('--out',required=True);p.add_argument('--judge',choices=['LG','HB'],default='HB');p.add_argument('--precision',choices=['fp16'],default='fp16');p.add_argument('--validate-input-only',action='store_true');p.add_argument('--preflight-only',action='store_true');args=p.parse_args()
    if auth_token is not None and (args.judge != 'LG' or not isinstance(auth_token,str) or not auth_token):
        raise ValueError('explicit nonempty in-memory token is permitted only for LG')
    out=Path(args.out)
    if not args.validate_input_only and (not out.resolve().is_relative_to(Path('/content')) or out.resolve().is_relative_to(Path('/content/drive'))):
        raise ValueError('GPU execution output must be private ephemeral /content outside /content/drive')
    out.mkdir(parents=True,exist_ok=True)
    lock=out/'.lock'; fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        os.write(fd,str(os.getpid()).encode());os.close(fd)
        tasks,provenance=inputs(args.zip,args.condition)
        freeze(out/'tasks.json',tasks);freeze(out/'input_provenance.json',provenance)
        if args.validate_input_only: print(json.dumps({'input_validation':'pass','tasks':TOTAL_TASKS,'models_executed':0}));return
        require_before_cutoff('gpu_package_preflight')
        environment=gpu_preflight(args.precision,['LG','HB'] if args.judge=='both' else [args.judge])
        freeze(out/'environment.json',environment)
        if args.preflight_only: print(json.dumps(environment));return
        inference(args,tasks,provenance,environment,auth_token=auth_token)
        print(json.dumps({'status':'finished','private_output_directory':str(out),'target_model_generated':False}))
    except Exception as exc:
        if isinstance(exc,DeadlineReached):
            freeze(out/('cutoff_stop_'+args.judge+'_'+uuid.uuid4().hex+'.json'),{'status':'incomplete_cutoff','cutoff_utc':EXECUTION_CUTOFF_UTC,'condition':args.condition,'judge':args.judge,'blocked_stage':CONTEXT.get('blocked_stage'),'records_preserved':len(list((out/'records').glob('*.json'))),'no_new_inference':True})
        # Do not print auth headers, token values, harmful input, or exception payloads.
        http_status=None; chain=exc
        for _ in range(4):
            response=getattr(chain,'response',None)
            if response is not None:http_status=getattr(response,'status_code',None)
            chain=getattr(chain,'__cause__',None)
            if chain is None:break
        detail=str(exc) if type(exc) in (ValueError,RuntimeError) and CONTEXT['stage'] in ('input_validation','gpu_package_preflight','final_record_validation') else 'operation stopped; secret-bearing exception text suppressed'
        if auth_token and auth_token in detail: detail='secret-bearing detail suppressed'
        print(json.dumps({'status':'stopped','context':CONTEXT,'exception_type':('RedactedException' if auth_token and auth_token in type(exc).__name__ else type(exc).__name__),'http_status':http_status,'missing_package':getattr(exc,'name',None) if isinstance(exc,(ModuleNotFoundError,importlib.metadata.PackageNotFoundError)) else None,'detail':detail,'partial_results_preserved':True,'action':'inspect package/GPU/access state; anonymous LG access may require existing HF permission; no automatic login, install or paid upgrade'}),file=sys.stderr)
        raise SystemExit(1)
    finally:
        auth_token=None
        lock.unlink()

if __name__=='__main__': main()
