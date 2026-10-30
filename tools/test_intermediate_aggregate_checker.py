"""Neutral synthetic aggregate fixtures; not the reported research results."""
import unittest
import check_intermediate_aggregate_results as check


def fixture(missing=False):
    rates, pairs, disagreements, legacy = [], [], [], []
    for condition in ('FP16',)+check.CONDITIONS:
        n = 0 if missing and condition != 'FP16' else 159
        for evaluator in check.EVALUATORS:
            rates.append(dict(condition=condition,evaluator=evaluator,is_reused_baseline=condition=='FP16',planned=159,
                records_present=n,judged=n,safe=n,unsafe=0,invalid=0,abstain=0,excluded=0,missing=159-n,
                valid_binary=n,unsafe_rate_valid=0 if n else None))
            legacy.append(dict(condition=condition,evaluator=evaluator,valid_binary=n,agreement_n=n,disagreement_n=0,
                nonbinary_or_missing=159-n,agreement_rate_valid=1 if n else None))
        disagreements.append(dict(condition=condition,mutually_valid=n,nonbinary_or_missing=159-n,disagreement_n=0,
            disagreement_rate_valid=0 if n else None,both_safe_n00=n,HB_safe_LG_unsafe_n01=0,HB_unsafe_LG_safe_n10=0,both_unsafe_n11=0))
    for i,(condition,evaluator) in enumerate(check.FAMILY,1):
        n = 0 if missing else 159
        pairs.append(dict(condition=condition,evaluator=evaluator,baseline='FP16',baseline_is_reused=True,family_order=i,
            valid_pairs=n,planned_pairs=159,nonvalid_pairs=159-n,both_safe_n00=n,b_increase_n01=0,c_decrease_n10=0,both_unsafe_n11=0,
            FP16_unsafe_rate_paired=0 if n else None,condition_unsafe_rate_paired=0 if n else None,risk_difference=0 if n else None,
            p_exact_two_sided=1 if n else None,p_holm_ten_test_family=1 if n else None,holm_sorted_rank=i))
    return rates,pairs,disagreements,legacy


class AggregateChecks(unittest.TestCase):
    def test_nonzero_discordances_and_holm_order(self):
        data=fixture()
        expected=[1,1,.75,.5,.3125,.1875,.109375,.0625,.03515625,.01953125]
        for b,pair in enumerate(data[1],1):
            pair.update(both_safe_n00=159-b,b_increase_n01=b,condition_unsafe_rate_paired=b/159,
                risk_difference=b/159,p_exact_two_sided=min(1,2/(2**b)),
                p_holm_ten_test_family=expected[b-1],holm_sorted_rank=11-b)
            rate=next(r for r in data[0] if (r['condition'],r['evaluator'])==(pair['condition'],pair['evaluator']))
            rate.update(safe=159-b,unsafe=b,unsafe_rate_valid=b/159)
        for i,row in enumerate(data[2][1:]):
            hb,lg=2*i+1,2*i+2
            row.update(both_safe_n00=159-lg,both_unsafe_n11=hb,HB_safe_LG_unsafe_n01=1,
                disagreement_n=1,disagreement_rate_valid=1/159)
        self.assertEqual(check.check_tables(*data)['new_judged'],1590)

    def test_complete_neutral_fixture(self):
        self.assertEqual(check.check_tables(*fixture())['new_judged'],1590)

    def test_missing_conditions_retain_ten_null_slots(self):
        result=check.check_tables(*fixture(True))
        self.assertEqual(result['family_size'],10)
        self.assertEqual(result['new_judged'],0)
        self.assertEqual(result['reused_baseline_records'],318)

    def test_shrinking_family_rejected(self):
        data=fixture();data[1].pop()
        with self.assertRaises(ValueError):check.check_tables(*data)

    def test_tiny_p_value_corruption_rejected(self):
        data=fixture();data[1][0]['p_exact_two_sided']=1e-30
        with self.assertRaises(ValueError):check.check_tables(*data)

    def test_marginal_corruption_rejected(self):
        data=fixture();data[0][0]['unsafe']=1
        with self.assertRaises(ValueError):check.check_tables(*data)

    def test_reuse_mislabel_rejected(self):
        data=fixture();data[0][0]['is_reused_baseline']=False
        with self.assertRaises(ValueError):check.check_tables(*data)

    def test_missing_baseline_is_not_allowed(self):
        data=fixture(True)
        data[0][0].update(records_present=0,judged=0,safe=0,missing=159,valid_binary=0,unsafe_rate_valid=None)
        with self.assertRaisesRegex(ValueError,'reused baseline'):check.check_tables(*data)

    def test_paired_intersection_lower_bound(self):
        data=fixture()
        data[1][0].update(valid_pairs=158,nonvalid_pairs=1,both_safe_n00=158)
        with self.assertRaisesRegex(ValueError,'intersection bounds'):check.check_tables(*data)

    def test_cross_judge_intersection_lower_bound(self):
        data=fixture()
        data[2][0].update(mutually_valid=158,nonbinary_or_missing=1,both_safe_n00=158)
        with self.assertRaisesRegex(ValueError,'intersection bounds'):check.check_tables(*data)

    def test_partial_pair_safe_marginal_bound(self):
        data=fixture()
        data[0][0].update(safe=99,unsafe=60,unsafe_rate_valid=60/159)
        data[0][2].update(records_present=100,judged=100,safe=100,missing=59,valid_binary=100)
        data[1][0].update(valid_pairs=100,nonvalid_pairs=59,both_safe_n00=100)
        with self.assertRaisesRegex(ValueError,'Paired safe count'):check.check_tables(*data)


if __name__=='__main__':unittest.main()
