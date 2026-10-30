"""Five-level raw exporter only: no models, credentials, network, or statistical tests.

Complete condition318 and aggregate1590 modes are distinct. Explicit partial
mode preserves missing/excluded records without claiming completion. Old and
new source folders stay read-only; archive commits are immutable siblings.
"""
if not __debug__:
    raise RuntimeError('Validation assertions must be enabled')
from pathlib import Path
import collections,contextlib,csv,datetime,hashlib,importlib.util,io,json,re,sys,zipfile,os

WRAPPER_SHA='c2ab469ddf7d41ef44fd39d0df72e0f58e3f9786f423cbad0151c0e4e38ebcb1'
RUNNER_SHA='5b63875349cf6409397282f4ce765dc8503ac8a32d5fec44ec5ab0793ccd1583'
PARSER_SHA='6616ea2e9fd27ced56a6e00bc73340bfa6e92cb0c6ee5a213382b6732bd0cbc8'
HB_TEMPLATE_SHA='6e40c2f76a74aa2dc38d83b557220017311e29c249d938a256c3f0a2d87f0cac'
PLAN_SHA='473ecba7402b70a171b0589e8eb761cbe802330bd6de4d717a31e948aa94a5c7'
BUNDLE_SHA=os.environ.get('SPARSEGPT_REVIEWED_BUNDLE_SHA256')
BUNDLE_NAME=Path(os.environ.get('SPARSEGPT_REVIEWED_BUNDLE_PATH','')).name
FOLDER_ID=os.environ.get('SPARSEGPT_DRIVE_FOLDER_ID')
CONDITIONS=('SP30','SP40','SP50','SP55','SP60')
SCHEMA='sparsegpt-mounted-drive-standard159-levels-v1'
PROTOCOL='new-standard159-levels-v1; not historical judge reproduction'
PLAN_STATUS='prospective locally frozen exploratory plan; not preregistered'
PINS={'colab_smoke.py':RUNNER_SHA,'research_parsers.py':PARSER_SHA,'HB_standard_template.txt':HB_TEMPLATE_SHA}
DEPLOYMENT_PINS={**PINS,'drive_wrapper.py':WRAPPER_SHA,'colab_secret_launcher.py':'4c1d1d7198d036b1f46937cb623c04276769a0183fc0d6ed65055bae5562c92c','analysis_plan.json':PLAN_SHA}
REQUIRED_DEPLOYMENT_MEMBERS=set(DEPLOYMENT_PINS)|{'COLAB_SETUP_LEVELS.py','COLAB_RUN_CONDITION.py'}
STATUSES=('safe','unsafe','invalid','abstain','excluded','missing')
BINARY={'safe':0,'unsafe':1}
DECODER={'parser_input_skip_special_tokens':True,'full_raw_skip_special_tokens':False,'clean_up_tokenization_spaces':False,'strip':False}

def require(condition,message='five-level export validation failed'):
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


def entry(name,data):return {'path':name,'bytes':len(data),'sha256':sha(data)}


def canonical(value):
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()

fail=require

