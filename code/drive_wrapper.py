"""Fail-closed mounted-Drive mirror for the unchanged, pinned smoke runner.

No authentication, mounts, package installs, model changes, or Drive API calls.
Read-back verifies the mounted filesystem, NOT Google's backend durability.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import uuid

CONFIGURED_DRIVE_FOLDER_ID = os.environ.get("SPARSEGPT_DRIVE_FOLDER_ID")

SCHEMA = "sparsegpt-mounted-drive-standard159-v1"
PINNED = {
    "colab_smoke.py": "d56b4e1a67b2f0b801ba98f46e65e4052e1e60217ea102d037520b455eb353ee",
    "research_parsers.py": "6616ea2e9fd27ced56a6e00bc73340bfa6e92cb0c6ee5a213382b6732bd0cbc8",
    "HB_standard_template.txt": "6e40c2f76a74aa2dc38d83b557220017311e29c249d938a256c3f0a2d87f0cac",
}
INPUT_SHA = "dd8e84fe8a6e1d4d6f460ab5cb27f1f4650f90f162f99450e8766a5c8254d482"
ANALYSIS_PLAN_SHA = "ea8e753776999b6b28868f9f692d8b6459685f598de1677c8802bfe98f776dfa"
PER_JUDGE = 318
TOTAL_TASKS = 636
SOURCE_LG_RUN_ID = os.environ.get("SPARSEGPT_SOURCE_LG_RUN_ID")
SOURCE_LG_CHECKPOINT_SHA = "8457acfdb17bda226f8c142cf747d05f1b872eeaee1148e25cbb3537fc23ecc4"
SOURCE_LG_RUNNER_SHA = "a35fde7c5c1ade041e9deed6100d212c9cba03bb3af571701ab17dcc030a7a19"
SOURCE_LG_WRAPPER_SHA = "c8e5777337d38cdc7d6602024debac8af74967c6275ef3d6d622afb9e71d827a"
SOURCE_HB_RUN_ID = os.environ.get("SPARSEGPT_SOURCE_HB_RUN_ID")
SOURCE_HB_CHECKPOINT_SHA = "c609231e01df928b0a2e6fcdec7ea94b446229a303dce7771cb8574d94e1b718"
SOURCE_RUNNER_SHA = "2be8a612888fe4a642480f65c2eaa996ce12935b32fb62318a7a928acf210ef8"
SOURCE_WRAPPER_SHA = "ee053c293766eaa70e32406d7868895c90244ab82488db8ddd23ec08166f5f43"


class PersistenceError(RuntimeError):
    """Any storage uncertainty stops the invocation; do not suppress or retry."""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def safe_exception_name(exc, secret=None):
    name = type(exc).__name__
    return "RedactedException" if isinstance(secret,str) and secret and secret in name else name


def require_official_hf_endpoint():
    """Check effective hub endpoints before credentials are read or forwarded."""
    official = "https://huggingface.co"
    if os.environ.get("HF_ENDPOINT") not in (None, official):
        raise PersistenceError("nonofficial Hugging Face endpoint refused")
    hub = importlib.import_module("huggingface_hub.constants")
    transformers_hub = importlib.import_module("transformers.utils.hub")
    if getattr(hub,"ENDPOINT",None) != official:
        raise PersistenceError("nonofficial effective Hugging Face endpoint refused")
    if getattr(transformers_hub,"HUGGINGFACE_CO_RESOLVE_ENDPOINT",official) != official:
        raise PersistenceError("nonofficial transformer download endpoint refused")


def validate_hb_lineage(source, runner, tasks, provenance):
    """Read-only validation of the exact old HB checkpoint; never import its records."""
    if not CONFIGURED_DRIVE_FOLDER_ID or not SOURCE_HB_RUN_ID:
        raise PersistenceError("historical source configuration missing")
    source = Path(source)
    if source.is_symlink() or source.name != SOURCE_HB_RUN_ID:
        raise PersistenceError("unexpected source HB run")
    def read(relative):
        return Mirror.target(source, relative).read_bytes()
    checkpoint_bytes = read("_mirror/HB_MIRROR_COMPLETE.json")
    if sha(checkpoint_bytes) != SOURCE_HB_CHECKPOINT_SHA:
        raise PersistenceError("source HB checkpoint hash mismatch")
    checkpoint = json.loads(checkpoint_bytes)
    if checkpoint.get("judge") != "HB" or checkpoint.get("judged") != 6:
        raise PersistenceError("source HB checkpoint scope mismatch")
    source_pins = dict(PINNED, **{"colab_smoke.py": SOURCE_RUNNER_SHA})
    identity = json.loads(read("_mirror/run_identity.json"))
    if (identity.get("run_id") != SOURCE_HB_RUN_ID or identity.get("input_sha256") != INPUT_SHA
        or identity.get("runner_code") != source_pins or identity.get("wrapper_sha256") != SOURCE_WRAPPER_SHA
        or identity.get("precision") != "fp16" or identity.get("verified_drive_folder_id") != CONFIGURED_DRIVE_FOLDER_ID):
        raise PersistenceError("source HB run identity mismatch")
    for name, digest in dict(source_pins, **{"drive_wrapper.py": SOURCE_WRAPPER_SHA}).items():
        if sha(read("_mirror/code/" + name)) != digest:
            raise PersistenceError("source HB pinned code mismatch")
    old_tasks=json.loads(read("tasks.json")); old_provenance=json.loads(read("input_provenance.json"))
    full_by_key={t['task_key']:t for t in tasks}
    if (len(tasks)!=TOTAL_TASKS or len(full_by_key)!=TOTAL_TASKS or len(old_tasks)!=12
        or len({t['task_key'] for t in old_tasks})!=12 or len({t['behavior_id'] for t in old_tasks})!=3
        or any(full_by_key.get(t['task_key'])!=t for t in old_tasks)
        or any(provenance.get(k)!=v for k,v in old_provenance.items())):
        raise PersistenceError("old 12 smoke tasks are not an exact subset of the new 636 tasks")
    for entry in checkpoint["artifacts"]:
        data = read(entry["path"])
        if len(data) != entry["bytes"] or sha(data) != entry["sha256"]:
            raise PersistenceError("source HB checkpoint artifact mismatch")
    protocol_bytes = read("HB_protocol.json")
    protocol = json.loads(protocol_bytes)
    if (protocol.get("runner_code_sha256") != SOURCE_RUNNER_SHA or protocol.get("parser_code_sha256") != PINNED["research_parsers.py"]
        or protocol.get("judge") != "HB" or protocol.get("model_id") != runner.MODELS["HB"][0]
        or protocol.get("model_revision") != runner.MODELS["HB"][1] or protocol.get("tasks_sha256") != sha(runner.canonical(old_tasks))
        or protocol.get("inputs") != old_provenance or protocol.get("settings") != {
            "seed":42,"do_sample":False,"temperature_inactive":0,"top_p_inactive":1,
            "max_new_tokens":1,"dtype":"float16","quantization":"none"}):
        raise PersistenceError("source HB scientific protocol mismatch")
    selected = {runner.sha(t["task_key"].encode()) + ".json": t for t in old_tasks if t["evaluator"] == "HB"}
    listed = [x for x in checkpoint["artifacts"] if x["path"].startswith("records/")]
    if len(selected) != 6 or {Path(x["path"]).name for x in listed} != set(selected):
        raise PersistenceError("source HB record membership mismatch")
    for entry in listed:
        record = json.loads(read(entry["path"]))
        runner.verify_record(record, selected[Path(entry["path"]).name], sha(runner.canonical(protocol)))
        if record["status"] != "judged":
            raise PersistenceError("source HB record was not judged")
    return {"source_run_id": SOURCE_HB_RUN_ID, "source_drive_folder_id": identity["verified_drive_folder_id"],
            "source_hb_checkpoint_sha256": SOURCE_HB_CHECKPOINT_SHA, "source_hb_protocol_sha256": sha(protocol_bytes),
            "source_runner_sha256": SOURCE_RUNNER_SHA, "source_wrapper_sha256": SOURCE_WRAPPER_SHA,
            "source_tasks_sha256": sha(runner.canonical(old_tasks)), "new_tasks_sha256": sha(runner.canonical(tasks)), "input_sha256": INPUT_SHA,
            "response_bindings": [{k:t[k] for k in ("task_key","response_sha256")} for t in old_tasks],
            "source_hb_records": listed, "source_hb_judged":6,
            "scope":"636 new judgments; old12 task subset verified as provenance only; no old records imported"}


def validate_lg_lineage(source, runner, tasks, hb_source):
    """Pin the successful v2 smoke LG checkpoint; inspect only, never import results."""
    if not CONFIGURED_DRIVE_FOLDER_ID or not SOURCE_LG_RUN_ID:
        raise PersistenceError("historical source configuration missing")
    source=Path(source)
    if source.is_symlink() or source.name!=SOURCE_LG_RUN_ID:
        raise PersistenceError('unexpected source LG run')
    def read(relative):
        return Mirror.target(source,relative).read_bytes()
    checkpoint_bytes=read('_mirror/LG_MIRROR_COMPLETE.json')
    if sha(checkpoint_bytes)!=SOURCE_LG_CHECKPOINT_SHA:
        raise PersistenceError('source LG checkpoint hash mismatch')
    checkpoint=json.loads(checkpoint_bytes)
    if checkpoint.get('judge')!='LG' or checkpoint.get('judged')!=6:
        raise PersistenceError('source LG checkpoint scope mismatch')
    pins=dict(PINNED,**{'colab_smoke.py':SOURCE_LG_RUNNER_SHA})
    identity=json.loads(read('_mirror/run_identity.json'))
    if (identity.get('run_id')!=SOURCE_LG_RUN_ID or identity.get('input_sha256')!=INPUT_SHA
        or identity.get('runner_code')!=pins or identity.get('wrapper_sha256')!=SOURCE_LG_WRAPPER_SHA
        or identity.get('precision')!='fp16' or identity.get('verified_drive_folder_id')!=CONFIGURED_DRIVE_FOLDER_ID):
        raise PersistenceError('source LG run identity mismatch')
    for name,digest in dict(pins,**{'drive_wrapper.py':SOURCE_LG_WRAPPER_SHA}).items():
        if sha(read('_mirror/code/'+name))!=digest:
            raise PersistenceError('source LG code mismatch')
    old_tasks=json.loads(read('tasks.json')); full={t['task_key']:t for t in tasks}
    if read('tasks.json')!=Mirror.target(Path(hb_source),'tasks.json').read_bytes() or len(full)!=TOTAL_TASKS or any(full.get(t['task_key'])!=t for t in old_tasks):
        raise PersistenceError('source LG task subset mismatch')
    for entry in checkpoint['artifacts']:
        data=read(entry['path'])
        if len(data)!=entry['bytes'] or sha(data)!=entry['sha256']:
            raise PersistenceError('source LG checkpoint artifact mismatch')
    protocol_bytes=read('LG_protocol.json'); protocol=json.loads(protocol_bytes)
    if (protocol.get('runner_code_sha256')!=SOURCE_LG_RUNNER_SHA or protocol.get('parser_code_sha256')!=PINNED['research_parsers.py']
        or protocol.get('judge')!='LG' or protocol.get('model_id')!=runner.MODELS['LG'][0]
        or protocol.get('model_revision')!=runner.MODELS['LG'][1] or protocol.get('tasks_sha256')!=sha(runner.canonical(old_tasks))
        or protocol.get('inputs')!=json.loads(read('input_provenance.json')) or protocol.get('settings')!={
            'seed':42,'do_sample':False,'temperature_inactive':0,'top_p_inactive':1,'max_new_tokens':128,'dtype':'float16','quantization':'none'}):
        raise PersistenceError('source LG scientific protocol mismatch')
    selected={runner.sha(t['task_key'].encode())+'.json':t for t in old_tasks if t['evaluator']=='LG'}
    listed=[x for x in checkpoint['artifacts'] if x['path'].startswith('records/')]
    if len(selected)!=6 or {Path(x['path']).name for x in listed}!=set(selected):
        raise PersistenceError('source LG record membership mismatch')
    for entry in listed:
        record=json.loads(read(entry['path']))
        runner.verify_record(record,selected[Path(entry['path']).name],sha(runner.canonical(protocol)))
        if record['status']!='judged': raise PersistenceError('source LG record not judged')
    return {'source_run_id':SOURCE_LG_RUN_ID,'source_lg_checkpoint_sha256':SOURCE_LG_CHECKPOINT_SHA,
        'source_lg_protocol_sha256':sha(protocol_bytes),'source_tasks_sha256':sha(runner.canonical(old_tasks)),
        'new_tasks_sha256':sha(runner.canonical(tasks)),'source_lg_judged':6,'source_lg_records':listed,
        'scope':'provenance only; all636 judgments are new; no old records imported'}


def validate_full_hb_stage(mirror, runner, tasks):
    """LG may only begin after all318 new HB judgments are verified in this run."""
    mirror.guard()
    marker=json.loads(Mirror.target(mirror.local,"_mirror/HB_MIRROR_COMPLETE.json").read_bytes())
    if marker.get('schema')!=SCHEMA or marker.get('judge')!='HB' or marker.get('judged')!=PER_JUDGE:
        raise PersistenceError('LG requires this full159 run HB318 checkpoint first')
    records=runner.records_checked(mirror.local,tasks)
    hb=[x for x in records if x['evaluator']=='HB']
    if len(hb)!=PER_JUDGE or any(x['status']!='judged' for x in hb):
        raise PersistenceError('LG requires all318 verified new HB judgments')
    mirror.audit(); mirror.audit_control(); mirror.guard()


def read_verified(path, expected):
    data = Path(path).read_bytes()
    if len(data) != len(expected) or sha(data) != sha(expected) or data != expected:
        raise PersistenceError("read-back verification failed")


def immutable_write(path, data):
    """Cooperative lock + atomic rename + exact read-back; never replace conflicts.

    Interrupted locks/temporary files require operator inspection, not auto-deletion.
    This is not a cross-client lock guarantee for Drive/FUSE.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise PersistenceError("symbolic-link output refused")
    lock = path.with_name(path.name + ".mirrorlock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        if path.exists():
            read_verified(path, data)
            return False
        temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".part")
        with temp.open("xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        read_verified(temp, data)
        if path.exists():
            raise PersistenceError("destination appeared during commit")
        os.replace(temp, path)
        read_verified(path, data)
        return True
    finally:
        lock.unlink()


def drive_mount_state(parent, mount=Path("/content/drive")):
    """Refuse an unmounted directory masquerading as Drive. No mount is performed."""
    mount = Path(mount).resolve(strict=True)
    parent = Path(parent).resolve(strict=True)
    if not parent.is_dir() or not parent.is_relative_to(mount) or parent == mount:
        raise PersistenceError("existing verified parent must be below Drive mount")
    found = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        before, after = line.split(" - ", 1)
        fields = before.split()
        point = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), fields[4])
        if Path(point) == mount:
            after_fields = after.split()
            found.append({"mount_id": fields[0], "device": fields[2], "mount_root": fields[3],
                          "mountpoint": point, "filesystem": after_fields[0], "source": after_fields[1]})
    if len(found) != 1 or found[0]["filesystem"] not in {"fuse.drive", "fuse.drivefs"}:
        raise PersistenceError("expected mounted Google Drive FUSE filesystem absent")
    return parent, found[0]


