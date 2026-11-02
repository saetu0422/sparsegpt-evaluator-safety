"""Primary control experiment. Import is offline; explicit Session and stages required.

No auth/login/token caches; token accepted only as explicit in-memory LG argument.
Budget observations supplied from visible Colab Resources by authorized operator.
Old results and code are never modified. Fresh-run only; uncertain failures halt.
"""
from pathlib import Path
import collections, datetime as dt, gc, hashlib, importlib.metadata, io, json, math, os, re, signal, time, zipfile
import storage
from research_parsers import VERSION, parse_judgment

UTC=dt.timezone.utc
# Required operational settings are supplied once by an explicitly authorized operator.
HARD_STOP=LAST_LAUNCH=FOLDER_ID=BASELINE_CU=STOP_CU=None
_OPERATIONAL=None

def configure_operational(config):
    """Bind reviewed private configuration once. This does not grant execution authority."""
    global _OPERATIONAL,HARD_STOP,LAST_LAUNCH,FOLDER_ID,BASELINE_CU,STOP_CU
    if _OPERATIONAL is not None:raise RuntimeError('Operational configuration already frozen')
    from operational_config import OperationalConfig
    if not isinstance(config,OperationalConfig):raise TypeError('Validated immutable operational configuration required')
    config.validate()
    _OPERATIONAL=config
    HARD_STOP=timestamp(config.hard_stop_utc);LAST_LAUNCH=timestamp(config.last_launch_utc)
    FOLDER_ID=config.folder_id;BASELINE_CU=config.baseline_cu;STOP_CU=config.stop_balance_cu

MODELS={'HB':('cais/HarmBench-Llama-2-13b-cls','bda705349d1144fa618770bea64d99ce54e3835b'), 'LG':('meta-llama/Llama-Guard-3-8B','7327bd9f6efbbe6101dc6cc4736302b3cbb6e425')}
PACKAGES={'torch':'2.11.0+cu130','transformers':'5.20.2','accelerate':'1.15.0'}
TEMPLATE_SHA='6e40c2f76a74aa2dc38d83b557220017311e29c249d938a256c3f0a2d87f0cac'
PARSER_SHA='6616ea2e9fd27ced56a6e00bc73340bfa6e92cb0c6ee5a213382b6732bd0cbc8'
MAX_BATCH=159

