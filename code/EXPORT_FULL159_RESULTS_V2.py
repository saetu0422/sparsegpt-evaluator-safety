"""Complete standard159 raw export only: no models, credentials, network, or statistics.

Existing run folders remain read-only. Mounted readback is not backend durability.
"""
if not __debug__:
    raise RuntimeError('Validation assertions must be enabled')
from pathlib import Path
import collections
import contextlib
import csv
import datetime
import hashlib
import importlib.util
import io
import json
import re
import os
import sys
import zipfile

WRAPPER_SHA='9d8934bd7af0e0bf69d610ade2a6e91f4cd42f7cabbb654ecfa9f48e14d657b8'
RUNNER_SHA='d56b4e1a67b2f0b801ba98f46e65e4052e1e60217ea102d037520b455eb353ee'
PARSER_SHA='6616ea2e9fd27ced56a6e00bc73340bfa6e92cb0c6ee5a213382b6732bd0cbc8'
HB_TEMPLATE_SHA='6e40c2f76a74aa2dc38d83b557220017311e29c249d938a256c3f0a2d87f0cac'
LG_TEMPLATE_SHA='5a5561f4ea9576d49d8b81328d0c7c42353549a9d610e0855ff107bf9a04c1f8'
PLAN_SHA='ea8e753776999b6b28868f9f692d8b6459685f598de1677c8802bfe98f776dfa'
FOLDER_ID=os.environ.get("SPARSEGPT_DRIVE_FOLDER_ID")
SCOPE='all159_standard_IDs_x_FP16_SP70_x_HB_LG_636_new_judgments'
SCHEMA='sparsegpt-mounted-drive-standard159-v1'
PROTOCOL='new-standard159-v1; not historical judge reproduction'
PLAN_STATUS='prospective locally frozen exploratory plan; not preregistered'
PLAN_FROZEN_AT='2026-10-29T07:24:00+00:00'
PINS={'colab_smoke.py':RUNNER_SHA,'research_parsers.py':PARSER_SHA,'HB_standard_template.txt':HB_TEMPLATE_SHA}


def require(condition,message='full159 export validation failed'):
    if not condition:raise ValueError(message)


def sha(data):return hashlib.sha256(data).hexdigest()


def safe_path(path):
    path=Path(path)
    for ancestor in (path,*path.parents):
        require(not ancestor.is_symlink(),'symbolic-link path refused')
    return path


@contextlib.contextmanager
def reviewed_modules(code_dir):
    code_dir=safe_path(code_dir).resolve(strict=True)
    for name,digest in {**PINS,'drive_wrapper.py':WRAPPER_SHA,'analysis_plan.json':PLAN_SHA}.items():
        require(sha(safe_path(code_dir/name).read_bytes())==digest,'reviewed exporter dependency SHA mismatch')
    def load(name,file):
        spec=importlib.util.spec_from_file_location(name,code_dir/file)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module
    parser=load('_export159_parser','research_parsers.py')
    prior=sys.modules.get('research_parsers');had_prior='research_parsers' in sys.modules
    try:
        # Ensure runner.verify_record uses the freshly pinned parser, not an unrelated cache.
        sys.modules['research_parsers']=parser
        yield load('_export159_wrapper','drive_wrapper.py'),load('_export159_runner','colab_smoke.py'),parser
    finally:
        if had_prior:sys.modules['research_parsers']=prior
        else:sys.modules.pop('research_parsers',None)


def inventory(root):
    root=safe_path(root)
    require(root.is_dir(),'run root missing')
    result={}
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(),'symbolic-link run entry refused')
        if path.is_file():
            require(path.name not in {'.lock','.mirror_session.lock'},'active run lock refused')
            require(path.suffix not in {'.tmp','.part','.commitlock','.mirrorlock'},'partial commit refused')
            relative=path.relative_to(root).as_posix()
            require(not relative.startswith('/') and '..' not in Path(relative).parts,'unsafe archive member')
            result[relative]=path.read_bytes()
        else:require(path.is_dir(),'nonregular run entry refused')
    return result