def mounted_drive_parent(parent, mount=Path("/content/drive")):
    return drive_mount_state(parent, mount)[0]


class DriveMountGuard:
    def __init__(self, parent):
        self.requested = parent
        self.parent, self.identity = drive_mount_state(parent)

    def __call__(self):
        parent, identity = drive_mount_state(self.requested)
        if parent != self.parent or identity != self.identity:
            raise PersistenceError("Drive mount identity or resolved parent changed during invocation")
        return parent


class Mirror:
    def __init__(self, local, remote, identity, storage_guard=None):
        if Path(local).is_symlink() or Path(remote).is_symlink():
            raise PersistenceError("symbolic-link run root refused")
        self.local = Path(local).resolve()
        self.remote = Path(remote).resolve()
        if self.local == self.remote or self.local.is_relative_to(self.remote) or self.remote.is_relative_to(self.local):
            raise PersistenceError("scratch and mirror must be separate")
        self.identity = identity
        self.invocation = uuid.uuid4().hex
        self.seq = 0
        self.broken = False
        self.locks = []
        self.storage_guard = storage_guard
        self.local_bound = False
        self.remote_bound = False
        self.forbidden_bytes = ()

    def guard(self):
        for root in (self.local, self.remote):
            if root.is_symlink() or (root / "_mirror").is_symlink():
                raise PersistenceError("symbolic-link run/metadata root refused")
        if self.storage_guard:
            self.storage_guard()

    @staticmethod
    def target(root, relative):
        relative = Path(relative)
        if relative.is_absolute() or ".." in relative.parts:
            raise PersistenceError("output path escaped run root")
        current = root
        for part in ("", *relative.parts):
            current = current / part
            if current.is_symlink():
                raise PersistenceError("symbolic-link output ancestor refused")
        return root / relative

    def assert_clean(self, data):
        if any(secret and secret in data for secret in self.forbidden_bytes):
            raise PersistenceError("credential material refused before artifact write")

    def _remote_write(self, relative, data):
        self.assert_clean(data)
        if self.broken:
            raise PersistenceError("mirror already failed; execution remains stopped")
        try:
            self.guard()
            changed = immutable_write(self.target(self.remote, relative), data)
            self.guard()
            return changed
        except Exception as exc:
            self.broken = True
            raise PersistenceError("Drive mirror commit failed; local data retained") from exc

    def dual(self, relative, data):
        self.assert_clean(data)
        immutable_write(self.target(self.local, relative), data)
        return self._remote_write(relative, data)

    def begin(self):
        self.guard()
        # Refuse adopting a nonempty unrelated destination as a new run.
        for root in (self.local, self.remote):
            if root.exists() and not (root / "_mirror/run_identity.json").exists() and any(root.iterdir()):
                raise PersistenceError("nonempty unbound run directory refused")
            if (root / "_mirror/run_identity.json").exists():
                read_verified(root / "_mirror/run_identity.json", canonical(self.identity))
            self.guard()
            root.mkdir(parents=True, exist_ok=True)
        for root in (self.local, self.remote):
            self.guard()
            path = root / ".mirror_session.lock"
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(fd, canonical({"invocation": self.invocation, "pid": os.getpid()}))
            os.close(fd)
            self.locks.append(path)
        relative = "_mirror/run_identity.json"
        immutable_write(self.target(self.local, relative), canonical(self.identity))
        self.local_bound = True
        self._remote_write(relative, canonical(self.identity))
        self.remote_bound = True
        self.health()
        self.reconcile()

    def close(self):
        for path in reversed(self.locks):
            path.unlink()  # Do not mask a lock-removal failure.
        self.locks.clear()

    def health(self):
        # Fresh, unique, retained write/read/hash probe for every invocation/record.
        self.seq += 1
        rel = f"_mirror/invocations/{self.invocation}/events/{self.seq:06d}.json"
        self.dual(rel, canonical({"event": "storage_probe", "utc": utc(), "nonce": uuid.uuid4().hex,
                                  "evidence": "mounted_filesystem_readback_only"}))

    @staticmethod
    def artifact_paths(root):
        if root.is_symlink() or (root / "_mirror").is_symlink():
            raise PersistenceError("symbolic-link run/metadata root refused")
        if not root.exists():
            return {}
        result = {}
        for p in root.rglob("*"):
            rel = p.relative_to(root)
            if rel.parts[0] == "_mirror" or rel.as_posix() in {".mirror_session.lock", ".lock"}:
                continue
            if p.is_symlink():
                raise PersistenceError("symbolic-link artifact refused")
            if p.is_file():
                if p.suffix in {".tmp", ".part", ".commitlock", ".mirrorlock"}:
                    raise PersistenceError("interrupted artifact commit needs inspection")
                result[rel.as_posix()] = p
        return result

    def reconcile(self):
        self.guard()
        # Restore missing local records from this same bound run; preserve all conflicts.
        local = self.artifact_paths(self.local)
        remote = self.artifact_paths(self.remote)
        for rel in sorted(local.keys() | remote.keys()):
            data = (local.get(rel) or remote[rel]).read_bytes()
            if rel in remote:
                read_verified(remote[rel], data)
            self.dual(rel, data)
        # Restore code/config/logs/checkpoints as well after a lost runtime.
        controls = set()
        for root in (self.local, self.remote):
            for path in (root / "_mirror").rglob("*"):
                if path.is_symlink():
                    raise PersistenceError("symbolic-link metadata refused")
                if path.is_file():
                    if path.suffix in {".part", ".mirrorlock"}:
                        raise PersistenceError("interrupted metadata commit needs inspection")
                    controls.add(path.relative_to(root).as_posix())
        for rel in sorted(controls):
            a, b = self.local / rel, self.remote / rel
            self.dual(rel, (a if a.exists() else b).read_bytes())
        self.audit_control()

    def audit_control(self):
        # These files are excluded from stable result manifests, but all local
        # metadata/events/code must still exist byte-for-byte on mounted Drive.
        self.guard()
        root = self.local / "_mirror"
        entries = []
        if root.exists():
            for p in root.rglob("*"):
                if p.is_symlink():
                    raise PersistenceError("symbolic-link metadata refused")
                if p.is_file():
                    if p.suffix in {".part", ".mirrorlock"}:
                        raise PersistenceError("interrupted metadata commit needs inspection")
                    data = p.read_bytes()
                    relative = p.relative_to(self.local).as_posix()
                    read_verified(self.remote / relative, data)
                    is_checkpoint = p.name == "MIRROR_VERIFIED.json" or p.name.endswith("MIRROR_COMPLETE.json")
                    if is_checkpoint:
                        previous = json.loads(data)
                        for entry in previous.get("artifacts", []) + previous.get("metadata", []):
                            rel = Path(entry["path"])
                            if rel.is_absolute() or ".." in rel.parts:
                                raise PersistenceError("invalid prior checkpoint path")
                            stored = (self.remote / rel).read_bytes()
                            if len(stored) != entry["bytes"] or sha(stored) != entry["sha256"]:
                                raise PersistenceError("prior checkpoint evidence mismatch")
                    else:
                        entries.append({"path": relative, "bytes": len(data), "sha256": sha(data)})
        self.guard()
        return sorted(entries, key=lambda x: x["path"])

    def audit(self):
        self.guard()
        local, remote = self.artifact_paths(self.local), self.artifact_paths(self.remote)
        if local.keys() != remote.keys():
            raise PersistenceError("artifact mirror inventory mismatch")
        entries = []
        for rel in sorted(local):
            data = local[rel].read_bytes()
            read_verified(remote[rel], data)
            entries.append({"path": rel, "bytes": len(data), "sha256": sha(data)})
        self.guard()
        return entries

    def event(self, kind, **fields):
        self.seq += 1
        rel = f"_mirror/invocations/{self.invocation}/events/{self.seq:06d}.json"
        self.dual(rel, canonical({"event": kind, "utc": utc(), **fields}))

    def hook(self, runner):
        original_freeze, original_render = runner.freeze, runner.render

        def freeze(path, obj):
            path = Path(path).resolve()
            if not path.is_relative_to(self.local) or path == self.local:
                raise PersistenceError("runner output escaped scratch")
            rel = path.relative_to(self.local).as_posix()
            self.assert_clean(runner.canonical(obj))
            changed = original_freeze(path, obj)  # Original exact conflict rules retained.
            data = path.read_bytes()
            self._remote_write(rel, data)  # Must finish before runner can continue.
            self.event("artifact_committed", path=rel, bytes=len(data), sha256=sha(data))
            return changed

        def render(*args, **kwargs):
            self.health()
            self.audit()
            self.audit_control()
            return original_render(*args, **kwargs)

        runner.freeze, runner.render = freeze, render
        return lambda: (setattr(runner, "freeze", original_freeze), setattr(runner, "render", original_render))

    def finish(self, mode, judge):
        entries = self.audit()
        metadata = self.audit_control()
        checkpoint = {"schema": SCHEMA, "mode": mode, "judge": judge,
                      "evidence": "mounted_filesystem_readback_only", "artifacts": entries, "metadata": metadata}
        self.dual(f"_mirror/invocations/{self.invocation}/MIRROR_VERIFIED.json", canonical(checkpoint))
        if mode != "inference":
            return
        judges = ("HB", "LG") if judge == "both" else (judge,)
        for j in judges:
            completion = json.loads((self.local / f"completion_{judge}.json").read_text())
            if not completion.get("requested_evaluation_complete"):
                continue
            selected = [p for p in (self.local / "records").glob("*.json")
                        if json.loads(p.read_text()).get("evaluator") == j]
            if len(selected) != PER_JUDGE or any(json.loads(p.read_text()).get("status") != "judged" for p in selected):
                raise PersistenceError("completion count disagrees with judged records")
            # Stable per-judge evidence; later LG failure cannot invalidate HB's checkpoint.
            # completion_HB/LG/both.json are invocation-shaped. They remain in
            # MIRROR_VERIFIED's complete artifact manifest, not the stable core.
            subset = [x for x in entries if x["path"] in {f"{j}_protocol.json", "tasks.json", "input_provenance.json", "environment.json"}
                      or x["path"] in {str(p.relative_to(self.local)) for p in selected}]
            self.dual(f"_mirror/{j}_MIRROR_COMPLETE.json", canonical({"schema": SCHEMA, "judge": j,
                      "judged": PER_JUDGE, "completion_evidence": "318 verified judged records; original completion file in invocation manifest",
                      "evidence": "mounted_filesystem_readback_only", "artifacts": subset}))
        if all((self.local / f"_mirror/{j}_MIRROR_COMPLETE.json").is_file() for j in ("HB", "LG")):
            for j in ("HB", "LG"):
                read_verified(self.remote / f"_mirror/{j}_MIRROR_COMPLETE.json", (self.local / f"_mirror/{j}_MIRROR_COMPLETE.json").read_bytes())
            core = [x for x in self.audit() if x["path"] in {"tasks.json", "input_provenance.json", "environment.json", "HB_protocol.json", "LG_protocol.json"}
                    or x["path"].startswith("records/")]
            self.dual("_mirror/RUN_MIRROR_COMPLETE.json", canonical({"schema": SCHEMA, "judged": TOTAL_TASKS,
                      "evidence": "mounted_filesystem_readback_only", "artifacts": core}))


