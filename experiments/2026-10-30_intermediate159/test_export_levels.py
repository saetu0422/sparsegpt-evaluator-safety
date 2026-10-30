"""Neutral synthetic exports only. Private plan/source/lineage are explicitly mocked.

Production guards are unchanged; no actual dataset, credentials or models are used.
"""
import contextlib,csv,datetime,io,json,shutil,subprocess,sys,tempfile,types,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import EXPORT_LEVELS_RESULTS as e
import colab_smoke as r
import drive_wrapper as w
from test_levels import FakeLibraries,BEFORE,FAKE
from synthetic_fixtures import bound_tasks,scientific_references

ROOT=Path(__file__).parent
CODE=None  # Generated private-deployment stand-in in class setup.
SYNTHETIC_BASELINE='full159_20000101T000000Z_000000000001'
SYNTHETIC_FOLDER='SYNTHETIC_FOLDER_ID'
SYNTHETIC_INPUT=b'NEUTRAL SYNTHETIC INPUT LOADER STAND-IN; NOT RESEARCH DATA'
SYNTHETIC_PLAN=b'NEUTRAL SYNTHETIC PLAN STAND-IN; NOT FROZEN PLAN'
SYNTHETIC_ARCHIVE=b'NEUTRAL SYNTHETIC BASELINE ARCHIVE STAND-IN; NO RESEARCH DATA'
SYNTHETIC_BUNDLE=None  # Generated complete private-deployment stand-in in class setup.
SYNTHETIC_BUNDLE_NAME='synthetic_reviewed_deployment_bundle.zip'
ARCHIVE_NAME=SYNTHETIC_BASELINE+'_HB_LG_636_complete_results.zip'


def synthetic_lineage(source,runner,tasks,provenance,archive):
    return {'synthetic_fixture':True,'new_condition':provenance['condition'],
            'new_tasks_sha256':runner.sha(runner.canonical(tasks)),
            'baseline_scientific_fields':scientific_references(runner)}
RUN_IDS={c:'levels159_'+c+'_20261030T043000Z_'+format(i+1,'012x') for i,c in enumerate(r.CONDITIONS)}
EXPORT_ID='levels159_export_20261030T043500Z_123456789abc'
ENV={'packages':r.BASELINE_PACKAGES,'precision':'fp16','device':'offline fixture','cuda':'fixture','total_memory':40*1024**3}


