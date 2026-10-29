import ast
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile
import os

import drive_wrapper as w
import colab_secret_launcher as launcher

ROOT = Path(__file__).parent
FAKE = 'SYNTHETIC_CREDENTIAL_SENTINEL_NOT_A_REAL_TOKEN'


def module(path):
    spec = importlib.util.spec_from_file_location('test_runner_'+path.parent.name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


class FakeLibraries:
    def __init__(self, fail=False, secret_output=False):
        self.loads, self.generations = [], []
        outer = self
        class Tokenizer:
            chat_template = 'fixture-template'
            eos_token_id = 2
            @classmethod
            def from_pretrained(cls, name, **kw):
                outer.loads.append(('tokenizer', name, dict(kw)))
                if fail:
                    print('Authorization: Bearer ' + FAKE)
                    raise RuntimeError('secret error detail ' + FAKE)
                return cls()
            def apply_chat_template(self, messages, tokenize, add_generation_prompt, return_dict=False):
                return [1, 3, 5] if tokenize else json.dumps(messages, sort_keys=True)
            def decode(self, continuation, **kw):
                return FAKE if secret_output else 'safe'
        class Result:
            def __getitem__(self, key):
                return types.SimpleNamespace(tolist=lambda:[9])
        class Model:
            config = types.SimpleNamespace(_commit_hash='7327bd9f6efbbe6101dc6cc4736302b3cbb6e425')
            @classmethod
            def from_pretrained(cls, name, **kw):
                outer.loads.append(('model', name, dict(kw)))
                return cls()
            def eval(self):
                pass
            def generate(self, **kw):
                outer.generations.append(kw)
                return Result()
        self.modules = {
            'torch': types.SimpleNamespace(float16='float16', tensor=lambda value,device:value,
                ones_like=lambda value:value, inference_mode=contextlib.nullcontext,
                cuda=types.SimpleNamespace(synchronize=lambda:None, empty_cache=lambda:None)),
            'transformers':types.SimpleNamespace(AutoTokenizer=Tokenizer, AutoModelForCausalLM=Model,
                BitsAndBytesConfig=lambda **kw:None, set_seed=lambda seed:None),
            'huggingface_hub.constants':types.SimpleNamespace(ENDPOINT='https://huggingface.co'),
            'transformers.utils.hub':types.SimpleNamespace(HUGGINGFACE_CO_RESOLVE_ENDPOINT='https://huggingface.co'),
        }


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runner = module(ROOT/'colab_smoke.py')
        from synthetic_fixtures import bound_tasks
        self.tasks, self.provenance = bound_tasks(self.runner)
        self.full_tasks=self.tasks
        ids={t["behavior_id"] for t in self.tasks[:6]}
        self.tasks=[t for t in self.tasks if t["behavior_id"] in ids]
        self.counts=patch.multiple(w,PER_JUDGE=6,TOTAL_TASKS=12);self.counts.start();self.addCleanup(self.counts.stop)
        self.runner.PER_JUDGE=6;self.runner.TOTAL_TASKS=12
        self.env = {'precision':'fp16','fixture':True}
        self.old_path = list(sys.path)
        sys.path.insert(0, str(ROOT))

    def tearDown(self):
        sys.path[:] = self.old_path
        self.temp.cleanup()

    def run_fake(self, libs=None, token=FAKE, judge='LG'):
        libs = libs or FakeLibraries()
        out = self.root/'scratch'
        mirror = w.Mirror(out,self.root/'drive',{'schema':w.SCHEMA,'run':'auth-fixture'})
        args = types.SimpleNamespace(out=str(out), judge=judge, precision='fp16')
        def test_main(auth_token=None):
            for name,obj in [('tasks.json',self.tasks),('input_provenance.json',self.provenance),('environment.json',self.env)]:
                self.runner.freeze(out/name,obj)
            self.runner.inference(args,self.tasks,self.provenance,self.env,auth_token=auth_token)
        self.runner.main = test_main
        captured = io.StringIO()
        with patch.dict(sys.modules, libs.modules), contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            code=w.execute(self.runner,mirror,[], 'inference',judge,auth_token=token)
        return code,libs,mirror,captured.getvalue()

    def assert_no_secret(self, captured=''):
        self.assertNotIn(FAKE,captured)
        for p in self.root.rglob('*'):
            if p.is_file():
                self.assertNotIn(FAKE.encode(),p.read_bytes(),str(p))

    def test_token_only_to_two_pinned_lg_loads_and_no_persist(self):
        code,libs,mirror,captured=self.run_fake()
        self.assertEqual(code,0)
        self.assertEqual(len(libs.loads),2)
        self.assertEqual(len(libs.generations),6)
        for kind,name,kwargs in libs.loads:
            self.assertEqual(name,'meta-llama/Llama-Guard-3-8B')
            self.assertEqual(kwargs['revision'],'7327bd9f6efbbe6101dc6cc4736302b3cbb6e425')
            self.assertEqual(kwargs['token'],FAKE)
            self.assertFalse(kwargs['trust_remote_code'])
        self.assert_no_secret(captured)
        protocol=json.loads((mirror.remote/'LG_protocol.json').read_text())
        self.assertEqual(protocol['auth_mode'],'ephemeral_explicit_read_token')
        self.assertEqual(mirror.forbidden_bytes,())
        self.assertTrue((mirror.remote/'_mirror/LG_MIRROR_COMPLETE.json').exists())
        self.assertFalse((mirror.remote/'_mirror/HB_MIRROR_COMPLETE.json').exists())
        self.assertFalse((mirror.remote/'_mirror/RUN_MIRROR_COMPLETE.json').exists())
        self.assertEqual({json.loads(p.read_text())['evaluator'] for p in (mirror.remote/'records').glob('*.json')},{'LG'})

    def test_hb_token_rejected_before_any_load_or_write(self):
        code,libs,mirror,captured=self.run_fake(judge='HB')
        self.assertEqual(code,1)
        self.assertEqual(libs.loads,[])
        self.assertEqual(libs.generations,[])
        self.assertFalse(mirror.remote.exists())
        self.assert_no_secret(captured)

    def test_library_secret_in_stdout_and_exception_suppressed(self):
        code,libs,mirror,captured=self.run_fake(FakeLibraries(fail=True))
        self.assertEqual(code,1)
        self.assertEqual(libs.generations,[])
        self.assert_no_secret(captured)
        self.assertTrue(list(mirror.remote.rglob('STOPPED.json')))
        self.assertEqual(mirror.forbidden_bytes,())

    def test_secret_in_raw_result_refused_before_local_write(self):
        code,libs,mirror,captured=self.run_fake(FakeLibraries(secret_output=True))
        self.assertEqual(code,1)
        self.assertEqual(len(libs.generations),1)
        self.assert_no_secret(captured)
        self.assertEqual(list((mirror.local/'records').glob('*.json')),[])
        self.assertEqual(list((mirror.remote/'records').glob('*.json')),[])







    def test_public_entry_never_prints_exception_payload(self):
        captured=io.StringIO()
        with patch.object(w,'_main',side_effect=RuntimeError(FAKE)),contextlib.redirect_stderr(captured):
            self.assertEqual(w.main([],auth_token=FAKE),1)
        self.assert_no_secret(captured.getvalue())

    def test_failure_diagnostics_and_exception_class_cannot_write_token(self):
        libs=FakeLibraries()
        out=self.root/'scratch'
        mirror=w.Mirror(out,self.root/'drive',{'schema':w.SCHEMA})
        def bad_main(auth_token=None):
            print(json.dumps({'status':'stopped','exception_type':auth_token}))
        self.runner.main=bad_main
        captured=io.StringIO()
        with patch.dict(sys.modules,libs.modules),contextlib.redirect_stdout(captured),contextlib.redirect_stderr(captured):
            self.assertEqual(w.execute(self.runner,mirror,[],'inference','LG',auth_token=FAKE),1)
        self.assert_no_secret(captured.getvalue())
        self.assertTrue(list(mirror.remote.rglob('STOPPED.json')))
        fake_class=type(FAKE,(RuntimeError,),{})
        with patch.object(w,'_main',side_effect=fake_class(FAKE)),contextlib.redirect_stderr(captured):
            self.assertEqual(w.main([],auth_token=FAKE),1)
        self.assert_no_secret(captured.getvalue())

    def test_custom_env_or_imported_endpoint_refused(self):
        libs=FakeLibraries()
        with patch.dict(sys.modules,libs.modules),patch.dict(os.environ,{'HF_ENDPOINT':'https://example.invalid'}):
            with self.assertRaises(w.PersistenceError):
                w.require_official_hf_endpoint()
        libs.modules['huggingface_hub.constants'].ENDPOINT='https://example.invalid'
        with patch.dict(sys.modules,libs.modules):
            with self.assertRaises(w.PersistenceError):
                w.require_official_hf_endpoint()

    def test_secrets_launcher_preflight_before_one_explicit_read(self):
        events=[]
        fake_userdata=types.SimpleNamespace(get=lambda key:(events.append(('read',key)) or FAKE))
        fake_colab=types.SimpleNamespace(userdata=fake_userdata)
        def main(args,auth_token=None):
            events.append(('main',args,auth_token is not None))
            if auth_token is not None:self.assertEqual(auth_token,FAKE)
            return 0
        captured=io.StringIO()
        with patch.object(w,'require_official_hf_endpoint',side_effect=lambda:events.append(('endpoint',))),patch.object(w,'main',side_effect=main),patch.dict(sys.modules,{'google.colab':fake_colab}),contextlib.redirect_stdout(captured):
            self.assertEqual(launcher.launch_from_colab_secrets(['--judge','LG']),0)
        self.assertEqual([x for x in events if x[0]=='read'],[('read','HF_TOKEN')])
        self.assertEqual([x for x in events if x[0]=='main'][0],('main',['--judge','LG','--preflight-only'],False))
        self.assertLess(next(i for i,x in enumerate(events) if x[0]=='main'),next(i for i,x in enumerate(events) if x[0]=='read'))
        self.assert_no_secret(captured.getvalue())

    def test_launcher_failed_preflight_never_reads_secret(self):
        fake_userdata=types.SimpleNamespace(get=lambda key:self.fail('secret read despite failed preflight'))
        captured=io.StringIO()
        with patch.object(w,'require_official_hf_endpoint'),patch.object(w,'main',return_value=1),patch.dict(sys.modules,{'google.colab':types.SimpleNamespace(userdata=fake_userdata)}),contextlib.redirect_stdout(captured):
            self.assertEqual(launcher.launch_from_colab_secrets(['--judge','LG']),1)
        self.assert_no_secret(captured.getvalue())

    def test_launcher_bad_endpoint_never_reads_secret(self):
        fake_userdata=types.SimpleNamespace(get=lambda key:self.fail('secret read despite bad endpoint'))
        with patch.object(w,'require_official_hf_endpoint',side_effect=w.PersistenceError('endpoint refused')),patch.dict(sys.modules,{'google.colab':types.SimpleNamespace(userdata=fake_userdata)}),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(launcher.launch_from_colab_secrets(['--judge','LG']),1)


if __name__=='__main__':
    unittest.main()
