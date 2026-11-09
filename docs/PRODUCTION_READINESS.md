# Production readiness: operational candidate, blocked release

## Target and decision boundary

The intended next product is a trusted-operator, single-host, noncritical
proposal/review recording service with **no external execution**. The first real
workflow and deployment environment have not yet been specified or accepted.
The current engine is still a fixture-driven research workshop, not that product:
`Workshop.create` selects authored scenarios, genesis says `LOCAL_RESEARCH`, and
operational commands have a fixed 256-command lifetime. These are not production
capacity or business-domain guarantees. Operational tooling must not relabel them.

Distribution **0.1.4rc2** is an unpublished operational prerequisite candidate.
Historical engine/runtime version **0.1.3** and all research reducers remain
unchanged. Separately versioned **O1 / operations-1.0.0** adds inspection, WSGI
adaptation and recovery. B1.1 is the selected host implementation; C2 remains the
separately installed client. This is not a package-index release, merge or deploy.

`python -m commonwealth.operations_v1 readiness` exits 2 and always reports
`production_ready: false`. Configuration cannot set these blockers to passed:

| Gate | Evidence now | Release disposition |
| --- | --- | --- |
| Real workload, domain schema, retention and acceptance criteria | Not specified; current fixtures intentionally preserved | BLOCKED |
| Local configuration and owner-only storage admission | Strict bounded config; POSIX file/parent ownership/mode and symlink checks; read-only B1.1 replay/accounting | Software checks implemented; actual host policy unverified |
| Gateway and HTTP security | PEP 3333 adapter, bounded bodies/concurrent routing; test gateway compatibility | Production gateway, parser/deadline/buffering/load/shutdown acceptance NOT RUN |
| Recovery | Verified snapshot; exclusive new-file restore; every restored capability revoked; clock floor retained | Synthetic regression checks; deployment restore/fencing drill NOT RUN |
| Operator/participant separation | C2 isolated artifact; historical U1 B1 observation | Corrected service/client production OS boundary NOT RUN |
| Release traceability | Prerelease version, wheel/source hashes and installed gates | No signing, independent supply-chain certification or publication |
| Operational SLOs and incident response | Runbook and explicit failure behavior | Actual monitoring, disk capacity, latency and operator response NOT RUN |

The supported O1 admission policy is unprivileged POSIX owner-only storage, currently intended
for a Linux host. Windows can run research and backup regression tests, but O1
service admission fails closed because portable POSIX checks cannot verify NTFS
ACLs. Filesystem hardlink support is required for backup/restore publication.

## Service setup contract (no live setup performed)

The operator supplies an existing B1.1 database and a JSON configuration:

```json
{"schema":"operations-1.0.0","database":"/absolute/private/host.sqlite","host":"127.0.0.1","port":8765,"max_inflight":2}
```

Service admission refuses effective UID 0. Database and immediate parent must be owned by the effective user, with no group
or other permission bits. Paths containing symlinks are refused. The tool checks
but never changes permissions, creates accounts, installs a service, changes
firewalls or issues deployment credentials. The parent hierarchy, operator,
interpreter and storage remain trusted; checks are not race-proof against the
owner changing paths after admission. A private directory is not independent
operator authentication. Preflight can be run without creating or changing DB
contents:

```sh
python -m commonwealth.operations_v1 preflight config.json
```

Exit 0 means **local prerequisites** passed, not production readiness. Existing
B1 databases must undergo the separately documented [B1.1 upgrade](PARTICIPANT_V1_1.md)
under an operator-approved recovery plan; startup does not silently migrate them.
O1 never creates a real-workload database from the research fixtures by default.

A trusted gateway calls `commonwealth.operations_v1.app.create_app(config_path)`
and mounts the resulting WSGI callable at `/`. No runnable development listener
is exposed by O1. The gateway must bind the configured literal loopback endpoint,
preserve the direct peer and Host, not proxy/forward requests, and own bounded
header/body parsing, socket deadlines, buffering, process supervision and response
draining. O1 refuses forwarded/origin/transfer-encoding/expect markers and
nonlocal peers. WSGI cannot independently detect duplicate raw headers after a
gateway has collapsed them; rejecting raw ambiguous framing is an unverified
gateway requirement. Gateway selection and configuration require review before
use. Do not expose this interface on the public network or add remote TLS/proxy
access by changing application code/configuration flags.

