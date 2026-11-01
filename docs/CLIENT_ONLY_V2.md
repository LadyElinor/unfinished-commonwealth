# C2: separately packaged participant client

## Finding and bounded repair

At `54199f7982291d585d62caf7d1517235362d4ffe`, importing the C1 outbox
transitively imports the workshop engine, pipeline, legacy reducer, host store,
and workshop store. Its CLI imports the host demonstration. The full workshop
wheel deliberately contains public fixture references. Merely excluding JSON
from that wheel would neither remove the dependency graph nor create secrecy.

C2 is an explicit separate distribution, `unfinished-commonwealth-client` 2.0.0,
with module `commonwealth_client_v2` and local schema `client-only-2.0.0`.
It copies the bounded C1 outbox behavior and B1 request implementation into a
standalone standard-library-only package, alongside compatible JSON/wire helpers.
It contains no host listener, keeper command, evaluator, fixture or host demo.
The full historical workshop distribution and C1 remain unchanged in behavior.
No package-index release or installation on another user's machine is implied.

## Build and inspect

From the source checkout with locally available setuptools, wheel, pip and venv:

```sh
python scripts/package_client.py .local/client-artifacts
```

The output directory must not exist. The script builds offline from a fixed
source allowlist, inspects the source archive, builds its wheel from that
extracted archive, checks exact wheel members and byte identity to reviewed
sources, rejects non-standard-library absolute imports and runtime dependencies,
and installs only that wheel in a fresh virtual environment. A separate process
uses Python isolated mode (`-I`), from a directory outside the checkout, to prove
`commonwealth` is not importable there. It stages, looks up, explicitly submits
and reads a cached outcome over real loopback HTTP to a B1.1 host in the builder.
The observed accounting must be one proposal and one server attempt. No client
host/demo command is exposed. JSON evidence and artifact SHA-256 hashes are saved
in `client-package-verification.json`. Builds are not claimed byte-reproducible:
archive timestamps can change hashes.

The ordinary `python scripts/package.py NEW_DIRECTORY` also performs this gate
from its extracted full source archive. Thus the four portable CI packaging jobs
exercise C2 installation separately from the full workshop installation. Existing
U1 cross-UID evidence stays historical B1 evidence; C2 adds no new UID test.

## Participant usage

An operator must separately provide a B1.1 host URL, original capability file,
task JSON and proposal request JSON. C2 cannot attest the host version. Install
only the reviewed client wheel into a separate environment, not the full workshop
wheel. After installation:

```sh
python -I -m commonwealth_client_v2 stage intent.sqlite http://127.0.0.1:PORT credential.txt task.json request.json
python -I -m commonwealth_client_v2 status intent.sqlite
python -I -m commonwealth_client_v2 resolve intent.sqlite credential.txt
python -I -m commonwealth_client_v2 retry intent.sqlite credential.txt
```

Replace `PORT` with the actual local host port. The `commonwealth-client` console
entry point offers the same four commands. Staging never sends. Only explicit
`retry` submits the immutable bytes, under the original capability digest and
request ID. No redirect, automatic renewal, automatic retry or execution exists.
Lookup alone remains unresolved because B1 receipts omit the request fingerprint;
exact retry reconciles against the trusted host's conflict check. Expired/revoked
or malformed outcomes remain unresolved. `RECORDED` may be a refusal, and a cached
record is historical, not current authorization. There is a 256-operation cap.
Exit codes: stage/status valid = 0; recovery recorded = 0; unresolved = 3;
local refusal = 2. See [C1](CLIENT_OUTBOX_V1.md) for inherited recovery semantics.

## Compatibility and migration boundary

Wire protocol remains `unfinished-commonwealth.participant.v1`. C2 has a distinct
local outbox version and refuses C1 databases; C1 refuses C2 databases. There is
no automatic migration. Resolve existing C1 intents with C1 and retain their
original files. Do not restage an uncertain old submission with a new ID or a
replacement capability to bypass unresolved status. C2 is for explicitly new
intents, not a silent default replacement. B1.1 remains the operator-selected
host; historical vulnerable B1 remains reproducible, not recommended.

## Evidence and limits

The exposed parity suite repeats C1's recovery, malformed-response, binding,
concurrency, refusal and abrupt-child-exit gates against the standalone imports.
Additional gates cover JSON parsing parity, cross-version refusal, dependency
absence and rejection of injected archive members/dependencies. Baseline hashes
preserve previous runtime and recorded evidence. These are software regression
checks, not an independently held-out competence evaluation.

A minimal artifact does not stop a participant reading other reachable files,
installing the full public package, accessing the network or using another
credential. External OS/filesystem and egress policies are still required.
Historical references are public; excluding them from this artifact does not
make them unknown. The test builder intentionally contains the host and fixtures.
The host can forge structurally matching receipts, local owners can rewrite
outboxes, cloned state can fork accounting, and no power-loss test or general
exactly-once guarantee follows. No model calls, external execution authority,
independent operator, sandbox, production security or hidden-evaluation claim.