class DiagnosticCapture(io.TextIOBase):
    """Retain safe, structured runner diagnostics, not arbitrary library output."""
    def __init__(self):
        self.buffer = ""
        self.characters = 0
        self.diagnostics = []

    def write(self, text):
        self.characters += len(text)
        self.buffer += text
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if len(line) > 8192 or len(self.diagnostics) >= 32:
                continue
            try:
                obj = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(obj, dict):
                continue
            # Deliberately omit free-text exception detail, paths, library logs, headers.
            keep = {}
            if obj.get("status") in {"finished", "stopped"}:
                keep["status"] = obj["status"]
            if obj.get("input_validation") == "pass":
                keep["input_validation"] = "pass"
            if keep:
                for key in ("tasks", "models_executed", "http_status"):
                    if type(obj.get(key)) is int:
                        keep[key] = obj[key]
                for key in ("partial_results_preserved", "target_model_generated"):
                    if type(obj.get(key)) is bool:
                        keep[key] = obj[key]
                value = obj.get("exception_type")
                if isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,80}", value):
                    keep["exception_type"] = value
                context = obj.get("context")
                if isinstance(context, dict):
                    safe = {}
                    stages = {"input_validation", "gpu_package_preflight", "tokenizer_load", "judge_weight_load", "judge_inference", "final_record_validation"}
                    if context.get("stage") in stages:
                        safe["stage"] = context["stage"]
                    if context.get("judge") in {"HB", "LG", None}:
                        safe["judge"] = context.get("judge")
                    if context.get("model_id") in {"meta-llama/Llama-Guard-3-8B", "cais/HarmBench-Llama-2-13b-cls", None}:
                        safe["model_id"] = context.get("model_id")
                    if context.get("revision") in {"7327bd9f6efbbe6101dc6cc4736302b3cbb6e425", "bda705349d1144fa618770bea64d99ce54e3835b", None}:
                        safe["revision"] = context.get("revision")
                    for key in ("required_free_gib", "observed_free_gib"):
                        if type(context.get(key)) in (int, float) and 0 <= context[key] < 10000:
                            safe[key] = context[key]
                    keep["context"] = safe
            if keep:
                self.diagnostics.append(keep)
        if len(self.buffer) > 8192:
            self.buffer = ""
        return len(text)

    def flush(self):
        pass


