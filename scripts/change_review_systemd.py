"""Activate the installed Change Review service unit on a disposable GitHub Ubuntu VM."""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time


PREFIX = Path("/opt/commonwealth")
UNIT = "commonwealth-change-review.service"
UNIT_FILE = Path("/etc/systemd/system") / UNIT
CONFIG = Path("/etc/commonwealth")
STATE = Path("/var/lib/commonwealth-change-review")
RUNTIME = Path("/run/commonwealth-change-review")
SOCKET = RUNTIME / "service.sock"
DB = STATE / "reviews.sqlite"
SERVICE = "commonwealth-review"
SUBMITTER = "cw-smoke-submit"
REVIEWER = "cw-smoke-review"
CLI = str(PREFIX / "bin/commonwealth-change-review")


class Blocked(Exception):
    """The disposable Linux/systemd prerequisites are unavailable."""


def run(*argv, stdin=None, check=True, limit=45):
    process = subprocess.run(argv, input=stdin, capture_output=True, text=True, timeout=limit)
    if check and process.returncode:
        # Commands may handle private request material. Retain only the operation and status.
        raise RuntimeError(f"{Path(argv[0]).name} failed with exit {process.returncode}")
    return process


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def preflight():
    if (os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"
            or os.environ.get("RUNNER_OS") != "Linux" or not os.environ.get("GITHUB_RUN_ID")):
        raise Blocked("requires the explicitly selected GitHub-hosted Linux job")
    if os.geteuid() != 0 or Path("/proc/1/comm").read_text().strip() != "systemd":
        raise Blocked("requires root supervisor and a running systemd as PID 1")
    release = {key: value.strip('"') for key, value in
               (line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)}
    if (release.get("ID"), release.get("VERSION_ID")) != ("ubuntu", "24.04"):
        raise Blocked("requires a disposable Ubuntu 24.04 runner")
    for path in (PREFIX, UNIT_FILE, CONFIG, STATE, RUNTIME):
        if os.path.lexists(path):
            raise Blocked(f"reserved location is already in use: {path}")
    load = run("systemctl", "show", "--property", "LoadState", "--value", UNIT, check=False)
    absent = load.stdout.strip() == "not-found" and load.returncode in (0, 4)
    if not absent and not (load.returncode == 4 and not load.stdout.strip()):
        raise Blocked("the unit name is already in use")
    for database, names in (("passwd", (SERVICE, SUBMITTER, REVIEWER)), ("group", (SERVICE,))):
        for name in names:
            if run("getent", database, name, check=False).returncode != 2:
                raise Blocked(f"reserved {database} name is unavailable: {name}")


def show(property_name):
    return run("systemctl", "show", "--property", property_name, "--value", UNIT).stdout.strip()


def install(cleanup, wheel):
    import shutil
    PREFIX.mkdir(mode=0o755)
    cleanup.callback(shutil.rmtree, PREFIX)
    run(sys.executable, "-I", "-m", "venv", "--without-pip", str(PREFIX), limit=90)
    python = str(PREFIX / "bin/python")
    run(sys.executable, "-I", "-m", "pip", "--python", python, "install", "--no-index", "--no-deps",
        "--disable-pip-version-check", str(wheel), limit=90)
    location = run(python, "-I", "-c", "from importlib.resources import files; "
                   "print(files('commonwealth.change_review_v1').joinpath('deploy'))").stdout.strip()
    unit_bytes = (Path(location) / UNIT).read_bytes()
    with UNIT_FILE.open("xb") as target:
        cleanup.callback(UNIT_FILE.unlink)
        target.write(unit_bytes)
    UNIT_FILE.chmod(0o644)
    return hashlib.sha256(unit_bytes).hexdigest()


def make_account(cleanup, name):
    run("useradd", "--system", "--no-create-home", "--no-user-group", "--gid", SERVICE,
        "--home-dir", "/nonexistent", "--shell", "/usr/sbin/nologin", name)
    cleanup.callback(run, "userdel", name)
    return int(run("id", "-u", name).stdout)


def client(account, op, payload=None, check=True):
    command = ["runuser", "-u", account, "--", CLI, op, "--socket", str(SOCKET)]
    proc = run(*command, stdin=json.dumps(payload) if payload is not None else None, check=check, limit=10)
    if not check and proc.returncode:
        return None
    envelope = json.loads(proc.stdout)
    require(envelope["ok"] is True, f"client {op} failed")
    return envelope["result"]


def wait_ready():
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        readiness = client(SUBMITTER, "ready", check=False)
        if readiness:
            return readiness["register_id"]
        if show("ActiveState") == "failed":
            break
        time.sleep(0.2)
    raise RuntimeError("service failed to become ready")


