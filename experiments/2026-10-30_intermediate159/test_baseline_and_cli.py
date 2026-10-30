"""Synthetic baseline archive/CLI integrity checks; private data never loaded."""
import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import colab_smoke as r
import drive_wrapper as w
import analysis as a
from synthetic_fixtures import bound_tasks
from test_analysis import make_run, save, OLD_RUNNER, OLD_PLAN, ENV

SYNTHETIC_BASELINE='full159_20000101T000000Z_000000000001'
SYNTHETIC_FOLDER='SYNTHETIC_FOLDER_ID'
ROOT=Path(__file__).parent


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
        self.source=self.root/SYNTHETIC_BASELINE
        self.archive=self.root/(SYNTHETIC_BASELINE+'_HB_LG_636_complete_results.zip')
        self.tasks,self.provenance=bound_tasks(r,'SP30')
        plan=copy.deepcopy(json.loads((ROOT/'analysis_plan.public.json').read_text())['plan'])
        plan['baseline_integrity']['run_id']=SYNTHETIC_BASELINE
        old_sha=w.sha(OLD_RUNNER.read_bytes())
        old,parser=a.bv.load_runner(OLD_RUNNER,old_sha,plan['baseline_integrity']['parser_sha256'])
        tasks,provenance=bound_tasks(old)
        make_run(self.source,tasks,provenance,old,old_sha,plan)
        wrapper_sha=w.sha(OLD_RUNNER.with_name('drive_wrapper.py').read_bytes())
        pins=dict(w.PINNED,**{'colab_smoke.py':old_sha})
        identity={'run_id':SYNTHETIC_BASELINE,'schema':w.BASELINE_SCHEMA,'input_sha256':w.INPUT_SHA,
                  'runner_code':pins,'wrapper_sha256':wrapper_sha,'precision':'fp16',
                  'verified_drive_folder_id':SYNTHETIC_FOLDER,'analysis_plan_sha256':w.BASELINE_PLAN_SHA}
        save(self.source/'_mirror/run_identity.json',identity)
        for name in (*pins,'drive_wrapper.py'):
            target=self.source/'_mirror/code'/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(OLD_RUNNER.with_name(name).read_bytes())
        with zipfile.ZipFile(self.archive,'w',zipfile.ZIP_DEFLATED) as z:
            for path in sorted(self.source.rglob('*')):
                if path.is_file():z.write(path,'run/'+str(path.relative_to(self.source)))
        # Substitute only test-generated artifact/configuration pins. Production
        # constants and frozen scientific source bytes are never modified.
        settings={'BASELINE_RUN_ID':SYNTHETIC_BASELINE,'CONFIGURED_DRIVE_FOLDER_ID':SYNTHETIC_FOLDER,
                  'BASELINE_ARCHIVE_BYTES':self.archive.stat().st_size,'BASELINE_ARCHIVE_SHA':w.sha(self.archive.read_bytes()),
                  'BASELINE_IDENTITY_SHA':w.sha((self.source/'_mirror/run_identity.json').read_bytes()),
                  'BASELINE_CHECKPOINT_SHA':w.sha((self.source/'_mirror/RUN_MIRROR_COMPLETE.json').read_bytes()),
                  'BASELINE_TASKS_SHA':w.sha((self.source/'tasks.json').read_bytes()),'BASELINE_RUNNER_SHA':old_sha,
                  'BASELINE_WRAPPER_SHA':wrapper_sha,
                  'BASELINE_JUDGE_CHECKPOINTS':{e:w.sha((self.source/f'_mirror/{e}_MIRROR_COMPLETE.json').read_bytes()) for e in ('HB','LG')},
                  'LG_TEMPLATE_SHA':json.loads((self.source/'LG_protocol.json').read_text())['template_sha256']}
        self.pins=patch.multiple(w,**settings);self.pins.start();self.addCleanup(self.pins.stop)

    def lineage(self,tasks=None):
        return w.validate_baseline_lineage(self.source,r,tasks or self.tasks,self.provenance,self.archive)

    def test_synthetic636_baseline_read_only_fp16_binding(self):
        before={str(p.relative_to(self.source)):w.sha(p.read_bytes()) for p in self.source.rglob('*') if p.is_file()}
        result=self.lineage()
        self.assertEqual(result['baseline_verified_judgments'],636)
        self.assertEqual(result['baseline_fp16_comparison_judgments'],318)
        self.assertEqual(result['baseline_archive_sha256'],w.BASELINE_ARCHIVE_SHA)
        self.assertEqual(result['new_condition'],'SP30')
        self.assertEqual(result['new_tasks_sha256'],r.sha(r.canonical(self.tasks)))
        self.assertEqual(result['baseline_package_versions'],r.BASELINE_PACKAGES)
        self.assertEqual(before,{str(p.relative_to(self.source)):w.sha(p.read_bytes()) for p in self.source.rglob('*') if p.is_file()})

    def test_archive_checkpoint_or_active_baseline_refused(self):
        original=self.archive.read_bytes();self.archive.write_bytes(original+b'x')
        with self.assertRaises(w.PersistenceError):self.lineage()
        self.archive.write_bytes(original)
        lock=self.source/'.lock';lock.write_text('preserve')
        with self.assertRaises(w.PersistenceError):self.lineage()
        self.assertEqual(lock.read_text(),'preserve');lock.unlink()
        mark=self.source/'_mirror/RUN_MIRROR_COMPLETE.json';mark.write_text('{}')
        with self.assertRaises(w.PersistenceError):self.lineage()
        self.assertEqual(mark.read_text(),'{}')

    def test_changed_canonical_binding_or_package_policy_refused(self):
        wrong=copy.deepcopy(self.tasks);wrong[0]['behavior']='synthetic mismatch'
        with self.assertRaises(w.PersistenceError):self.lineage(wrong)
        with patch.object(r,'BASELINE_PACKAGES',{**r.BASELINE_PACKAGES,'torch':'drift'}),self.assertRaises(w.PersistenceError):self.lineage()

    def test_configured_folder_must_match_historical_identity(self):
        with patch.object(w,'CONFIGURED_DRIVE_FOLDER_ID','DIFFERENT_SYNTHETIC_FOLDER'),self.assertRaisesRegex(w.PersistenceError,'identity'):
            self.lineage()


