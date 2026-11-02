import os, copy, unittest, tempfile, subprocess, sys, json
from pathlib import Path
import analyze as a

def fixture():
    tasks=[];records=[]
    for i in range(a.N):
        bid=f'id{i:03d}'
        cells=[(p,q,j) for p in ('H','N') for q in ('F','S') for j in ('HB','LG')]+[('H','R',j) for j in ('HB','LG')]
        for p,q,j in cells:
            key='|'.join((bid,p,q,j));t=dict(task_key=key,behavior_id=bid,prompt_factor=p,response_factor=q,evaluator=j,behavior='prompt',response='garden',behavior_sha256=a.sha(b'prompt'),response_sha256=a.sha(b'garden'),skeleton_id=f's{i%12}')
            tasks.append(t);r={k:t[k] for k in ('task_key','behavior_id','prompt_factor','response_factor','evaluator','behavior_sha256','response_sha256')}
            r.update(task_sha256=a.sha(a.canonical(t)),protocol_sha256=j,status='judged',new_label_binary=0,parsed={'label':'safe'},serialized_input_before_prompt_truncation='input',serialized_input_sha256=a.sha(b'input'),input_token_ids=[1],input_token_ids_sha256=a.sha(a.canonical([1])),raw_judge_completion='safe',raw_judge_sha256=a.sha(b'safe'),token_policy={'dropped_prompt_tokens':0,'dropped_response_tokens':0})
            raw='no' if j=='HB' else 'safe'
            cfg={'contract':'harmbench-official-lower-no-strip'} if j=='HB' else {'contract':'lg3-8b-lines-v1','categories':[f'S{i}' for i in range(1,15)]}
            r.update(parser_version=a.VERSION,input_tokens=1,raw_judge_completion=raw,raw_judge_sha256=a.sha(raw.encode()),parsed=a.parse_judgment(raw,j,cfg),output_token_ids=[2],output_tokens=1,raw_decoded_with_special_tokens=raw,raw_decoded_with_special_tokens_sha256=a.sha(raw.encode()))
            seal(r);records.append(r)
    return tasks,records

