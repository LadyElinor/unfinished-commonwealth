"""Opt-in Linux cross-UID demonstration. Temporary files only; no account setup."""

import argparse
import concurrent.futures
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
UIDS = {"host": 61001, "p1": 61002, "p2": 61003}
VERSION = "uid-isolation-1.0.0"


def prerequisites():
    if sys.platform != "linux":
        return "requires Linux"
    if os.geteuid() != 0:
        return "requires an explicitly authorized privileged supervisor"
    fields = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
    required = sum(1 << bit for bit in (0, 1, 3, 5, 6, 7))  # CHOWN, DAC_OVERRIDE, FOWNER, KILL, SETGID, SETUID
    if int(fields["CapEff"].strip(), 16) & required != required:
        return "supervisor lacks required CHOWN/DAC_OVERRIDE/FOWNER/KILL/SETGID/SETUID capabilities"
    return None


def valid_identity(identity, uid):
    return (identity.get("Uid", "").split() == [str(uid)] * 4
            and identity.get("Gid", "").split() == [str(uid)] * 4
            and not identity.get("Groups", "").split()
            and int(identity.get("CapEff", "1"), 16) == 0
            and identity.get("NoNewPrivs") == "1")


class Demonstration:
    def __init__(self, directory):
        self.root = Path(directory)
        self.records = []
        self.process = None
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.host = self.root / "host"
        self.client = self.root / "client"
        self.homes = {name: self.root / name for name in UIDS}

    def require(self, condition, reason):
        if not condition:
            raise RuntimeError(reason)

    def setup(self):
        os.chmod(self.root, 0o755)
        for name, home in self.homes.items():
            home.mkdir(mode=0o700)
            os.chown(home, UIDS[name], UIDS[name])
        for directory, owner in ((self.client, 0), (self.host / "code", UIDS["host"])):
            directory.mkdir(mode=0o755)
            shutil.copytree(ROOT / "commonwealth", directory / "commonwealth",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            shutil.copyfile(ROOT / "scripts/isolation/worker.py", directory / "worker.py")
            for item in [directory, *directory.rglob("*")]:
                os.chown(item, owner, owner)
                os.chmod(item, 0o555 if item.is_dir() else 0o444)

    def options(self, role, private=False):
        code = self.host / "code" if private else self.client
        return {"args": [sys.executable, "-I", str(code / "worker.py")],
                "cwd": self.homes[role], "user": UIDS[role], "group": UIDS[role],
                "extra_groups": [], "close_fds": True, "start_new_session": True,
                "env": {"PATH": "/usr/bin:/bin", "HOME": str(self.homes[role]), "PYTHONIOENCODING": "utf-8"},
                "text": True}

    def read_host(self):
        line = self.pool.submit(self.process.stdout.readline).result(timeout=15)
        self.require(bool(line), "host stopped without a response")
        return json.loads(line)

    def start_host(self, drop_reply=False):
        options = self.options("host", private=True)
        self.process = subprocess.Popen(**options, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        config = {"op": "host", "home": str(self.host), "drop_reply": drop_reply}
        self.process.stdin.write(json.dumps(config) + "\n")
        self.process.stdin.flush()
        ready = self.read_host()
        self.records.append({"label": "host-start", "argv": options["args"], "input": config, "response": ready})
        self.require(valid_identity(ready["identity"], UIDS["host"]), "host identity gate failed")
        self.ready = ready
        return ready

    def stop_host(self):
        if self.process is not None:
            process, self.process = self.process, None
            try:
                process.stdin.write('{"op":"stop"}\n')
                process.stdin.flush()
                _, error = process.communicate(timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
                _, error = process.communicate(timeout=5)
            self.records.append({"label": "host-stop", "exit_code": process.returncode, "stderr": error[:4000]})
            self.require(process.returncode == 0, "host did not stop cleanly")

    def host_call(self, **config):
        self.process.stdin.write(json.dumps(config) + "\n")
        self.process.stdin.flush()
        result = self.read_host()
        self.records.append({"label": "host-control", "input": config, "response": result})
        return result

    def run(self, role, label, **config):
        options = self.options(role)
        started = time.perf_counter()
        child = subprocess.run(**options, input=json.dumps(config) + "\n", capture_output=True, timeout=15)
        elapsed = (time.perf_counter() - started) * 1000
        record = {"label": label, "role": role, "argv": options["args"], "input": config,
                  "exit_code": child.returncode, "elapsed_ms": round(elapsed, 3), "stderr": child.stderr[:4000]}
        self.records.append(record)
        self.require(child.returncode == 0, f"{label}: probe execution failed")
        result = json.loads(child.stdout)
        record["response"] = result
        self.require(valid_identity(result["identity"], UIDS[role]), f"{label}: identity gate failed")
        return result

    def deliver(self, name, role, destination=None):
        target = self.homes[role] / (destination or name + ".credential")
        with (self.host / (name + ".credential")).open("rb") as source, target.open("xb") as out:
            shutil.copyfileobj(source, out)
        os.chown(target, UIDS[role], UIDS[role])
        os.chmod(target, 0o600)
        return str(target)

    def check(self):
        self.setup()
        self.start_host(drop_reply=True)
        p1 = self.deliver("p1", "p1")
        p2 = self.deliver("p2", "p2")
        url = self.ready["url"]
        packet = str(self.homes["p1"] / "request.json")
        common = {"url": url, "credential": p1}
        initial = self.host_call(op="audit")
        normal = self.run("p1", "submit", op="roundtrip", request_id="normal", request_file=packet, **common)
        self.require(normal["status"] == 200, "allowed submission blocked")
        for operation, fields in (("repeat", {"request_file": packet}), ("receipt", {"request_id": "normal"})):
            repeated = self.run("p1", operation, op=operation, **fields, **common)
            self.require(repeated["status"] == 200 and repeated["response"] == normal["response"], "retry or receipt differs")
        audit = self.host_call(op="audit")
        self.require(audit["proposal_count"] == 1 and sum(c["used"] for c in audit["capabilities"]) == 1, "duplicate effect or attempt")
        for role, label, operation, path in (
            ("p1", "db-read", "read", self.host / "workshop.sqlite"),
            ("p1", "db-write", "write", self.host / "workshop.sqlite"),
            ("p1", "host-credential", "read", self.host / "p1.credential"),
            ("p1", "other-credential", "read", Path(p2)),
            ("p1", "host-source-read", "read", self.host / "code/worker.py"),
            ("p1", "host-source-write", "write", self.host / "code/worker.py"),
            ("p1", "host-directory-write", "create", self.host / "forbidden"),
            ("p1", "client-code-write", "write", self.client / "worker.py"),
            ("host", "host-reading-delivered-copy", "read", Path(p1)),
        ):
            self.require(operation == "create" or path.exists(), "negative probe path missing")
            probe = self.run(role, label, op=operation, path=str(path))
            self.require(probe.get("access") is False and probe.get("errno") in (1, 13), f"{label}: not a permission denial")
        for action in ("approve", "execute"):
            probe = self.run("p1", "keeper-" + action, op="keeper", action=action,
                             database=str(self.host / "workshop.sqlite"), proposal=normal["response"]["proposal_id"])
            self.require(probe["exit_code"] == 2 and "unable to open database file" in probe["stderr"], "keeper refusal not caused by DB access")
        signal = self.run("p1", "signal-host", op="signal", pid=self.ready["pid"])
        self.require(signal.get("access") is False and signal.get("errno") == 1, "host signal permission granted")
        malformed = self.run("p1", "malformed-socket", op="malformed", url=url)
        self.require(malformed["sent"] and (not malformed["response"] or "HTTP_REFUSED" in malformed["response"]), "malformed traffic not refused")
        after = self.host_call(op="audit")
        self.require(after["head"] == audit["head"] and after["capabilities"] == audit["capabilities"], "negative probes changed state or quota")
        # The administrator already read the host file to deliver it. Deliberately
        # copying a second bearer demonstrates the exact limit without printing it.
        stolen = self.deliver("p2", "p1", "deliberately-leaked.credential")
        theft = self.run("p1", "leaked-bearer-control", op="task", url=url, credential=stolen)
        self.require(theft["status"] == 200, "stolen-bearer control changed semantics")
        other = self.run("p2", "other-holder-receipt", op="receipt", url=url, credential=p2, request_id="normal")
        self.require(other["status"] == 404, "receipt escaped capability scope")
        lost_file = str(self.homes["p1"] / "lost.json")
        lost = self.run("p1", "lost-response", op="roundtrip", request_id="lost-reply", request_file=lost_file, **common)
        self.require(lost["status"] == 0 and lost["response"]["disposition"] == "UNKNOWN", "lost response not unknown")
        self.stop_host()
        self.start_host()
        common["url"] = self.ready["url"]
        recovered = self.run("p1", "recovery-receipt", op="receipt", request_id="lost-reply", **common)
        retry = self.run("p1", "recovery-repeat", op="repeat", request_file=lost_file, **common)
        self.require(recovered["status"] == 200 and recovered["response"] == retry["response"], "recovery failed")
        audit = self.host_call(op="audit")
        self.require(audit["proposal_count"] == 2 and sum(c["used"] for c in audit["capabilities"]) == 2, "recovery duplicated effect or attempts")
        self.host_call(op="revoke")
        for op, extra in (("task", {}), ("repeat", {"request_file": packet}), ("receipt", {"request_id": "normal"})):
            self.require(self.run("p1", "revoked-" + op, op=op, **extra, **common)["status"] == 401, "revocation failed")
        self.require(self.host_call(op="receipt", request_id="normal")[0] == 200, "host inspection failed")
        expires = self.host_call(op="issue-expiring")["expires"]
        expiring = self.deliver("expiring", "p1")
        expiry_common = {"url": self.ready["url"], "credential": expiring}
        self.require(self.run("p1", "before-expiry", op="task", **expiry_common)["status"] == 200, "TTL control already expired")
        time.sleep(max(0, expires - time.time()) + 0.1)
        for op, extra in (("task", {}), ("repeat", {"request_file": packet}), ("receipt", {"request_id": "normal"})):
            self.require(self.run("p1", "expired-" + op, op=op, **extra, **expiry_common)["status"] == 401, "expiry failed")
        final = self.host_call(op="audit")
        # Comparable transport measurement in the host UID, using a newly copied
        # request file and no score of decision quality. This adds one proposal.
        baseline = self.run("host", "same-uid-transport-control", op="roundtrip", url=self.ready["url"],
                            credential=str(self.host / "p2.credential"), request_id="same-uid",
                            request_file=str(self.host / "same-uid.json"))
        self.require(baseline["status"] == 200, "same-UID control failed")
        for action in ("approve", "execute"):
            keeper = self.run("host", "host-keeper-" + action, op="keeper", action=action,
                              database=str(self.host / "workshop.sqlite"), proposal=normal["response"]["proposal_id"])
            self.require(keeper["exit_code"] == 0, "host keeper positive control failed")
        self.host_call(op="audit")
        self.require(Path(p1).read_bytes() == (self.host / "p1.credential").read_bytes(), "supervisor-read control failed")
        return {"initial_head": initial["head"], "participant_proposals": final["proposal_count"],
                "participant_attempts": sum(c["used"] for c in final["capabilities"]),
                "task_submit_ms_separate_uid": normal["transport_ms"], "task_submit_ms_same_uid": baseline["transport_ms"],
                "recovery_transport_ms": recovered["transport_ms"] + retry["transport_ms"],
                "recovery_network_calls": 2, "supervisor_can_read_all_copies": True,
                "leaked_bearer_works": True, "network_egress_restricted": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="explicitly opt into temporary privileged UID switching")
    parser.add_argument("output", help="new report path; never overwrite")
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve report before launching any child; never replace an existing file.
    with output.open("x", encoding="utf-8") as handle:
        reason = prerequisites() if args.run else "explicit --run opt-in required"
        report = {"version": VERSION, "status": "BLOCKED", "reason": reason,
                  "environment": {"system": platform.system(), "kernel": platform.release(),
                                  "python": platform.python_version(), "uids": UIDS},
                  "model_calls": 0, "external_actions": 0, "scope": "LOCAL_RESEARCH_ONLY"}
        result_code = 77
        if reason is None:
            with tempfile.TemporaryDirectory(prefix="commonwealth-uid-") as temporary:
                demo = Demonstration(temporary)
                try:
                    report["measurements"] = demo.check()
                    report["status"] = "PASSED"
                    result_code = 0
                except Exception as exc:
                    report.update(status="FAILED", reason=f"{type(exc).__name__}: {exc}")
                    result_code = 1
                finally:
                    try:
                        demo.stop_host()
                    except Exception as exc:
                        report.update(status="FAILED", reason=f"host cleanup: {type(exc).__name__}")
                        result_code = 1
                    demo.pool.shutdown(wait=True)
                    report["records"] = demo.records
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(json.dumps({"status": report["status"], "reason": report["reason"], "report": str(output)}))
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
