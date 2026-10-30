"""Fixed local test worker, copied beside a staged commonwealth package."""

import ctypes
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))


def identity():
    fields = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in ("Uid", "Gid", "Groups", "CapEff", "NoNewPrivs"):
            fields[key] = value.strip()
    return fields


def host(config):
    from commonwealth.store import Workshop
    from commonwealth.participant_v1.store import Boundary, read_credential
    from commonwealth.participant_v1.transport import Handler, Server
    home = Path(config["home"])
    database = home / "workshop.sqlite"
    if not database.exists():
        Workshop.create(database)
        Boundary(database).install()
        for name in ("p1", "p2"):
            Boundary(database).issue(home / (name + ".credential"), ttl=300, attempts=8)
    boundary = Boundary(database)
    original_send = Handler._send
    dropped = False

    def send(handler, status, payload):
        nonlocal dropped
        if config.get("drop_reply") and not dropped and payload.get("request_id") == "lost-reply" and status == 200:
            dropped = True
            handler.connection.shutdown(socket.SHUT_RDWR)
            raise ConnectionResetError("local test response drop")
        return original_send(handler, status, payload)

    Handler._send = send
    with Server(boundary) as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
        thread.start()
        print(json.dumps({"identity": identity(), "pid": os.getpid(), "url": server.url}), flush=True)
        try:
            for line in sys.stdin:
                command = json.loads(line)
                operation = command["op"]
                if operation == "stop":
                    break
                if operation == "audit":
                    result = boundary.audit()
                    result["proposal_count"] = len(Workshop(database).state()["proposals"])
                elif operation == "revoke":
                    result = boundary.revoke(read_credential(home / "p1.credential").split(".")[1])
                elif operation == "issue-expiring":
                    result = boundary.issue(home / "expiring.credential", ttl=3, attempts=2)
                elif operation == "receipt":
                    result = boundary.operator_receipt(read_credential(home / "p1.credential").split(".")[1], command["request_id"])
                else:
                    raise ValueError("unknown host test operation")
                print(json.dumps(result), flush=True)
        finally:
            server.shutdown()
            thread.join()


def probe(config):
    from commonwealth.engine import canonical
    from commonwealth.participant_v1 import PROTOCOL
    from commonwealth.participant_v1.store import read_credential
    from commonwealth.participant_v1.transport import request
    result = {"identity": identity()}
    operation = config["op"]
    if operation in ("read", "write", "create", "signal"):
        try:
            if operation == "signal":
                os.kill(config["pid"], 0)  # permission check; does not deliver a signal
            else:
                flags = {"read": os.O_RDONLY, "write": os.O_WRONLY,
                         "create": os.O_WRONLY | os.O_CREAT | os.O_EXCL}[operation]
                descriptor = os.open(config["path"], flags, 0o600)
                os.close(descriptor)  # do not truncate or print protected contents
            result.update(access=True)
        except OSError as exc:
            result.update(access=False, errno=exc.errno, error=type(exc).__name__)
        return result
    if operation == "keeper":
        # The code is available. Actual access to the real DB must be refused.
        bootstrap = "import sys;sys.path.insert(0,sys.argv.pop(1));from commonwealth.cli import main;raise SystemExit(main())"
        argv = [sys.executable, "-I", "-c", bootstrap, str(Path(__file__).parent),
                config["action"], config["database"], config["proposal"]]
        child = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        result.update(argv=argv, exit_code=child.returncode, stdout=child.stdout, stderr=child.stderr)
        return result
    if operation == "malformed":
        from urllib.parse import urlsplit
        port = urlsplit(config["url"]).port
        with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
            connection.sendall(b"THIS IS NOT HTTP\r\n\r\n")
            connection.shutdown(socket.SHUT_WR)
            try:
                raw = connection.recv(4096)
            except ConnectionResetError:
                raw = b""
        result.update(sent=True, response=raw.decode("ascii", errors="replace"))
        return result
    token = read_credential(config["credential"])
    started = time.perf_counter()
    if operation == "roundtrip":
        status, view = request(config["url"], token)
        if status != 200:
            result.update(status=status, response=view)
            return result
        raw = canonical({"protocol": PROTOCOL, "request_id": config["request_id"],
                         "view_head": view["view_head"], "proposal": view["task"]["proposal_example"]}).encode()
        with Path(config["request_file"]).open("xb") as handle:
            handle.write(raw)
        os.chmod(config["request_file"], 0o600)
        reply = request(config["url"], token, "POST", "/proposals", raw)
    elif operation == "repeat":
        reply = request(config["url"], token, "POST", "/proposals", Path(config["request_file"]).read_bytes())
    elif operation == "receipt":
        reply = request(config["url"], token, "GET", "/receipts/" + config["request_id"])
    elif operation == "task":
        reply = request(config["url"], token)
    else:
        raise ValueError("unknown participant test operation")
    result.update(status=reply[0], response=reply[1], transport_ms=round((time.perf_counter() - started) * 1000, 3))
    return result


def main():
    # Irreversible for this disposable process; no privilege-gaining exec later.
    if ctypes.CDLL(None, use_errno=True).prctl(38, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS failed")
    config = json.loads(sys.stdin.readline())
    if config["op"] == "host":
        host(config)
    else:
        print(json.dumps(probe(config)), flush=True)


if __name__ == "__main__":
    main()
