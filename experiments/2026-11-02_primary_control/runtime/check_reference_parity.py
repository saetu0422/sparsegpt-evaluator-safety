"""CPU source/render parity against a separately retained private executed runner."""
import argparse,ast,hashlib,importlib.util,json
from pathlib import Path
import control_runner as public
EXPECTED='2a23efdacce1507e7bbe5599d2730a42fe5505501a2ce04b476553fc7013aa96'

def normalized(node):return ast.dump(node,include_attributes=False)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--executed-reference',type=Path,required=True);a=p.parse_args()
 raw=a.executed_reference.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED
 oldtree=ast.parse(raw);newtree=ast.parse(Path(public.__file__).read_text())
 oldclass=next(n for n in oldtree.body if isinstance(n,ast.ClassDef) and n.name=='Session')
 newclass=next(n for n in newtree.body if isinstance(n,ast.ClassDef) and n.name=='Session')
 funcs={n.name:n for n in newclass.body if isinstance(n,ast.FunctionDef)};matched=[]
 for n in oldclass.body:
  if isinstance(n,ast.FunctionDef) and n.name!='__init__':assert normalized(n)==normalized(funcs[n.name]),n.name;matched.append('Session.'+n.name)
 newfuncs={n.name:n for n in newtree.body if isinstance(n,ast.FunctionDef)}
 for n in oldtree.body:
  if isinstance(n,ast.FunctionDef):assert normalized(n)==normalized(newfuncs[n.name]),n.name;matched.append(n.name)
 spec=importlib.util.spec_from_file_location('executed_reference',a.executed_reference);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
 assert public.MODELS==old.MODELS and public.PACKAGES==old.PACKAGES and public.TEMPLATE_SHA==old.TEMPLATE_SHA and public.PARSER_SHA==old.PARSER_SHA
 class Tok:
  truncation_side='right'
  def encode(self,text,max_length=None,truncation=False):
   ids=[ord(c) for c in text]
   if truncation and max_length is not None:ids=ids[-max_length:] if self.truncation_side=='left' else ids[:max_length]
   return ids
  def decode(self,ids,**kw):return ''.join(chr(c) for c in ids)
  def apply_chat_template(self,messages,tokenize=False,**kw):
   text='ONLY THE LAST Agent message\n'+messages[0]['content']+'\n'+messages[1]['content']
   return self.encode(text) if tokenize else text
 checks=0
 for judge in ('HB','LG'):
  for quality,response in [('F','A quiet garden.'),('S','garden. quiet A'),('R','x'*9000)]:
   task={'evaluator':judge,'response_factor':quality,'response':response,'behavior':'Describe a quiet garden.'}
   outcomes=[]
   for mod in (old,public):
    s=mod.Session.__new__(mod.Session);s.tok=Tok();s.template=Path(__file__).with_name('HB_standard_template.txt').read_text()
    try:outcomes.append(('value',s.render(task)))
    except Exception as e:outcomes.append(('error',type(e).__name__,str(e)))
   assert outcomes[0]==outcomes[1];checks+=1
 for judge in ('HB','LG'):
  for raw in ('safe','unsafe\nS1','yes','no','unrecognized-output',''):
   assert public.parse(raw,judge)==old.parse(raw,judge);checks+=1
 for judge in ('HB','LG'):
  original=json.loads(a.executed_reference.with_name(judge+'_baseline_protocol.json').read_text())
  projection=json.loads(Path(public.__file__).with_name(judge+'_baseline_protocol.json').read_text())
  assert all(original[k]==v for k,v in projection.items())
 result={'status':'CPU_PARITY_PASS','executed_reference_sha256':EXPECTED,'unchanged_ast_methods':matched,'synthetic_render_and_parse_checks':checks,'model_calls':0,'credentials_used':False,'scope':'source AST equality plus deterministic mocked-tokenizer render/parser parity; not a fresh GPU or real-tokenizer rerun'}
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