def seal(r):r['content_sha256']=a.sha(a.canonical({k:v for k,v in r.items() if k!='content_sha256'}))
class Tests(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(a.exact_mcnemar(0,0),1)
        self.assertEqual(a.exact_mcnemar(4,4),1)
        self.assertEqual(a.exact_mcnemar(6,0),.03125)
        self.assertEqual(a.exact_mcnemar(0,6),.03125)
        self.assertEqual(a.exact_mcnemar(5,1),.21875)
    def test_direction(self):
        z=a.contrast([0,0,0,1],[1,1,0,0])
        self.assertEqual((z['b_F0_S1'],z['c_F1_S0']),(2,1));self.assertEqual(z['risk_difference_S_minus_F'],.25)
    def test_zero_and_bootstrap(self):
        z=a.contrast([0]*159,[0]*159,True)
        self.assertEqual(z['exact_two_sided_mcnemar_p'],1);self.assertEqual(z['nominal_paired_bootstrap95'],[0,0]);self.assertGreater(z['any_paired_change_one_sided95_upper_under_sampling_model'],0)
        self.assertTrue(a.contrast([0],[0])['material_plus10pp_unresolved'])
        self.assertEqual(a.bootstrap([-1,0,1]*53),a.bootstrap([-1,0,1]*53))
    def test_full_missing_invalid(self):
        t,r=fixture();z=a.summarize(t,r,{'HB':'HB','LG':'LG'});self.assertEqual(len(z['primary_eligible_ids']),159)
        remove=next(i for i,x in enumerate(r) if x['task_key']=='id000|H|F|HB');r.pop(remove)
        v=next(x for x in r if x['task_key']=='id001|H|S|LG');v.update(raw_judge_completion='invalid',raw_judge_sha256=a.sha(b'invalid'),parsed=a.parse_judgment('invalid','LG',{'contract':'lg3-8b-lines-v1','categories':[f'S{i}' for i in range(1,15)]}),new_label_binary=None);seal(v)
        z=a.summarize(t,r,{'HB':'HB','LG':'LG'});self.assertEqual(z['primary_missing_or_invalid_ids'],['id000','id001']);self.assertIsNone(z['primary']['exact_two_sided_mcnemar_p']);self.assertEqual(z['primary']['n'],157)
    def test_neutral_missing_not_primary(self):
        t,r=fixture();r=[x for x in r if x['task_key']!='id000|N|F|HB'];z=a.summarize(t,r,{'HB':'HB','LG':'LG'});self.assertEqual(z['primary']['n'],159);self.assertEqual(z['neutral']['n'],158)
    def test_duplicates_and_hashes(self):
        t,r=fixture();by,_=a.validate_tasks(t)
        with self.assertRaises(ValueError):a.validate_records(by,r+[r[0]],{'HB':'HB','LG':'LG'})
        with self.assertRaises(ValueError):a.validate_tasks(t[:-1]+[t[0]])
        r[0]['task_sha256']='tampered';seal(r[0])
        with self.assertRaises(ValueError):a.validate_records(by,r,{'HB':'HB','LG':'LG'})
    @unittest.skipUnless(os.environ.get("PRIMARY_HISTORICAL_RUN"), "Private historical protocols required; set PRIMARY_HISTORICAL_RUN")
    def test_cli_real_protocol_schema_and_create_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);bundle=root/'bundle';run=root/'run';hist=root/'hist'
            for p in (bundle,run,run/'records',hist,hist/'records'):p.mkdir(parents=True,exist_ok=True)
            def put(p,x):p.write_bytes(a.canonical(x))
            tasks,records=fixture();put(bundle/'tasks.json',tasks);put(run/'tasks.json',tasks)
            historical=[]
            for t in tasks:
                if t['response_factor']=='R':
                    old=dict(task_key=t['task_key'],condition='SP70',source_seed=42,behavior_id=t['behavior_id'],evaluator=t['evaluator'],response_sha256=t['response_sha256'],status='judged',new_label_binary=0)
                    put(hist/'records'/(a.sha(t['task_key'].encode())+'.json'),old)
            put(hist/'tasks.json',tasks)
            baseline={}
            for j in ('HB','LG'):
                baseline[j]=json.loads((Path(os.environ['PRIMARY_HISTORICAL_RUN'])/(j+'_protocol.json')).read_text())
                put(hist/(j+'_protocol.json'),baseline[j])
            inventory={'files':{str(p.relative_to(hist)):a.sha(p.read_bytes()) for p in hist.rglob('*.json')}}
            put(bundle/'historical_inventory.json',inventory)
            for name in ('analyze.py','frozen_parsers.py'):(bundle/name).write_bytes(Path(a.__file__).with_name(name).read_bytes())
            manifest={'tasks_file':'tasks.json','files':{p.name:a.sha(p.read_bytes()) for p in bundle.iterdir()}}
            put(bundle/'manifest.json',manifest);digest=a.sha((bundle/'manifest.json').read_bytes());put(run/'run_identity.json',{'manifest_sha256':digest})
            protocols={}
            for j in ('HB','LG'):
                current=copy.deepcopy(baseline[j]);current.update(manifest_sha256=digest,tasks_sha256=a.sha(a.canonical(tasks)));put(run/(j+'_protocol.json'),current);protocols[j]=a.sha(a.canonical(current))
            pf={'status':'PASS','labels_seen':0,'report':{j:{'True':{'tasks':{}}} for j in ('HB','LG')}}
            for r in records:
                r['protocol_sha256']=protocols[r['evaluator']];seal(r);put(run/'records'/(a.sha(r['task_key'].encode())+'.json'),r)
                pf['report'][r['evaluator']]['True']['tasks'][r['task_key']]={'serialized_sha256':r['serialized_input_sha256'],'input_ids_sha256':r['input_token_ids_sha256'],'token_policy':r['token_policy']}
            put(run/'all_tokenizer_preflight.json',pf)
            command=[sys.executable,a.__file__,'--manifest',str(bundle/'manifest.json'),'--manifest-sha256',digest,'--run-dir',str(run),'--historical-dir',str(hist),'--historical-inventory',str(bundle/'historical_inventory.json'),'--output',str(root/'out.json')]
            result=subprocess.run(command,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads((root/'out.json').read_text())['primary']['n'],159)
            self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)
    def test_reparse_and_counts_fail_closed(self):
        t,r=fixture();by,_=a.validate_tasks(t)
        r[0]['raw_judge_completion']='safe';r[0]['raw_judge_sha256']=a.sha(b'safe');seal(r[0])
        with self.assertRaises(ValueError):a.validate_records(by,r,{'HB':'HB','LG':'LG'})
        t,r=fixture();r[0]['output_tokens']=2;seal(r[0])
        with self.assertRaises(ValueError):a.validate_records(by,r,{'HB':'HB','LG':'LG'})
    def test_nonbinary_not_safe(self):
        self.assertIsNone(a.binary({'status':'judged','new_label_binary':None}));self.assertIsNone(a.binary({'status':'judged','new_label_binary':False}));self.assertIsNone(a.binary(None))
if __name__=='__main__':unittest.main(verbosity=2)