def build_run(content,parent,condition,partial=False,excluded=False):
    run_id=RUN_IDS[condition];local=content/run_id;remote=parent/run_id
    tasks,provenance=bound_tasks(r,condition)
    lineage=w.validate_baseline_lineage(parent/w.BASELINE_RUN_ID,r,tasks,provenance,parent/ARCHIVE_NAME)
    identity={'schema':w.SCHEMA,'run_id':run_id,'input_sha256':w.INPUT_SHA,'runner_code':w.PINNED,'wrapper_sha256':e.WRAPPER_SHA,'precision':'fp16','verified_drive_folder_id':e.FOLDER_ID,'authentication_policy':'explicit_in_memory_LG_argument_only_no_login_or_token_save','scope':'one_condition159_standard_IDs_x_HB_LG_318_new_judgments','condition':condition,'planned_conditions':list(w.CONDITIONS),'planned_new_judgments_all_conditions':1590,'analysis_plan_sha256':w.ANALYSIS_PLAN_SHA,'analysis_plan_status':e.PLAN_STATUS,'expected_ids':159,'expected_per_judge':159,'expected_total_tasks':318,'execution_cutoff_utc':r.EXECUTION_CUTOFF_UTC,'required_package_versions':r.BASELINE_PACKAGES,'folder_mapping_evidence':'operator verified; FUSE cannot prove Drive folder ID','durability_evidence':'mounted filesystem write/read/hash only, backend verification outstanding','baseline_lineage':lineage}
    libs=FakeLibraries()
    tok=libs.modules['transformers'].AutoTokenizer
    def decode(self,ids,**kwargs):
        if len(ids)!=1:return 'No'
        index=getattr(self,'fixture_output_index',0)
        raw='unrecognized' if index==0 else ('Yes' if self.judge=='HB' else 'unsafe\nS1') if index==1 else 'No' if self.judge=='HB' else 'safe'
        if kwargs.get('skip_special_tokens') is False:self.fixture_output_index=index+1
        return raw
    tok.decode=decode
    if excluded:
        original=tok.apply_chat_template
        def chat(self,messages,**kwargs):
            if kwargs['tokenize'] and not getattr(self,'fixture_exclusion_done',False):self.fixture_exclusion_done=True;return [1]*8193
            return original(self,messages,**kwargs)
        tok.apply_chat_template=chat
    for judge in ('HB','LG'):
        mirror=w.Mirror(local,remote,identity);mirror.begin()
        try:
            if judge=='HB':
                for name in w.PINNED:mirror.dual('_mirror/code/'+name,(CODE/name).read_bytes())
                mirror.dual('_mirror/code/drive_wrapper.py',(CODE/'drive_wrapper.py').read_bytes())
                for name,obj in [('config.json',identity),('lineage/baseline.json',lineage)]:mirror.dual('_mirror/'+name,r.canonical(obj))
                mirror.dual('_mirror/analysis/analysis_plan.json',SYNTHETIC_PLAN);mirror.dual('_mirror/inputs/verified_inputs.zip',SYNTHETIC_INPUT)
                for name,obj in [('tasks.json',tasks),('input_provenance.json',provenance),('environment.json',ENV)]:r.freeze(local/name,obj)
            args=types.SimpleNamespace(out=str(local),condition=condition,judge=judge,precision='fp16')
            selected=tasks
            if partial and judge=='LG':selected=[t for t in tasks if t['evaluator']=='HB']+[t for t in tasks if t['evaluator']=='LG'][:1]
            with patch.dict(sys.modules,libs.modules),patch.object(r,'execution_utcnow',return_value=BEFORE),patch.object(r,'utc',return_value=BEFORE.isoformat()):
                # Keep protocol bound to all318 tasks even in partial fixture by
                # interrupting actual fake generation after first LG output.
                if partial and judge=='LG':
                    model=libs.modules['transformers'].AutoModelForCausalLM;original=model.generate;calls=[0]
                    def generate(self,**kwargs):
                        calls[0]+=1
                        if calls[0]>1:raise RuntimeError('offline partial fixture interruption')
                        return original(self,**kwargs)
                    with patch.object(model,'generate',generate):
                        try:r.inference(args,tasks,provenance,ENV,auth_token=FAKE)
                        except RuntimeError:pass
                else:r.inference(args,tasks,provenance,ENV,auth_token=FAKE if judge=='LG' else None)
            mirror.reconcile()
            if not(partial and judge=='LG'):mirror.finish('inference',judge)
        finally:mirror.close()
    return local,remote


