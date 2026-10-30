"""Deterministic, data-free cross-check of the fixed ten-test Holm family."""
import random
import unittest
import analysis as a


class ExtendedMathTests(unittest.TestCase):
    def test_1000_holm_cases_with_ties_zeros_ones_and_missing(self):
        rng=random.Random(20261030)
        for case in range(1000):
            values=[rng.choice([None,0.0,1.0,0.005,0.05,rng.random()]) for _ in range(10)]
            ranked=sorted(enumerate(values),key=lambda item:(1.0 if item[1] is None else item[1],item[0]))
            factors=[(10-i)*(1.0 if p is None else p) for i,(_,p) in enumerate(ranked)]
            expected=[None]*10;ranks=[None]*10
            for i,(original,p) in enumerate(ranked):
                ranks[original]=i+1
                if p is not None:expected[original]=min(1.0,max(factors[:i+1]))
            with self.subTest(case=case):
                adjusted,actual_ranks=a.holm_ten(values)
                self.assertEqual(adjusted,expected)
                self.assertEqual(actual_ranks,ranks)
                self.assertEqual(len(adjusted),10)


if __name__=='__main__':unittest.main()
