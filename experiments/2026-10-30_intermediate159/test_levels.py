"""Neutral synthetic-only fixtures; no private archives, baseline outputs or tokens."""
import ast
import collections
import contextlib
import csv
import datetime
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

import colab_smoke as r
import drive_wrapper as w
import colab_secret_launcher as launcher

ROOT=Path(__file__).parent
OLD_CORE=ROOT.parents[1]/'code'
INPUT=Path('SYNTHETIC_INPUT_NOT_A_PRIVATE_ARCHIVE')
from synthetic_fixtures import source_rows, bound_tasks, scientific_references, LG_TEMPLATE
FAKE='SYNTHETIC_CREDENTIAL_SENTINEL_NOT_A_REAL_TOKEN'
BEFORE=datetime.datetime(2026,10,30,7,59,59,tzinfo=datetime.timezone.utc)
AFTER=datetime.datetime(2026,10,30,8,0,1,tzinfo=datetime.timezone.utc)


class FakeLibraries:
    def __init__(self,fail=False,secret_output=False,on_generate=None,template=None):
        self.loads=[];self.generations=[];outer=self
        class Tokenizer:
            chat_template=template or LG_TEMPLATE
            eos_token_id=2
            @classmethod
            def from_pretrained(cls,name,**kwargs):
                outer.loads.append(('tokenizer',name,kwargs))
                if fail:
                    print('Authorization: Bearer '+FAKE)
                    raise RuntimeError('synthetic secret '+FAKE)
                tok=cls();tok.judge='HB' if name==r.MODELS['HB'][0] else 'LG';return tok
            def encode(self,text,**kwargs):return [1,3,5]
            def apply_chat_template(self,messages,tokenize,add_generation_prompt,return_dict=True):
                if not tokenize:return json.dumps(messages,sort_keys=True)
                return {'input_ids':[1,3,5]} if return_dict else [1,3,5]
            def decode(self,ids,**kwargs):
                return FAKE if secret_output else ('No' if self.judge=='HB' else 'safe')
        class Result:
            def __getitem__(self,key):return types.SimpleNamespace(tolist=lambda:[9])
        class Model:
            @classmethod
            def from_pretrained(cls,name,**kwargs):
                outer.loads.append(('model',name,kwargs));obj=cls();obj.config=types.SimpleNamespace(_commit_hash=kwargs['revision']);return obj
            def eval(self):pass
            def generate(self,**kwargs):
                outer.generations.append(kwargs)
                if on_generate:on_generate()
                return Result()
        self.modules={
            'torch':types.SimpleNamespace(float16='float16',tensor=lambda value,device:value,ones_like=lambda value:value,inference_mode=contextlib.nullcontext,
                version=types.SimpleNamespace(cuda='fixture'),cuda=types.SimpleNamespace(is_available=lambda:True,mem_get_info=lambda:(35*1024**3,40*1024**3),get_device_name=lambda i:'offline fixture',synchronize=lambda:None,empty_cache=lambda:None)),
            'transformers':types.SimpleNamespace(AutoTokenizer=Tokenizer,AutoModelForCausalLM=Model,BitsAndBytesConfig=lambda **kw:None,set_seed=lambda seed:None),
            'huggingface_hub.constants':types.SimpleNamespace(ENDPOINT='https://huggingface.co'),
            'transformers.utils.hub':types.SimpleNamespace(HUGGINGFACE_CO_RESOLVE_ENDPOINT='https://huggingface.co')}


class LevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data={c:bound_tasks(r,c) for c in r.CONDITIONS}
        cls.rows,cls.blobs,cls.mb,cls.manifest=source_rows()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
        self.clock=patch.object(r,'execution_utcnow',return_value=BEFORE);self.clock.start();self.addCleanup(self.clock.stop)
        self.time=patch.object(r,'utc',return_value=BEFORE.isoformat());self.time.start();self.addCleanup(self.time.stop)
    def test_synthetic_all1590_exact_membership_order_seed_and_conditions(self):
        all_tasks=[]
        ids=None
        for condition,(tasks,provenance) in self.data.items():
            self.assertEqual(len(tasks),318);self.assertEqual({x['condition'] for x in tasks},{condition})
            self.assertEqual(collections.Counter(t['evaluator'] for t in tasks),{'HB':159,'LG':159})
            self.assertTrue(all(t['source_seed']==42 for t in tasks))
            selected=provenance['selected_id_order']
            self.assertEqual(selected,sorted(selected,key=lambda x:(r.sha(('42:'+x).encode()),x)))
            if ids is None:ids=selected
            self.assertEqual(selected,ids)
            self.assertEqual(provenance['excluded_counts'],{'contextual':81,'copyright':80})
            for c,inventory in provenance['verified_all_conditions_all_available_seeds'].items():
                self.assertEqual(inventory['available_seeds'],[42] if c in ('SP30','SP40') else [42,123,2024])
            for task in tasks:
                self.assertEqual(task['response_sha256'],r.sha(task['response'].encode()))
                self.assertIs(type(task['legacy_label']),int)
            all_tasks.extend(tasks)
        self.assertEqual((len(all_tasks),len({t['task_key'] for t in all_tasks})),(1590,1590))
    def bind(self,blobs):return r.bind_condition_tasks(self.rows,blobs,self.mb,self.manifest,'SP30')
    def test_unselected_condition_excluded_row_and_other_seed_mismatch_refused(self):
        i=next(i for i,row in enumerate(self.rows) if row['FunctionalCategory']=='copyright')
        for name,seed in [('raw/safety_sparsegpt-sp60-multiseed_harmbench.json',42),('raw/safety_sparsegpt-sp55-multiseed_llamaguard.json',123)]:
            blobs=dict(self.blobs);obj=json.loads(blobs[name]);next(x for x in obj['evaluations'] if x['seed']==seed)['samples'][i]['response']='synthetic mismatch';blobs[name]=json.dumps(obj).encode()
            with self.subTest(name=name,seed=seed),self.assertRaises(ValueError):self.bind(blobs)
    def test_duplicate_or_missing_seed_and_short_arrays_refused(self):
        name='raw/responses_sparsegpt-sp50-multiseed.json'
        for kind in ('duplicate','missing','short'):
            blobs=dict(self.blobs);obj=json.loads(blobs[name])
            if kind=='duplicate':obj['generations'][1]['seed']=42
            elif kind=='missing':obj['generations'].pop()
            else:obj['generations'][0]['responses'].pop()
            blobs[name]=json.dumps(obj).encode()
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.bind(blobs)
    def test_unknown_condition_refused(self):
        for condition in ('FP16','SP70','SP35','both',''):
            with self.assertRaises(ValueError):r.inputs(INPUT,condition)
    def test_render_parser_and_scientific_settings_unchanged(self):
        old=ast.parse((OLD_CORE/'colab_smoke.py').read_text());new=ast.parse((ROOT/'colab_smoke.py').read_text())
        a={x.name:ast.dump(x) for x in old.body if isinstance(x,ast.FunctionDef)};b={x.name:ast.dump(x) for x in new.body if isinstance(x,ast.FunctionDef)}
        for name in ('render','parser','verify_record','commit_record','freeze','records_checked','seed42'):
            self.assertEqual(a[name],b[name],name)
        self.assertEqual((ROOT/'research_parsers.py').read_bytes(),(OLD_CORE/'research_parsers.py').read_bytes())
        self.assertEqual((ROOT/'HB_standard_template.txt').read_bytes(),(OLD_CORE/'HB_standard_template.txt').read_bytes())
    def test_package_version_gate_exact_and_drift_stops_before_load(self):
        libs=FakeLibraries()
        with patch.dict(sys.modules,libs.modules),patch.object(r.importlib.metadata,'version',side_effect=lambda p:r.BASELINE_PACKAGES[p]):
            self.assertEqual(r.gpu_preflight('fp16',['HB'])['packages'],r.BASELINE_PACKAGES)
        wrong={**r.BASELINE_PACKAGES,'transformers':'5.99.0'}
        with patch.dict(sys.modules,libs.modules),patch.object(r.importlib.metadata,'version',side_effect=lambda p:wrong[p]),self.assertRaises(RuntimeError):r.gpu_preflight('fp16',['HB'])
        self.assertFalse(libs.loads)
    def test_v5_mapping_default_is_explicitly_disabled(self):
        libs=FakeLibraries();tok=libs.modules['transformers'].AutoTokenizer.from_pretrained(r.MODELS['LG'][0]);task=self.data['SP30'][0][0]
        default=tok.apply_chat_template([],tokenize=True,add_generation_prompt=True)
        self.assertIsInstance(default,dict)
        _,ids,policy=r.render(task,'LG',tok)
        self.assertEqual(ids,default['input_ids']);self.assertIs(policy['apply_chat_template_return_dict'],False)

    def run_stage(self,condition,judge,libs=None,token=None,small=False,mirror=None,real_main=False):
        libs=libs or FakeLibraries();tasks,prov=self.data[condition]
        if small:tasks=tasks[:6]
        local=self.root/condition/'scratch';remote=self.root/condition/'drive'
        identity={'schema':w.SCHEMA,'condition':condition,'required_package_versions':r.BASELINE_PACKAGES}
        m=mirror or w.Mirror(local,remote,identity)
        env={'packages':r.BASELINE_PACKAGES,'precision':'fp16','fixture':True}
        args=types.SimpleNamespace(out=str(local),judge=judge,precision='fp16',condition=condition)
        def main(auth_token=None):
            for name,obj in [('tasks.json',tasks),('input_provenance.json',prov),('environment.json',env)]:r.freeze(local/name,obj)
            r.inference(args,tasks,prov,env,auth_token=auth_token)
        old_main=r.main
        captured=io.StringIO()
        scope=contextlib.ExitStack()
        with scope:
            scope.enter_context(patch.dict(sys.modules,libs.modules))
            scope.enter_context(contextlib.redirect_stdout(captured));scope.enter_context(contextlib.redirect_stderr(captured))
            if not real_main:scope.enter_context(patch.object(r,'main',main))
            else:scope.enter_context(patch.object(r,'inputs',side_effect=lambda path,condition:bound_tasks(r,condition)))
            if small:
                scope.enter_context(patch.multiple(w,PER_JUDGE=3,TOTAL_TASKS=6));scope.enter_context(patch.multiple(r,PER_JUDGE=3,TOTAL_TASKS=6))
            argv=['--condition',condition,'--zip',str(INPUT),'--out',str(local),'--judge',judge,'--precision','fp16'] if real_main else []
            code=w.execute(r,m,argv,'inference',judge,auth_token=token)
        return code,libs,m,captured.getvalue()

    def test_all_five_condition_fake1590_records_and_separate_checkpoints(self):
        libs=FakeLibraries();all_keys=set()
        refs=scientific_references(r)
        for condition in r.CONDITIONS:
            for judge in ('HB','LG'):
                local=self.root/condition/'scratch';remote=self.root/condition/'drive'
                m=w.Mirror(local,remote,{'schema':w.SCHEMA,'condition':condition,'required_package_versions':r.BASELINE_PACKAGES});m.scientific_references=refs
                if judge=='LG':w.validate_condition_hb_stage(m,r,self.data[condition][0])
                code,_,m,captured=self.run_stage(condition,judge,libs,FAKE if judge=='LG' else None,mirror=m)
                self.assertEqual(code,0,captured)
                mark=json.loads((m.remote/f'_mirror/{judge}_MIRROR_COMPLETE.json').read_text());self.assertEqual(mark['judged'],159)
            self.assertEqual(json.loads((m.remote/'_mirror/RUN_MIRROR_COMPLETE.json').read_text())['judged'],318)
            records=r.records_checked(m.local,self.data[condition][0]);self.assertEqual(len(records),318)
            self.assertFalse(all_keys&{x['task_key'] for x in records});all_keys.update(x['task_key'] for x in records)
        self.assertEqual((len(libs.generations),len(all_keys)),(1590,1590))
        self.assertEqual(len(libs.loads),20)
        for _,name,kw in libs.loads:self.assertEqual(kw['token'],False if name==r.MODELS['HB'][0] else FAKE)
        for p in self.root.rglob('*'):
            if p.is_file():self.assertNotIn(FAKE.encode(),p.read_bytes())
    def test_protocol_template_drift_stops_before_weight_load(self):
        condition='SP30';m=w.Mirror(self.root/condition/'scratch',self.root/condition/'drive',{'condition':condition,'required_package_versions':r.BASELINE_PACKAGES})
        m.scientific_references=scientific_references(r)
        code,libs,m,_=self.run_stage(condition,'LG',FakeLibraries(template='changed template'),FAKE,mirror=m)
        self.assertEqual(code,1);self.assertEqual(len(libs.loads),1);self.assertFalse(libs.generations)
        self.assertFalse((m.remote/'LG_protocol.json').exists())
    def test_cross_condition_identity_resume_refused(self):
        code,_,m,_=self.run_stage('SP30','HB',small=True);self.assertEqual(code,0)
        changed=w.Mirror(m.local,m.remote,{**m.identity,'condition':'SP40'})
        code,libs,_,_=self.run_stage('SP30','HB',small=True,mirror=changed)
        self.assertEqual(code,1);self.assertFalse(libs.loads)
    def test_secret_in_library_output_exception_and_raw_never_written(self):
        for fail,secret in ((True,False),(False,True)):
            with self.subTest(fail=fail,secret=secret):
                self.temp.cleanup();self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
                code,libs,m,captured=self.run_stage('SP30','LG',FakeLibraries(fail=fail,secret_output=secret),FAKE,small=True)
                self.assertEqual(code,1);self.assertNotIn(FAKE,captured)
                self.assertEqual(len(libs.generations),0 if fail else 1)
                for p in self.root.rglob('*'):
                    if p.is_file():self.assertNotIn(FAKE.encode(),p.read_bytes())
    def test_token_rejected_for_hb_before_any_load(self):
        code,libs,m,captured=self.run_stage('SP30','HB',token=FAKE,small=True)
        self.assertEqual(code,1);self.assertFalse(libs.loads);self.assertFalse(m.remote.exists())
    def test_lg_launcher_failed_preflight_does_not_read_secret(self):
        colab=types.SimpleNamespace(userdata=types.SimpleNamespace(get=lambda key:self.fail('secret read despite cutoff/preflight failure')))
        with patch.object(w,'require_official_hf_endpoint'),patch.object(w,'main',return_value=1),patch.dict(sys.modules,{'google.colab':colab}),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(launcher.launch_from_colab_secrets(['--condition','SP30','--judge','LG']),1)
    def test_cutoff_before_start_blocks_all_loads_with_explicit_incomplete(self):
        with patch.object(r,'execution_utcnow',return_value=AFTER):code,libs,m,_=self.run_stage('SP30','HB')
        self.assertEqual(code,1);self.assertFalse(libs.loads)
        stopped=list(m.remote.rglob('STOPPED.json'));self.assertEqual(len(stopped),1)
        self.assertEqual(json.loads(stopped[0].read_text())['status'],'incomplete_cutoff')
    def test_inflight_crosses_cutoff_record_mirrored_before_stop(self):
        now=[BEFORE]
        libs=FakeLibraries(on_generate=lambda:now.__setitem__(0,AFTER))
        root=self.root
        class TestPath(type(Path())):
            def is_relative_to(self,other):
                if str(other)=='/content':return str(self).startswith(str(root))
                if str(other)=='/content/drive':return False
                return super().is_relative_to(other)
        with patch.object(r,'Path',TestPath),patch.object(r,'execution_utcnow',side_effect=lambda:now[0]),patch.object(r,'gpu_preflight',return_value={'packages':r.BASELINE_PACKAGES,'precision':'fp16'}):
            code,libs,m,captured=self.run_stage('SP30','HB',libs=libs,real_main=True)
        self.assertEqual(code,1,captured);self.assertEqual(len(libs.generations),1)
        local=list((m.local/'records').glob('*.json'));remote=list((m.remote/'records').glob('*.json'))
        self.assertEqual((len(local),len(remote)),(1,1));self.assertEqual(local[0].read_bytes(),remote[0].read_bytes())
        stop=list(m.remote.glob('cutoff_stop_HB_*.json'));self.assertEqual(len(stop),1)
        self.assertEqual(json.loads(stop[0].read_text())['status'],'incomplete_cutoff')
        self.assertFalse((m.remote/'_mirror/HB_MIRROR_COMPLETE.json').exists())


if __name__=='__main__':unittest.main()