def validate_record(record, task, protocol, protocol_sha, runner, parser_version):
    runner.verify_record(record, task, protocol_sha)
    for field in ('source_seed', 'judge_seed'):
        fail(type(record.get(field)) is int and record[field] == 42, f'record {field} mismatch')
    fail(type(record.get('legacy_label')) is int, 'record legacy label type mismatch')
    for field in ('model_revision', 'tokenizer_revision', 'template_sha256', 'parser_version'):
        fail(record.get(field) == protocol[field], f'record protocol field mismatch: {field}')
    fail(record.get('observed_config_commit') in (None, protocol['model_revision']), 'observed model revision mismatch')
    prompt = record.get('serialized_input_before_prompt_truncation')
    fail(isinstance(prompt, str) and record.get('serialized_input_sha256') == sha(prompt.encode()), 'serialized prompt hash mismatch')
    ids = record.get('input_token_ids')
    fail(type(ids) is list and bool(ids) and all(type(i) is int and i >= 0 for i in ids), 'invalid input token IDs')
    fail(type(record.get('input_tokens')) is int and record['input_tokens'] == len(ids), 'input token count mismatch')
    fail(record.get('input_token_ids_sha256') == sha(canonical(ids)), 'input token hash mismatch')
    policy = record.get('token_policy')
    fail(isinstance(policy, dict), 'record token policy missing')
    if task['evaluator'] == 'LG':
        fail(policy.get('apply_chat_template_return_dict') is False and policy.get('input_ids_contract') == 'nonempty flat list[int]', 'LG token serialization contract mismatch')
        if record['status'] == 'judged':
            fail(set(policy) == {'truncation', 'apply_chat_template_return_dict', 'input_ids_contract'} and policy['truncation'] == 'none; conversation user behavior then assistant stored response', 'LG truncation policy mismatch')
        else:
            fail(set(policy) == {'exclude_reason', 'apply_chat_template_return_dict', 'input_ids_contract'}, 'LG exclusion token policy mismatch')
    else:
        fail(set(policy) == {'response_clip_tokens', 'clipped_response_sha256', 'full_prompt_left_truncated'}, 'HB token policy keys mismatch')
        fail(type(policy['response_clip_tokens']) is int and 0 <= policy['response_clip_tokens'] <= 512 and type(policy['full_prompt_left_truncated']) is bool, 'HB clipping policy mismatch')
        prefix, suffix = runner.HB_TEMPLATE.split('{generation}')
        prefix, suffix = prefix.format(behavior=task['behavior']), suffix.format(behavior=task['behavior'])
        fail(prompt.startswith(prefix) and prompt.endswith(suffix), 'HB prompt task/template binding mismatch')
        clipped = prompt[len(prefix):len(prompt) - len(suffix)] if suffix else prompt[len(prefix):]
        fail(policy['clipped_response_sha256'] == sha(clipped.encode()), 'HB clipped response hash mismatch')
    if record['status'] == 'excluded':
        fail(task['evaluator'] == 'LG' and len(ids) > 8192 and policy.get('exclude_reason') == 'LG_input_over_8192_no_truncation', 'unexpected exclusion')
        fail(record.get('output_tokens') == 0 and type(record.get('output_tokens')) is int, 'excluded record output count')
        for field in ('raw_judge_completion', 'raw_judge_sha256', 'parsed', 'new_label_binary', 'legacy_changed', 'started_at_utc', 'ended_at_utc', 'output_token_ids',
                      'raw_decoded_with_special_tokens', 'raw_decoded_with_special_tokens_sha256', 'decoder_settings'):
            fail(record.get(field) is None, f'excluded record has unexpected {field}')
        return 'excluded'
    fail(record['status'] == 'judged' and 'exclude_reason' not in policy, 'judged/exclusion conflict')
    if task['evaluator'] == 'LG':
        fail(len(ids) <= 8192, 'LG judged over context cap')
    else:
        fail(len(ids) <= 2048, 'HB judged over context cap')
    parsed = record.get('parsed')
    fail(isinstance(parsed, dict) and parsed.get('parser_version') == parser_version and parsed.get('label') in STATUSES[:4], 'invalid parsed status')
    status = parsed['label']
    binary = BINARY.get(status)
    fail(record.get('new_label_binary') == binary and (binary is None or type(record.get('new_label_binary')) is int), 'new binary label does not match raw parser')
    changed = None if binary is None else binary != task['legacy_label']
    fail(record.get('legacy_changed') == changed and (changed is None or type(record.get('legacy_changed')) is bool), 'legacy change flag mismatch')
    fail(record.get('decoder_settings') == DECODER, 'decoder settings mismatch')
    output_ids = record.get('output_token_ids')
    fail(type(output_ids) is list and all(type(i) is int and i >= 0 for i in output_ids), 'invalid output token IDs')
    fail(type(record.get('output_tokens')) is int and len(output_ids) == record['output_tokens'] and 0 < len(output_ids) <= protocol['settings']['max_new_tokens'], 'output token count mismatch')
    times = []
    for key in ('started_at_utc', 'ended_at_utc'):
        fail(isinstance(record.get(key), str) and bool(record[key]), 'judgment time missing')
        parsed_time = datetime.datetime.fromisoformat(record[key])
        fail(parsed_time.tzinfo is not None, 'judgment timestamp must be timezone-aware')
        times.append(parsed_time)
    fail(times[0] <= times[1] and times[0] >= datetime.datetime.fromisoformat('2026-10-30T03:46:36.916135+00:00'), 'judgment time order or pre-plan timestamp')
    return status


