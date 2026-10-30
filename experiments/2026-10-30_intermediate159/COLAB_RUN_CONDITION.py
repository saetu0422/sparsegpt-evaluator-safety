if not __debug__:
    raise RuntimeError('Validation assertions must be enabled')
"""Execute this reviewed helper after explicit private deployment/setup, then call run_condition(CONDITION,RUN_ID).

Exactly one explicitly chosen condition. No all-condition loop. Globals CODE,
PARENT, ARCHIVE, REVIEWED_BUNDLE_SHA and prepare_condition come from that setup. The exact original private installer is not bundled.
"""
from pathlib import Path
import hashlib,io,json,re,zipfile

# Immutable reviewed dependency bytes; setup/helper self-hashes are intentionally
# covered by the separately reviewed bundle digest plus installed-byte equality.
DEPLOYMENT_PINS={'colab_smoke.py': '5b63875349cf6409397282f4ce765dc8503ac8a32d5fec44ec5ab0793ccd1583', 'research_parsers.py': '6616ea2e9fd27ced56a6e00bc73340bfa6e92cb0c6ee5a213382b6732bd0cbc8', 'HB_standard_template.txt': '6e40c2f76a74aa2dc38d83b557220017311e29c249d938a256c3f0a2d87f0cac', 'drive_wrapper.py': 'c2ab469ddf7d41ef44fd39d0df72e0f58e3f9786f423cbad0151c0e4e38ebcb1', 'colab_secret_launcher.py': '4c1d1d7198d036b1f46937cb623c04276769a0183fc0d6ed65055bae5562c92c', 'analysis_plan.json': '473ecba7402b70a171b0589e8eb761cbe802330bd6de4d717a31e948aa94a5c7'}
REQUIRED_DEPLOYMENT_MEMBERS=set(DEPLOYMENT_PINS)|{'COLAB_SETUP_LEVELS.py','COLAB_RUN_CONDITION.py'}