def verify_controls(expected_uid):
    properties = {}
    for name in ("NoNewPrivileges", "PrivateTmp", "ProtectHome", "ProtectSystem",
                 "RestrictAddressFamilies", "CapabilityBoundingSet", "UMask", "ActiveState"):
        properties[name] = show(name)
    for name in ("NoNewPrivileges", "PrivateTmp", "ProtectHome"):
        require(properties[name] in ("yes", "true"), f"unexpected unit property {name}")
    for key, expected in (("ProtectSystem", "strict"), ("RestrictAddressFamilies", "AF_UNIX"),
                          ("CapabilityBoundingSet", ""), ("UMask", "0077"), ("ActiveState", "active")):
        require(properties[key] == expected, f"unexpected unit property {key}")
    pid = int(show("MainPID"))
    status = dict(line.split(":", 1) for line in Path(f"/proc/{pid}/status").read_text().splitlines() if ":" in line)
    require(int(status["Uid"].split()[1]) == expected_uid, "unexpected service effective UID")
    require(int(status["NoNewPrivs"]) == 1 and int(status["CapEff"], 16) == 0 and int(status["CapBnd"], 16) == 0,
            "unexpected kernel privilege state")
    require(stat.S_IMODE(STATE.stat().st_mode) == 0o700 and stat.S_IMODE(SOCKET.stat().st_mode) == 0o660,
            "unexpected data or socket modes")
    return pid, properties


def exercise(cleanup, ids):
    import shutil
    CONFIG.mkdir(mode=0o755)
    cleanup.callback(shutil.rmtree, CONFIG)
    access = CONFIG / "change-review.env"
    with access.open("x") as handle:
        handle.write(f"SUBMITTER_UID={ids[SUBMITTER]}\nREVIEWER_UID={ids[REVIEWER]}\n")
    access.chmod(0o600)
    STATE.mkdir(mode=0o700)
    cleanup.callback(shutil.rmtree, STATE)
    shutil.chown(STATE, user=SERVICE, group=SERVICE)
    run("runuser", "-u", SERVICE, "--", CLI, "init", str(DB))
    run("systemd-analyze", "verify", str(UNIT_FILE))
    run("systemctl", "daemon-reload")
    cleanup.callback(run, "systemctl", "stop", UNIT)
    run("systemctl", "start", UNIT)
    register_id = wait_ready()
    pid, properties = verify_controls(ids[SERVICE])
    request = {"op":"submit","register_id":register_id,"id":"ci-service-review","title":"CI title marker 68219",
               "proposal":"CI private proposal marker 75193","evidence":["CI evidence marker 49523"]}
    submitted = client(SUBMITTER, "request", request)["record"]
    listing = client(REVIEWER, "request", {"op":"list"})
    require(any(item["id"] == request["id"] and item["owner_uid"] == ids[SUBMITTER] for item in listing["items"]),
            "reviewer inbox did not contain the expected submission")
    decision = {"op":"decide","register_id":register_id,"submission_digest":submitted["submission_digest"],
                "id":request["id"],"owner_uid":ids[SUBMITTER],
                "decision":"approve","rationale":"CI private decision marker 61943"}
    decided = client(REVIEWER, "request", decision)["record"]
    require(decided["submission_digest"] == submitted["submission_digest"]
            and decided["decision"]["decision"] == "approve"
            and decided["decision"]["reviewer_uid"] == ids[REVIEWER], "decision did not bind the submission")
    run("systemctl", "restart", UNIT)
    require(wait_ready() == register_id, "restart changed the register identity")
    second_pid, _ = verify_controls(ids[SERVICE])
    require(second_pid != pid, "restart did not replace the service process")
    current = client(SUBMITTER, "request", {"op":"get","id":request["id"]})["record"]
    require(current == decided, "record changed across service restart")
    run("systemctl", "stop", UNIT)
    require(show("ActiveState") == "inactive" and show("Result") == "success" and not SOCKET.exists(),
            "service did not stop cleanly")
    audited = run("runuser", "-u", SERVICE, "--", CLI, "verify", str(DB))
    verified = json.loads(audited.stdout)
    require(verified.get("ok") is True and verified["records"] == verified["decisions"] == 1,
            "stopped database failed the single-record verification")
    logs = run("journalctl", "--no-pager", "--unit", UNIT, "--output=cat").stdout
    for marker in (request["title"], request["proposal"], request["evidence"][0], decision["rationale"]):
        require(marker not in logs, "request contents appeared in the unit journal")
    return {"unit_properties": properties, "kernel_effective_uid": ids[SERVICE], "kernel_no_new_privs": 1,
            "kernel_effective_and_bounding_capabilities": 0, "distinct_uids": ids,
            "submit_list_decide": "passed", "restart_readback": "identical record",
            "stop_and_verify": "passed", "request_markers_in_journal": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-hosted-disposable", action="store_true", required=True)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    evidence = {"scope": "disposable GitHub-hosted Ubuntu 24.04 systemd service", "status": "failed"}
    with args.receipt.open("x", encoding="utf-8") as output:
        try:
            preflight()
            with ExitStack() as cleanup:
                cleanup.callback(run, "systemctl", "daemon-reload")
                evidence["wheel_sha256"] = hashlib.sha256(args.wheel.read_bytes()).hexdigest()
                evidence["installed_unit_sha256"] = install(cleanup, args.wheel.resolve())
                run("groupadd", "--system", SERVICE)
                cleanup.callback(run, "groupdel", SERVICE)
                ids = {name: make_account(cleanup, name) for name in (SERVICE, SUBMITTER, REVIEWER)}
                require(len(set(ids.values())) == 3 and all(uid > 0 for uid in ids.values()), "invalid test identities")
                evidence.update(exercise(cleanup, ids))
            evidence["status"] = "passed"
        except Blocked as exc:
            evidence.update(status="blocked", reason=str(exc))
        except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            evidence.update(reason=str(exc))
        json.dump(evidence, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps(evidence, sort_keys=True))
    return 0 if evidence["status"] == "passed" else 2 if evidence["status"] == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