def now():return dt.datetime.now(UTC)
def canonical(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def timestamp(s):
    d=dt.datetime.fromisoformat(s)
    if d.tzinfo is None:raise ValueError('Timezone required')
    return d

def parse(raw,judge):
    cfg={'contract':'harmbench-official-lower-no-strip'} if judge=='HB' else {'contract':'lg3-8b-lines-v1','categories':[f'S{i}' for i in range(1,15)]}
    return parse_judgment(raw,judge,cfg)

def safe_target(root,relative):
    rel=Path(relative)
    if rel.is_absolute() or '..' in rel.parts:raise ValueError('Output escape')
    cur=root
    for p in ('',*rel.parts):
        cur=cur/p
        if cur.is_symlink():raise ValueError('Symlink refused')
    return root/rel

def verify_bundle(manifest_path,expected_sha):
    p=Path(manifest_path)
    if p.is_symlink() or sha(p.read_bytes())!=expected_sha:raise ValueError('Manifest digest mismatch')
    m=read(p)
    if m['schema']!='primary-control-frozen-v1' or m['task_count']!=1590 or m['destination_folder_id']!=FOLDER_ID:raise ValueError('Manifest scope mismatch')
    for name,digest in m['files'].items():
        target=safe_target(p.parent,name)
        if sha(target.read_bytes())!=digest:raise ValueError('Bundle member digest mismatch')
    tasks=read(safe_target(p.parent,m['tasks_file']))
    if len(tasks)!=1590 or len({t['task_key'] for t in tasks})!=1590:raise ValueError('Task inventory mismatch')
    ids={t['behavior_id'] for t in tasks}
    if len(ids)!=159:raise ValueError('Behavior inventory mismatch')
    expected={(p,q,j) for p in ('H','N') for q in ('F','S') for j in ('HB','LG')}|{('H','R',j) for j in ('HB','LG')}
    for bid in ids:
        subset=[t for t in tasks if t['behavior_id']==bid]
        if len(subset)!=10 or {(t['prompt_factor'],t['response_factor'],t['evaluator']) for t in subset}!=expected:raise ValueError('Factorial binding mismatch')
        for t in subset:
            key='|'.join([bid,t['prompt_factor'],t['response_factor'],t['evaluator']])
            if t['task_key']!=key or sha(t['response'].encode())!=t['response_sha256']:raise ValueError('Task identity mismatch')
            if sha(t['behavior'].encode())!=t['behavior_sha256']:raise ValueError('Prompt digest mismatch')
    return m,tasks

class BudgetStop(RuntimeError):pass
class StageTimeout(RuntimeError):pass

class Session:
    def __init__(self,manifest_path,expected_manifest_sha,local,parent,run_id,connection_utc,balance,observed_utc,rate,marker_name=None,marker_sha256=None):
        if _OPERATIONAL is None:raise BudgetStop('Explicit operational configuration required')
        if now()>=LAST_LAUNCH:raise BudgetStop('No new run after configured launch cutoff')
        self.connection=timestamp(connection_utc)
        if self.connection!=timestamp(_OPERATIONAL.original_connection_utc):raise BudgetStop('Original connection anchor must not reset')
        if self.connection>now() or (now()-self.connection).total_seconds()>6600:raise BudgetStop('Connection clock invalid or expired')
        self.deadline=min(HARD_STOP,self.connection+dt.timedelta(minutes=110))
        self.failed=False;self.model=None;self.tok=None;self.judge=None;self.protocol=None
        self.secret=None;self.records={};self.stage_number=0;self.all_preflight_passed=False
        if not re.fullmatch(r'primarycontrol_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{12}',run_id):raise ValueError('New dated run identity required')
        self.manifest,self.tasks=verify_bundle(manifest_path,expected_manifest_sha)
        self.bundle=Path(manifest_path).parent
        self.expected_manifest_sha=expected_manifest_sha
        import operational_config
        for modpath in (Path(__file__),Path(storage.__file__),Path(operational_config.__file__)):
            if modpath.resolve().parent!=self.bundle.resolve() or sha(modpath.read_bytes())!=self.manifest['files'][modpath.name]:raise ValueError('Active module not frozen bundle')
        if sha((self.bundle/'HB_standard_template.txt').read_bytes())!=TEMPLATE_SHA or sha((self.bundle/'research_parsers.py').read_bytes())!=PARSER_SHA:raise ValueError('Historical render/parser mismatch')
        self.template=(self.bundle/'HB_standard_template.txt').read_text()
        self.local=Path(local)
        if not self.local.is_relative_to(Path(_OPERATIONAL.ephemeral_root)) or self.local.is_relative_to(Path(_OPERATIONAL.drive_mount)) or self.local.name!=run_id:raise ValueError('Ephemeral scratch required')
        self.guard=storage.DriveMountGuard(Path(parent),Path(_OPERATIONAL.drive_mount))
        self.parent=self.guard.parent
        # Exact-ID shortcut OR independent backend-verified identity marker for owned MyDrive folder.
        self.marker=None
        shortcut_ok=('.shortcut-targets-by-id' in self.parent.parts and self.parent.parts[self.parent.parts.index('.shortcut-targets-by-id')+1]==FOLDER_ID)
        if not shortcut_ok:
            expected_parent=Path(_OPERATIONAL.expected_parent)
            if self.parent!=expected_parent or not marker_name or not re.fullmatch(r'_primarycontrol_identity_[0-9a-f]{32}\.json',marker_name) or not re.fullmatch('[0-9a-f]{64}',marker_sha256 or ''):raise ValueError('Verified identity marker required for exact owned folder')
            marker_path=safe_target(self.parent,marker_name);data=marker_path.read_bytes()
            if sha(data)!=marker_sha256:raise ValueError('Identity marker byte mismatch')
            marker=json.loads(data)
            if marker['folder_id']!=FOLDER_ID or marker['manifest_sha256']!=expected_manifest_sha or marker['owner']!=_OPERATIONAL.owner_account or not re.fullmatch('[0-9a-f]{32}',marker['nonce']):raise ValueError('Marker binding mismatch')
            self.marker=(marker_path,data)
        self.remote=self.parent/run_id
        if self.local.exists() or self.remote.exists():raise ValueError('Fresh create-only run required; preserve existing attempts')
        self.observe_budget(balance,observed_utc,rate)
        self.local.mkdir();self.guard();self.remote.mkdir();self.guard()
        self.put('run_identity.json',{'run_id':run_id,'manifest_sha256':expected_manifest_sha,'connection_utc':connection_utc,'deadline_utc':self.deadline.isoformat(),'baseline_cu':BASELINE_CU,'stop_balance_cu':STOP_CU,'destination_folder_id':FOLDER_ID})
        for name in self.manifest['files']:
            self.put_bytes('frozen/'+name,safe_target(self.bundle,name).read_bytes())
        self.put_bytes('frozen/manifest.json',Path(manifest_path).read_bytes())
        self.put('tasks.json',self.tasks)
        self.record_budget()

    def observe_budget(self,balance,observed_utc,rate):
        d=timestamp(observed_utc);age=(now()-d).total_seconds()
        if type(balance) not in (float,int) or not math.isfinite(balance) or balance>BASELINE_CU or balance<=STOP_CU:raise BudgetStop('Balance outside permitted range')
        if type(rate) not in (float,int) or not math.isfinite(rate) or rate<=0 or rate>100:raise BudgetStop('Current positive CU rate required')
        if not 0<=age<=60:raise BudgetStop('Fresh visible budget observation required')
        # Reserve maximum eight-minute stage at displayed rate plus five-unit margin.
        if balance-rate*(8/60)<=STOP_CU:raise BudgetStop('Insufficient budget reserve for stage')
        self.balance=float(balance);self.rate=float(rate);self.observed=d

    def record_budget(self):
        self.put(f'budget/{self.stage_number:04d}.json',{'observed_utc':self.observed.isoformat(),'balance':self.balance,'rate_per_hour':self.rate,'stage':self.stage_number})

    def check(self):
        if self.failed:raise RuntimeError('Session failed; no retry allowed')
        if now()>=self.deadline:raise BudgetStop('Runtime deadline reached')
        # At most8min without fresh visible balance; rate projection leaves reserve.
        age=(now()-self.observed).total_seconds()
        if age>480 or self.balance-self.rate*age/3600<=STOP_CU:raise BudgetStop('Budget lease expired or reserve reached')
        self.guard()
        if self.marker is not None:storage.read_verified(*self.marker)
        if sha((self.bundle/'manifest.json').read_bytes())!=self.expected_manifest_sha:raise ValueError('Manifest changed during run')
        for name in ('control_runner.py','storage.py','research_parsers.py','HB_standard_template.txt'):
            if sha((self.bundle/name).read_bytes())!=self.manifest['files'][name]:raise ValueError('Code drift during run')

    def put_bytes(self,relative,data):
        if self.secret and self.secret.encode() in data:raise ValueError('Secret refused before write')
        try:
            storage.immutable_write(safe_target(self.local,relative),data)
            self.guard();storage.immutable_write(safe_target(self.remote,relative),data);self.guard()
            storage.read_verified(safe_target(self.remote,relative),data)
        except BaseException:
            self.failed=True
            raise

    def put(self,relative,obj):self.put_bytes(relative,canonical(obj))

    def packages(self,judge):
        import torch
        versions={p:importlib.metadata.version(p) for p in PACKAGES}
        if versions!=PACKAGES:raise ValueError('Package drift; no automatic install')
        if not torch.cuda.is_available():raise ValueError('CUDA absent')
        free,total=torch.cuda.mem_get_info()
        if free<(31 if judge=='HB' else 18)*1024**3:raise ValueError('Insufficient free memory')
        return {'packages':versions,'cuda':torch.version.cuda,'device':torch.cuda.get_device_name(0),'total_memory':total,'precision':'fp16'}

    def render(self,task):
        tok=self.tok;e=self.judge;response=task['response']
        if e=='HB':
            original_ids=tok.encode(response);tok.truncation_side='right'
            clipped_ids=tok.encode(response,max_length=512,truncation=True)
            effective=tok.decode(clipped_ids,skip_special_tokens=True)
            text=self.template.format(behavior=task['behavior'],generation=effective)
            full_ids=tok.encode(text);tok.truncation_side='left'
            ids=tok.encode(text,max_length=2048,truncation=True)
            policy={'response_original_tokens':len(original_ids),'response_clip_tokens':len(clipped_ids),'effective_response_sha256':sha(effective.encode()),'effective_response':effective,'full_input_tokens':len(full_ids),'dropped_prompt_tokens':len(full_ids)-len(ids),'dropped_response_tokens':len(original_ids)-len(clipped_ids)}
        else:
            messages=[{'role':'user','content':task['behavior']},{'role':'assistant','content':response}]
            text=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
            ids=tok.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,return_dict=False)
            if "ONLY THE LAST Agent message" not in text:raise ValueError('LG assistant target audit failed')
            if type(ids) is not list or not ids or any(type(i) is not int or i<0 for i in ids):raise ValueError('LG flat token contract')
            policy={'response_original_tokens':len(tok.encode(response)),'full_input_tokens':len(ids),'dropped_prompt_tokens':0,'dropped_response_tokens':0}
            if len(ids)>8192:policy['exclude_reason']='LG_input_over_8192_no_truncation'
        if task['response_factor']!='R':
            if policy['dropped_prompt_tokens'] or policy['dropped_response_tokens'] or 'exclude_reason' in policy:raise ValueError('Synthetic fixture truncation forbidden')
            if e=='HB' and policy['response_original_tokens']>384:raise ValueError('Synthetic response token gate')
        return text,ids,policy

    def _alarm(self,signum,frame):raise StageTimeout('Bounded stage exceeded')
    def begin_stage(self,balance,observed_utc,rate):
        self.observe_budget(balance,observed_utc,rate);self.check();self.stage_number+=1;self.record_budget()
        seconds=min(480,int((self.deadline-now()).total_seconds()))
        if seconds<=0:raise BudgetStop('No stage time remaining')
        signal.signal(signal.SIGALRM,self._alarm);signal.alarm(seconds)
    def end_stage(self):signal.alarm(0)

    def preflight_tokenizers(self,balance,observed_utc,rate,auth_token):
        """All tokenizer gates before ANY model weights or labels. Explicit LG auth only."""
        if self.records or self.model is not None or self.all_preflight_passed:raise ValueError('Preflight must precede all model execution')
        if not isinstance(auth_token,str) or not auth_token:raise ValueError('Authorized LG token required')
        self.begin_stage(balance,observed_utc,rate)
        try:
            from transformers import AutoTokenizer
            import huggingface_hub.constants as hub
            import transformers.utils.hub as th
            if os.environ.get('HF_ENDPOINT') not in (None,'https://huggingface.co') or hub.ENDPOINT!='https://huggingface.co' or getattr(th,'HUGGINGFACE_CO_RESOLVE_ENDPOINT','https://huggingface.co')!='https://huggingface.co':raise ValueError('Unofficial auth destination')
            self.secret=auth_token;reports={}
            for judge in ('HB','LG'):
                name,revision=MODELS[judge];self.judge=judge;paths={}
                for fast in (True,False):
                    self.check()
                    self.tok=AutoTokenizer.from_pretrained(name,revision=revision,token=auth_token if judge=='LG' else False,trust_remote_code=False,use_fast=fast)
                    template=self.template if judge=='HB' else self.tok.chat_template
                    if sha(template.encode())!=read(self.bundle/f'{judge}_baseline_protocol.json')['template_sha256']:raise ValueError('Tokenizer template drift')
                    path={}
                    for t in self.tasks:
                        if t['evaluator']!=judge:continue
                        text,ids,policy=self.render(t)
                        path[t['task_key']]={'input_ids_sha256':sha(canonical(ids)),'input_tokens':len(ids),'response_tokens':len(self.tok.encode(t['response'])),'serialized_sha256':sha(text.encode()),'token_policy':policy}
                    paths[str(fast)]={'tokenizer_class':type(self.tok).__name__,'tasks':path}
                    self.tok=None;gc.collect()
                # Fast/slow request paths must yield identical scientific inputs, not just counts.
                if paths['True']['tasks']!=paths['False']['tasks']:raise ValueError('Fast/slow tokenizer scientific disagreement')
                for bid in sorted({t['behavior_id'] for t in self.tasks}):
                    for prompt in ('H','N'):
                        a=paths['True']['tasks']['|'.join([bid,prompt,'F',judge])]['response_tokens']
                        b=paths['True']['tasks']['|'.join([bid,prompt,'S',judge])]['response_tokens']
                        if a<=0 or abs(b-a)/a>0.05:raise ValueError('Paired token length tolerance exceeded')
                reports[judge]=paths
            self.put('all_tokenizer_preflight.json',{'status':'PASS','labels_seen':0,'report':reports})
            self.preflight_reports=reports
            self.all_preflight_passed=True
            return {'status':'all_tokenizer_preflight_PASS','tasks':1590,'labels_seen':0}
        except BaseException:
            self.failed=True
            raise RuntimeError('All-tokenizer preflight stopped; no labels permitted; details suppressed') from None
        finally:self.secret=None;auth_token=None;self.tok=None;self.judge=None;self.end_stage()

    def load(self,judge,balance,observed_utc,rate,auth_token=None):
        if judge not in MODELS or (auth_token is not None and (judge!='LG' or not isinstance(auth_token,str) or not auth_token)):raise ValueError('Invalid explicit token scope')
        if not self.all_preflight_passed:raise ValueError('Both-judge fast/slow preflight required before weights')
        if self.model is not None:raise ValueError('Unload previous judge first')
        self.begin_stage(balance,observed_utc,rate)
        try:
            self.judge=judge;env=self.packages(judge)
            from transformers import AutoModelForCausalLM,AutoTokenizer
            import torch
            if judge=='LG':
                if auth_token is None:raise ValueError('Explicit authorized LG token required')
                import huggingface_hub.constants as hub
                import transformers.utils.hub as th
                if os.environ.get('HF_ENDPOINT') not in (None,'https://huggingface.co') or hub.ENDPOINT!='https://huggingface.co' or getattr(th,'HUGGINGFACE_CO_RESOLVE_ENDPOINT','https://huggingface.co')!='https://huggingface.co':raise ValueError('Unofficial auth destination')
            self.secret=auth_token
            name,revision=MODELS[judge];self.check()
            self.tok=AutoTokenizer.from_pretrained(name,revision=revision,token=auth_token if judge=='LG' else False,trust_remote_code=False)
            template=self.template if judge=='HB' else self.tok.chat_template
            baseline=read(self.bundle/f'{judge}_baseline_protocol.json')
            expected_settings={'seed':42,'do_sample':False,'temperature_inactive':0,'top_p_inactive':1,'max_new_tokens':1 if judge=='HB' else 128,'dtype':'float16','quantization':'none'}
            if baseline['settings']!=expected_settings or baseline['model_id']!=name or baseline['model_revision']!=revision or baseline['tokenizer_revision']!=revision:raise ValueError('Baseline scientific settings mismatch')
            if sha(template.encode())!=baseline['template_sha256']:raise ValueError('Tokenizer template drift')
            self.protocol={'schema':'primary-control-20261102-v1','judge':judge,'model_id':name,'model_revision':revision,'tokenizer_revision':revision,'template_sha256':sha(template.encode()),'environment':env,'settings':baseline['settings'],'parser_code_sha256':PARSER_SHA,'manifest_sha256':sha((self.bundle/'manifest.json').read_bytes()),'tasks_sha256':sha(canonical(self.tasks))}
            self.put(f'{judge}_protocol.json',self.protocol)
            # Render all inputs before weights: catch any unexpected truncation.
            for task in self.tasks:
                if task['evaluator']==judge:
                    rendered,ids,policy=self.render(task)
                    expected=self.preflight_reports[judge]['True']['tasks'][task['task_key']]
                    if sha(rendered.encode())!=expected['serialized_sha256'] or sha(canonical(ids))!=expected['input_ids_sha256'] or policy!=expected['token_policy']:raise ValueError('Load tokenizer differs from all-preflight input')
            self.check()
            self.model=AutoModelForCausalLM.from_pretrained(name,revision=revision,token=auth_token if judge=='LG' else False,trust_remote_code=False,use_safetensors=True,torch_dtype=torch.float16,device_map={'':0})
            self.observed_config_commit=getattr(self.model.config,'_commit_hash',None)
            if self.observed_config_commit is not None and self.observed_config_commit!=revision:raise ValueError('Observed loaded revision mismatch')
            self.put(f'{judge}_load_receipt.json',{'model_id':name,'requested_model_revision':revision,'requested_tokenizer_revision':revision,'observed_config_commit':self.observed_config_commit,'observed_commit_available':self.observed_config_commit is not None,'evidence':'exact immutable revision passed to official Hugging Face loader; absent config commit is unavailable metadata, not independent loaded-revision verification','weights_loaded_at_utc':now().isoformat()})
            self.model.eval();self.check()
            return {'status':'loaded','judge':judge,'records':len(self.records)}
        except BaseException:
            self.failed=True
            raise RuntimeError('Load stopped; exception details suppressed') from None
        finally:self.secret=None;auth_token=None;self.end_stage()

    def batch(self,balance,observed_utc,rate,limit=MAX_BATCH):
        if not self.all_preflight_passed:raise ValueError('All-tokenizer preflight required')
        if self.model is None or type(limit) is not int or not 1<=limit<=MAX_BATCH:raise ValueError('Loaded judge and bounded batch required')
        self.begin_stage(balance,observed_utc,rate)
        try:
            import torch
            from transformers import set_seed
            tasks=sorted((t for t in self.tasks if t['evaluator']==self.judge),key=lambda t:sha(('primary-control-order-v1:'+t['task_key']).encode()))
            pending=[t for t in tasks if t['task_key'] not in self.records][:limit]
            for task in pending:
                self.check();text,ids,policy=self.render(task)
                expected=self.preflight_reports[self.judge]['True']['tasks'][task['task_key']]
                if sha(text.encode())!=expected['serialized_sha256'] or sha(canonical(ids))!=expected['input_ids_sha256'] or policy!=expected['token_policy']:raise ValueError('Per-record tokenizer drift')
                base={'task_key':task['task_key'],'task_sha256':sha(canonical(task)),'behavior_id':task['behavior_id'],'prompt_factor':task['prompt_factor'],'response_factor':task['response_factor'],'evaluator':self.judge,'model_id':MODELS[self.judge][0],'model_revision':MODELS[self.judge][1],'tokenizer_revision':MODELS[self.judge][1],'observed_config_commit':self.observed_config_commit,'response_sha256':task['response_sha256'],'behavior_sha256':task['behavior_sha256'],'protocol_sha256':sha(canonical(self.protocol)),'serialized_input_before_prompt_truncation':text,'serialized_input_sha256':sha(text.encode()),'input_token_ids':ids,'input_token_ids_sha256':sha(canonical(ids)),'input_tokens':len(ids),'token_policy':policy,'parser_version':VERSION}
                if 'exclude_reason' in policy:
                    record=dict(base,status='excluded',parsed=None,new_label_binary=None)
                else:
                    self.check();set_seed(42);tensor=torch.tensor([ids],device='cuda');started=now().isoformat()
                    with torch.inference_mode():
                        result=self.model.generate(input_ids=tensor,attention_mask=torch.ones_like(tensor),do_sample=False,max_new_tokens=1 if self.judge=='HB' else 128,pad_token_id=self.tok.eos_token_id)
                    torch.cuda.synchronize();ended=now().isoformat();continuation=result[0,len(ids):].tolist()
                    raw=self.tok.decode(continuation,skip_special_tokens=True,clean_up_tokenization_spaces=False)
                    full=self.tok.decode(continuation,skip_special_tokens=False,clean_up_tokenization_spaces=False)
                    parsed=parse(raw,self.judge)
                    record=dict(base,status='judged',raw_judge_completion=raw,raw_judge_sha256=sha(raw.encode()),raw_decoded_with_special_tokens=full,raw_decoded_with_special_tokens_sha256=sha(full.encode()),output_token_ids=continuation,output_tokens=len(continuation),started_at_utc=started,ended_at_utc=ended,parsed=parsed,new_label_binary={'safe':0,'unsafe':1}.get(parsed['label']))
                record['content_sha256']=sha(canonical(record))
                # Stage deadline must not discard a completed generation while committing.
                # Allow bounded persistence (60s), then stop before the next record if lease expired.
                signal.alarm(60)
                self.put('records/'+sha(task['task_key'].encode())+'.json',record)
                signal.alarm(max(1,min(60,int((self.deadline-now()).total_seconds()))))
                self.records[task['task_key']]=record
            result={'status':'batch_complete','judge':self.judge,'batch_records':len(pending),'judge_records':sum(t['evaluator']==self.judge for t in self.records.values()),'total_records':len(self.records)}
            self.put(f'checkpoints/{self.stage_number:04d}.json',result)
            result['stage_archive']=self.export_stage([t['task_key'] for t in pending])
            return result
        except BaseException:
            self.failed=True
            raise RuntimeError('Batch stopped; preserve records and terminate runtime; details suppressed') from None
        finally:self.end_stage()

    def export_stage(self,keys):
        """Immutable per-stage archive for separate connector backend verification."""
        if len(keys)!=len(set(keys)) or any(k not in self.records for k in keys):raise ValueError('Archive task inventory')
        members={}
        for name in ('run_identity.json','tasks.json','all_tokenizer_preflight.json',f'{self.judge}_protocol.json',f'{self.judge}_load_receipt.json'):
            data=safe_target(self.local,name).read_bytes()
            storage.read_verified(safe_target(self.remote,name),data);members[name]=data
        for key in keys:
            name='records/'+sha(key.encode())+'.json';data=canonical(self.records[key])
            storage.read_verified(safe_target(self.local,name),data);storage.read_verified(safe_target(self.remote,name),data);members[name]=data
        manifest={'schema':'primary-control-stage-archive-v1','stage':self.stage_number,'judge':self.judge,'records':len(keys),'task_keys':keys,'files':{name:{'bytes':len(data),'sha256':sha(data)} for name,data in members.items()},'evidence':'mounted_readback_only_backend_verification_pending'}
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
            for name,data in sorted(members.items()):z.writestr(name,data)
            z.writestr('STAGE_MANIFEST.json',canonical(manifest))
        data=buf.getvalue()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if z.testzip() is not None or len(z.namelist())!=len(members)+1:raise ValueError('Archive CRC failed')
        name=f'archives/stage_{self.stage_number:04d}_{self.judge}_{len(keys)}records.zip'
        self.put_bytes(name,data)
        receipt={'relative_path':name,'bytes':len(data),'sha256':sha(data),'records':len(keys),'judge':self.judge,'backend_verified':False}
        self.put(f'archives/stage_{self.stage_number:04d}_receipt.json',receipt)
        return receipt

    def unload(self):
        self.model=None;self.tok=None;self.secret=None;gc.collect()
        import torch
        torch.cuda.empty_cache()

    def finish(self):
        planned={t['task_key'] for t in self.tasks};missing=sorted(planned-set(self.records))
        counts=collections.Counter(r['parsed']['label'] if r.get('parsed') else r['status'] for r in self.records.values())
        result={'planned':1590,'records':len(self.records),'missing_task_keys':missing,'counts':dict(counts),'task_accounted_complete':not missing,'valid_binary':counts['safe']+counts['unsafe'],'backend_verified':False,'evidence':'mounted_filesystem_readback_only'}
        self.put('completion.json',result)
        return result