class PublicConfigurationTests(unittest.TestCase):
    def args(self):
        return ['--runner','unavailable','--drive-parent','unavailable',
                '--verified-drive-folder-id',SYNTHETIC_FOLDER,
                '--run-id','levels159_SP30_20000101T000000Z_000000000001',
                '--baseline-run','unavailable','--baseline-archive','unavailable','--',
                '--condition','SP30','--zip','unavailable',
                '--out','/content/levels159_SP30_20000101T000000Z_000000000001','--judge','HB','--precision','fp16']

    def test_public_projection_cannot_replace_private_frozen_plan(self):
        public_plan=ROOT/'analysis_plan.public.json'
        with self.assertRaisesRegex(ValueError,'hash mismatch'):a.read_plan(public_plan)
        with patch.object(r,'ANALYSIS_PLAN_PATH',public_plan),self.assertRaisesRegex(ValueError,'plan bytes mismatch'):
            r.inputs('unavailable','SP30')

    def test_private_plan_is_not_bundled(self):
        self.assertFalse((ROOT/'analysis_plan.json').exists())
        self.assertEqual(r.ANALYSIS_PLAN_SHA,'473ecba7402b70a171b0589e8eb761cbe802330bd6de4d717a31e948aa94a5c7')
        self.assertEqual(a.PLAN_SHA,r.ANALYSIS_PLAN_SHA)

    def test_missing_baseline_config_fails_before_file_reads(self):
        with patch.object(w,'CONFIGURED_DRIVE_FOLDER_ID',None),self.assertRaises(w.PersistenceError):
            w.validate_baseline_lineage('unavailable',r,[],{},'unavailable')

    def test_mismatched_folder_fails_before_mount_or_model(self):
        with patch.object(w,'CONFIGURED_DRIVE_FOLDER_ID','DIFFERENT_SYNTHETIC_FOLDER'),self.assertRaisesRegex(w.PersistenceError,'must agree'):
            w._main(self.args())

    def test_missing_baseline_run_id_fails_before_mount_or_model(self):
        with patch.object(w,'CONFIGURED_DRIVE_FOLDER_ID',SYNTHETIC_FOLDER),patch.object(w,'BASELINE_RUN_ID',None),self.assertRaisesRegex(w.PersistenceError,'baseline run ID'):
            w._main(self.args())

    def test_condition_run_prefix_mismatch_fails_before_mount(self):
        args=self.args();args[args.index('--run-id')+1]='levels159_SP40_20000101T000000Z_000000000001'
        with patch.object(w,'DriveMountGuard',side_effect=AssertionError('mount touched')),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(w.main(args),1)


if __name__=='__main__':unittest.main()