def build_project(root):
    content=root/'content';content.mkdir();parent=content/'drive/.shortcut-targets-by-id'/e.FOLDER_ID/'cc_project';parent.mkdir(parents=True)
    baseline=parent/w.BASELINE_RUN_ID
    input_path=baseline/'_mirror/inputs/verified_inputs.zip';input_path.parent.mkdir(parents=True)
    input_path.write_bytes(SYNTHETIC_INPUT)
    (parent/ARCHIVE_NAME).write_bytes(SYNTHETIC_ARCHIVE)
    (parent/SYNTHETIC_BUNDLE_NAME).write_bytes(SYNTHETIC_BUNDLE)
    for c in r.CONDITIONS:build_run(content,parent,c)


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global CODE,SYNTHETIC_BUNDLE
        cls.fixture=tempfile.TemporaryDirectory();cls.fixture_root=Path(cls.fixture.name)
        cls.addClassCleanup(cls.fixture.cleanup)
        CODE=cls.fixture_root/'code';CODE.mkdir()
        for name in ('colab_smoke.py','research_parsers.py','HB_standard_template.txt','drive_wrapper.py','colab_secret_launcher.py','COLAB_SETUP_LEVELS.py','COLAB_RUN_CONDITION.py','EXPORT_LEVELS_RESULTS.py'):
            shutil.copyfile(ROOT/name,CODE/name)
        (CODE/'analysis_plan.json').write_bytes(SYNTHETIC_PLAN)
        contents={name:(CODE/name).read_bytes() for name in e.REQUIRED_DEPLOYMENT_MEMBERS}
        manifest={'files':{name:{'bytes':len(data),'sha256':e.sha(data)} for name,data in contents.items()}}
        contents['MANIFEST.json']=json.dumps(manifest,sort_keys=True).encode()
        (CODE/'MANIFEST.json').write_bytes(contents['MANIFEST.json'])
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
            for name,data in contents.items():z.writestr(name,data)
        SYNTHETIC_BUNDLE=buffer.getvalue()
        cls.bundle_contents={name:data for name,data in contents.items() if name!='MANIFEST.json'}
        cls.settings=contextlib.ExitStack();cls.addClassCleanup(cls.settings.close)
        # Only the neutral plan member gets a synthetic deployment-pin override.
        cls.settings.enter_context(patch.dict(e.DEPLOYMENT_PINS,{'analysis_plan.json':e.sha(SYNTHETIC_PLAN)}))
        cls.settings.enter_context(patch.multiple(e,FOLDER_ID=SYNTHETIC_FOLDER,PLAN_SHA=e.sha(SYNTHETIC_PLAN),
            BUNDLE_SHA=e.sha(SYNTHETIC_BUNDLE),BUNDLE_NAME=SYNTHETIC_BUNDLE_NAME))
        cls.settings.enter_context(patch.multiple(w,INPUT_SHA=e.sha(SYNTHETIC_INPUT),ANALYSIS_PLAN_SHA=e.sha(SYNTHETIC_PLAN),
            BASELINE_RUN_ID=SYNTHETIC_BASELINE,CONFIGURED_DRIVE_FOLDER_ID=SYNTHETIC_FOLDER,
            BASELINE_ARCHIVE_SHA=e.sha(SYNTHETIC_ARCHIVE),BASELINE_ARCHIVE_BYTES=len(SYNTHETIC_ARCHIVE)))
        cls.settings.enter_context(patch.object(w,'validate_baseline_lineage',side_effect=synthetic_lineage))
        cls.settings.enter_context(patch.multiple(r,ANALYSIS_PLAN_SHA=e.sha(SYNTHETIC_PLAN),BASELINE_ARCHIVE_SHA=e.sha(SYNTHETIC_ARCHIVE)))
        build_project(cls.fixture_root)
    @classmethod
    def tearDownClass(cls):pass  # Registered cleanups restore all explicit test mocks.
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
        shutil.copytree(self.fixture_root,self.root,dirs_exist_ok=True)
        self.content=self.root/'content';self.parent=self.content/'drive/.shortcut-targets-by-id'/e.FOLDER_ID/'cc_project'
    def export(self,mapping=None,partial=False,condition=None,fail_save=False,export_id=EXPORT_ID):
        original=e.reviewed_modules;outer=self
        @contextlib.contextmanager
        def modules(code):
            with original(code) as (dw,runner,parser):
                class Guard:
                    def __init__(self,parent):self.parent=Path(parent);self.identity={'mountpoint':str(self.parent.parents[2])}
                    def __call__(self):return self.parent
                write=dw.immutable_write
                def fail_write(path,data):
                    if fail_save and Path(path).parent==outer.parent and Path(path).name.startswith('levels159_export_'):raise OSError('offline simulated save failure')
                    return write(path,data)
                with patch.object(dw,'DriveMountGuard',Guard),patch.object(dw,'immutable_write',side_effect=fail_write), \
                     patch.multiple(dw,INPUT_SHA=e.sha(SYNTHETIC_INPUT),ANALYSIS_PLAN_SHA=e.sha(SYNTHETIC_PLAN),
                        BASELINE_RUN_ID=SYNTHETIC_BASELINE,CONFIGURED_DRIVE_FOLDER_ID=SYNTHETIC_FOLDER,
                        BASELINE_ARCHIVE_SHA=e.sha(SYNTHETIC_ARCHIVE),BASELINE_ARCHIVE_BYTES=len(SYNTHETIC_ARCHIVE)), \
                     patch.object(dw,'validate_baseline_lineage',side_effect=synthetic_lineage), \
                     patch.multiple(runner,ANALYSIS_PLAN_SHA=e.sha(SYNTHETIC_PLAN),BASELINE_ARCHIVE_SHA=e.sha(SYNTHETIC_ARCHIVE)), \
                     patch.object(runner,'inputs',side_effect=lambda path,condition:bound_tasks(runner,condition)):
                    yield dw,runner,parser
        with patch.object(e,'reviewed_modules',modules),contextlib.redirect_stdout(io.StringIO()):
            if condition:return e.export_condition(self.parent,condition,RUN_IDS[condition],CODE,export_id,allow_partial=partial,local_root=self.content)
            return e.export_all(self.parent,RUN_IDS if mapping is None else mapping,CODE,export_id,allow_partial=partial,local_root=self.content)
    @contextlib.contextmanager
    def bundle_variant(self,contents,update_installed=False):
        original={name:(CODE/name).read_bytes() for name in (*e.REQUIRED_DEPLOYMENT_MEMBERS,'MANIFEST.json')}
        manifest={'files':{name:{'bytes':len(data),'sha256':e.sha(data)} for name,data in contents.items()}}
        complete={**contents,'MANIFEST.json':json.dumps(manifest,sort_keys=True).encode()}
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
            for name,data in complete.items():z.writestr(name,data)
        data=buffer.getvalue();(self.parent/SYNTHETIC_BUNDLE_NAME).write_bytes(data)
        if update_installed:
            for name,value in complete.items():(CODE/name).write_bytes(value)
        else:(CODE/'MANIFEST.json').write_bytes(complete['MANIFEST.json'])
        try:
            with patch.object(e,'BUNDLE_SHA',e.sha(data)):yield
        finally:
            for name,value in original.items():(CODE/name).write_bytes(value)
            (self.parent/SYNTHETIC_BUNDLE_NAME).write_bytes(SYNTHETIC_BUNDLE)

    def test_each_required_bundle_member_omission_refused_before_export_write(self):
        for missing in sorted(e.REQUIRED_DEPLOYMENT_MEMBERS):
            with self.subTest(missing=missing):
                contents={name:data for name,data in self.bundle_contents.items() if name!=missing}
                with self.bundle_variant(contents),self.assertRaisesRegex(ValueError,'bundle manifest inventory'):
                    self.export(mapping={},partial=True)
                self.assertFalse(list(self.parent.glob('levels159_export_*.zip')))
                self.assertFalse(list(self.content.glob('levels159_export_*.zip')))

    def test_tiny_helper_only_bundle_refused_before_export_write(self):
        with self.bundle_variant({'COLAB_RUN_CONDITION.py':self.bundle_contents['COLAB_RUN_CONDITION.py']}),self.assertRaisesRegex(ValueError,'bundle manifest inventory'):
            self.export(mapping={},partial=True)
        self.assertFalse(list(self.parent.glob('levels159_export_*.zip')))

    def test_wrong_bundle_plan_or_public_projection_refused(self):
        for plan in (b'WRONG NEUTRAL PLAN',(ROOT/'analysis_plan.public.json').read_bytes()):
            with self.subTest(plan_bytes=len(plan)):
                with self.bundle_variant({**self.bundle_contents,'analysis_plan.json':plan}),self.assertRaisesRegex(ValueError,'bundle reviewed dependency SHA'):
                    self.export(mapping={},partial=True)
                self.assertFalse(list(self.parent.glob('levels159_export_*.zip')))

    def test_rehashed_runtime_science_or_launcher_bundle_drift_refused(self):
        for name in sorted(set(e.DEPLOYMENT_PINS)-{'analysis_plan.json'}):
            with self.subTest(member=name):
                contents={**self.bundle_contents,name:self.bundle_contents[name]+b'\n# synthetic drift\n'}
                # Altered launcher remains installed-byte consistent too; the
                # immutable launcher pin must reject it before any export write.
                with self.bundle_variant(contents,update_installed=name=='colab_secret_launcher.py'),self.assertRaisesRegex(ValueError,'bundle reviewed dependency SHA'):
                    self.export(mapping={},partial=True)
                self.assertFalse(list(self.parent.glob('levels159_export_*.zip')))

    def test_complete1590_nested_content_drive_manifest_raw_union_and_replay(self):
        protected=[self.parent/w.BASELINE_RUN_ID]+[self.parent/x for x in RUN_IDS.values()]+[self.content/x for x in RUN_IDS.values()]
        before={str(p):e.sha(p.read_bytes()) for root in protected for p in root.rglob('*') if p.is_file()}
        result=self.export();self.assertTrue(result['complete']);self.assertEqual(result['actual_new_judgments'],1590)
        self.assertEqual(before,{str(p):e.sha(p.read_bytes()) for root in protected for p in root.rglob('*') if p.is_file()})
        path=self.parent/result['archive_name'];self.assertEqual(path.read_bytes(),(self.content/result['archive_name']).read_bytes())
        with zipfile.ZipFile(path) as z:
            self.assertIsNone(z.testzip());manifest=json.loads(z.read('EXPORT_MANIFEST.json'));summary=json.loads(z.read('RAW_EXPORT_SUMMARY.json'))
            self.assertEqual(len([n for n in z.namelist() if '/records/' in n]),1590)
            self.assertEqual(e.sha(z.read('shared/baseline_original636.zip')),w.BASELINE_ARCHIVE_SHA)
            for entry in manifest['files']:
                b=z.read(entry['path']);self.assertEqual((len(b),e.sha(b)),(entry['bytes'],entry['sha256']))
            self.assertEqual(summary['primary_hypothesis_family_size'],10);self.assertEqual(summary['missing_tasks'],0)
            rows=list(csv.DictReader(io.StringIO(z.read('new_judgments_comparison.csv').decode('utf-8-sig'))));self.assertEqual(len(rows),1590)
            self.assertEqual({x['new_status'] for x in rows},{'safe','unsafe','invalid','abstain'})
        self.assertEqual(self.export(),result)
    def test_complete_condition318_not_falsely_full1590(self):
        result=self.export(condition='SP30');self.assertTrue(result['complete']);self.assertEqual((result['expected_new_judgments'],result['actual_new_judgments']),(318,318))
        with zipfile.ZipFile(self.parent/result['archive_name']) as z:
            s=json.loads(z.read('RAW_EXPORT_SUMMARY.json'));self.assertEqual(s['full_plan_expected_new_judgments'],1590);self.assertEqual(s['primary_hypothesis_family_size'],10)
    def test_missing_whole_condition_requires_explicit_partial_fixed1590(self):
        mapping={c:v for c,v in RUN_IDS.items() if c!='SP60'}
        with self.assertRaises(ValueError):self.export(mapping=mapping)
        result=self.export(mapping=mapping,partial=True);self.assertFalse(result['complete']);self.assertEqual((result['expected_new_judgments'],result['actual_new_judgments'],result['missing_tasks']),(1590,1272,318))
    def test_partial_run_records_preserved_and_missing_explicit(self):
        for root in (self.content/RUN_IDS['SP30'],self.parent/RUN_IDS['SP30']):shutil.rmtree(root)
        build_run(self.content,self.parent,'SP30',partial=True)
        with self.assertRaises(ValueError):self.export(condition='SP30')
        result=self.export(condition='SP30',partial=True)
        self.assertFalse(result['complete']);self.assertEqual((result['actual_new_judgments'],result['missing_tasks']),(160,158))
    def test_excluded_record_not_complete_or_imputed_safe(self):
        for root in (self.content/RUN_IDS['SP30'],self.parent/RUN_IDS['SP30']):shutil.rmtree(root)
        build_run(self.content,self.parent,'SP30',excluded=True)
        with self.assertRaises(ValueError):self.export(condition='SP30')
        result=self.export(condition='SP30',partial=True);self.assertFalse(result['complete']);self.assertEqual((result['actual_new_judgments'],result['excluded_tasks'],result['missing_tasks']),(317,1,0))
    def test_conflict_savefailure_and_locks_preserved(self):
        result=self.export(condition='SP30');dest=self.parent/result['archive_name'];dest.write_bytes(b'conflict preserve')
        with self.assertRaises(RuntimeError):self.export(condition='SP30')
        self.assertEqual(dest.read_bytes(),b'conflict preserve')
        with self.assertRaises(OSError):self.export(condition='SP40',fail_save=True,export_id='levels159_export_20261030T043501Z_123456789abc')
        lock=self.parent/RUN_IDS['SP50']/'.lock';lock.write_text('active')
        with self.assertRaises(ValueError):self.export(condition='SP50')
        self.assertEqual(lock.read_text(),'active')
    def test_protocol_drift_raw_binary_and_late_timestamp_refused(self):
        condition='SP30';local=self.content/RUN_IDS[condition];remote=self.parent/RUN_IDS[condition]
        for root in (local,remote):
            p=root/'HB_protocol.json';obj=json.loads(p.read_text());obj['settings']['dtype']='bfloat16';p.write_bytes(e.canonical(obj))
        with self.assertRaises((ValueError,RuntimeError)):self.export(condition=condition,partial=True)
        tasks,prov=bound_tasks(r,condition);task=next(t for t in tasks if t['evaluator']=='LG');protocol=json.loads((local/'LG_protocol.json').read_text())
        record=json.loads((local/'records'/(r.sha(task['task_key'].encode())+'.json')).read_text());record['new_label_binary']=0;record['content_sha256']=r.sha(r.canonical({k:v for k,v in record.items() if k!='content_sha256'}))
        import research_parsers
        with self.assertRaises(ValueError):e.validate_record(record,task,protocol,r.sha(r.canonical(protocol)),r,research_parsers.VERSION)
    def test_late_started_timestamp_rejected_before_checkpoint_comparison(self):
        condition='SP30';local=self.content/RUN_IDS[condition];remote=self.parent/RUN_IDS[condition]
        tasks,provenance=bound_tasks(r,condition);task=next(t for t in tasks if t['evaluator']=='LG')
        name='records/'+r.sha(task['task_key'].encode())+'.json'
        record=json.loads((local/name).read_text())
        record.update(started_at_utc='2026-10-30T08:00:01+00:00',ended_at_utc='2026-10-30T08:00:02+00:00')
        record['content_sha256']=r.sha(r.canonical({k:v for k,v in record.items() if k!='content_sha256'}))
        for root in (local,remote):(root/name).write_bytes(r.canonical(record))
        lineage=w.validate_baseline_lineage(self.parent/w.BASELINE_RUN_ID,r,tasks,provenance,self.parent/ARCHIVE_NAME)
        import research_parsers
        # Isolate timestamp validation from deliberately stale fixture manifests.
        with patch.object(w.Mirror,'audit',return_value=[]),patch.object(w.Mirror,'audit_control',return_value=[]),self.assertRaisesRegex(ValueError,'judgment started at/after execution cutoff'):
            e.validate_run(local,remote,condition,RUN_IDS[condition],tasks,provenance,lineage,lambda:None,w,r,research_parsers,True)

    def test_mapping_scope_and_drive_as_local_root_refused(self):
        with self.assertRaises(ValueError):self.export(mapping={'SP30':RUN_IDS['SP40']})
        self.content=self.parent
        with self.assertRaises(ValueError):self.export(condition='SP30')
    def test_zero_run_partial_explicit_and_optimized_mode_failclosed(self):
        result=self.export(mapping={},partial=True);self.assertFalse(result['complete']);self.assertEqual((result['actual_new_judgments'],result['missing_tasks']),(0,1590))
        proc=subprocess.run([sys.executable,'-O',str(CODE/'EXPORT_LEVELS_RESULTS.py')],capture_output=True,text=True)
        self.assertNotEqual(proc.returncode,0);self.assertIn('Validation assertions must be enabled',proc.stderr)




