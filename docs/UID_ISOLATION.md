# U1: observing B1 across Linux identities

The [fixed design](UID_ISOLATION_DESIGN.md) extends B1 testing without changing
`participant-1.0.0`. It distinguishes a configured access policy from an observed
permission boundary. Run only on a disposable Linux host whose administrator has
authorized the test. It uses privileged setup for temporary files and child UID
switching; it creates no accounts, services, mounts or firewall rules.

```bash
sudo "$(command -v python)" scripts/uid_isolation.py --run .local/uid-isolation.json
```

The output path must be new. Exit 0 means the required observations passed;
1 is failure; 77 means missing prerequisites or missing explicit opt-in. Linux
with UID 0 but no effective capabilities is **blocked**, not validated. The
ordinary unit suite does not require or silently attempt privileged operations.
The separate Linux CI job runs the opt-in demonstration and prints its sanitized
report. A CI success is evidence about that runner, not the reader's machine.

The supervisor launches an ordinary host as UID/GID 61001, participant 1 as
61002 and participant 2 as 61003. These are numeric process credentials, not
new passwd entries. Use a disposable runner: these numbers may correspond to
existing principals on an arbitrary machine. Children have no supplementary
groups, no effective capabilities and no-new-privileges enabled. Real,
effective, saved and filesystem IDs are checked in `/proc/self/status`.

Each actor has a private 0700 directory. Credentials are 0600. Shared client
code is administrator-owned and read-only; the host imports a separate private
copy. The participant deliberately receives protected paths for negative tests:
not knowing a path would not establish inability to access it. The supervisor
delivers credentials between the directories without printing their values.

## What each result means

| Check | Required evidence |
| --- | --- |
| Allowed task/submission/receipt | Successful calls across UIDs, one proposal and one consumed attempt after identical retry |
| Protected files | EACCES or EPERM on existing DB, host source, host credential and other participant credential; not missing-file errors |
| Host/code writes | Write-open or creation denied, without trying to truncate the live DB |
| Keeper commands | Available CLI returns a DB access refusal as participant; succeeds separately as host; journal unchanged by refused attempts |
| Host process | Signal permission check (`kill(pid, 0)`) refused; no disruptive signal is sent |
| Delivered credential | Ordinary host cannot read participant's private copy; privileged supervisor deliberately can |
| Malformed socket traffic | Bytes are sent, then refused/connection closed; unchanged verified journal and attempt accounting |
| Lost reply | Post-commit response loss is UNKNOWN; restart and same-ID lookup/retry recover one original proposal |
| Expiry/revocation | Real-time expiry and host revocation deny task, submission and receipt; host can inspect the retained receipt |
| Leaked bearer | Deliberately copied second token still works: possession remains sufficient |

The JSON report preserves commands, inputs, exit codes, identity observations,
permission errors, audit/accounting checks and per-process elapsed times. It
does not contain bearer values or protected file contents. Task-plus-submit
transport time and receipt recovery time are measured separately from subprocess
startup. One host-UID transport control is recorded for comparison. This is one
smoke-test timing sample, not a benchmark or causal isolation-overhead estimate.

Two participant proposals/attempts precede the control. The same-UID control adds
one more proposal; final host approval/execution are deliberate local positive
controls. No model or external effect adapter is involved. The root supervisor
removes only its generated temporary tree after preserving the report.

## Corrections to the supplied checklist

1. **The port and request ID must be concrete.** `serve` prints an actual
   `http://127.0.0.1:PORT`; receipt lookup also needs the submitted request ID.
   B1 credentials are opaque text tokens, not JSON despite a possible `.json`
   filename. See [the B1 commands](PARTICIPANT_V1.md).
2. **A private network namespace changes reachability.** Its loopback is separate
   from the host's. This demonstration shares a network namespace and makes no
   egress restriction claim. A private namespace needs an explicitly protected
   bridge/proxy or a different transport. Binding a server to loopback does not
   limit the participant's other outbound connections.
3. **Allowed TCP is not an HTTP-only sending capability.** A participant can send
   arbitrary bytes to a permitted socket. The defensible check is refusal plus
   unchanged state, not an inability to send malformed bytes.
4. **Administrator access is a retained trust assumption.** Distinct unprivileged
   UIDs plus private directories can deny mutual file access. Root or a process
   with relevant capabilities can bypass discretionary access checks. The host
   also knew and can retain the bearer it issued; inability to read the delivered
   copy does not make that bearer unknown to its issuer.
5. **Command availability is not authority.** The participant may have the entire
   public source and a working keeper CLI. The relevant boundary is inability
   to affect the protected workshop, not `command not found`.
6. **seccomp alone is not a path/port policy.** Syscall filtering does not establish
   arbitrary path and destination-port restrictions. Landlock/LSMs, network rules
   or namespace arrangements need their own supported configuration and tests.

This suite does not establish resistance to kernel exploits, ptrace via privileged
principals, denial of service, host compromise, or all possible access paths. It
does not set up a production sandbox, multi-host trust or independently verified
people/organizations. Existing B1 negative controls remain valid.

## Primary implementation references

- [Linux network namespaces](https://man7.org/linux/man-pages/man7/network_namespaces.7.html):
  network devices, routing, sockets and other networking resources are isolated.
- [Linux capabilities](https://man7.org/linux/man-pages/man7/capabilities.7.html):
  discretionary access overrides, UID changes and signal permissions depend on
  capabilities as well as numeric identities.
- [Python subprocess](https://docs.python.org/3/library/subprocess.html): `user`,
  `group` and `extra_groups` configure child process credentials on POSIX.

The development environment's own UID-switch demonstration was blocked because
its effective capability set was empty. Hosted execution is recorded separately
in the draft pull request and CI logs. Passing portable unit tests alone must
never be reported as passing this OS-boundary check.