def validate_protocol(protocol,condition,judge,tasks,provenance,environment,baseline,runner,parser):
    expected={'protocol':PROTOCOL,'condition':condition,'judge':judge,'analysis_plan_sha256':PLAN_SHA,
        'analysis_plan_status':PLAN_STATUS,'baseline_archive_sha256':runner.BASELINE_ARCHIVE_SHA,
        'baseline_full_checkpoint_sha256':runner.BASELINE_FULL_CHECKPOINT_SHA,
        'runner_code_sha256':RUNNER_SHA,'parser_code_sha256':PARSER_SHA,'parser_version':parser.VERSION,
        'tasks_sha256':sha(canonical(tasks)),'inputs':provenance,'environment':environment,
        'auth_mode':'anonymous' if judge=='HB' else 'ephemeral_explicit_read_token',
        'model_execution_authorized':True,'target_research_model':'Meta-Llama-3-8B-Instruct; saved responses only, not loaded'}
    for key,value in expected.items():require(canonical(protocol.get(key))==canonical(value),'protocol binding mismatch: '+key)
    for key,value in baseline.items():require(canonical(protocol.get(key))==canonical(value),'scientific protocol drift: '+key)
    require(environment.get('precision')=='fp16' and environment.get('packages')==runner.BASELINE_PACKAGES,'package/precision mismatch')
    require(protocol['template_sha256']==sha(protocol['template'].encode()),'template SHA mismatch')


def completion_for(records,judge):
    counts=collections.Counter(x.get('parsed',{}).get('label',x['status']) for x in records)
    judged=sum(x['status']=='judged' for x in records);valid=counts['safe']+counts['unsafe']
    return {'task_accounted_complete':len(records)==159,'requested_evaluation_complete':judged==159,'requested_judge':judge,'records':len(records),'judged':judged,'valid':valid,'invalid':counts['invalid'],'abstain':counts['abstain'],'excluded':counts['excluded'],'counts':dict(counts),'positive_rate_all_judged':counts['unsafe']/judged if judged else None,'positive_rate_valid':counts['unsafe']/valid if valid else None,'mode':'new raw judging only; legacy labels retained separately'}


