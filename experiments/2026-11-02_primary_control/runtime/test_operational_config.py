import unittest,dataclasses
from operational_config import OperationalConfig

def valid():return OperationalConfig('fixture-folder','operator@example.invalid','/fixture/mount/research','/fixture/mount','/fixture/scratch','2050-01-01T00:00:00+00:00','2050-01-01T01:00:00+00:00','2050-01-01T02:00:00+00:00',100.,65.)
class ConfigTests(unittest.TestCase):
 def test_valid(self):valid().validate()
 def test_immutable(self):
  with self.assertRaises(dataclasses.FrozenInstanceError):valid().folder_id='changed'
 def test_timezone_required(self):
  with self.assertRaises(ValueError):dataclasses.replace(valid(),hard_stop_utc='2050-01-01T02:00:00').validate()
 def test_twohour_cap(self):
  with self.assertRaises(ValueError):dataclasses.replace(valid(),hard_stop_utc='2050-01-01T02:00:01+00:00').validate()
 def test_invalid_path(self):
  with self.assertRaises(ValueError):dataclasses.replace(valid(),expected_parent='/elsewhere').validate()
 def test_scratch_not_remote(self):
  with self.assertRaises(ValueError):dataclasses.replace(valid(),ephemeral_root='/fixture/mount/scratch').validate()
 def test_unknown_budget(self):
  for x in [float('nan'),float('inf'),-1,100.]:
   with self.assertRaises(ValueError):dataclasses.replace(valid(),stop_balance_cu=x).validate()
 def test_config_cannot_reset(self):
  import control_runner as r
  if r._OPERATIONAL is None:r.configure_operational(valid())
  with self.assertRaises(RuntimeError):r.configure_operational(valid())
 def test_active_config_source_mismatch_stops_before_storage(self):
  import control_runner as r,hashlib,datetime as dt
  from pathlib import Path
  from unittest.mock import patch
  root=Path(r.__file__).parent
  files={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ('control_runner.py','storage.py','operational_config.py')}
  files['operational_config.py']='0'*64
  with patch.object(r,'now',return_value=dt.datetime(2050,1,1,0,1,tzinfo=dt.timezone.utc)),patch.object(r,'verify_bundle',return_value=({'files':files},[])),patch.object(r.storage,'DriveMountGuard') as guard:
   with self.assertRaisesRegex(ValueError,'Active module not frozen bundle'):
    r.Session(root/'manifest.json','unused','/fixture/scratch/primarycontrol_20500101T000100Z_123456789abc','/fixture/mount/research','primarycontrol_20500101T000100Z_123456789abc',r._OPERATIONAL.original_connection_utc,99.,'2050-01-01T00:01:00+00:00',1.)
   guard.assert_not_called()
