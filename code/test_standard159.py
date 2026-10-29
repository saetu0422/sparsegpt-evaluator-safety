import collections
import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

import colab_smoke as r
import drive_wrapper as w
import colab_secret_launcher as launcher
from test_lg_auth import FAKE, FakeLibraries
from synthetic_fixtures import bound_tasks, source_rows



class StandardScopeTests(unittest.TestCase):
    def setUp(self):
        self.tasks,self.provenance=bound_tasks(r)
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def test_all159_exact636_condition_evaluator_binding_and_no_drop(self):
        self.assertEqual(len(self.tasks),636)
        self.assertEqual(len({t['task_key'] for t in self.tasks}),636)
        self.assertEqual(len({t['behavior_id'] for t in self.tasks}),159)
        self.assertEqual(collections.Counter((t['condition'],t['evaluator']) for t in self.tasks),{(c,e):159 for c in ('FP16','SP70') for e in ('HB','LG')})
        ids=self.provenance['selected_id_order']
        self.assertEqual(ids,sorted(ids,key=lambda x:(r.sha(('42:'+x).encode()),x)))
        self.assertEqual(self.provenance['excluded_counts'],{'contextual':81,'copyright':80})
        for t in self.tasks:
            self.assertEqual(t['response_sha256'],r.sha(t['response'].encode()))
            self.assertIs(type(t['legacy_label']),int)
        self.assertEqual(self.tasks,bound_tasks(r)[0])

    def test_correspondence_failure_in_excluded_row_is_not_silently_dropped(self):
        rows,blobs,manifest_bytes,manifest=source_rows()
        i=next(i for i,x in enumerate(rows) if x['FunctionalCategory']=='copyright')
        for target in ('raw/responses_sparsegpt-fp16.json','raw/safety_baseline_harmbench.json'):
            altered=dict(blobs);obj=json.loads(blobs[target])
            if 'responses_' in target:obj['items'][i]['index']=319
            else:obj['evaluations'][0]['samples'][i]['response']='mismatch fixture'
            altered[target]=json.dumps(obj).encode()
            with self.subTest(source=target),self.assertRaises(ValueError):
                r.bind_standard_tasks(rows,altered,manifest_bytes,manifest)
        rows[i]['FunctionalCategory']='standard'
        with self.assertRaises(ValueError):r.bind_standard_tasks(rows,blobs,manifest_bytes,manifest)

    def test_legacy_array_missing_row_refused(self):
        rows,blobs,manifest_bytes,manifest=source_rows()
        name='raw/safety_sparsegpt-sp70-multiseed_llamaguard.json';obj=json.loads(blobs[name]);obj['evaluations'][0]['samples'].pop();blobs[name]=json.dumps(obj).encode()
        with self.assertRaises(ValueError):r.bind_standard_tasks(rows,blobs,manifest_bytes,manifest)



    def test_hb_stage_never_reads_secret_and_lg_rejects_hb_arguments(self):
        reads=[];calls=[]
        colab=types.SimpleNamespace(userdata=types.SimpleNamespace(get=lambda k:reads.append(k)))
        with patch.dict(sys.modules,{'google.colab':colab}),patch.object(w,'main',side_effect=lambda a,**kw:(calls.append((a,kw)) or 0)),patch.object(w,'require_official_hf_endpoint'),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(launcher.launch_hb_without_secret(['--judge','HB']),0)
            self.assertEqual(launcher.launch_from_colab_secrets(['--judge','HB']),1)
        self.assertFalse(reads)
        self.assertEqual(len(calls),2)
        self.assertTrue(all(not x[1] for x in calls))

    def test_plan_bytes_and_code_pins_match(self):
        self.assertEqual(w.sha(r.ANALYSIS_PLAN_PATH.read_bytes()),w.ANALYSIS_PLAN_SHA)
        self.assertEqual(r.ANALYSIS_PLAN_SHA,w.ANALYSIS_PLAN_SHA)
        for name,digest in w.PINNED.items():self.assertEqual(w.sha(Path(__file__).with_name(name).read_bytes()),digest)

    def test_lg_gate_refuses_missing_or_smoke_scope_hb_marker(self):
        m=w.Mirror(self.root/'scratch',self.root/'drive',{'scope':'full159'})
        m.begin()
        try:
            with self.assertRaises(FileNotFoundError):w.validate_full_hb_stage(m,r,self.tasks)
            m.dual('_mirror/HB_MIRROR_COMPLETE.json',w.canonical({'schema':w.SCHEMA,'judge':'HB','judged':6}))
            with self.assertRaises(w.PersistenceError):w.validate_full_hb_stage(m,r,self.tasks)
        finally:m.close()

    def test_synthetic636_fake_judgments_hb_first_partial_lg_failure_then_recovery(self):
        # Full production318/636 counts, real runner serializers/record validation,
        # real fail-closed mirror guards/audits; model libraries only are fake.
        libs=FakeLibraries()
        tok=libs.modules['transformers'].AutoTokenizer
        tok.encode=lambda self,text,**kw:[1,3,5]
        orig_load=tok.from_pretrained.__func__
        def load(cls,name,**kw):
            value=orig_load(cls,name,**kw);value.evaluator='HB' if name==r.MODELS['HB'][0] else 'LG';return value
        tok.from_pretrained=classmethod(load)
        tok.decode=lambda self,ids,**kw:'No' if self.evaluator=='HB' else 'safe'
        model=libs.modules['transformers'].AutoModelForCausalLM
        original_model=model.from_pretrained.__func__
        def load_model(cls,name,**kw):
            value=original_model(cls,name,**kw);value.config=types.SimpleNamespace(_commit_hash=kw['revision']);return value
        model.from_pretrained=classmethod(load_model)
        local,remote=self.root/'scratch',self.root/'drive'
        env={'precision':'fp16','fixture':'offline-full636'};identity={'schema':w.SCHEMA,'scope':'full159-test'}
        def stage(judge,fail=False):
            mirror=w.Mirror(local,remote,identity)
            args=types.SimpleNamespace(out=str(local),judge=judge,precision='fp16')
            def main(auth_token=None):
                for name,obj in [('tasks.json',self.tasks),('input_provenance.json',self.provenance),('environment.json',env)]:r.freeze(local/name,obj)
                if judge=='LG':w.validate_full_hb_stage(mirror,r,self.tasks)
                if fail:raise RuntimeError('simulated gated LG failure')
                r.inference(args,self.tasks,self.provenance,env,auth_token=auth_token)
            with patch.object(r,'main',main),patch.dict(sys.modules,libs.modules),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                code=w.execute(r,mirror,[],'inference',judge,auth_token=FAKE if judge=='LG' else None)
            return code
        self.assertEqual(stage('HB'),0)
        self.assertEqual(len(libs.generations),318)
        self.assertTrue(all(x[2]['token'] is False for x in libs.loads))
        hbmark=(remote/'_mirror/HB_MIRROR_COMPLETE.json').read_bytes()
        self.assertEqual(json.loads(hbmark)['judged'],318)
        self.assertEqual(stage('LG',fail=True),1)
        self.assertEqual(len(libs.generations),318)
        self.assertFalse((remote/'_mirror/RUN_MIRROR_COMPLETE.json').exists())
        self.assertEqual(stage('LG'),0)
        self.assertEqual(len(libs.generations),636)
        self.assertEqual((remote/'_mirror/HB_MIRROR_COMPLETE.json').read_bytes(),hbmark)
        self.assertEqual(len(r.records_checked(local,self.tasks)),636)
        self.assertEqual(json.loads((remote/'_mirror/RUN_MIRROR_COMPLETE.json').read_text())['judged'],636)
        for judge in ('HB','LG'):
            completion=json.loads((remote/f'completion_{judge}.json').read_text())
            self.assertEqual((completion['records'],completion['judged'],completion['excluded']),(318,318,0))
        for p in self.root.rglob('*'):
            if p.is_file():self.assertNotIn(FAKE.encode(),p.read_bytes())


if __name__=='__main__':unittest.main()
