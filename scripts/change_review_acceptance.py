"""Exercise the installed change-review service with real local UIDs on a disposable Linux host."""
import argparse
import errno
import importlib.metadata
import json
import math
import os
import platform
from pathlib import Path
import signal
import statistics
import subprocess
import sys
import sysconfig
import tempfile
import time

# No accounts are created. These IDs must be free on the disposable host.
SERVICE, AUTHOR, REVIEWER, OUTSIDER = 61231, 61232, 61233, 61234
SOCKET_GROUP = 61235
CANARY = "discardable-acceptance-evidence-3d901a"


class Blocked(Exception):
    pass


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def prerequisites():
    if sys.platform != "linux" or os.geteuid() != 0:
        raise Blocked("requires an explicitly privileged supervisor on disposable Linux")
    import grp
    import pwd
    for uid in (SERVICE, AUTHOR, REVIEWER, OUTSIDER):
        try:
            pwd.getpwuid(uid)
        except KeyError:
            continue
        raise Blocked("a reserved test UID already belongs to an account")
    try:
        grp.getgrgid(SOCKET_GROUP)
    except KeyError:
        pass
    else:
        raise Blocked("the reserved socket GID already belongs to a group")
    status = Path("/proc/self/status").read_text().splitlines()
    caps = int(next(line.split()[1] for line in status if line.startswith("CapEff:")), 16)
    needed = sum(1 << bit for bit in (0, 1, 3, 5, 6, 7))
    if caps & needed != needed:
        raise Blocked("supervisor lacks the required file, signal, or identity capabilities")