def validate_run(local,remote,condition,run_id,tasks,provenance,lineage,guard,dw,runner,parser,allow_partial):
    guard();a=inventory(local);b=inventory(remote);guard();require(a==b,'local/Drive complete snapshot mismatch')
    def obj(name):return json.loads(a[name])
    identity=obj('_mirror/run_identity.json')
    require(identity.get('run_id')==run_id and identity.get('schema')==SCHEMA and identity.get('condition')==condition,'run identity/scope mismatch')
    require(identity.get('scope')=='one_condition159_standard_IDs_x_HB_LG_318_new_judgments','run scope mismatch')
    require(identity.get('input_sha256')==dw.INPUT_SHA and identity.get('runner_code')==PINS and identity.get('wrapper_sha256')==WRAPPER_SHA,'run source code/input mismatch')
    require(identity.get('precision')=='fp16' and identity.get('verified_drive_folder_id')==FOLDER_ID,'run precision/folder mismatch')
    require(identity.get('expected_ids')==159 and identity.get('expected_per_judge')==159 and identity.get('expected_total_tasks')==318 and identity.get('planned_new_judgments_all_conditions')==1590 and identity.get('planned_conditions')==list(CONDITIONS),'run task counts mismatch')
    require(identity.get('execution_cutoff_utc')==runner.EXECUTION_CUTOFF_UTC and identity.get('required_package_versions')==runner.BASELINE_PACKAGES,'run execution policy mismatch')
    require(identity.get('analysis_plan_sha256')==PLAN_SHA and identity.get('analysis_plan_status')==PLAN_STATUS,'run plan mismatch')
    require(canonical(identity.get('baseline_lineage'))==canonical(lineage),'baseline lineage mismatch')
    require(a['_mirror/config.json']==canonical(identity) and a['_mirror/lineage/baseline.json']==canonical(lineage),'archived config/lineage mismatch')
    require(sha(a['_mirror/analysis/analysis_plan.json'])==PLAN_SHA and sha(a['_mirror/inputs/verified_inputs.zip'])==dw.INPUT_SHA,'archived plan/input mismatch')
    for name,digest in {**PINS,'drive_wrapper.py':WRAPPER_SHA}.items():require(sha(a['_mirror/code/'+name])==digest,'archived code mismatch')
    metadata_ready='tasks.json' in a and 'input_provenance.json' in a
    if metadata_ready:
        require(a['tasks.json']==canonical(tasks) and a['input_provenance.json']==canonical(provenance),'task/source binding mismatch')
    else:
        require(allow_partial and not any(n.startswith('records/') or n.endswith('_protocol.json') for n in a),'missing task metadata with existing judgments')
        if 'tasks.json' in a:require(a['tasks.json']==canonical(tasks),'partial tasks mismatch')
        if 'input_provenance.json' in a:require(a['input_provenance.json']==canonical(provenance),'partial provenance mismatch')
    mirror=dw.Mirror(local,remote,identity,storage_guard=guard);mirror.audit();mirror.audit_control();guard()
    protocols={j:obj(j+'_protocol.json') for j in ('HB','LG') if j+'_protocol.json' in a}
    environment=obj('environment.json') if 'environment.json' in a else None
    if environment is not None:require(environment.get('precision')=='fp16' and environment.get('packages')==runner.BASELINE_PACKAGES,'environment drift')
    require(not protocols or environment is not None,'protocol lacks environment')
    for j,protocol in protocols.items():validate_protocol(protocol,condition,j,tasks,provenance,environment,lineage['baseline_scientific_fields'][j],runner,parser)
    expected={'records/'+sha(t['task_key'].encode())+'.json':t for t in tasks};records=[];by_key={}
    for name in sorted(n for n in a if n.startswith('records/')):
        require(name in expected,'unexpected record filename')
        task=expected[name];record=obj(name);judge=task['evaluator'];require(judge in protocols,'record lacks protocol')
        status=validate_record(record,task,protocols[judge],sha(canonical(protocols[judge])),runner,parser.VERSION)
        if status!='excluded':require(datetime.datetime.fromisoformat(record['started_at_utc'])<datetime.datetime.fromisoformat(runner.EXECUTION_CUTOFF_UTC),'judgment started at/after execution cutoff')
        require(record['task_key'] not in by_key,'duplicate task record');by_key[record['task_key']]=(record,status);records.append(record)
    summaries={};judge_markers={}
    for judge in ('HB','LG'):
        selected=[x for x in records if x['evaluator']==judge];summary=completion_for(selected,judge);summaries[judge]=summary
        cname='completion_'+judge+'.json';mname='_mirror/'+judge+'_MIRROR_COMPLETE.json'
        if cname in a:require(obj(cname)==summary,'completion disagrees with raw records')
        if mname in a:
            mark=obj(mname)
            require(summary['judged']==159 and mark.get('schema')==SCHEMA and mark.get('judge')==judge and mark.get('judged')==159,'false judge-complete marker')
            names={'tasks.json','input_provenance.json','environment.json',judge+'_protocol.json'}|{'records/'+sha(x['task_key'].encode())+'.json' for x in selected}
            require(mark.get('artifacts')==[entry(n,a[n]) for n in sorted(names)],'judge marker artifact membership/hash mismatch')
            judge_markers[judge]=sha(a[mname])
    all_judged=len(records)==318 and all(r['status']=='judged' for r in records)
    full='_mirror/RUN_MIRROR_COMPLETE.json';full_sha=None
    if full in a:
        mark=obj(full);require(all_judged and len(judge_markers)==2 and mark.get('schema')==SCHEMA and mark.get('judged')==318,'false full318 marker')
        names={'tasks.json','input_provenance.json','environment.json','HB_protocol.json','LG_protocol.json'}|set(expected)
        require(mark.get('artifacts')==[entry(n,a[n]) for n in sorted(names)],'full318 marker artifact membership/hash mismatch');full_sha=sha(a[full])
    complete=all_judged and full_sha is not None
    require(allow_partial or complete,'condition not completely checkpointed318; explicit partial mode required')
    missing=[t['task_key'] for t in tasks if t['task_key'] not in by_key]
    summary={'condition':condition,'run_id':run_id,'complete':complete,'records_present':len(records),'judged':sum(r['status']=='judged' for r in records),'excluded':sum(r['status']=='excluded' for r in records),'missing_tasks':len(missing),'missing_task_keys':missing,'HB':summaries['HB'],'LG':summaries['LG'],'judge_checkpoint_sha256':judge_markers,'full_checkpoint_sha256':full_sha,'run_identity_sha256':sha(a['_mirror/run_identity.json'])}
    return a,by_key,summary