def run_condition(condition,run_id):
    stage='configuration'
    try:
        if condition not in ('SP30','SP40','SP50','SP55','SP60') or not isinstance(run_id,str) or re.fullmatch(r'levels159_'+condition+r'_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{12}',run_id) is None:
            raise ValueError('explicit matching condition/run ID required')
        dw=colab_secret_launcher.drive_wrapper
        hb_args,lg_args=prepare_condition(condition,run_id)
        for args,judge in ((hb_args,'HB'),(lg_args,'LG')):
            for flag,value in (('--condition',condition),('--run-id',run_id),('--judge',judge),('--runner',str(CODE/'colab_smoke.py')),('--drive-parent',str(PARENT)),('--out','/content/'+run_id)):
                if args.count(flag)!=1 or args[args.index(flag)+1:] [:1]!=[value]:
                    raise ValueError('prepared argument binding mismatch')
        if Path(colab_secret_launcher.__file__).resolve()!=CODE/'colab_secret_launcher.py' or Path(dw.__file__).resolve()!=CODE/'drive_wrapper.py':
            raise ValueError('unexpected active code module path')
        stage='archive_reviewed_bundle'
        data=Path(ARCHIVE).read_bytes()
        if not isinstance(REVIEWED_BUNDLE_SHA,str) or re.fullmatch('[0-9a-f]{64}',REVIEWED_BUNDLE_SHA) is None or hashlib.sha256(data).hexdigest()!=REVIEWED_BUNDLE_SHA:
            raise ValueError('reviewed bundle SHA mismatch')
        if re.fullmatch(r'[A-Za-z0-9_.-]+[.]zip',Path(ARCHIVE).name) is None:
            raise ValueError('unexpected code bundle filename')
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if z.testzip() is not None or len(z.namelist())!=len(set(z.namelist())):
                raise ValueError('bundle CRC/inventory mismatch')
            manifest=json.loads(z.read('MANIFEST.json'))
            if not REQUIRED_DEPLOYMENT_MEMBERS.issubset(manifest['files']) or set(z.namelist())!=set(manifest['files'])|{'MANIFEST.json'}:
                raise ValueError('bundle manifest inventory mismatch')
            for name,digest in DEPLOYMENT_PINS.items():
                if hashlib.sha256(z.read(name)).hexdigest()!=digest:
                    raise ValueError('bundle reviewed dependency SHA mismatch')
            for name in z.namelist():
                if '/' in name or '\\' in name or name in ('.','..') or (CODE/name).is_symlink():
                    raise ValueError('unsafe code bundle member')
                member=z.read(name)
                if (CODE/name).read_bytes()!=member:
                    raise ValueError('installed code differs from reviewed bundle')
                if name!='MANIFEST.json' and (len(member)!=manifest['files'][name]['bytes'] or hashlib.sha256(member).hexdigest()!=manifest['files'][name]['sha256']):
                    raise ValueError('bundle member digest mismatch')
        if not isinstance(dw.CONFIGURED_DRIVE_FOLDER_ID,str) or re.fullmatch(r'[A-Za-z0-9_-]{10,100}',dw.CONFIGURED_DRIVE_FOLDER_ID) is None:
            raise ValueError('explicit verified Drive folder configuration required')
        guard=dw.DriveMountGuard(PARENT);guard()
        parent=guard.parent;parts=parent.parts
        if '.shortcut-targets-by-id' not in parts or parts[parts.index('.shortcut-targets-by-id')+1]!=dw.CONFIGURED_DRIVE_FOLDER_ID:
            raise ValueError('Drive parent ID binding mismatch')
        destination=parent/Path(ARCHIVE).name
        if destination.is_symlink():raise ValueError('symbolic-link bundle destination refused')
        guard();dw.immutable_write(destination,data);guard();dw.read_verified(destination,data);guard()
        print(json.dumps({'condition':condition,'run_id':run_id,'stage':stage,'bundle_sha256':REVIEWED_BUNDLE_SHA,'evidence':'mounted_filesystem_readback_only'}))
        stage='input_validation'
        code=dw.main([*hb_args,'--validate-input-only'])
        if code!=0:
            result={'status':'stopped_or_incomplete','condition':condition,'run_id':run_id,'stage':stage,'exit_code':code};print(json.dumps(result));return result
        stage='HB'
        code=colab_secret_launcher.launch_hb_without_secret(hb_args)
        if code!=0:
            result={'status':'stopped_or_incomplete','condition':condition,'run_id':run_id,'stage':stage,'exit_code':code};print(json.dumps(result));return result
        local=Path('/content')/run_id;remote=parent/run_id
        def read_both(relative):
            guard();a=dw.Mirror.target(local,relative);b=dw.Mirror.target(remote,relative)
            value=a.read_bytes();dw.read_verified(b,value);guard();return value
        identity=json.loads(read_both('_mirror/run_identity.json'))
        if identity.get('condition')!=condition or identity.get('run_id')!=run_id or identity.get('schema')!=dw.SCHEMA or identity.get('analysis_plan_sha256')!=dw.ANALYSIS_PLAN_SHA or identity.get('runner_code')!=dw.PINNED or identity.get('wrapper_sha256')!=dw.sha(Path(dw.__file__).read_bytes()):
            raise ValueError('completed run identity mismatch')
        def checkpoint(judge):
            completion=json.loads(read_both('completion_'+judge+'.json'))
            if completion.get('requested_judge')!=judge or completion.get('requested_evaluation_complete') is not True or completion.get('task_accounted_complete') is not True or completion.get('records')!=159 or completion.get('judged')!=159 or completion.get('excluded')!=0:
                raise ValueError('condition judge is not fully judged159')
            counts=completion.get('counts')
            if not isinstance(counts,dict) or set(counts)-{'safe','unsafe','invalid','abstain'} or any(type(v) is not int or v<0 for v in counts.values()) or sum(counts.values())!=159:
                raise ValueError('unsafe completion count schema')
            marker_bytes=read_both('_mirror/'+judge+'_MIRROR_COMPLETE.json');marker=json.loads(marker_bytes)
            if marker.get('schema')!=dw.SCHEMA or marker.get('judge')!=judge or marker.get('judged')!=159:
                raise ValueError('condition checkpoint count mismatch')
            return {'judged':159,'counts':counts,'checkpoint_sha256':hashlib.sha256(marker_bytes).hexdigest()}
        stage='HB_checkpoint'
        hb=checkpoint('HB')
        print(json.dumps({'status':'HB159_complete','condition':condition,'run_id':run_id,'HB':hb,'evidence':'mounted_filesystem_readback_only'}))
        stage='LG'
        code=colab_secret_launcher.launch_from_colab_secrets(lg_args)
        if code!=0:
            result={'status':'stopped_or_incomplete','condition':condition,'run_id':run_id,'stage':stage,'exit_code':code,'HB':hb};print(json.dumps(result));return result
        stage='LG_checkpoint'
        lg=checkpoint('LG')
        overall_bytes=read_both('_mirror/RUN_MIRROR_COMPLETE.json');overall=json.loads(overall_bytes)
        if overall.get('schema')!=dw.SCHEMA or overall.get('judged')!=318:
            raise ValueError('condition318 checkpoint missing')
        result={'status':'condition318_complete','condition':condition,'run_id':run_id,'HB':hb,'LG':lg,'judged':318,'full_checkpoint_sha256':hashlib.sha256(overall_bytes).hexdigest(),'evidence':'mounted_filesystem_readback_only'}
        print(json.dumps(result));return result
    except BaseException as exc:
        # This helper never holds credentials; omit arbitrary exception payloads.
        result={'status':'stopped_or_incomplete','condition':condition if condition in ('SP30','SP40','SP50','SP55','SP60') else 'invalid','run_id':run_id if isinstance(run_id,str) and re.fullmatch(r'levels159_(SP30|SP40|SP50|SP55|SP60)_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{12}',run_id) else 'invalid','stage':stage,'exception_type':type(exc).__name__ if type(exc).__name__ in {'ValueError','RuntimeError','PersistenceError','FileNotFoundError','PermissionError','OSError','AssertionError','KeyError','TypeError'} else 'Exception'}
        print(json.dumps(result));return result
