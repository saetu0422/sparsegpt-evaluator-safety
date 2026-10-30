import unittest
import quality as q

class FeatureTests(unittest.TestCase):
    def test_empty(self):
        x=q.features(''); self.assertEqual(x['empty'],1); self.assertIsNone(x['unique_ratio']); self.assertIsNone(x['dominance']); self.assertIsNone(x['repeated_trigram_ratio']); self.assertEqual(x['high_repetition'],0)
    def test_whitespace_preserved(self):
        x=q.features(' \n\t'); self.assertEqual(x['character_length'],3); self.assertEqual(x['empty'],1); self.assertEqual(x['unit_count'],0)
    def test_unicode_casefold(self):
        x=q.features('Straße STRASSE 한글!'); self.assertEqual(x['unit_count'],4); self.assertEqual(x['unique_ratio'],3/4); self.assertEqual(x['dominance'],.5); self.assertEqual(x['character_length'],len('Straße STRASSE 한글!'))
    def test_short(self):
        self.assertIsNone(q.features('a b')['repeated_trigram_ratio']); self.assertEqual(q.features('a b c')['repeated_trigram_ratio'],0)
    def test_punctuation_is_unit(self):
        self.assertEqual(q.features('a,b!')['unit_count'],4)
    def test_overlap(self):
        self.assertEqual(q.features('a b a b a')['repeated_trigram_ratio'],1/3)
    def test_repeat19_not_flagged(self):
        self.assertEqual(q.features(' '.join(['a']*19))['high_repetition'],0)
    def test_repeat20_flagged(self):
        self.assertEqual(q.features(' '.join(['a']*20))['high_repetition'],1)
    def test_dominance_boundary(self):
        text=' '.join(['a']*6+[str(i) for i in range(14)])
        x=q.features(text); self.assertEqual(x['dominance'],.3); self.assertEqual(x['high_repetition'],1)
    def test_distinct20(self):
        x=q.features(' '.join(str(i) for i in range(20))); self.assertEqual(x['high_repetition'],0); self.assertEqual(x['repeated_trigram_ratio'],0)
    def test_nonstrings(self):
        with self.assertRaises(ValueError): q.features(None)
    def test_null_stats(self):
        self.assertEqual(q.stats([None]),{'valid_n':0,'mean':None,'median':None})
    def test_valid_stats(self):
        self.assertEqual(q.stats([1,None,3]),{'valid_n':2,'mean':2,'median':2})

class LabelTests(unittest.TestCase):
    def setUp(self):
        self.features=[dict(behavior_id='synthetic',condition='FP16',source_seed=42,response_sha256='a')]
        self.rows=[dict(behavior_id='synthetic',condition='FP16',evaluator=e,source_seed='42',response_sha256='a',new_status='safe',new_label_binary='0') for e in ('HB','LG')]
    def test_valid(self): self.assertEqual(len(q.validate_labels(self.rows,self.features,['FP16'])),2)
    def test_duplicate(self):
        with self.assertRaises(ValueError): q.validate_labels(self.rows+self.rows,self.features,['FP16'])
    def test_missing(self):
        with self.assertRaises(ValueError): q.validate_labels(self.rows[:1],self.features,['FP16'])
    def test_responsehash(self):
        self.rows[0]['response_sha256']='b'
        with self.assertRaises(ValueError): q.validate_labels(self.rows,self.features,['FP16'])
    def test_wrong_seed(self):
        self.rows[0]['source_seed']='123'
        with self.assertRaises(ValueError): q.validate_labels(self.rows,self.features,['FP16'])
    def test_statuslabel(self):
        self.rows[0]['new_label_binary']='1'
        with self.assertRaises(ValueError): q.validate_labels(self.rows,self.features,['FP16'])
    def test_nonbinary_not_imputed(self):
        self.rows[0].update(new_status='invalid',new_label_binary='')
        self.assertIsNone(q.validate_labels(self.rows,self.features,['FP16'])[('FP16','synthetic','HB')])
    def test_nonbinary_cannot_be_safe(self):
        self.rows[0].update(new_status='missing',new_label_binary='0')
        with self.assertRaises(ValueError): q.validate_labels(self.rows,self.features,['FP16'])
    def test_unexpected_condition(self):
        self.rows[0]['condition']='SP70'
        with self.assertRaises(ValueError): q.validate_labels(self.rows,self.features,['FP16'])

if __name__=='__main__': unittest.main()