def execute(runner, mirror, argv, mode, judge, auth_token=None):
    """Testable orchestration: all storage gates precede the original runner."""
    stdout, stderr = DiagnosticCapture(), DiagnosticCapture()
    restore, old_argv = None, sys.argv
    try:
        if auth_token is not None and (judge != "LG" or not isinstance(auth_token, str) or not auth_token):
            raise PersistenceError("explicit nonempty in-memory token is permitted only for LG")
        if auth_token is not None:
            require_official_hf_endpoint()
        mirror.forbidden_bytes = (auth_token.encode(),) if auth_token is not None else ()
        mirror.begin()
        mirror.event("invocation_started", mode=mode, judge=judge)
        restore = mirror.hook(runner)
        sys.argv = [str(runner.__file__), *argv]
        code = 0
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                runner.main(auth_token=auth_token) if auth_token is not None else runner.main()
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
        mirror.event("runner_finished", exit_code=code, diagnostics=stdout.diagnostics + stderr.diagnostics,
                     console_policy="arbitrary library text omitted to avoid credentials",
                     observed_stdout_characters=stdout.characters, observed_stderr_characters=stderr.characters)
        if code:
            return code
        mirror.finish(mode, judge)
        return 0
    except BaseException as exc:
        # Never leak exception payloads (may include remote HTTP headers/tokens).
        diagnostics = stdout.diagnostics + stderr.diagnostics
        if auth_token and auth_token.encode() in canonical(diagnostics):
            diagnostics = []
        error_type = safe_exception_name(exc, auth_token)
        record = canonical({"status": "stopped", "utc": utc(), "exception_type": error_type,
                            "drive_verified": False, "no_further_inference": True,
                            "diagnostics": diagnostics})
        path = mirror.local / f"_mirror/invocations/{mirror.invocation}/STOPPED.json"
        try:
            mirror.assert_clean(record)
            if mirror.local_bound:
                immutable_write(mirror.target(mirror.local, path.relative_to(mirror.local)), record)
            if mirror.remote_bound and not mirror.broken:
                mirror._remote_write(str(path.relative_to(mirror.local)), record)
        except Exception:
            pass
        print(json.dumps({"status": "stopped", "exception_type": error_type,
                          "partial_local_outputs_preserved": True, "drive_verified": False}), file=sys.stderr)
        return 1
    finally:
        sys.argv = old_argv
        if restore:
            restore()
        try:
            mirror.close()
        finally:
            mirror.forbidden_bytes = ()
            auth_token = None


