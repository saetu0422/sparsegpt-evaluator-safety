import unittest
import numpy as np
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
import analyze as a

class AnalysisTests(unittest.TestCase):
    def test_whitespace_punctuation_case(self):
        q=a.quality('A a A,\tA,\nB');self.assertEqual(q['words'],5);self.assertEqual(q['unique_ratio'],3/5);self.assertEqual(q['dominance'],2/5)
    def test_empty(self):
        self.assertEqual(a.quality(''),dict(words=0,unique_ratio=0.,repeat=0.,legacy_repeat=0.,dominance=0.,collapse=0))
    def test_missing_rejected(self):
        for value in [None,42,float('nan')]:
            with self.assertRaises(ValueError):a.quality(value)
    def test_under_six_override(self):
        self.assertEqual(a.quality('a '*5)['repeat'],0);self.assertAlmostEqual(a.quality('a '*5)['legacy_repeat'],2/3)
        self.assertEqual(a.quality('a '*6)['repeat'],.75)
    def test_collapse_boundary(self):
        self.assertEqual(a.quality('x '*19)['collapse'],0);self.assertEqual(a.quality('x '*20)['collapse'],1)
        self.assertEqual(a.quality(' '.join(str(i) for i in range(500)))['collapse'],0)
    def test_wilson(self):
        self.assertAlmostEqual(a.wilson(0,10)[0],0);self.assertAlmostEqual(a.wilson(0,10)[1],.2775327998628892)
        self.assertEqual(a.wilson(0,0),[None,None]);self.assertAlmostEqual(a.wilson(5,10)[0],1-a.wilson(5,10)[1])
    def test_holm(self):
        np.testing.assert_allclose(a.holm([.04,.001,.03,.5]),[.09,.004,.09,.5]);self.assertEqual(a.holm([1,1]),[1,1])
    def test_auc_ties(self):
        self.assertEqual(a.auc([0,1],[.5,.5]),.5);self.assertEqual(a.auc([0,1],[0,1]),1);self.assertEqual(a.auc([0,1],[1,0]),0)
        y=[0,1,1,0,1];p=[.3,.3,.6,.1,.2];self.assertAlmostEqual(a.auc(y,p),roc_auc_score(y,p))
    def test_separation(self):
        self.assertEqual(a.separation(np.array([[1,-2],[1,-1],[1,1],[1,2]]),[0,0,1,1]),'complete')
        self.assertEqual(a.separation(np.array([[1,-1],[1,0],[1,0],[1,1]]),[0,0,1,1]),'quasi')
        self.assertEqual(a.separation(np.array([[1,-1],[1,-1],[1,1],[1,1]]),[0,1,0,1]),'none')
    def test_logistic_reference(self):
        rng=np.random.default_rng(123);X=rng.normal(size=(300,3));y=rng.binomial(1,a.special.expit(.1+X@np.array([.2,-.4,.3])))
        r,_=a.logistic(X,y);ref=LogisticRegression(penalty=None,tol=1e-10,max_iter=10000).fit(X,y)
        self.assertEqual(r['status'],'ok');np.testing.assert_allclose(r['original_units']['coefficients'],np.r_[ref.intercept_,ref.coef_[0]],atol=2e-6)
    def test_separated_model_invalid(self):
        X=np.array([[i,i*i,i*i*i] for i in range(-5,6)]);y=(X[:,0]>0).astype(int);r,fit=a.logistic(X,y);self.assertEqual(r['status'],'invalid_inference');self.assertIsNone(fit)
    def test_rank_deficiency(self):
        X=np.array([[i,i,i*i] for i in range(10)]);r,fit=a.logistic(X,[0,1]*5);self.assertEqual(r['status'],'rank_deficient')
    def test_bootstrap_seed(self):
        self.assertEqual(a.bootmean([1,2,3],np.random.default_rng(42),1000),a.bootmean([1,2,3],np.random.default_rng(42),1000))
    def test_no_discordant_p(self):
        # all discordance-free paired samples must have p1, not binomtest(n0)
        import pandas as pd
        f=pd.DataFrame([dict(condition=c,behavior_id=str(i),LG=i%2,HB=i%2) for c in ['FP16','SP30'] for i in range(8)])
        rows=a.paired(f,np.random.default_rng(42),1000,[('FP16','SP30')]);self.assertTrue(all(r['raw_p']==r['holm_p']==1 and r['delta_pp']==0 for r in rows))
if __name__=='__main__':unittest.main(verbosity=2)
