"""Synthetic-only export integration; no research text or private archives."""
import contextlib
import csv
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

import EXPORT_FULL159_RESULTS_V2 as e
import colab_smoke as r
import drive_wrapper as w
from test_lg_auth import FAKE, FakeLibraries
from synthetic_fixtures import bound_tasks

CODE=Path(__file__).parent
SYNTHETIC_FOLDER='SYNTHETIC_FOLDER_ID'
SYNTHETIC_HB='smoke_20000101T000000Z_000000000001'
SYNTHETIC_LG='smoke_20000101T000000Z_000000000002'
SYNTHETIC_LG_TEMPLATE='Neutral synthetic LG template; not model data'
SYNTHETIC_INPUT=b'Neutral synthetic input archive placeholder; not research data'
SYNTHETIC_LINEAGE={'synthetic_fixture':True}
RUN_ID='full159_20261029T073700Z_123456789abc'


def build_fixture(root):
    content=root/'content';parent=root/'drive/.shortcut-targets-by-id'/e.FOLDER_ID/'cc_project'
    content.mkdir(parents=True);parent.mkdir(parents=True)
    templates={'LG':SYNTHETIC_LG_TEMPLATE}
    tasks,provenance=bound_tasks(r)
    hblineage=lglineage=SYNTHETIC_LINEAGE
    identity={'schema':w.SCHEMA,'run_id':RUN_ID,'input_sha256':w.INPUT_SHA,'runner_code':w.PINNED,'wrapper_sha256':e.WRAPPER_SHA,'precision':'fp16','verified_drive_folder_id':e.FOLDER_ID,'authentication_policy':'explicit_in_memory_LG_argument_only_no_login_or_token_save','scope':e.SCOPE,'analysis_plan_sha256':e.PLAN_SHA,'analysis_plan_status':e.PLAN_STATUS,'expected_ids':159,'expected_per_judge':318,'expected_total_tasks':636,'folder_mapping_evidence':'operator verified; FUSE cannot prove Drive folder ID','durability_evidence':'mounted filesystem write/read/hash only, backend verification outstanding','source_hb_lineage':hblineage,'source_lg_lineage':lglineage}
    local,remote=content/RUN_ID,parent/RUN_ID
    libs=FakeLibraries()
    tok=libs.modules['transformers'].AutoTokenizer
    tok.chat_template=templates['LG'];tok.encode=lambda self,text,**kw:[1,3,5]
    orig=tok.from_pretrained.__func__
    def token_load(cls,name,**kw):
        value=orig(cls,name,**kw);value.judge='HB' if name==r.MODELS['HB'][0] else 'LG';return value
    tok.from_pretrained=classmethod(token_load)
    def decode(self,ids,**kw):
        if len(ids)!=1:return 'No'  # HB response-clipping fixture only.
        index=getattr(self,'fixture_record_index',0)
        raw=('unrecognized' if index==0 else ('Yes' if self.judge=='HB' else 'unsafe\nS1') if index==1 else 'No' if self.judge=='HB' else 'safe')
        if kw.get('skip_special_tokens') is False:self.fixture_record_index=index+1
        return raw
    tok.decode=decode
    model=libs.modules['transformers'].AutoModelForCausalLM
    orig_model=model.from_pretrained.__func__
    def model_load(cls,name,**kw):
        value=orig_model(cls,name,**kw);value.config=types.SimpleNamespace(_commit_hash=kw['revision']);return value
    model.from_pretrained=classmethod(model_load)
    env={'precision':'fp16','fixture':'offline-export636'}
    for judge in ('HB','LG'):
        mirror=w.Mirror(local,remote,identity);mirror.begin()
        try:
            if judge=='HB':
                for name in w.PINNED:mirror.dual('_mirror/code/'+name,(CODE/name).read_bytes())
                mirror.dual('_mirror/code/drive_wrapper.py',(CODE/'drive_wrapper.py').read_bytes())
                for name,obj in [('config.json',identity),('lineage/source_hb.json',hblineage),('lineage/source_lg.json',lglineage)]:mirror.dual('_mirror/'+name,r.canonical(obj))
                mirror.dual('_mirror/analysis/analysis_plan.json',(CODE/'analysis_plan.json').read_bytes())
                mirror.dual('_mirror/inputs/verified_inputs.zip',SYNTHETIC_INPUT)
                for name,obj in [('tasks.json',tasks),('input_provenance.json',provenance),('environment.json',env)]:r.freeze(local/name,obj)
            args=types.SimpleNamespace(out=str(local),judge=judge,precision='fp16')
            with patch.dict(sys.modules,libs.modules):r.inference(args,tasks,provenance,env,auth_token=FAKE if judge=='LG' else None)
            mirror.reconcile();mirror.finish('inference',judge)
        finally:mirror.close()
    return content,parent


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Only source-archive loading, old lineage and LG template identity are
        # mocked; mirror/export record and archive checks remain production code.
        cls.settings=patch.multiple(e,FOLDER_ID=SYNTHETIC_FOLDER,LG_TEMPLATE_SHA=e.sha(SYNTHETIC_LG_TEMPLATE.encode()))
        cls.settings.start()
        cls.fixture=tempfile.TemporaryDirectory();cls.fixture_root=Path(cls.fixture.name)
        build_fixture(cls.fixture_root)
    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup();cls.settings.stop()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
        shutil.copytree(self.fixture_root,self.root,dirs_exist_ok=True)
        self.content=self.root/'content';self.parent=self.root/'drive/.shortcut-targets-by-id'/e.FOLDER_ID/'cc_project'
        self.local=self.content/RUN_ID;self.remote=self.parent/RUN_ID
    def export(self,write_failure=False):
        reviewed=e.reviewed_modules
        @contextlib.contextmanager
        def mocked_guard(code):
            with reviewed(code) as (dw,runner,parser):
                class Guard:
                    def __init__(self,parent):
                        self.parent=Path(parent)
                        self.identity={'mountpoint':str(self.parent.parents[2])}
                    def __call__(self):return self.parent
                original=dw.immutable_write
                def write(path,data):
                    if write_failure and Path(path).parent==self.parent and Path(path).suffix=='.zip':raise OSError('simulated storage unavailable')
                    return original(path,data)
                with patch.object(dw,'DriveMountGuard',Guard),patch.object(dw,'immutable_write',side_effect=write), \
                     patch.object(dw,'SOURCE_HB_RUN_ID',SYNTHETIC_HB),patch.object(dw,'SOURCE_LG_RUN_ID',SYNTHETIC_LG), \
                     patch.object(dw,'validate_hb_lineage',return_value=SYNTHETIC_LINEAGE), \
                     patch.object(dw,'validate_lg_lineage',return_value=SYNTHETIC_LINEAGE), \
                     patch.object(runner,'inputs',return_value=bound_tasks(runner)):
                    yield dw,runner,parser
        with patch.object(e,'reviewed_modules',mocked_guard),contextlib.redirect_stdout(io.StringIO()):
            return e.export_completed(self.parent,RUN_ID,CODE,local_root=self.content)
    def test_full636_export_manifest_raw_members_and_replay(self):
        before=e.inventory(self.remote)
        result=self.export();self.assertEqual((result['actual_judgments'],result['HB'],result['LG']),(636,318,318))
        local=self.content/result['archive_name'];remote=self.parent/result['archive_name']
        self.assertEqual(local.read_bytes(),remote.read_bytes())
        with zipfile.ZipFile(remote) as z:
            self.assertIsNone(z.testzip());manifest=json.loads(z.read('EXPORT_MANIFEST.json'))
            self.assertEqual(manifest['complete_judgments'],636)
            self.assertEqual(e.sha(z.read('EXPORTER_SOURCE.py')),manifest['exporter_source_sha256'])
            self.assertEqual(z.read('EXPORTER_SOURCE.py'),Path(e.__file__).read_bytes())
            self.assertEqual(len([n for n in z.namelist() if n.startswith('run/records/')]),636)
            self.assertFalse(any(n.startswith(('HB_source_run/','LG_continuation_run/')) for n in z.namelist()))
            self.assertEqual(e.sha(z.read('run/_mirror/analysis/analysis_plan.json')),e.PLAN_SHA)
            for item in manifest['files']:
                data=z.read(item['path']);self.assertEqual((len(data),e.sha(data)),(item['bytes'],item['sha256']))
            summary=json.loads(z.read('FULL159_RESULT_SUMMARY.json'));self.assertEqual(summary['old_smoke_records_imported'],0)
            self.assertEqual(len(list(csv.DictReader(io.StringIO(z.read('full159_comparison.csv').decode('utf-8-sig'))))),636)
            self.assertEqual((summary['HB']['abstain'],summary['LG']['invalid']),(1,1))
            self.assertEqual((summary['HB']['counts']['unsafe'],summary['LG']['counts']['unsafe']),(1,1))
        self.assertEqual(self.export(),result)
        self.assertEqual(e.inventory(self.remote),before)
    def test_existing_archive_conflict_preserved(self):
        result=self.export();dest=self.parent/result['archive_name'];dest.write_bytes(b'preserve conflict')
        with self.assertRaises(RuntimeError):self.export()
        self.assertEqual(dest.read_bytes(),b'preserve conflict')
    def test_missing_record_refused(self):
        file=next((self.local/'records').glob('*.json'))
        (self.remote/'records'/file.name).unlink();file.unlink()
        with self.assertRaises((ValueError,RuntimeError,FileNotFoundError)):self.export()
        self.assertFalse(list(self.parent.glob(RUN_ID+'*.zip')))
    def test_precision_drift_and_binary_binding_refused(self):
        protocol=json.loads((self.local/'LG_protocol.json').read_text());protocol['settings']['dtype']='bfloat16'
        tasks,prov=bound_tasks(r);env=json.loads((self.local/'environment.json').read_text())
        import research_parsers
        with self.assertRaises(ValueError):e.validate_protocol(protocol,'LG',tasks,prov,env,r,research_parsers)
        task=[t for t in tasks if t['evaluator']=='LG'][2];record=json.loads((self.local/'records'/(r.sha(task['task_key'].encode())+'.json')).read_text())
        record['new_label_binary']=1;content={k:v for k,v in record.items() if k!='content_sha256'};record['content_sha256']=r.sha(r.canonical(content))
        with self.assertRaises(ValueError):e.validate_record(record,task,json.loads((self.local/'LG_protocol.json').read_text()),r,research_parsers)
    def test_record_metadata_hardening_rejects_rehashed_drift(self):
        import research_parsers
        tasks,prov=bound_tasks(r)
        for judge in ('HB','LG'):
            task=next(t for t in tasks if t['evaluator']==judge)
            protocol=json.loads((self.local/(judge+'_protocol.json')).read_text())
            original=json.loads((self.local/'records'/(r.sha(task['task_key'].encode())+'.json')).read_text())
            alterations=[{'legacy_label':bool(original['legacy_label'])},
                {'output_tokens':0,'output_token_ids':[]},
                {'started_at_utc':'2026-10-29T07:30:00','ended_at_utc':'2026-10-29T07:31:00'},
                {'started_at_utc':'2026-10-29T07:23:59+00:00'},
                {'ended_at_utc':'2026-10-29T07:24:00+00:00'}]
            if judge=='HB':
                wrong_prompt='mismatched fixture prompt'
                alterations.append({'serialized_input_before_prompt_truncation':wrong_prompt,'serialized_input_sha256':r.sha(wrong_prompt.encode())})
                alterations.append({'token_policy':{**original['token_policy'],'clipped_response_sha256':'0'*64}})
            for changes in alterations:
                with self.subTest(judge=judge,fields=list(changes)):
                    record={**original,**changes}
                    record['content_sha256']=r.sha(r.canonical({k:v for k,v in record.items() if k!='content_sha256'}))
                    with self.assertRaises(ValueError):e.validate_record(record,task,protocol,r,research_parsers)

    def test_save_failure_no_success_and_no_remote_archive(self):
        with self.assertRaises(OSError):self.export(write_failure=True)
        self.assertFalse(list(self.parent.glob(RUN_ID+'*.zip')))
        self.assertTrue(list(self.content.glob(RUN_ID+'*.zip')))
    def test_locks_partial_files_symlinks_refused(self):
        for name in ('.lock','.mirror_session.lock','pending.part','pending.commitlock'):
            with self.subTest(name=name):
                path=self.remote/name;path.write_text('preserve')
                with self.assertRaises(ValueError):self.export()
                self.assertEqual(path.read_text(),'preserve');path.unlink()
        outside=self.root/'outside';outside.write_text('not collected');link=self.remote/'linked';link.symlink_to(outside)
        with self.assertRaises(ValueError):self.export()
        self.assertEqual(outside.read_text(),'not collected')
    def test_stale_archive_partial_refused(self):
        partial=self.parent/(RUN_ID+'_HB_LG_636_complete_results.zip.123.part');partial.write_text('preserve')
        with self.assertRaises(ValueError):self.export()
        self.assertEqual(partial.read_text(),'preserve')
        self.assertFalse(list(self.content.glob(RUN_ID+'*.zip')))
    def test_real_colab_shaped_content_contains_drive_export_succeeds(self):
        # Model real /content/<run> and /content/drive/.shortcut-targets-by-id/.../<run>.
        old_drive=self.root/'drive'
        nested_drive=self.content/'drive'
        shutil.move(old_drive,nested_drive)
        self.parent=nested_drive/'.shortcut-targets-by-id'/e.FOLDER_ID/'cc_project'
        self.remote=self.parent/RUN_ID
        result=self.export()
        self.assertEqual(result['actual_judgments'],636)
        self.assertTrue((self.content/result['archive_name']).is_file())
        self.assertTrue((self.parent/result['archive_name']).is_file())

    def test_local_root_inside_drive_or_same_run_is_refused(self):
        old_content=self.content
        for root in (self.root/'drive',self.parent):
            with self.subTest(local_root=str(root)):
                self.content=root
                with self.assertRaises(ValueError):self.export()
                self.assertFalse(list(root.glob(RUN_ID+'*.zip')))
        self.content=old_content

    def test_run_tree_overlap_refused_before_inventory_or_writes(self):
        # A Drive mount nested in the actual scratch run (rather than /content)
        # must be refused before any run inventories are read.
        nested=self.local/'drive'
        shutil.move(self.root/'drive',nested)
        self.parent=nested/'.shortcut-targets-by-id'/e.FOLDER_ID/'cc_project'
        self.remote=self.parent/RUN_ID
        with patch.object(e,'inventory',side_effect=AssertionError('source read before isolation gate')):
            with self.assertRaisesRegex(ValueError,'local run and Drive run must be separate'):
                self.export()
        # Conversely, scratch beneath the remote run is on Drive and forbidden.
        self.content=self.remote/'scratch';self.content.mkdir()
        with patch.object(e,'inventory',side_effect=AssertionError('source read before isolation gate')):
            with self.assertRaisesRegex(ValueError,'local export root must be outside the Drive mount'):
                self.export()
        self.assertFalse(list(self.parent.glob(RUN_ID+'*.zip')))

    def test_wrong_scope_and_optimized_mode_fail_closed(self):
        with self.assertRaises(ValueError):e.export_completed(self.parent,SYNTHETIC_HB,CODE,local_root=self.content)
        result=subprocess.run([sys.executable,'-O',str(CODE/'EXPORT_FULL159_RESULTS_V2.py')],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('Validation assertions must be enabled',result.stderr)


if __name__=='__main__':unittest.main()
