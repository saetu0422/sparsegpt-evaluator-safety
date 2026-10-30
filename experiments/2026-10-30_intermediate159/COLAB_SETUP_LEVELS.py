if not __debug__:
    raise RuntimeError('Validation assertions must be enabled')
# Code-only setup. No credentials, mounts, package installation, or model execution.
from pathlib import Path
import hashlib,sys,re,os
REQUIRED=('SPARSEGPT_CODE_DIR','SPARSEGPT_DRIVE_PARENT','SPARSEGPT_DRIVE_FOLDER_ID',
          'SPARSEGPT_BASELINE_RUN_ID','SPARSEGPT_REVIEWED_BUNDLE_PATH','SPARSEGPT_REVIEWED_BUNDLE_SHA256')
if any(not os.environ.get(name) for name in REQUIRED):
    raise ValueError('Set every documented private deployment configuration variable first')
CODE=Path(os.environ['SPARSEGPT_CODE_DIR']).resolve(strict=True)
ARCHIVE=Path(os.environ['SPARSEGPT_REVIEWED_BUNDLE_PATH']).resolve(strict=True)
REVIEWED_BUNDLE_SHA=os.environ['SPARSEGPT_REVIEWED_BUNDLE_SHA256']
if re.fullmatch('[0-9a-f]{64}',REVIEWED_BUNDLE_SHA) is None:
    raise ValueError('Supply the independently reviewed private bundle SHA256')
PINS={'colab_smoke': '5b63875349cf6409397282f4ce765dc8503ac8a32d5fec44ec5ab0793ccd1583', 'drive_wrapper': 'c2ab469ddf7d41ef44fd39d0df72e0f58e3f9786f423cbad0151c0e4e38ebcb1', 'colab_secret_launcher': '4c1d1d7198d036b1f46937cb623c04276769a0183fc0d6ed65055bae5562c92c'}
KNOWN={str(CODE):PINS}
for name,digest in PINS.items():
    assert not (CODE/(name+'.py')).is_symlink()
    assert hashlib.sha256((CODE/(name+'.py')).read_bytes()).hexdigest()==digest
assert hashlib.sha256((CODE/'analysis_plan.json').read_bytes()).hexdigest()=='473ecba7402b70a171b0589e8eb761cbe802330bd6de4d717a31e948aa94a5c7'
for name in PINS:
    if name in sys.modules:
        origin=Path(sys.modules[name].__file__).resolve()
        assert str(origin.parent) in KNOWN and origin.name==name+'.py','Unexpected cached code module; stop.'
        assert hashlib.sha256(origin.read_bytes()).hexdigest()==KNOWN[str(origin.parent)][name]
for name in PINS:
    if name in sys.modules:del sys.modules[name]
sys.path.insert(0,str(CODE))
import colab_secret_launcher
assert Path(colab_secret_launcher.__file__).resolve()==CODE/'colab_secret_launcher.py'
assert Path(colab_secret_launcher.drive_wrapper.__file__).resolve()==CODE/'drive_wrapper.py'
for name in ('drive_wrapper','colab_secret_launcher'):
    assert hashlib.sha256(Path(sys.modules[name].__file__).read_bytes()).hexdigest()==PINS[name]
PARENT=Path(os.environ['SPARSEGPT_DRIVE_PARENT']).resolve(strict=True)
FOLDER_ID=os.environ['SPARSEGPT_DRIVE_FOLDER_ID']
BASELINE=PARENT/os.environ['SPARSEGPT_BASELINE_RUN_ID']
BASELINE_ARCHIVE=PARENT/(BASELINE.name+'_HB_LG_636_complete_results.zip')
INPUT=BASELINE/'_mirror/inputs/verified_inputs.zip'

def prepare_condition(condition,run_id):
    if condition not in ('SP30','SP40','SP50','SP55','SP60') or not isinstance(run_id,str) or re.fullmatch(r'levels159_'+condition+r'_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{12}',run_id) is None:
        raise ValueError('Supply the explicit condition and its unique matching run ID')
    base=['--runner',str(CODE/'colab_smoke.py'),'--drive-parent',str(PARENT),'--verified-drive-folder-id',FOLDER_ID,'--baseline-run',str(BASELINE),'--baseline-archive',str(BASELINE_ARCHIVE),'--run-id',run_id,'--','--condition',condition,'--zip',str(INPUT),'--out','/content/'+run_id,'--precision','fp16']
    return base+['--judge','HB'],base+['--judge','LG']

print('Five-level code prepared. Call prepare_condition(condition,run_id) explicitly. Secrets read: no. Models executed: 0.')