def validate_protocol(protocol,judge,tasks,provenance,environment,runner,parser):
    require(protocol['protocol']==PROTOCOL and protocol['judge']==judge,'protocol scope mismatch')
    require(protocol['analysis_plan_sha256']==PLAN_SHA and protocol['analysis_plan_status']==PLAN_STATUS,'protocol plan mismatch')
    require(protocol['model_id']==runner.MODELS[judge][0] and protocol['model_revision']==protocol['tokenizer_revision']==runner.MODELS[judge][1],'model revision mismatch')
    require(protocol['runner_code_sha256']==RUNNER_SHA and protocol['parser_code_sha256']==PARSER_SHA and protocol['parser_version']==parser.VERSION,'protocol code mismatch')
    require(protocol['auth_mode']==('anonymous' if judge=='HB' else 'ephemeral_explicit_read_token'),'authentication protocol mismatch')
    require(protocol['tasks_sha256']==sha(runner.canonical(tasks)) and protocol['inputs']==provenance,'task/provenance mismatch')
    require(protocol['environment']==environment and environment['precision']=='fp16','environment precision mismatch')
    require(protocol['settings']=={'seed':42,'do_sample':False,'temperature_inactive':0,'top_p_inactive':1,'max_new_tokens':1 if judge=='HB' else 128,'dtype':'float16','quantization':'none'},'generation settings mismatch')
    require(protocol['template_sha256']==sha(protocol['template'].encode())==(HB_TEMPLATE_SHA if judge=='HB' else LG_TEMPLATE_SHA),'template mismatch')
    require(protocol['model_execution_authorized'] is True and protocol['target_research_model']=='Meta-Llama-3-8B-Instruct; saved responses only, not loaded','target model scope mismatch')
    require(protocol['token_policy']=='HB right clip generation512 encode/decode, full prompt left2048; LG no truncate cap8192','token policy mismatch')


def validate_record(record,task,protocol,runner,parser):
    runner.verify_record(record,task,sha(runner.canonical(protocol)))
    require(record['status']=='judged','excluded or unjudged record cannot complete636 export')
    require(type(record['legacy_label']) is int,'legacy label type mismatch')
    judge=task['evaluator'];revision=runner.MODELS[judge][1]
    require(record['source_seed']==record['judge_seed']==42 and type(record['source_seed']) is int and type(record['judge_seed']) is int,'seed mismatch')
    require(record['model_revision']==record['tokenizer_revision']==revision and record['observed_config_commit'] in (None,revision),'record revision mismatch')
    require(record['template_sha256']==protocol['template_sha256'] and record['parser_version']==parser.VERSION,'record protocol fields mismatch')
    ids=record['input_token_ids'];out=record['output_token_ids']
    require(type(ids) is list and len(ids)>0 and all(type(x) is int and x>=0 for x in ids),'invalid input token IDs')
    require(type(out) is list and all(type(x) is int and x>=0 for x in out),'invalid output token IDs')
    require(record['input_tokens']==len(ids) and type(record['input_tokens']) is int and record['input_token_ids_sha256']==sha(runner.canonical(ids)),'input token binding mismatch')
    require(type(record['output_tokens']) is int and record['output_tokens']==len(out) and 0<len(out)<=protocol['settings']['max_new_tokens'],'output token count mismatch')
    require(record['serialized_input_sha256']==sha(record['serialized_input_before_prompt_truncation'].encode()),'serialized prompt hash mismatch')
    require(record['decoder_settings']=={'parser_input_skip_special_tokens':True,'full_raw_skip_special_tokens':False,'clean_up_tokenization_spaces':False,'strip':False},'decoder contract mismatch')
    label=record['parsed']['label'];require(label in {'safe','unsafe','invalid','abstain'},'unknown parsed label')
    binary={'safe':0,'unsafe':1}.get(label)
    require((record['new_label_binary'] is None if binary is None else type(record['new_label_binary']) is int and record['new_label_binary']==binary),'binary label mismatch')
    changed=None if binary is None else binary!=task['legacy_label']
    require(record['legacy_changed'] is changed,'legacy transition mismatch')
    policy=record['token_policy']
    if judge=='LG':
        require(len(ids)<=8192 and policy=={'truncation':'none; conversation user behavior then assistant stored response','apply_chat_template_return_dict':False,'input_ids_contract':'nonempty flat list[int]'},'LG tokenization policy mismatch')
    else:
        require(len(ids)<=2048 and set(policy)=={'response_clip_tokens','clipped_response_sha256','full_prompt_left_truncated'},'HB tokenization policy mismatch')
        require(type(policy['response_clip_tokens']) is int and 0<=policy['response_clip_tokens']<=512 and type(policy['full_prompt_left_truncated']) is bool and re.fullmatch('[0-9a-f]{64}',policy['clipped_response_sha256']) is not None,'HB clipping evidence mismatch')
        prefix,suffix=runner.HB_TEMPLATE.split('{generation}')
        prefix,suffix=prefix.format(behavior=task['behavior']),suffix.format(behavior=task['behavior'])
        prompt=record['serialized_input_before_prompt_truncation']
        require(prompt.startswith(prefix) and prompt.endswith(suffix),'HB prompt task/template mismatch')
        clipped=prompt[len(prefix):len(prompt)-len(suffix)] if suffix else prompt[len(prefix):]
        require(policy['clipped_response_sha256']==sha(clipped.encode()),'HB clipped response hash mismatch')
    times=[]
    for key in ('started_at_utc','ended_at_utc'):
        require(isinstance(record[key],str) and bool(record[key]),'missing timing metadata')
        parsed_time=datetime.datetime.fromisoformat(record[key])
        require(parsed_time.tzinfo is not None,'judgment timestamp must be timezone-aware')
        times.append(parsed_time)
    require(times[0]<=times[1] and times[0]>=datetime.datetime.fromisoformat(PLAN_FROZEN_AT),'judgment time order or pre-plan timestamp')


