import unittest
from reference_interpretation import interval_relation
class Tests(unittest.TestCase):
    def test_below(self):self.assertEqual(interval_relation([-.02,.09]),'wholly_below_reference')
    def test_crossing(self):self.assertEqual(interval_relation([.05,.15]),'contains_or_touches_reference')
    def test_above(self):self.assertEqual(interval_relation([.40,.56]),'wholly_above_reference')
    def test_touching(self):
        self.assertEqual(interval_relation([0,.1]),'contains_or_touches_reference')
        self.assertEqual(interval_relation([.1,.2]),'contains_or_touches_reference')
    def test_missing_and_invalid(self):
        self.assertEqual(interval_relation(None),'unavailable')
        with self.assertRaises(ValueError):interval_relation([.2,.1])
        with self.assertRaises(ValueError):interval_relation([float('nan'),.2])
if __name__=='__main__':unittest.main(verbosity=2)
