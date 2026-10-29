"""Verify local public-release bytes; does not install, download or execute models."""
from pathlib import Path
import hashlib
import json


def verify(root=None):
    root=Path(root) if root is not None else Path(__file__).parent
    manifest=json.loads((root/'CODE_PROVENANCE.json').read_text(encoding='utf8'))
    for entry in manifest['files']:
        name=entry['path']
        if Path(name).name!=name or name in {'.','..'}:
            raise ValueError('Unexpected manifest path')
        path=root/name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing or symbolic-link release file')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=entry['release_sha256'] or len(data)!=entry['release_bytes']:
            raise ValueError('Public release bytes differ from the manifest')
    return len(manifest['files'])


if __name__=='__main__':
    print(json.dumps({'verified_files':verify(),'network_used':False,'models_loaded':0}))