def _main(argv=None, auth_token=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runner", required=True, type=Path)
    p.add_argument("--drive-parent", "--verified-parent", required=True, type=Path)
    p.add_argument("--verified-drive-folder-id", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--source-hb-run", required=True, type=Path)
    p.add_argument("--source-lg-run", required=True, type=Path)
    p.add_argument("runner_args", nargs=argparse.REMAINDER)
    args = p.parse_args(argv)
    runner_args = args.runner_args[1:] if args.runner_args[:1] == ["--"] else args.runner_args
    rp = argparse.ArgumentParser(add_help=False)
    rp.add_argument("--zip", required=True, type=Path)
    rp.add_argument("--out", required=True, type=Path)
    rp.add_argument("--judge", choices=("HB", "LG"), default="HB")
    rp.add_argument("--precision", choices=("fp16",), default="fp16")
    rp.add_argument("--validate-input-only", action="store_true")
    rp.add_argument("--preflight-only", action="store_true")
    original = rp.parse_args(runner_args)
    if original.validate_input_only and original.preflight_only:
        p.error("choose one preflight mode")
    if not re.fullmatch(r"full159_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{12}", args.run_id):
        p.error("run-id must be full159_YYYYMMDDTHHMMSSZ_<12 random hex>")
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,100}", args.verified_drive_folder_id):
        p.error("invalid verified Drive folder ID")
    if (not isinstance(CONFIGURED_DRIVE_FOLDER_ID, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{10,100}", CONFIGURED_DRIVE_FOLDER_ID)
        or args.verified_drive_folder_id != CONFIGURED_DRIVE_FOLDER_ID):
        raise PersistenceError("configured and supplied Drive folder IDs must agree")
    if any(not isinstance(value, str) or re.fullmatch(r"smoke_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{12}", value) is None
           for value in (SOURCE_HB_RUN_ID, SOURCE_LG_RUN_ID)):
        raise PersistenceError("configure exact historical source run IDs before invocation")
    if auth_token is not None and (original.judge != "LG" or not isinstance(auth_token, str) or not auth_token):
        raise PersistenceError("nonempty explicit in-memory token required when supplied")
    if args.run_id == SOURCE_HB_RUN_ID:
        raise PersistenceError("continuation must use a new run ID")
    local = original.out.resolve()
    if local.name != args.run_id:
        raise PersistenceError("scratch basename must match new continuation run ID")
    if not local.is_relative_to(Path("/content")) or local.is_relative_to(Path("/content/drive")):
        raise PersistenceError("local scratch must be /content outside /content/drive")
    mount_guard = DriveMountGuard(args.drive_parent)
    parent = mount_guard.parent
    bound_parts = parent.parts
    if ".shortcut-targets-by-id" not in bound_parts:
        raise PersistenceError("use verified ID-bound shortcut-targets-by-id parent, not ambiguous MyDrive name")
    index = bound_parts.index(".shortcut-targets-by-id")
    if len(bound_parts) <= index + 1 or bound_parts[index + 1] != args.verified_drive_folder_id:
        raise PersistenceError("Drive parent path and verified folder ID disagree")
    if (parent / args.run_id).is_symlink() or original.out.is_symlink():
        raise PersistenceError("symbolic-link run root refused")
    code_dir = args.runner.resolve(strict=True).parent
    code_bytes = {name: (code_dir / name).read_bytes() for name in PINNED}
    if args.runner.name != "colab_smoke.py" or any(sha(code_bytes[n]) != value for n, value in PINNED.items()):
        raise PersistenceError("reviewed code SHA mismatch")
    plan_bytes=(code_dir / "analysis_plan.json").read_bytes()
    if sha(plan_bytes)!=ANALYSIS_PLAN_SHA:
        raise PersistenceError("prospective analysis plan SHA mismatch")
    input_bytes = original.zip.read_bytes()
    if len(input_bytes) != 2264723 or sha(input_bytes) != INPUT_SHA:
        raise PersistenceError("input archive size/SHA mismatch")
    if args.source_hb_run.is_symlink() or args.source_hb_run.resolve() != parent / SOURCE_HB_RUN_ID:
        raise PersistenceError("source HB run must be the exact previously verified sibling")
    if args.source_lg_run.is_symlink() or args.source_lg_run.resolve() != parent / SOURCE_LG_RUN_ID:
        raise PersistenceError("source LG run must be exact previously verified sibling")
    identity = {"schema": SCHEMA, "run_id": args.run_id, "input_sha256": INPUT_SHA, "runner_code": PINNED,
                "wrapper_sha256": sha(Path(__file__).read_bytes()), "precision": original.precision,
                "verified_drive_folder_id": args.verified_drive_folder_id,
                "authentication_policy": "explicit_in_memory_LG_argument_only_no_login_or_token_save",
                "scope": "all159_standard_IDs_x_FP16_SP70_x_HB_LG_636_new_judgments",
                "analysis_plan_sha256":ANALYSIS_PLAN_SHA, "analysis_plan_status":"prospective locally frozen exploratory plan; not preregistered",
                "expected_ids":159, "expected_per_judge":PER_JUDGE, "expected_total_tasks":TOTAL_TASKS,
                "folder_mapping_evidence": "operator verified; FUSE cannot prove Drive folder ID",
                "durability_evidence": "mounted filesystem write/read/hash only, backend verification outstanding"}
    mirror = Mirror(local, parent / args.run_id, identity,
                    storage_guard=mount_guard)
    # Bundle exact code/config/input hashes before imports; no credentials or environment dump.
    spec = importlib.util.spec_from_file_location("reviewed_smoke_runner", args.runner)
    runner = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(code_dir))
    spec.loader.exec_module(runner)
    tasks, provenance = runner.inputs(original.zip)
    mount_guard()
    lineage = validate_hb_lineage(args.source_hb_run, runner, tasks, provenance)
    mount_guard()
    lg_lineage = validate_lg_lineage(args.source_lg_run, runner, tasks, args.source_hb_run)
    mount_guard()
    identity["source_hb_lineage"] = lineage
    identity["source_lg_lineage"] = lg_lineage
    # begin() must own the new empty roots before inventory is committed.
    old_begin = mirror.begin
    def begin_with_inventory():
        old_begin()
        if original.judge == "LG":
            validate_full_hb_stage(mirror, runner, tasks)
        for name, data in code_bytes.items():
            mirror.dual("_mirror/code/" + name, data)
        mirror.dual("_mirror/code/drive_wrapper.py", Path(__file__).read_bytes())
        mirror.dual("_mirror/inputs/verified_inputs.zip", input_bytes)
        mirror.dual("_mirror/analysis/analysis_plan.json", plan_bytes)
        mirror.dual("_mirror/config.json", canonical(identity))
        mirror.dual("_mirror/lineage/source_hb.json", canonical(lineage))
        mirror.dual("_mirror/lineage/source_lg.json", canonical(lg_lineage))
        mirror.dual(f"_mirror/invocations/{mirror.invocation}/config.json", canonical({
            "input_archive": str(original.zip.resolve()), "input_archive_sha256": INPUT_SHA,
            "local_scratch": str(local), "verified_parent": str(parent), "runner": str(args.runner.resolve()),
            "observed_mount_identity": mount_guard.identity,
            "judge": original.judge, "precision": original.precision,
            "auth_mode": "ephemeral_explicit_read_token" if auth_token is not None else "anonymous",
            "validate_input_only": original.validate_input_only, "preflight_only": original.preflight_only}))
    mirror.begin = begin_with_inventory
    mode = "input_validation" if original.validate_input_only else "gpu_preflight" if original.preflight_only else "inference"
    code = execute(runner, mirror, runner_args, mode, original.judge, auth_token=auth_token)
    print(json.dumps({"exit_code": code, "run_id": args.run_id, "evidence": "mounted_filesystem_readback_only"}))
    return code


def main(argv=None, *, auth_token=None):
    """Public in-process entry; never expose exception payloads or a traceback."""
    try:
        return _main(argv, auth_token=auth_token)
    except BaseException as exc:
        print(json.dumps({"status": "stopped", "exception_type": safe_exception_name(exc,auth_token)}), file=sys.stderr)
        return 1
    finally:
        auth_token = None


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "stopped_before_or_after_execution", "exception_type": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(1)
