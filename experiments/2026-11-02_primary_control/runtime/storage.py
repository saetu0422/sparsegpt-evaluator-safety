"""Derived pinned storage guards; no cloud calls or model imports on import."""
import os,re,uuid,json,hashlib,importlib
from pathlib import Path
class PersistenceError(RuntimeError): pass
def sha(data): return hashlib.sha256(data).hexdigest()
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


def drive_mount_state(parent, mount):
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


def mounted_drive_parent(parent, mount):
    return drive_mount_state(parent, mount)[0]


class DriveMountGuard:
    def __init__(self, parent, mount):
        self.requested = parent
        self.mount = mount
        self.parent, self.identity = drive_mount_state(parent, self.mount)

    def __call__(self):
        parent, identity = drive_mount_state(self.requested, self.mount)
        if parent != self.parent or identity != self.identity:
            raise PersistenceError("Drive mount identity or resolved parent changed during invocation")
        return parent


