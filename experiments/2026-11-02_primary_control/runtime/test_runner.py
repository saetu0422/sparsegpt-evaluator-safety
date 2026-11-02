import datetime as dt,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import control_runner as r
import storage
from operational_config import OperationalConfig
r.configure_operational(OperationalConfig("fixture-folder","operator@example.invalid","/fixture/mount/research","/fixture/mount","/fixture/scratch","2050-01-01T00:00:00+00:00","2050-01-01T01:00:00+00:00","2050-01-01T02:00:00+00:00",100.0,65.0))

class Tests(unittest.TestCase):
 def test_atomic_identical_conflict(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'record.json';self.assertTrue(storage.immutable_write(p,b'one'));self.assertFalse(storage.immutable_write(p,b'one'))
   with self.assertRaises(storage.PersistenceError):storage.immutable_write(p,b'two')
   self.assertEqual(p.read_bytes(),b'one')
 def test_symlink(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'link').symlink_to('/tmp',target_is_directory=True)
   with self.assertRaises(ValueError):r.safe_target(p,'link/a')
   with self.assertRaises(ValueError):r.safe_target(p,'../a')
 def test_abandoned_lock_retained(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a';lock=Path(str(p)+'.mirrorlock');lock.touch()
   with self.assertRaises(FileExistsError):storage.immutable_write(p,b'a')
   self.assertTrue(lock.exists());self.assertFalse(p.exists())
 def budget(self,balance=99.0,age=0,rate=10):
  s=r.Session.__new__(r.Session);t=r.now()-dt.timedelta(seconds=age);s.observe_budget(balance,t.isoformat(),rate);return s
 def test_budget_good(self):self.assertEqual(self.budget().balance,99)
 def test_budget_reserve(self):
  for x in [65.0,60.0,101,float('nan')]:
   with self.assertRaises(r.BudgetStop):self.budget(balance=x)
  with self.assertRaises(r.BudgetStop):self.budget(balance=66,rate=10)
 def test_budget_stale_future(self):
  for a in [61,-30]:
   with self.assertRaises(r.BudgetStop):self.budget(age=a)
 def test_rate_unknown_stops(self):
  for rate in [0,-1,float('nan'),101]:
   with self.assertRaises(r.BudgetStop):self.budget(rate=rate)
 def test_preflight_gate(self):
  s=r.Session.__new__(r.Session);s.all_preflight_passed=False
  with self.assertRaises(ValueError):s.load('HB',99,r.now().isoformat(),10)
  with self.assertRaises(ValueError):s.batch(99,r.now().isoformat(),10)
 def test_invalid_not_safe(self):
  for judge in ['HB','LG']:
   result=r.parse('unrecognized-output',judge)
   self.assertNotEqual(result['label'],'safe')
   self.assertIsNone({'safe':0,'unsafe':1}.get(result['label']))
 def test_cutoff_and_lease(self):
  s=self.budget();s.failed=False;s.deadline=r.now()-dt.timedelta(seconds=1);s.guard=lambda:None
  with self.assertRaises(r.BudgetStop):s.check()
  s.deadline=r.now()+dt.timedelta(hours=1);s.observed=r.now()-dt.timedelta(seconds=481)
  with self.assertRaises(r.BudgetStop):s.check()
 def test_secret_refused_local_write(self):
  s=r.Session.__new__(r.Session);s.secret='FAKE_TEST_SECRET'
  with self.assertRaises(ValueError):s.put_bytes('a',b'FAKE_TEST_SECRET')
 def test_fresh_run_configured_cutoff(self):
  with patch.object(r,'now',return_value=dt.datetime(2050,1,1,1,tzinfo=r.UTC)):
   with self.assertRaises(r.BudgetStop):r.Session(None,None,None,None,None,None,None,None,None)
 def test_immutable_record_digest(self):
  data={'task_key':'x|H|F|HB','parsed':{'label':'invalid'},'new_label_binary':None};raw=r.canonical(data);data['content_sha256']=r.sha(raw)
  self.assertEqual(data['content_sha256'],r.sha(r.canonical({k:v for k,v in data.items() if k!='content_sha256'})))
if __name__=='__main__':unittest.main(verbosity=2)

class FunctionalPreflight(unittest.TestCase):
 def run_preflight(self,mode):
  import sys,types
  class Tok:
   chat_template='pinned-lg-template'
   def __init__(self,fast):self.fast=fast
   def encode(self,text,**kwargs):return list(range(len(text)))
  def gettok(name,**kw):return Tok(kw.get('use_fast',True))
  fake_transformers=types.ModuleType('transformers');fake_transformers.AutoTokenizer=types.SimpleNamespace(from_pretrained=gettok)
  fake_hub=types.ModuleType('huggingface_hub.constants');fake_hub.ENDPOINT='https://huggingface.co'
  fake_th=types.ModuleType('transformers.utils.hub');fake_th.HUGGINGFACE_CO_RESOLVE_ENDPOINT='https://huggingface.co'
  fake_hfp=types.ModuleType('huggingface_hub');fake_hfp.constants=fake_hub
  fake_utils=types.ModuleType('transformers.utils');fake_utils.hub=fake_th;fake_transformers.utils=fake_utils
  mods={'transformers':fake_transformers,'transformers.utils':fake_utils,'transformers.utils.hub':fake_th,'huggingface_hub':fake_hfp,'huggingface_hub.constants':fake_hub}
  with tempfile.TemporaryDirectory() as d:
   s=r.Session.__new__(r.Session);s.records={};s.model=None;s.all_preflight_passed=False;s.failed=False;s.template='hb-template';s.bundle=Path(d);s.secret=None
   for judge in ['HB','LG']:(s.bundle/f'{judge}_baseline_protocol.json').write_text(json.dumps({'template_sha256':r.sha(('hb-template' if judge=='HB' else 'pinned-lg-template').encode())}))
   s.tasks=[]
   for judge in ['HB','LG']:
    for prompt in ['H','N']:
     for q in ['F','S']:
      response='a'*20 if q=='F' or mode!='length' else 'a'*22
      s.tasks.append({'task_key':f'one|{prompt}|{q}|{judge}','behavior_id':'one','evaluator':judge,'prompt_factor':prompt,'response_factor':q,'response':response})
   s.begin_stage=lambda *x:None;s.end_stage=lambda:None;s.check=lambda:None
   writes=[];s.put=lambda name,obj:writes.append((name,obj))
   def render(task):
    if mode=='truncation':raise ValueError('Synthetic fixture truncation forbidden')
    ids=[1,2,3] if s.tok.fast or mode!='mismatch' else [1,2,4]
    return 'same',ids,{'dropped_prompt_tokens':0,'dropped_response_tokens':0}
   s.render=render
   with patch.dict(sys.modules,mods):
    if mode=='pass':
     out=s.preflight_tokenizers(99,r.now().isoformat(),10,'FAKE_AUTH_ONLY');self.assertEqual(out['status'],'all_tokenizer_preflight_PASS');self.assertTrue(s.all_preflight_passed);self.assertEqual(len(writes),1)
    else:
     with self.assertRaises(RuntimeError):s.preflight_tokenizers(99,r.now().isoformat(),10,'FAKE_AUTH_ONLY')
     self.assertFalse(s.all_preflight_passed);self.assertTrue(s.failed);self.assertEqual(writes,[])
   self.assertIsNone(s.secret)
 def test_success(self):self.run_preflight('pass')
 def test_fast_slow_fail(self):self.run_preflight('mismatch')
 def test_length_fail(self):self.run_preflight('length')
 def test_truncation_fail(self):self.run_preflight('truncation')

class StageExport(unittest.TestCase):
 def test_backend_archive_manifest(self):
  import io,zipfile
  with tempfile.TemporaryDirectory() as d:
   s=r.Session.__new__(r.Session);s.local=Path(d)/'local';s.remote=Path(d)/'remote';s.local.mkdir();s.remote.mkdir();s.secret=None;s.guard=lambda:None;s.stage_number=3;s.judge='HB';s.failed=False
   record={'task_key':'one|H|F|HB','status':'judged','parsed':{'label':'safe'}};s.records={record['task_key']:record}
   for root in (s.local,s.remote):
    for name in ('run_identity.json','tasks.json','all_tokenizer_preflight.json','HB_protocol.json','HB_load_receipt.json'):(root/name).write_bytes(b'{}\n')
    (root/'records').mkdir();(root/'records'/(r.sha(record['task_key'].encode())+'.json')).write_bytes(r.canonical(record))
   receipt=s.export_stage([record['task_key']]);data=(s.remote/receipt['relative_path']).read_bytes()
   self.assertEqual(receipt['sha256'],r.sha(data));self.assertFalse(receipt['backend_verified'])
   with zipfile.ZipFile(io.BytesIO(data)) as z:
    m=json.loads(z.read('STAGE_MANIFEST.json'));self.assertEqual(m['records'],1)
    for name,entry in m['files'].items():self.assertEqual(r.sha(z.read(name)),entry['sha256'])

