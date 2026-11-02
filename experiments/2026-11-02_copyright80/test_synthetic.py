"""Offline tests using only synthetic values; no private data or downloads."""
import hashlib,io,pickle,tempfile,unittest
from pathlib import Path
import numpy as np
import copyright_eval as e
class SyntheticTests(unittest.TestCase):
 def test_git_blob_hash(self):
  self.assertEqual(e.gitsha(b'example'),hashlib.sha1(b'blob 7\0example').hexdigest())
 def test_forbidden_pickle_global(self):
  with self.assertRaises(pickle.UnpicklingError):e.ReferenceUnpickler(io.BytesIO(pickle.dumps(eval))).load()
 def test_hash_mismatch_before_unpickle(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'synthetic.pkl';p.write_bytes(b'not a pickle')
   with self.assertRaises(AssertionError):e.load_reference(p,{'size':12,'git_blob_sha':'wrong','sha256':'wrong'})
 def test_reference_roundtrip_and_compatibility(self):
  with tempfile.TemporaryDirectory() as d:
   h=e.MinHash();h.update(b'synthetic');b=pickle.dumps([h]);p=Path(d)/'synthetic.pkl';p.write_bytes(b)
   refs=e.load_reference(p,{'size':len(b),'git_blob_sha':e.gitsha(b),'sha256':e.sha(b)})
   self.assertEqual(len(refs),1);np.testing.assert_array_equal(h.hashvalues,refs[0].hashvalues)
 def test_reference_incompatible_seed(self):
  with tempfile.TemporaryDirectory() as d:
   b=pickle.dumps([e.MinHash(seed=2)]);p=Path(d)/'synthetic.pkl';p.write_bytes(b)
   with self.assertRaises(AssertionError):e.load_reference(p,{'size':len(b),'git_blob_sha':e.gitsha(b),'sha256':e.sha(b)})
if __name__=='__main__':unittest.main(verbosity=2)
