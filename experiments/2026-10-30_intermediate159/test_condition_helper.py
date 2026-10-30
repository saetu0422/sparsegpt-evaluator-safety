"""Generated public-code bundles and mocked stages only; no private input data."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile
import drive_wrapper as w

ROOT=Path(__file__).parent
RUN='levels159_SP30_20261030T040000Z_123456789abc'
BUNDLE_NAME='synthetic_reviewed_code_bundle.zip'
SYNTHETIC_FOLDER='SYNTHETIC_FOLDER_ID'


class ConditionHelperTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
        self.code=self.root/'code';self.code.mkdir()
        # No private ZIP: construct a neutral bundle in temporary storage.
        contents={name:(ROOT/name).read_bytes() for name in ('colab_smoke.py','drive_wrapper.py','colab_secret_launcher.py','research_parsers.py','HB_standard_template.txt','COLAB_SETUP_LEVELS.py','COLAB_RUN_CONDITION.py')}
        self.plan_marker=b'NEUTRAL SYNTHETIC PRIVATE PLAN MARKER; TEST ONLY'
        contents['analysis_plan.json']=self.plan_marker
        self.original_contents=dict(contents)
        manifest={'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in contents.items()}}
        contents['MANIFEST.json']=json.dumps(manifest,sort_keys=True).encode()
        for name,data in contents.items():(self.code/name).write_bytes(data)
        self.parent=self.root/'drive/.shortcut-targets-by-id'/SYNTHETIC_FOLDER/'project';self.parent.mkdir(parents=True)
        self.folder_config=patch.object(w,'CONFIGURED_DRIVE_FOLDER_ID',SYNTHETIC_FOLDER)
        self.folder_config.start();self.addCleanup(self.folder_config.stop)
        self.content=self.root/'content';self.content.mkdir();self.calls=[]
        self.archive=self.content/BUNDLE_NAME
        with zipfile.ZipFile(self.archive,'w',zipfile.ZIP_DEFLATED) as z:
            for name,data in contents.items():z.writestr(name,data)
        self.fake_launcher=types.SimpleNamespace(__file__=str(self.code/'colab_secret_launcher.py'),drive_wrapper=w)
        def prepare(condition,run_id):
            base=['--runner',str(self.code/'colab_smoke.py'),'--drive-parent',str(self.parent),'--run-id',run_id,'--','--condition',condition,'--out','/content/'+run_id]
            return base+['--judge','HB'],base+['--judge','LG']
        self.namespace={'CODE':self.code,'PARENT':self.parent,'ARCHIVE':self.archive,'REVIEWED_BUNDLE_SHA':hashlib.sha256(self.archive.read_bytes()).hexdigest(),'prepare_condition':prepare,'colab_secret_launcher':self.fake_launcher}
        exec(compile((self.code/'COLAB_RUN_CONDITION.py').read_text(),'reviewed-helper','exec'),self.namespace)
        def fixture_path(value):return self.content if str(value)=='/content' else Path(value)
        self.namespace['Path']=fixture_path
    def produce(self,judge,complete=True):
        for root in (self.content/RUN,self.parent/RUN):
            (root/'_mirror').mkdir(parents=True,exist_ok=True)
            identity={'condition':'SP30','run_id':RUN,'schema':w.SCHEMA,'analysis_plan_sha256':w.ANALYSIS_PLAN_SHA,'runner_code':w.PINNED,'wrapper_sha256':w.sha((self.code/'drive_wrapper.py').read_bytes())}
            (root/'_mirror/run_identity.json').write_bytes(w.canonical(identity))
            if complete:
                completion={'requested_judge':judge,'requested_evaluation_complete':True,'task_accounted_complete':True,'records':159,'judged':159,'excluded':0,'counts':{'safe':158,'abstain':1}}
                (root/('completion_'+judge+'.json')).write_bytes(w.canonical(completion))
                (root/('_mirror/'+judge+'_MIRROR_COMPLETE.json')).write_bytes(w.canonical({'schema':w.SCHEMA,'judge':judge,'judged':159}))
                if judge=='LG':(root/'_mirror/RUN_MIRROR_COMPLETE.json').write_bytes(w.canonical({'schema':w.SCHEMA,'judged':318}))
    def run_helper(self,fail_stage=None,incomplete_stage=None,archive_error=False,condition='SP30',run_id=RUN,accept_synthetic_plan=True):
        self.guard_calls=0
        def validation(args,**kwargs):self.calls.append('input_validation');return 1 if fail_stage=='input_validation' else 0
        def hb(args):
            self.calls.append('HB')
            if fail_stage=='HB':return 1
            self.produce('HB',incomplete_stage!='HB');return 0
        def lg(args):
            self.calls.append('LG')
            if fail_stage=='LG':return 1
            self.produce('LG',incomplete_stage!='LG');return 0
        self.fake_launcher.launch_hb_without_secret=hb;self.fake_launcher.launch_from_colab_secrets=lg
        outer=self
        class Guard:
            def __init__(self,parent):
                self.parent=Path(parent);outer.guard_calls+=1
            def __call__(self):return self.parent
        original=w.immutable_write
        def archive_write(path,data):
            self.calls.append('bundle_write')
            if archive_error:raise OSError('synthetic storage failure')
            return original(path,data)
        captured=io.StringIO()
        plan_mock=patch.dict(self.namespace['DEPLOYMENT_PINS'],{'analysis_plan.json':hashlib.sha256(self.plan_marker).hexdigest()}) if accept_synthetic_plan else contextlib.nullcontext()
        with plan_mock,patch.object(w,'__file__',str(self.code/'drive_wrapper.py')),patch.object(w,'DriveMountGuard',Guard),patch.object(w,'main',side_effect=validation),patch.object(w,'immutable_write',side_effect=archive_write),contextlib.redirect_stdout(captured):
            result=self.namespace['run_condition'](condition,run_id)
        return result,captured.getvalue()
    def test_one_condition_order_archives_bundle_first_and_reports_hashes(self):
        result,_=self.run_helper();self.assertEqual(self.calls,['bundle_write','input_validation','HB','LG'])
        self.assertEqual(result['status'],'condition318_complete');self.assertEqual(result['judged'],318)
        self.assertEqual(result['HB']['counts']['abstain'],1)
        self.assertEqual((self.parent/BUNDLE_NAME).read_bytes(),self.archive.read_bytes())
        self.assertEqual(len(result['full_checkpoint_sha256']),64)
    def test_each_failed_stage_stops_subsequent_work(self):
        for stage,expected in [('input_validation',['bundle_write','input_validation']),('HB',['bundle_write','input_validation','HB']),('LG',['bundle_write','input_validation','HB','LG'])]:
            with self.subTest(stage=stage):
                self.calls=[];result,_=self.run_helper(fail_stage=stage)
                self.assertEqual(self.calls,expected);self.assertEqual(result['status'],'stopped_or_incomplete');self.assertEqual(result['stage'],stage)
    def test_success_exit_with_missing_hb_checkpoint_does_not_read_lg_secret(self):
        result,_=self.run_helper(incomplete_stage='HB')
        self.assertEqual(self.calls,['bundle_write','input_validation','HB']);self.assertEqual(result['status'],'stopped_or_incomplete')
    def test_success_exit_with_missing_lg_checkpoint_is_not_complete(self):
        result,_=self.run_helper(incomplete_stage='LG')
        self.assertEqual(result['status'],'stopped_or_incomplete');self.assertEqual(result['stage'],'LG_checkpoint')
    def test_bundle_failure_or_conflict_prevents_input_and_inference(self):
        result,_=self.run_helper(archive_error=True);self.assertEqual(self.calls,['bundle_write']);self.assertEqual(result['stage'],'archive_reviewed_bundle')
        self.calls=[];dest=self.parent/BUNDLE_NAME;dest.write_bytes(b'preserve conflict')
        result,_=self.run_helper();self.assertEqual(self.calls,['bundle_write']);self.assertEqual(dest.read_bytes(),b'preserve conflict')
    def test_wrong_condition_bundle_or_installed_bytes_fail_before_write(self):
        result,_=self.run_helper(condition='SP70');self.assertEqual(self.calls,[]);self.assertEqual(result['status'],'stopped_or_incomplete')
        self.namespace['REVIEWED_BUNDLE_SHA']='0'*64
        result,_=self.run_helper();self.assertEqual(self.calls,[])
        self.namespace['REVIEWED_BUNDLE_SHA']=hashlib.sha256(self.archive.read_bytes()).hexdigest()
        (self.code/'colab_smoke.py').write_bytes(b'mismatch')
        result,_=self.run_helper();self.assertEqual(self.calls,[])
    def rewrite_bundle(self,contents):
        manifest={'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in contents.items()}}
        complete={**contents,'MANIFEST.json':json.dumps(manifest,sort_keys=True).encode()}
        for name,data in complete.items():(self.code/name).write_bytes(data)
        with zipfile.ZipFile(self.archive,'w',zipfile.ZIP_DEFLATED) as z:
            for name,data in complete.items():z.writestr(name,data)
        self.namespace['REVIEWED_BUNDLE_SHA']=hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def test_each_required_member_omission_fails_before_mount_or_write(self):
        for missing in sorted(self.namespace['REQUIRED_DEPLOYMENT_MEMBERS']):
            with self.subTest(missing=missing):
                self.calls=[]
                self.rewrite_bundle({name:data for name,data in self.original_contents.items() if name!=missing})
                result,_=self.run_helper(fail_stage='input_validation')
                self.assertEqual(result['stage'],'archive_reviewed_bundle')
                self.assertEqual(result['status'],'stopped_or_incomplete')
                self.assertEqual(self.calls,[]);self.assertEqual(self.guard_calls,0)
                self.assertFalse((self.parent/BUNDLE_NAME).exists())

    def test_tiny_helper_only_self_consistent_bundle_is_refused(self):
        self.rewrite_bundle({'COLAB_RUN_CONDITION.py':self.original_contents['COLAB_RUN_CONDITION.py']})
        result,_=self.run_helper(fail_stage='input_validation')
        self.assertEqual(result['stage'],'archive_reviewed_bundle')
        self.assertEqual(self.calls,[]);self.assertEqual(self.guard_calls,0)
        self.assertFalse((self.parent/BUNDLE_NAME).exists())

    def test_wrong_plan_and_public_projection_refused_before_write(self):
        for plan in (b'WRONG NEUTRAL PLAN', (ROOT/'analysis_plan.public.json').read_bytes()):
            with self.subTest(plan_bytes=len(plan)):
                self.calls=[];self.rewrite_bundle({**self.original_contents,'analysis_plan.json':plan})
                # No plan mock: production's exact original frozen-plan pin applies.
                result,_=self.run_helper(fail_stage='input_validation',accept_synthetic_plan=False)
                self.assertEqual(result['stage'],'archive_reviewed_bundle')
                self.assertEqual(self.calls,[]);self.assertEqual(self.guard_calls,0)

    def test_rehashed_science_wrapper_or_launcher_drift_is_refused(self):
        for name in sorted(set(self.namespace['DEPLOYMENT_PINS'])-{'analysis_plan.json'}):
            with self.subTest(member=name):
                self.calls=[];changed=self.original_contents[name]+b'\n# synthetic drift\n'
                self.rewrite_bundle({**self.original_contents,name:changed})
                result,_=self.run_helper(fail_stage='input_validation')
                self.assertEqual(result['stage'],'archive_reviewed_bundle')
                self.assertEqual(self.calls,[]);self.assertEqual(self.guard_calls,0)

    def test_optimized_mode_fails_before_actions(self):
        result=subprocess.run([sys.executable,'-O',str(ROOT/'COLAB_RUN_CONDITION.py')],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('Validation assertions must be enabled',result.stderr)




class PublicSetupTests(unittest.TestCase):
    """Only the success-branch plan digest is mocked; no original private plan."""
    def setUp(self):
        import os
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
        self.code=self.root/'code';self.code.mkdir()
        for name in ('colab_smoke.py','drive_wrapper.py','colab_secret_launcher.py'):
            shutil.copyfile(ROOT/name,self.code/name)
        self.marker=b'NEUTRAL SYNTHETIC PRIVATE PLAN STAND-IN; TEST ONLY'
        (self.code/'analysis_plan.json').write_bytes(self.marker)
        self.parent=self.root/'drive/.shortcut-targets-by-id'/SYNTHETIC_FOLDER/'project';self.parent.mkdir(parents=True)
        self.bundle=self.root/'synthetic_private_deployment_bundle.zip';self.bundle.write_bytes(b'neutral archive placeholder')
        self.env={'SPARSEGPT_CODE_DIR':str(self.code),'SPARSEGPT_DRIVE_PARENT':str(self.parent),
                  'SPARSEGPT_DRIVE_FOLDER_ID':SYNTHETIC_FOLDER,
                  'SPARSEGPT_BASELINE_RUN_ID':'full159_20000101T000000Z_000000000001',
                  'SPARSEGPT_REVIEWED_BUNDLE_PATH':str(self.bundle),
                  'SPARSEGPT_REVIEWED_BUNDLE_SHA256':hashlib.sha256(self.bundle.read_bytes()).hexdigest()}
        self.source=(ROOT/'COLAB_SETUP_LEVELS.py').read_text()
        self.original_path=list(sys.path);self.addCleanup(lambda:sys.path.__setitem__(slice(None),self.original_path))

    def execute(self,accept_synthetic_plan=False,cached=False):
        import os
        original_sha=hashlib.sha256
        def test_sha(data=b'',*args,**kwargs):
            if accept_synthetic_plan and data==self.marker:
                return types.SimpleNamespace(hexdigest=lambda:w.ANALYSIS_PLAN_SHA)
            return original_sha(data,*args,**kwargs)
        namespace={}
        with patch.dict(os.environ,self.env),patch.dict(sys.modules),patch.object(hashlib,'sha256',side_effect=test_sha),contextlib.redirect_stdout(io.StringIO()):
            for name in ('colab_smoke','drive_wrapper','colab_secret_launcher'):sys.modules.pop(name,None)
            if cached:sys.modules['colab_smoke']=types.SimpleNamespace(__file__=str(ROOT/'colab_smoke.py'))
            exec(compile(self.source,'public-setup','exec'),namespace)
        return namespace

    def test_missing_configuration_refused(self):
        import os
        with patch.dict(os.environ,{},clear=True),self.assertRaisesRegex(ValueError,'configuration'):
            exec(compile(self.source,'public-setup','exec'),{})

    def test_unapproved_plan_bytes_refused(self):
        with self.assertRaises(AssertionError):self.execute()

    def test_synthetic_setup_keeps_explicit_bundle_and_argument_binding(self):
        namespace=self.execute(accept_synthetic_plan=True)
        self.assertEqual(namespace['ARCHIVE'],self.bundle)
        self.assertEqual(namespace['REVIEWED_BUNDLE_SHA'],self.env['SPARSEGPT_REVIEWED_BUNDLE_SHA256'])
        hb,lg=namespace['prepare_condition']('SP30',RUN)
        for args,judge in ((hb,'HB'),(lg,'LG')):
            self.assertEqual(args[args.index('--judge')+1],judge)
            self.assertEqual(args[args.index('--verified-drive-folder-id')+1],SYNTHETIC_FOLDER)
            self.assertEqual(args[args.index('--baseline-run')+1],str(self.parent/self.env['SPARSEGPT_BASELINE_RUN_ID']))
        with self.assertRaises(ValueError):namespace['prepare_condition']('SP70',RUN)

    def test_unknown_cached_source_module_is_not_adopted(self):
        with self.assertRaisesRegex(AssertionError,'cached code module'):
            self.execute(accept_synthetic_plan=True,cached=True)

    def test_setup_optimized_mode_fails_before_actions(self):
        result=subprocess.run([sys.executable,'-O',str(ROOT/'COLAB_SETUP_LEVELS.py')],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Validation assertions must be enabled',result.stderr)


if __name__=='__main__':unittest.main()