class ExportConfigurationTests(unittest.TestCase):
    def test_public_wrapper_pin_matches_modified_copy(self):
        self.assertEqual(e.WRAPPER_SHA,e.sha((ROOT/'drive_wrapper.py').read_bytes()))
        self.assertEqual(e.PINS,w.PINNED)
        for name,digest in e.PINS.items():
            self.assertEqual(e.sha((ROOT/name).read_bytes()),digest)

    def test_missing_deployment_configuration_fails_before_source_reads(self):
        with patch.object(e,'FOLDER_ID',None),self.assertRaisesRegex(ValueError,'folder configuration'):
            e.export_all('unavailable',{},'unavailable',EXPORT_ID,allow_partial=True)
        with patch.object(e,'FOLDER_ID',SYNTHETIC_FOLDER),patch.object(e,'BUNDLE_SHA',None),self.assertRaisesRegex(ValueError,'bundle SHA'):
            e.export_all('unavailable',{},'unavailable',EXPORT_ID,allow_partial=True)
        with patch.object(e,'FOLDER_ID',SYNTHETIC_FOLDER),patch.object(e,'BUNDLE_SHA','0'*64),patch.object(e,'BUNDLE_NAME',''),self.assertRaisesRegex(ValueError,'bundle path'):
            e.export_all('unavailable',{},'unavailable',EXPORT_ID,allow_partial=True)

    def test_public_projection_does_not_pass_exporter_private_plan_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in (*e.PINS,'drive_wrapper.py'):
                shutil.copyfile(ROOT/name,root/name)
            shutil.copyfile(ROOT/'analysis_plan.public.json',root/'analysis_plan.json')
            with self.assertRaisesRegex(ValueError,'dependency SHA mismatch'):
                with e.reviewed_modules(root):self.fail('unapproved plan was accepted')


if __name__=='__main__':unittest.main()
