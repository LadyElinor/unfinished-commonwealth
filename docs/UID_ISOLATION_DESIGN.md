# U1: fixed Linux UID-boundary demonstration

Baseline: `293c4d3a7c07f0b1d71528309e1289c87a11ae57` (B1 unchanged).
This candidate is specified before execution. It tests kernel discretionary
access controls around B1, not new protocol logic or efficacy.

An opt-in privileged supervisor creates a fresh temporary tree and launches a
non-root host and two participants as three distinct numeric UIDs/GIDs, clearing
supplementary groups. It creates no user accounts, changes no global permissions,
installs no services and changes no firewall or namespace configuration. Children
set no-new-privileges and must report zero effective capabilities. The supervisor
is trusted and can read all test files; ordinary host/participant processes cannot.

Private host/participant directories are mode 0700, credentials mode 0600, and
shared client code root-owned/read-only. Host imports a separate private copy.
Processes share a network namespace, so host loopback remains reachable. No
egress restriction is claimed. A separate private network namespace would need
an explicitly designed connection path; its loopback is not the host's loopback.

## Required observations

1. Correct distinct real/effective/saved/filesystem UIDs and GIDs, no supplementary
   groups, zero effective capabilities, no-new-privileges enabled.
2. Participant task, proposal, identical retry and receipt work; one proposal and
   attempt are recorded. Measured task/submit time excludes process startup, which
   is separately included in each subprocess elapsed time.
3. Deliberately disclosed protected paths cannot be opened: DB read/write, host
   credential/source, other participant credential, host source write, creation
   in host working directory and client-code write. Require EACCES/EPERM, never
   merely a missing path or missing executable.
4. Actual keeper CLI approval/execution attempts fail against the real DB, with
   an unchanged verified journal. Signal permission to the host is refused.
5. Non-root host cannot read participant's private delivered copy. Trusted root
   can read it. Deliberately leaked bearer still works: filesystem separation
   cannot revoke possession or establish human identity.
6. Malformed bytes can reach the allowed socket, but receive an error or close
   and leave workshop state and attempt accounting unchanged. Reject the claim
   that allowing a TCP connection prevents sending non-HTTP traffic.
7. Lost response after commit yields UNKNOWN; receipt/retry after host restart
   recover the original disposition with no duplicate proposal or attempt.
8. Revocation and real TTL expiry refuse further task/submission/receipt access;
   host inspection remains available. Ordinary keeper control remains local.

Failures stop the run and remain failures. Missing Linux/privilege prerequisites
produce BLOCKED with exit 77, never a pass. The current local runtime may lack
capabilities even when its numeric UID is zero. Hosted evidence must be labeled
as hosted, not as a successful local UID-switch experiment.

The report records commands, probe parameters, exit codes, permission errors,
identities, accounting, latency and limitations. It excludes bearer values and
private file contents. Root cleanup removes only the generated temporary tree.
No model calls, production records, remote host or external effects are involved.