Python documents [http.server as not recommended for production](https://docs.python.org/3/library/http.server.html).
O1 instead exposes the [PEP 3333 application interface](https://peps.python.org/pep-3333/),
which separates application routing from the gateway. This interface alone does
not make a deployment production-ready. The standard-library test gateway used
in regressions is expressly not a production gateway recommendation.

### Routes and failure semantics

B1-compatible `/task`, `/proposals`, and `/receipts/ID` retain scoped bearer
checks, exact-view binding, corrected clock handling and no execution authority.
There is no keeper, issue, revoke, shell or general workflow-admin route. New
work uses the [C2 client](CLIENT_ONLY_V2.md); existing C1 outboxes remain with C1.
`GET /health/ready` is unauthenticated but direct-loopback only. It exposes only
sanitized prerequisite state and fixed production blockers, no paths, bearers or
work content. Its 200 means inspection succeeded, not that a particular proposal
has capacity, that tokens are valid, or that the service is production-ready.

At most 1–8 routing operations per app instance are admitted; excess work gets
503 without application-side queuing. This is not a fleet/global concurrency
limit. Gateway worker/thread/queue budgets remain separately constrained. A
blocking input read relies on gateway deadlines. `Application.drain()` refuses
new calls and reports active **routing operations**. Zero does not mean all HTTP
responses have reached clients; the gateway must drain buffered responses and
manage its own shutdown deadline. An interrupted POST may have committed; retain
original intent and use explicit C2 exact-byte recovery, never invent a new ID.

Application failures return controlled labels; no request/body/credential/path or
traceback is logged by the adapter. Gateway access/error logs, trace collection
and operator shells require a separate secret-redaction policy. Local replay and
accounting detect inconsistency, not deliberate host forgery or substantive truth.

## Backup, restore and rollback runbook

```sh
python -m commonwealth.operations_v1 backup /private/host.sqlite /private/new-snapshot.sqlite
python -m commonwealth.operations_v1 restore /private/snapshot.sqlite /private/new-restored.sqlite
```

Both source and destination directories must be trusted and protected by the
operator; backup path checks do not establish their ACL policy. The destination
must not exist. Copy uses SQLite backup, verifies the actual copied snapshot,
replay and participant accounting, checks a 128 MiB bound, and publishes a private
0600 file using an exclusive same-directory hardlink. Existing or racing outputs
are never overwritten. Unsupported filesystems fail closed. The default ten-second
budget is a **cooperative** copy/check deadline, not a hard process timeout;
verification may run before the next check. File bytes are synchronized, but no
power-loss/directory-fsync durability or universal filesystem guarantee is claimed.
Failed operations remove only their own staging name; crashes may leave private
staging files for operator inspection. Never indiscriminately delete files.

Snapshots contain capability digests and all retained work, potentially sensitive
future inputs; protect, inventory and retain/delete them under an approved policy.
A raw backup is not a safe replacement service: restore is mandatory before reuse.
The restore tool publishes a new database with **every old capability revoked**,
preserves receipt instance IDs and journal history, and refuses a wall clock below
the retained floor. It does not create replacement credentials. Preserving the
instance is necessary because historical receipts bind it. Existing receipts are
historical evidence, not active authorization. Client outbox restoration is not
an exactly-once guarantee and is not automated here.

Before recovery, an operator must stop/fence the original service and all other
copies. This tool cannot stop a surviving source or fork: original capabilities
may still work there. Never run source and restore concurrently. Verify the
restored audit, clock, file policy and readiness in an isolated recovery drill;
resolve outstanding operations against retained receipts before approving fresh
credentials or resuming traffic. A restore loses changes after its snapshot; that
recovery-point loss must be measured and accepted. Do not roll an upgraded DB back
by replacing it with an older capability-bearing copy. Reverting binaries is not
a DB downgrade procedure. Preserve original evidence and keep service stopped
when replay, accounting, clock or credential disposition is uncertain.

## Release and incident acceptance still required

1. Define the real workflow/data schema, responsible operator, consent/retention,
   decision limits, expected volume and measurable acceptance tests.
2. Choose/pin/review a supported gateway and OS; test raw ambiguous headers, slow
   bodies, oversized inputs, bounded queues, clean shutdown and restart on that
   exact stack. No live settings are changed by this source candidate.
3. Validate corrected host/C2 access separation and backup access on the actual
   host. A same-owner process or administrator remains trusted; no general sandbox.
4. Exercise disk-full, corruption, process kill, clock rollback, restore-point
   loss, credential revocation and source fencing. Test real storage failure and
   monitor health/errors without secrets; synthetic SQLite trigger failures are
   not a real full-disk or power-loss experiment.
5. Establish SLOs, capacity/retention limits, alerts, incident owner and maintenance
   policy. Freeze and archive the final artifact/commit and deployment acceptance
   record before any explicit approval to release, merge or deploy.

Until those gates are evidenced, this candidate is useful operational preparation,
not completion of the user's production goal. No independent identity, arbitrary
real-world authority, certified decisions, hidden-evaluation performance or model
competence follows from the test count.