def _export(project_parent,run_ids,code_dir,export_id,conditions,allow_partial,local_root):
    require(isinstance(FOLDER_ID,str) and re.fullmatch(r'[A-Za-z0-9_-]{10,100}',FOLDER_ID) is not None,'explicit verified Drive folder configuration required')
    require(isinstance(BUNDLE_SHA,str) and re.fullmatch(r'[0-9a-f]{64}',BUNDLE_SHA) is not None,'explicit reviewed private deployment bundle SHA required')
    require(re.fullmatch(r'[A-Za-z0-9_.-]+[.]zip',BUNDLE_NAME) is not None,'explicit reviewed private deployment bundle path required')
    require(type(run_ids) is dict and set(run_ids)<=set(conditions),'unexpected condition mapping')
    require(isinstance(export_id,str) and re.fullmatch(r'levels159_export_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{12}',export_id) is not None,'invalid explicit export ID')
    for condition,run_id in run_ids.items():require(isinstance(run_id,str) and re.fullmatch(r'levels159_'+condition+r'_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{12}',run_id) is not None,'run ID/condition mismatch')
    require(len(set(run_ids.values()))==len(run_ids),'duplicate run ID')
    require(allow_partial or set(run_ids)==set(conditions),'all requested conditions required for complete export')
    parent=safe_path(project_parent).resolve(strict=True);local_root=safe_path(local_root).resolve(strict=True)
    with reviewed_modules(code_dir) as (dw,runner,parser):
        guard=dw.DriveMountGuard(parent);guard();require(parent==guard.parent,'Drive parent changed')
        parts=parent.parts;require('.shortcut-targets-by-id' in parts and parts[parts.index('.shortcut-targets-by-id')+1]==FOLDER_ID,'Drive parent ID mismatch')
        mount=safe_path(guard.identity['mountpoint']).resolve(strict=True);require(not local_root.is_relative_to(mount),'local export root must be outside Drive')
        baseline=parent/dw.BASELINE_RUN_ID;baseline_archive=parent/(dw.BASELINE_RUN_ID+'_HB_LG_636_complete_results.zip')
        input_zip=baseline/'_mirror/inputs/verified_inputs.zip'
        source_input=safe_path(input_zip).read_bytes();baseline_bytes=safe_path(baseline_archive).read_bytes()
        require(len(baseline_bytes)==dw.BASELINE_ARCHIVE_BYTES and sha(baseline_bytes)==dw.BASELINE_ARCHIVE_SHA,'baseline original archive mismatch')
        bundle_path=safe_path(parent/BUNDLE_NAME);bundle=bundle_path.read_bytes();require(sha(bundle)==BUNDLE_SHA,'reviewed code bundle missing/mismatch')
        # Configurable deployment bundles must retain the original completeness
        # guarantee; a caller-supplied whole-bundle digest is not sufficient alone.
        with zipfile.ZipFile(io.BytesIO(bundle)) as z:
            require(z.testzip() is None and len(z.namelist())==len(set(z.namelist())),'bundle CRC/inventory mismatch')
            manifest=json.loads(z.read('MANIFEST.json'))
            require(REQUIRED_DEPLOYMENT_MEMBERS.issubset(manifest['files']) and set(z.namelist())==set(manifest['files'])|{'MANIFEST.json'},'bundle manifest inventory mismatch')
            for name,digest in DEPLOYMENT_PINS.items():
                require(sha(z.read(name))==digest,'bundle reviewed dependency SHA mismatch')
            for name in z.namelist():
                require('/' not in name and '\\' not in name and name not in {'.','..'},'unsafe code bundle member')
                member=z.read(name)
                require(safe_path(Path(code_dir)/name).read_bytes()==member,'installed code differs from reviewed bundle')
                if name!='MANIFEST.json':
                    require(len(member)==manifest['files'][name]['bytes'] and sha(member)==manifest['files'][name]['sha256'],'bundle member digest mismatch')
        expected={c:runner.inputs(input_zip,c) for c in CONDITIONS}
        union=[t for c in CONDITIONS for t in expected[c][0]]
        require(len(union)==1590 and len({t['task_key'] for t in union})==1590,'planned1590 source union mismatch')
        require(all(expected[c][1]['selected_id_order']==expected[CONDITIONS[0]][1]['selected_id_order'] for c in CONDITIONS),'condition ID pairing mismatch')
        lineages={}
        for c in conditions:
            guard();lineages[c]=dw.validate_baseline_lineage(baseline,runner,*expected[c],baseline_archive);guard()
        snapshots={};record_map={};condition_summaries={};payloads={}
        for c in conditions:
            tasks,provenance=expected[c]
            if c not in run_ids:
                require(allow_partial,'missing condition')
                condition_summaries[c]={'condition':c,'run_id':None,'complete':False,'records_present':0,'judged':0,'excluded':0,'missing_tasks':318,'missing_task_keys':[t['task_key'] for t in tasks]}
                continue
            run_id=run_ids[c];local=local_root/run_id;remote=parent/run_id
            require(not local.is_relative_to(mount) and local!=remote and not local.is_relative_to(remote) and not remote.is_relative_to(local),'run tree overlap or local scratch on Drive')
            snapshot,records,summary=validate_run(local,remote,c,run_id,tasks,provenance,lineages[c],guard,dw,runner,parser,allow_partial)
            require(not set(record_map)&set(records),'duplicate task across condition runs');record_map.update(records);condition_summaries[c]=summary
            snapshots[c]=(local,remote,snapshot)
            for name,data in snapshot.items():payloads['runs/'+run_id+'/'+name]=data
        planned=[t for c in conditions for t in expected[c][0]];planned_keys={t['task_key'] for t in planned}
        require(set(record_map)<=planned_keys,'unexpected union task')
        judged=sum(status not in ('excluded','missing') for _,status in record_map.values());excluded=sum(status=='excluded' for _,status in record_map.values())
        complete=all(condition_summaries[c]['complete'] for c in conditions) and judged==len(planned)
        require(allow_partial or complete,'full requested scope is incomplete')
        suffix=('COMPLETE'+str(len(planned)) if complete else 'PARTIAL'+str(len(planned)))+('_'+conditions[0] if len(conditions)==1 else '')
        name=export_id+'_'+suffix+'_results.zip'
        summary={'schema':'standard159-levels-raw-export-v1','complete':complete,'partial':not complete,'requested_conditions':list(conditions),'planned_conditions_all5':list(CONDITIONS),'expected_new_judgments':len(planned),'full_plan_expected_new_judgments':1590,'new_records_present':len(record_map),'new_judged':judged,'new_excluded':excluded,'missing_tasks':len(planned_keys-set(record_map)),'missing_task_keys':sorted(planned_keys-set(record_map)),'conditions':condition_summaries,'analysis_plan_sha256':PLAN_SHA,'baseline_archive_sha256':dw.BASELINE_ARCHIVE_SHA,'baseline_full_checkpoint_sha256':dw.BASELINE_CHECKPOINT_SHA,'baseline_full_judgments_verified':636,'baseline_fp16_reuse_for_combined_analysis':318,'full_plan_analysis_records':1908,'primary_hypothesis_family_size':10,'target_model_generated':False,'statistics_computed':False,'missing_nonbinary_policy':'explicit; never imputed safe; no condition/test-family reduction','input_copy_policy':'per-run input ZIP copies intentionally retained for exact standalone mirror recovery; original baseline ZIP included once unchanged','input_archive_member':('runs/'+run_ids[next(c for c in conditions if c in run_ids)]+'/_mirror/inputs/verified_inputs.zip' if run_ids else 'shared/verified_inputs.zip'),'evidence':'mounted_filesystem_readback_only; independent backend verification pending'}
        columns=['task_key','behavior_id','condition','evaluator','response_sha256','legacy_label','new_status','new_label_binary','legacy_changed','raw_judge_completion']
        output=io.StringIO(newline='');writer=csv.DictWriter(output,fieldnames=columns);writer.writeheader()
        for task in sorted(planned,key=lambda t:t['task_key']):
            record,status=record_map.get(task['task_key'],({},'missing'))
            row={k:task.get(k) for k in columns};row.update(new_status=status,new_label_binary=record.get('new_label_binary'),legacy_changed=record.get('legacy_changed'),raw_judge_completion=record.get('raw_judge_completion'));writer.writerow(row)
        exporter=safe_path(Path(__file__)).read_bytes()
        payloads.update({'RAW_EXPORT_SUMMARY.json':canonical(summary),'new_judgments_comparison.csv':output.getvalue().encode('utf-8-sig'),'shared/baseline_original636.zip':baseline_bytes,'shared/reviewed_code_bundle.zip':bundle,'shared/analysis_plan.json':safe_path(Path(code_dir)/'analysis_plan.json').read_bytes(),'EXPORTER_SOURCE.py':exporter})
        if not run_ids:payloads['shared/verified_inputs.zip']=source_input
        manifest={'schema':'standard159-levels-raw-export-manifest-v1','complete':complete,'expected_new_judgments':len(planned),'actual_new_judgments':judged,'missing_tasks':summary['missing_tasks'],'excluded_tasks':excluded,'exporter_source_sha256':sha(exporter),'files':[entry(n,b) for n,b in sorted(payloads.items())]}
        payloads['EXPORT_MANIFEST.json']=canonical(manifest)
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for n,b in sorted(payloads.items()):
                info=zipfile.ZipInfo(n,(2026,10,30,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o600<<16;z.writestr(info,b)
        archive=buffer.getvalue();local_archive=safe_path(local_root/name);remote_archive=safe_path(parent/name)
        require(not local_archive.is_relative_to(mount) and local_archive!=remote_archive,'local archive on Drive or overlapping remote')
        for local,remote,snapshot in snapshots.values():
            require(not local_archive.is_relative_to(local) and not remote_archive.is_relative_to(remote),'archive must be outside source runs')
            guard();require(inventory(local)==snapshot and inventory(remote)==snapshot,'source changed during export');guard()
        require(sha(safe_path(baseline_archive).read_bytes())==dw.BASELINE_ARCHIVE_SHA and sha(bundle_path.read_bytes())==BUNDLE_SHA,'reference input changed during export');guard()
        for path in (local_archive,remote_archive):
            require(not path.with_name(path.name+'.mirrorlock').exists(),'active archive lock refused')
            require(not any(path.parent.glob(path.name+'.*.part')) and not any(path.parent.glob(path.name+'.*.tmp')),'interrupted archive commit refused')
            if path.exists():dw.read_verified(path,archive)
        guard();dw.immutable_write(local_archive,archive);guard();dw.immutable_write(remote_archive,archive);guard();dw.read_verified(remote_archive,archive);guard()
        stored=remote_archive.read_bytes();guard();require(stored==archive,'archive readback mismatch')
        with zipfile.ZipFile(io.BytesIO(stored)) as z:
            require(z.testzip() is None and len(z.namelist())==len(payloads) and set(z.namelist())==set(payloads),'archive CRC/inventory mismatch')
            require(z.read('EXPORT_MANIFEST.json')==payloads['EXPORT_MANIFEST.json'],'export manifest changed')
            for item in manifest['files']:
                data=z.read(item['path']);require(len(data)==item['bytes'] and sha(data)==item['sha256'],'archive member hash mismatch')
        for local,remote,snapshot in snapshots.values():require(inventory(local)==snapshot and inventory(remote)==snapshot,'source changed during archive save')
        guard()
        evidence={'archive_name':name,'bytes':len(archive),'sha256':sha(archive),'members':len(payloads),'manifest_verified_files':len(manifest['files']),'complete':complete,'expected_new_judgments':len(planned),'actual_new_judgments':judged,'missing_tasks':summary['missing_tasks'],'excluded_tasks':excluded,'evidence':'mounted_filesystem_readback_only'}
        print(json.dumps(evidence,sort_keys=True));return evidence


def export_all(project_parent,run_ids,code_dir,export_id,*,allow_partial=False,local_root=Path('/content')):
    """Five-condition scope always expects1590, even when explicit partial mode is used."""
    return _export(project_parent,run_ids,code_dir,export_id,CONDITIONS,allow_partial,local_root)


def export_condition(project_parent,condition,run_id,code_dir,export_id,*,allow_partial=False,local_root=Path('/content')):
    """One operational318-task checkpoint export; does not redefine the10-test family."""
    require(condition in CONDITIONS,'unexpected condition')
    return _export(project_parent,{condition:run_id},code_dir,export_id,(condition,),allow_partial,local_root)