class Drill:
    def __init__(self, root, cli, report):
        self.cli = str(cli)
        self.root = root
        self.report = report
        self.active = None
        self.database = root / "state" / "reviews.sqlite"
        self.socket = root / "run" / "service.sock"
        self.log = root / "supervisor.log"
        root.chmod(0o711)
        for name, mode in (("run", 0o750), ("state", 0o700), ("backups", 0o700)):
            path = root / name
            path.mkdir()
            os.chown(path, SERVICE, SOCKET_GROUP)
            path.chmod(mode)

    def options(self, uid):
        return dict(cwd=self.root, user=uid, group=SOCKET_GROUP, extra_groups=[], umask=0o077,
                    env={"PATH": "/usr/bin:/bin", "PYTHONNOUSERSITE": "1", "LC_ALL": "C.UTF-8"})

    def cli_run(self, uid, args, payload=None):
        return subprocess.run([self.cli, *map(str, args)], **self.options(uid), timeout=10,
                              input=json.dumps(payload) if payload is not None else "",
                              capture_output=True, text=True)

    def operate(self, *args):
        result = self.cli_run(SERVICE, args)
        require(result.returncode == 0, f"installed {args[0]} failed (exit {result.returncode})")
        return json.loads(result.stdout)

    def call(self, uid, payload, denied=None):
        result = self.cli_run(uid, ["request", "--socket", self.socket], payload)
        response = json.loads(result.stdout)
        if denied:
            require(result.returncode == 2 and response.get("ok") is False and
                    response.get("error") in denied, f"unexpected rejection for {payload['op']}")
            return None
        require(result.returncode == 0 and response.get("ok") is True, f"{payload['op']} failed")
        return response["result"]

    def start(self, db, author=AUTHOR, reviewer=REVIEWER):
        require(self.active is None, "source must be stopped before starting another daemon")
        args = [self.cli, "serve", "--database", str(db), "--socket", str(self.socket),
                "--submitter-uid", str(author), "--reviewer-uid", str(reviewer)]
        start = time.monotonic()
        with self.log.open("ab") as logfile:
            self.active = subprocess.Popen(args, **self.options(SERVICE), stdin=subprocess.DEVNULL,
                                           stdout=logfile, stderr=logfile)
        while time.monotonic() - start < 10:
            require(self.active.poll() is None, "daemon exited during startup")
            result = self.cli_run(author, ["ready", "--socket", self.socket])
            if result.returncode == 0:
                ready = json.loads(result.stdout)["result"]
                require(ready.get("ready") is True and isinstance(ready.get("register_id"), str),
                        "readiness did not identify the register")
                self.report["start_to_ready_ms"].append(round(1000 * (time.monotonic() - start), 2))
                return ready["register_id"]
            time.sleep(0.05)
        raise RuntimeError("readiness deadline exceeded")

    def stop(self, abrupt=False):
        if self.active is None:
            return
        try:
            self.active.send_signal(signal.SIGKILL if abrupt else signal.SIGTERM)
            code = self.active.wait(timeout=10)
            require(code == (-signal.SIGKILL if abrupt else 0), "unexpected service exit status")
        finally:
            if self.active.poll() is None:
                self.active.kill()
                self.active.wait(timeout=5)
            self.active = None

    def storage_drill(self):
        """Exhaust only this newly mounted 2 MiB filesystem. Never fill its parent."""
        mount = self.root / "limited"
        mount.mkdir(mode=0o700)
        opts = f"size=2m,uid={SERVICE},gid={SOCKET_GROUP},mode=0700,nodev,nosuid,noexec"
        attempt = subprocess.run(["/usr/bin/mount", "-t", "tmpfs", "-o", opts, "tmpfs", str(mount)],
                                 capture_output=True, timeout=10)
        if attempt.returncode:
            raise Blocked("a dedicated size-limited tmpfs could not be mounted for the storage drill")
        try:
            mounts = [line.split(" - ", 1) for line in Path("/proc/self/mountinfo").read_text().splitlines()]
            require(any(fields.split()[4] == str(mount) and fs.split()[0] == "tmpfs" for fields, fs in mounts),
                    "separate tmpfs mount unconfirmed")
            info = os.statvfs(mount)
            capacity = info.f_blocks * info.f_frsize
            require(mount.stat().st_dev != self.root.stat().st_dev and 0 < capacity <= 2 * 1024**2,
                    "storage drill requires a distinct bounded volume")
            database = mount / "small.sqlite"
            self.operate("init", database)
            register_id = self.start(database)
            initial = {"op": "submit", "register_id": register_id, "id": "before-full", "title": "Storage rehearsal",
                       "proposal": "Retain the first proposal.", "evidence": ["Synthetic storage rehearsal"]}
            retained = self.call(AUTHOR, initial)["record"]
            retry = {**initial, "id": "retry-full"}
            filler = mount / "drill-owned-filler"
            try:
                with filler.open("xb", buffering=0) as output:
                    # Even if storage accounting changes, at most (capacity + one page)
                    # can be attempted through this new file on the confirmed mount.
                    page = bytes(info.f_frsize)
                    for _ in range(info.f_blocks + 1):
                        try:
                            output.write(page)
                        except OSError as exc:
                            if exc.errno != errno.ENOSPC:
                                raise
                            break
                require(os.statvfs(mount).f_bavail == 0, "private volume still has writable blocks")
                self.call(AUTHOR, retry, denied={"storage_full"})
            finally:
                filler.unlink(missing_ok=True)
            self.call(AUTHOR, {"op": "get", "id": retry["id"]}, denied={"not_found"})
            saved = self.call(AUTHOR, retry)["record"]
            self.stop()
            self.start(database)
            require(self.call(AUTHOR, initial)["record"] == retained and self.call(AUTHOR, retry)["record"] == saved,
                    "committed record or retried request changed on restart")
            self.stop()
            require(self.operate("verify", database)["records"] == 2, "storage recovery row count differs")
            self.report["storage_drill"] = {"filesystem": "tmpfs", "volume_bytes": capacity,
                                            "observed_error": "storage_full", "partial_row_absent": True,
                                            "prior_and_retried_records_replayed": 2}
        finally:
            if self.active is not None:
                if self.active.poll() is None:
                    self.active.kill()
                    self.active.wait(timeout=5)
                self.active = None
            unmount = subprocess.run(["/usr/bin/umount", str(mount)], capture_output=True, timeout=10)
            require(unmount.returncode == 0, "failed to unmount the disposable storage drill volume")

    def exercise(self):
        created = self.operate("init", self.database)
        register_id = self.start(self.database)
        require(register_id == created["register_id"], "new register differs from serving instance")
        # Probe ordinary filesystem access using the same unprivileged peer identity.
        check = subprocess.run([sys.executable, "-I", "-c",
                                "import os,sys; sys.exit(int(os.access(sys.argv[1], os.R_OK)))",
                                str(self.database)], **self.options(AUTHOR), timeout=5)
        require(check.returncode == 0, "participant can read service storage")
        sample = {"op": "submit", "register_id": register_id, "id": "change-alpha", "title": "Review a proposed change",
                  "proposal": "Record this decision locally.", "evidence": [CANARY]}
        rec = self.call(AUTHOR, sample)["record"]
        require(rec["owner_uid"] == AUTHOR and rec["decision"] is None, "peer identity or initial state lost")
        self.call(OUTSIDER, {"op": "ready"}, denied={"permission_denied"})
        decision = {"op": "decide", "register_id": register_id, "id": sample["id"], "owner_uid": AUTHOR,
                    "submission_digest": rec["submission_digest"],
                    "decision": "approve", "rationale": "Evidence accepted for this scoped proposal."}
        self.call(AUTHOR, decision, denied={"permission_denied", "forbidden"})
        queue = self.call(REVIEWER, {"op": "list", "after": 0, "limit": 5})
        require([item["id"] for item in queue["items"]] == [sample["id"]], "review queue wrong")
        self.stop(abrupt=True)
        self.start(self.database)
        require(self.call(AUTHOR, sample)["record"] == rec, "committed proposal changed on replay")
        self.call(AUTHOR, {**sample, "title": "Different change"}, denied={"id_conflict"})
        decided = self.call(REVIEWER, decision)["record"]
        require(decided["decision"]["reviewer_uid"] == REVIEWER and
                decided["decision"]["decision"] == "approve", "decision lost its reviewer or disposition")
        require(self.call(REVIEWER, decision)["record"] == decided, "decision retry changed the receipt")

        latencies = []
        pending = None
        for number in range(16):
            before = time.monotonic()
            result = self.call(AUTHOR, {**sample, "id": f"batch-{number:02d}"})
            if number == 0:
                pending = result["record"]
            latencies.append((time.monotonic() - before) * 1000)
        self.report["sequential_submission_cli_ms"] = {
            "count": len(latencies), "median": round(statistics.median(latencies), 2),
            "p95_nearest_rank": round(sorted(latencies)[math.ceil(0.95 * len(latencies)) - 1], 2),
            "max": round(max(latencies), 2),
        }
        self.stop()
        snapshot = self.root / "backups" / "snapshot.sqlite"
        backup = self.operate("backup", self.database, snapshot)
        require(backup.get("records") == 17 and backup.get("decisions") == 1,
                "snapshot lost submitted or decided records")
        self.start(self.database)
        self.call(AUTHOR, {**sample, "id": "after-snapshot"})
        self.stop()

        restored = self.root / "state" / "restored.sqlite"
        before = time.monotonic()
        restoration = self.operate("restore", snapshot, restored, "--expected-sha256", backup["sha256"])
        require(restoration.get("sha256") == backup["sha256"], "restored digest changed")
        require(self.operate("verify", restored).get("records") == 17, "wrong restored record count")
        self.report["recovery_point"] = {"records": backup["records"], "decisions": backup["decisions"],
                                         "later_records_absent": 1, "snapshot_digest_matched": True}
        require(self.start(restored) == register_id, "register identity changed on restore")
        self.report["restore_verify_to_ready_ms"] = round((time.monotonic() - before) * 1000, 2)
        require(self.call(AUTHOR, {"op": "get", "id": sample["id"]})["record"] == decided,
                "receipt changed across restore")
        self.call(AUTHOR, {"op": "get", "id": "after-snapshot"}, denied={"not_found"})
        self.stop()

        # Simulate a changed duty assignment. Access to the review queue must not confer
        # the right to decide a submission made under the same OS identity in the past.
        self.start(restored, author=REVIEWER, reviewer=AUTHOR)
        self.call(AUTHOR, {**decision, "id": pending["id"], "submission_digest": pending["submission_digest"]},
                  denied={"self_review"})
        self.stop()
        require(CANARY.encode() not in self.log.read_bytes(), "daemon disclosed synthetic evidence in logs")
        self.report["observations"] = ["peer UID recorded", "private storage unreadable to submitting UID",
                                       "unlisted peer and author decision refused",
                                       "acknowledged proposal recovered after SIGKILL",
                                       "changed replay refused", "decision retry stable",
                                       "pre-snapshot receipt recovered", "post-snapshot proposal absent",
                                       "same UID refused after role change", "evidence marker absent from daemon log"]
        self.report["process_uids"] = {"service": SERVICE, "submitter": AUTHOR, "reviewer": REVIEWER,
                                       "unlisted": OUTSIDER}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", required=True, type=Path, metavar="NEW_REPORT")
    output = ap.parse_args().run
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {"profile": "change-review-installed-linux-v1", "start_to_ready_ms": [],
              "scope": "Disposable host, one machine, sequential CLI workload, process signals, local storage"}
    with output.open("x", encoding="utf-8") as handle:
        try:
            prerequisites()
            cli = Path(sysconfig.get_path("scripts")) / "commonwealth-change-review"
            require(cli.is_file(), "entry point absent from this Python installation")
            report["distribution_version"] = importlib.metadata.version("unfinished-commonwealth")
            report["kernel"] = platform.release()
            report["python"] = platform.python_version()
            with tempfile.TemporaryDirectory(prefix="cw-review-", dir="/tmp") as temporary:
                drill = Drill(Path(temporary), cli, report)
                try:
                    drill.exercise()
                    drill.storage_drill()
                finally:
                    if drill.active is not None and drill.active.poll() is None:
                        drill.active.kill()
                        drill.active.wait(timeout=5)
            report["status"] = "PASS"
            code = 0
        except Blocked as exc:
            report.update(status="BLOCKED", reason=str(exc))
            code = 2
        except (OSError, ValueError, RuntimeError, LookupError, subprocess.SubprocessError) as exc:
            # A child command contains no credentials. Its stdout/stderr may include
            # user input, so never copy child output into the acceptance receipt.
            if isinstance(exc, RuntimeError):
                reason = str(exc)
            else:
                reason = type(exc).__name__
            report.update(status="FAIL", reason=reason)
            code = 1
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"status": report["status"], "report": str(output)}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