def expected_completion(records,judge):
    counts=collections.Counter(r['parsed']['label'] for r in records)
    valid=counts['safe']+counts['unsafe'];judged=len(records)
    return {'task_accounted_complete':judged==318,'requested_evaluation_complete':judged==318,'requested_judge':judge,'records':judged,'judged':judged,'valid':valid,'invalid':counts['invalid'],'abstain':counts['abstain'],'excluded':0,'counts':dict(counts),'positive_rate_all_judged':counts['unsafe']/judged if judged else None,'positive_rate_valid':counts['unsafe']/valid if valid else None,'mode':'new raw judging only; legacy labels retained separately'}


def entry(name,data):return {'path':name,'bytes':len(data),'sha256':sha(data)}


def export_completed(project_parent,run_id,code_dir,*,local_root=Path('/content')):
    """Build a deterministic sibling ZIP after exact636 completion; return safe evidence."""
    require(isinstance(FOLDER_ID,str) and re.fullmatch(r'[A-Za-z0-9_-]{10,100}',FOLDER_ID) is not None,'configure an explicit Drive folder ID')
    require(isinstance(run_id,str) and re.fullmatch(r'full159_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{12}',run_id) is not None,'invalid full159 run ID')
    local_root=safe_path(local_root).resolve(strict=True)
    parent=safe_path(project_parent).resolve(strict=True)
    with reviewed_modules(code_dir) as (dw,runner,parser):
        guard=dw.DriveMountGuard(parent);guard()
        require(parent==guard.parent,'Drive parent resolution changed')
        parts=parent.parts
        require('.shortcut-targets-by-id' in parts and parts[parts.index('.shortcut-targets-by-id')+1]==FOLDER_ID,'Drive ID-bound parent mismatch')
        local,remote=local_root/run_id,parent/run_id
        # Colab's /content legitimately contains the /content/drive mount.
        # Isolate actual scratch/output paths, not their broad /content ancestor.
        mount=safe_path(guard.identity['mountpoint']).resolve(strict=True)
        require(not local_root.is_relative_to(mount),'local export root must be outside the Drive mount')
        require(local!=remote and not local.is_relative_to(remote) and not remote.is_relative_to(local),'local run and Drive run must be separate')
        require(not local.is_relative_to(mount),'local run must be outside the Drive mount')
        first_local,first_remote=inventory(local),inventory(remote)
        require(first_local==first_remote,'complete local/Drive inventory or bytes mismatch')
        tasks,provenance=runner.inputs(local/'_mirror/inputs/verified_inputs.zip')
        require(first_local['tasks.json']==runner.canonical(tasks) and first_local['input_provenance.json']==runner.canonical(provenance),'saved task/provenance drift')
        require(len(tasks)==636 and len({t['task_key'] for t in tasks})==636 and len({t['behavior_id'] for t in tasks})==159,'full scope mismatch')
        require(collections.Counter((t['condition'],t['evaluator']) for t in tasks)=={(c,e):159 for c in ('FP16','SP70') for e in ('HB','LG')},'condition/evaluator scope mismatch')
        identity=json.loads(first_local['_mirror/run_identity.json'])
        require(identity['run_id']==run_id and identity['schema']==SCHEMA and identity['scope']==SCOPE,'run identity mismatch')
        require(identity['runner_code']==PINS and identity['wrapper_sha256']==WRAPPER_SHA and identity['input_sha256']==dw.INPUT_SHA and identity['precision']=='fp16','run source/precision mismatch')
        require(identity['verified_drive_folder_id']==FOLDER_ID and identity['expected_ids']==159 and identity['expected_per_judge']==318 and identity['expected_total_tasks']==636,'run count identity mismatch')
        require(identity['analysis_plan_sha256']==PLAN_SHA and identity['analysis_plan_status']==PLAN_STATUS,'identity plan mismatch')
        require(first_local['_mirror/config.json']==runner.canonical(identity) and sha(first_local['_mirror/analysis/analysis_plan.json'])==PLAN_SHA,'archived config/plan mismatch')
        for name,digest in {**PINS,'drive_wrapper.py':WRAPPER_SHA}.items():require(sha(first_local['_mirror/code/'+name])==digest,'archived code mismatch')
        hb_source,parent_lg=parent/dw.SOURCE_HB_RUN_ID,parent/dw.SOURCE_LG_RUN_ID
        hb_lineage=dw.validate_hb_lineage(hb_source,runner,tasks,provenance)
        lg_lineage=dw.validate_lg_lineage(parent_lg,runner,tasks,hb_source)
        require(identity['source_hb_lineage']==hb_lineage and identity['source_lg_lineage']==lg_lineage,'source lineage mismatch')
        require(first_local['_mirror/lineage/source_hb.json']==runner.canonical(hb_lineage) and first_local['_mirror/lineage/source_lg.json']==runner.canonical(lg_lineage),'archived lineage mismatch')
        mirror=dw.Mirror(local,remote,identity,storage_guard=guard)
        mirror.audit();mirror.audit_control();guard()
        environment=json.loads(first_local['environment.json'])
        protocols={j:json.loads(first_local[j+'_protocol.json']) for j in ('HB','LG')}
        for j,p in protocols.items():validate_protocol(p,j,tasks,provenance,environment,runner,parser)
        records=runner.records_checked(local,tasks)
        require(len(records)==636 and {r['task_key'] for r in records}=={t['task_key'] for t in tasks},'expected636 record membership incomplete')
        by_task={t['task_key']:t for t in tasks}
        for record in records:validate_record(record,by_task[record['task_key']],protocols[record['evaluator']],runner,parser)
        completions={}
        core_names={'tasks.json','input_provenance.json','environment.json','HB_protocol.json','LG_protocol.json'}|{p for p in first_local if p.startswith('records/')}
        for judge in ('HB','LG'):
            selected=[r for r in records if r['evaluator']==judge]
            require(len(selected)==318,'expected318 per-judge records')
            completions[judge]=expected_completion(selected,judge)
            require(json.loads(first_local['completion_'+judge+'.json'])==completions[judge],'completion summary disagrees with raw records')
            marker=json.loads(first_local['_mirror/'+judge+'_MIRROR_COMPLETE.json'])
            selected_names={'tasks.json','input_provenance.json','environment.json',judge+'_protocol.json'}|{'records/'+runner.sha(r['task_key'].encode())+'.json' for r in selected}
            require(marker['schema']==SCHEMA and marker['judge']==judge and marker['judged']==318,'judge checkpoint scope mismatch')
            require(marker['artifacts']==[entry(n,first_local[n]) for n in sorted(selected_names)],'judge checkpoint artifact membership mismatch')
        overall=json.loads(first_local['_mirror/RUN_MIRROR_COMPLETE.json'])
        require(overall['schema']==SCHEMA and overall['judged']==636 and overall['artifacts']==[entry(n,first_local[n]) for n in sorted(core_names)],'overall636 checkpoint mismatch')
        summary={'status':'complete_636_new_judgments','run_id':run_id,'expected_judgments':636,'actual_judgments':636,'selected_standard_ids':159,'conditions':['FP16','SP70'],'HB':completions['HB'],'LG':completions['LG'],'excluded_categories':{'contextual':81,'copyright':80},'input_zip_sha256':dw.INPUT_SHA,'analysis_plan_sha256':PLAN_SHA,'analysis_plan_status':PLAN_STATUS,'target_model_generated':False,'old_smoke_records_imported':0,'full_checkpoint_sha256':sha(first_local['_mirror/RUN_MIRROR_COMPLETE.json']),'interpretation':'Saved-response classifier judgments only. No evaluator-accuracy or pruning-causal conclusion. Statistical analysis is separate.','durability_evidence':'mounted FUSE byte/hash readback only; independent backend verification pending'}
        columns=['behavior_id','condition','evaluator','response_sha256','legacy_label','new_label_binary','legacy_changed','status','parsed_label','parsed_categories','raw_judge_completion']
        buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=columns);writer.writeheader()
        for record in sorted(records,key=lambda x:x['task_key']):
            row={k:record.get(k) for k in columns};row['parsed_label']=record['parsed']['label'];row['parsed_categories']=json.dumps(record['parsed'].get('categories',[]),separators=(',',':'))
            writer.writerow(row)
        exporter_source=safe_path(Path(__file__)).read_bytes()
        payloads={'EXPORTER_SOURCE.py':exporter_source,'FULL159_RESULT_SUMMARY.json':runner.canonical(summary),'full159_comparison.csv':buf.getvalue().encode('utf-8-sig'),**{'run/'+n:b for n,b in first_remote.items()}}
        manifest={'schema':'full159-complete-export-v1','exporter_source_sha256':sha(exporter_source),'complete_judgments':636,'HB':318,'LG':318,'files':[entry(n,b) for n,b in sorted(payloads.items())]}
        payloads['EXPORT_MANIFEST.json']=runner.canonical(manifest)
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for name,data in sorted(payloads.items()):
                info=zipfile.ZipInfo(name,date_time=(2026,10,29,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o600<<16
                z.writestr(info,data)
        archive=buffer.getvalue();name=run_id+'_HB_LG_636_complete_results.zip'
        local_archive,remote_archive=safe_path(local_root/name),safe_path(parent/name)
        require(not local_archive.is_relative_to(mount) and local_archive!=remote_archive,'local archive must be outside the Drive mount')
        # Source snapshots must remain unchanged and unlocked before committing anything.
        guard();require(inventory(local)==first_local and inventory(remote)==first_remote,'run changed during export validation');guard()
        for path in (local_archive,remote_archive):
            require(not path.with_name(path.name+'.mirrorlock').exists(),'active archive lock refused')
            require(not any(path.parent.glob(path.name+'.*.part')) and not any(path.parent.glob(path.name+'.*.tmp')),'interrupted archive commit refused')
            if path.exists():dw.read_verified(path,archive)
        guard();dw.immutable_write(local_archive,archive);guard()
        dw.immutable_write(remote_archive,archive);guard();dw.read_verified(remote_archive,archive);guard()
        stored=remote_archive.read_bytes();guard()
        require(stored==archive,'archive readback mismatch')
        with zipfile.ZipFile(io.BytesIO(stored)) as z:
            require(z.testzip() is None and len(z.namelist())==len(payloads) and set(z.namelist())==set(payloads),'archive inventory/CRC mismatch')
            require(z.read('EXPORT_MANIFEST.json')==payloads['EXPORT_MANIFEST.json'],'export manifest changed')
            for item in manifest['files']:
                data=z.read(item['path']);require(len(data)==item['bytes'] and sha(data)==item['sha256'],'archive member hash mismatch')
        require(inventory(local)==first_local and inventory(remote)==first_remote,'run changed during export save');guard()
        evidence={'archive_name':name,'bytes':len(archive),'sha256':sha(archive),'members':len(payloads),'manifest_verified_files':len(manifest['files']),'actual_judgments':636,'HB':318,'LG':318,'evidence':'mounted_filesystem_readback_only'}
        print(json.dumps(evidence,sort_keys=True))
        return evidence
