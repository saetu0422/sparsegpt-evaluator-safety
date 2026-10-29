"""Configure a new private continuation using explicitly supplied local settings.

Run only with access to the separately retained, hash-bound source artifacts.
This public release does not supply or reconstruct that private input package.
No credentials are read and no model is loaded by this setup cell.
"""
if not __debug__:
    raise RuntimeError('Validation assertions must be enabled')
from pathlib import Path
import hashlib
import os
import re
import sys

# Set these environment variables before importing any release module.
REQUIRED=('SPARSEGPT_CODE_DIR','SPARSEGPT_DRIVE_PARENT','SPARSEGPT_DRIVE_FOLDER_ID',
          'SPARSEGPT_SOURCE_HB_RUN_ID','SPARSEGPT_SOURCE_LG_RUN_ID','SPARSEGPT_FULL159_RUN_ID')
if any(not os.environ.get(name) for name in REQUIRED):
    raise ValueError('Set every documented SPARSEGPT_* configuration variable first')
CODE=Path(os.environ['SPARSEGPT_CODE_DIR']).resolve(strict=True)
PARENT=Path(os.environ['SPARSEGPT_DRIVE_PARENT']).resolve(strict=True)
FOLDER_ID=os.environ['SPARSEGPT_DRIVE_FOLDER_ID']
FULL159_RUN_ID=os.environ['SPARSEGPT_FULL159_RUN_ID']
if not re.fullmatch(r'full159_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{12}',FULL159_RUN_ID):
    raise ValueError('Provide an explicit unique full159 run ID')
PINS={'drive_wrapper': '9d8934bd7af0e0bf69d610ade2a6e91f4cd42f7cabbb654ecfa9f48e14d657b8', 'colab_secret_launcher': '5d07ffca7bfb089f53909a1337506a1f91d8a15f2e51382dd02dcc75644d062e', 'colab_smoke': 'd56b4e1a67b2f0b801ba98f46e65e4052e1e60217ea102d037520b455eb353ee'}
for name,digest in PINS.items():
    source=CODE/(name+'.py')
    if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest()!=digest:
        raise ValueError('Release code SHA mismatch')
    if name in sys.modules:
        raise ValueError('Restart the runtime before switching release versions')
if hashlib.sha256((CODE/'analysis_plan.json').read_bytes()).hexdigest()!='ea8e753776999b6b28868f9f692d8b6459685f598de1677c8802bfe98f776dfa':
    raise ValueError('Frozen analysis plan SHA mismatch')
sys.path.insert(0,str(CODE))
import colab_secret_launcher
if Path(colab_secret_launcher.__file__).resolve()!=CODE/'colab_secret_launcher.py':
    raise ValueError('Unexpected launcher import')
if Path(colab_secret_launcher.drive_wrapper.__file__).resolve()!=CODE/'drive_wrapper.py':
    raise ValueError('Unexpected wrapper import')
SOURCE_HB=PARENT/os.environ['SPARSEGPT_SOURCE_HB_RUN_ID']
SOURCE_LG=PARENT/os.environ['SPARSEGPT_SOURCE_LG_RUN_ID']
INPUT=SOURCE_HB/'_mirror/inputs/verified_inputs.zip'
BASE_ARGS=['--runner',str(CODE/'colab_smoke.py'),'--drive-parent',str(PARENT),
           '--verified-drive-folder-id',FOLDER_ID,'--source-hb-run',str(SOURCE_HB),
           '--source-lg-run',str(SOURCE_LG),'--run-id',FULL159_RUN_ID,'--',
           '--zip',str(INPUT),'--out','/content/'+FULL159_RUN_ID,'--precision','fp16']
HB_ARGS=BASE_ARGS+['--judge','HB']
LG_ARGS=BASE_ARGS+['--judge','LG']
print('Prepared explicit standard159 configuration. Secret read: no. Models executed: 0.')