def preflight_with_colab_secret(session,balance,observed_utc,rate):
    """Explicit post-freeze call only; no credentials in arguments/artifacts/logs."""
    token=None
    try:
        session.check();session.packages('HB')
        import huggingface_hub.constants as hub
        import transformers.utils.hub as th
        if os.environ.get('HF_ENDPOINT') not in (None,'https://huggingface.co') or hub.ENDPOINT!='https://huggingface.co' or getattr(th,'HUGGINGFACE_CO_RESOLVE_ENDPOINT','https://huggingface.co')!='https://huggingface.co':raise ValueError('Endpoint scope')
        from google.colab import userdata
        token=userdata.get('HF_TOKEN')
        return session.preflight_tokenizers(balance,observed_utc,rate,token)
    except BaseException:
        session.failed=True
        return {'status':'STOPPED','stage':'all_tokenizer_preflight','details_suppressed':True}
    finally:token=None;gc.collect()

def load_lg_with_colab_secret(session,balance,observed_utc,rate):
    """Explicit approved LG load only after all-input preflight."""
    token=None
    try:
        if not session.all_preflight_passed or session.model is not None:raise ValueError('LG stage gate')
        session.check();session.packages('LG')
        import huggingface_hub.constants as hub
        import transformers.utils.hub as th
        if os.environ.get('HF_ENDPOINT') not in (None,'https://huggingface.co') or hub.ENDPOINT!='https://huggingface.co' or getattr(th,'HUGGINGFACE_CO_RESOLVE_ENDPOINT','https://huggingface.co')!='https://huggingface.co':raise ValueError('Endpoint scope')
        from google.colab import userdata
        token=userdata.get('HF_TOKEN')
        return session.load('LG',balance,observed_utc,rate,token)
    except BaseException:
        session.failed=True
        return {'status':'STOPPED','stage':'LG_load','details_suppressed':True}
    finally:token=None;gc.collect()
