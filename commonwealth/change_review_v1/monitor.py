"""Check private recorder storage and a retained backup against operator thresholds."""
import hashlib
import json
from pathlib import Path
import shutil
import time

from . import store


def _digest(path):
    with Path(path).open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def check(database, snapshot, receipt, max_age, min_free):
    if max_age <= 0 or min_free <= 0:
        raise ValueError("thresholds must be positive")
    if Path(database).samefile(snapshot):
        raise ValueError("provide a separate backup")
    with Path(receipt).open("rb") as source:
        raw = source.read(8193)
    if len(raw) > 8192:
        raise ValueError("invalid backup receipt")
    issued = json.loads(raw)
    if (not isinstance(issued, dict) or issued.get("ok") is not True or issued.get("operation") != "backup"
            or type(issued.get("completed_at")) is not int):
        raise ValueError("invalid backup receipt")
    live = store.verify(database)
    copy = store.verify(snapshot)
    age = int(time.time()) - issued["completed_at"]
    free = shutil.disk_usage(Path(database).parent).free
    checks = {
        "snapshot_digest": _digest(snapshot) == issued.get("sha256"),
        "snapshot_receipt": all(copy[k] == issued.get(k) for k in
                                ("schema", "register_id", "records", "decisions"))
                            and Path(snapshot).stat().st_size == issued.get("bytes"),
        "same_register": live["register_id"] == copy["register_id"],
        "counts_at_least_snapshot": (live["records"] >= copy["records"]
                                     and live["decisions"] >= copy["decisions"]),
        "snapshot_within_age": 0 <= age <= max_age,
        "disk_headroom": free >= min_free,
        "proposal_slots_available": live["records"] < store.MAX_RECORDS,
    }
    return {
        "ok": all(checks.values()), "checks": checks, "register_id": live["register_id"],
        "records": live["records"], "decisions": live["decisions"],
        "pending_reviews": live["records"] - live["decisions"],
        "proposal_slots_remaining": store.MAX_RECORDS - live["records"],
        "snapshot_age_seconds": age, "max_backup_age_seconds": max_age,
        "disk_free_bytes": free, "minimum_free_bytes": min_free,
    }
