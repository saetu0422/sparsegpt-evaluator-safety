import ast
from collections import UserDict
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parent


def load(path):
    spec=importlib.util.spec_from_file_location('render_fixture',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class TokenizerV5:
    def __init__(self, ids=None):
        self.ids=[11,23,34] if ids is None else ids
        self.calls=[]
    def apply_chat_template(self,messages,**kwargs):
        self.calls.append(dict(kwargs))
        if not kwargs['tokenize']:
            return json.dumps(messages,sort_keys=True)
        if kwargs.get('return_dict',True):
            return UserDict(input_ids=self.ids,attention_mask=[1]*len(self.ids))
        return self.ids


class TokenizerCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.runner=load(ROOT/'colab_smoke.py')
        self.task={'behavior':'fixture question','response':'fixture saved answer'}

    def test_explicit_false_keeps_exact_mapping_input_ids(self):
        tokenizer=TokenizerV5()
        messages=[{'role':'user','content':self.task['behavior']},{'role':'assistant','content':self.task['response']}]
        default=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True)
        self.assertIsInstance(default,UserDict)
        tokenizer.calls.clear()
        text,ids,policy=self.runner.render(self.task,'LG',tokenizer)
        self.assertEqual(ids,default['input_ids'])
        self.assertIs(type(ids),list)
        self.assertEqual(text,json.dumps(messages,sort_keys=True))
        self.assertEqual(tokenizer.calls,[{'tokenize':False,'add_generation_prompt':True},
                                         {'tokenize':True,'add_generation_prompt':True,'return_dict':False}])
        self.assertEqual(policy['apply_chat_template_return_dict'],False)
        json.dumps(ids)

    def test_rejects_nonflat_noninteger_empty_or_negative_ids(self):
        for bad in ({'input_ids':[1]},[],(1,2),[[1]],[True],[-1],['1']):
            with self.subTest(value=type(bad).__name__),self.assertRaises(TypeError):
                self.runner.render(self.task,'LG',TokenizerV5(ids=bad))

    def test_length_cap_and_compatibility_metadata_preserved(self):
        _,ids,policy=self.runner.render(self.task,'LG',TokenizerV5(ids=[1]*8193))
        self.assertEqual(len(ids),8193)
        self.assertEqual(policy['exclude_reason'],'LG_input_over_8192_no_truncation')
        self.assertEqual(policy['apply_chat_template_return_dict'],False)



if __name__=='__main__':
    unittest.main()
