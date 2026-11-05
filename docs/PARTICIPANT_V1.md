# B1: local proposal-only participant service

B1 provides a usable transport boundary over the existing protocol-2 workshop.
A participant can retrieve a minimized task, submit a proposal and retrieve its
receipt. Approval, execution, credential issuance and revocation remain local
operator functions. This closes a concrete gap in the old JSON handoff: a caller
of that unrestricted CLI can supply any fixture actor, including `keeper`.

B1 is separately versioned as `participant-1.0.0`. It changes no earlier reducer,
fixture or study output. The [design and gates](PARTICIPANT_V1_DESIGN.md) were
recorded before implementation; the [results](PARTICIPANT_V1_RESULTS.md) include
failure injections and negative controls. No model calls or external effects occur.

## Try the complete local demonstration

```bash
python -m commonwealth.participant_v1 demo
```

This opens an ephemeral IPv4 loopback server, issues a temporary credential,
retrieves the task, submits one proposal and repeats the same request. It then
uses separate host calls to approve, execute and observe the result, revokes the
credential and checks replay/accounting. Temporary credentials and databases are
deleted. The JSON output contains no credential and measures the actual local
task-plus-submit elapsed time. It measures neither model latency nor efficacy.

## Operator and participant workflow

These commands illustrate a single-host setup. To enforce actual separation,
the operator must independently restrict the participant's OS/filesystem access.
Do not give an untrusted participant access to the database, raw CLI, issuer,
server process, evaluator references or other participants' credential files.

```bash
python -m commonwealth init .local/participant.sqlite
python -m commonwealth.participant_v1 install .local/participant.sqlite
python -m commonwealth.participant_v1 issue .local/participant.sqlite .local/participant.credential --ttl 300 --attempts 8
python -m commonwealth.participant_v1 serve .local/participant.sqlite
```

The server prints its `http://127.0.0.1:PORT` endpoint and runs until interrupted.
In a second terminal, replace `PORT` with that returned port:

```bash
python -m commonwealth.participant_v1 task http://127.0.0.1:PORT .local/participant.credential
python -m commonwealth.participant_v1 submit http://127.0.0.1:PORT .local/participant.credential request.json
python -m commonwealth.participant_v1 receipt http://127.0.0.1:PORT .local/participant.credential request-1
```

Create `request.json` using the returned `view_head` and task. Keep the exact
file bytes for receipt recovery. The following shape is illustrative; replace
the head placeholder with the actual 64-character head:

```json
{
  "protocol": "unfinished-commonwealth.participant.v1",
  "request_id": "request-1",
  "view_head": "REPLACE_WITH_THE_EXACT_TASK_HEAD",
  "proposal": {
    "method": "quality-stream",
    "prediction": {"primary_correct": 0.9, "peer_on_time": 0.8},
    "purpose": "Test the method against the stated validity contract."
  }
}
```

The service derives `actor` and `action`; supplying either is refused. A fresh
request ID does not grant more quota. A changed workshop head requires a fresh
task view and a new request ID for the revised submission. A successor also needs
its host-recorded observation, as required by the original reducer.

After examining a proposal, the operator may separately use the original
`approve` and `execute` CLI commands. No participant endpoint performs either.
Operator inspection and revocation use the capability ID printed at issuance:

```bash
python -m commonwealth.participant_v1 audit .local/participant.sqlite
python -m commonwealth.participant_v1 operator-receipt .local/participant.sqlite CAPABILITY_ID request-1
python -m commonwealth.participant_v1 revoke .local/participant.sqlite CAPABILITY_ID
```

The credential is written exclusively to a new file. POSIX creation requests
mode `0600`; on Windows the operator must configure an appropriate directory
ACL. Keep the parent directory protected. Existing files and symlinks are never
overwritten. The database stores only a token digest. A crash during issuance
may leave an unusable file or an issued credential whose delivery is uncertain;
inspect locally and revoke rather than reusing an uncertain credential.

## Protocol, receipts and accounting

| Route | Meaning |
| --- | --- |
| `GET /task` | Current minimized view, exact journal head, remaining attempts |
| `POST /proposals` | One bounded proposal envelope, authenticated by bearer |
| `GET /receipts/REQUEST_ID` | Original response, limited to the issuing capability |

There is one SQLite write transaction for authentication/current state checks,
attempt consumption, event append, snapshot update and receipt persistence.
The unchanged workshop verifier replays the original event stream. B1 tables
are auxiliary; older workshop commands can still operate on the same DB.

Identical bytes and request ID under the same valid capability return the
original receipt without consuming another attempt, even if the head has
advanced or the attempt budget is exhausted. Different bytes under an existing
ID are refused and consume an attempt if quota remains. They cannot replace the
original receipt. Requests under a different capability are a separate scope.

Bounded, fully received authenticated submissions consume attempts even when
JSON, fields, head or proposal semantics are invalid. If a valid request ID is
recoverable, the refusal is durable. Malformed input with no valid ID is counted
but has no retrievable receipt; retransmitting it consumes another attempt.
Authentication, HTTP framing, size and route failures happen before this
submission ledger and do not consume its quota. GET calls have no attempt quota.
These counters measure submission attempts, not every network connection or cost.

| Response | Interpretation |
| --- | --- |
| `200 ACCEPTED` | Local proposal recorded; `permits_execution` remains false |
| `400 INVALID_REQUEST` | Invalid envelope; an identified submission has a refusal receipt |
| `401 UNAUTHORIZED` | Missing/invalid, expired or revoked capability |
| `403 CAPABILITY_EXHAUSTED` | No new attempts available; exact cached requests may still be read |
| `409 STALE_VIEW` | Workshop history changed since the supplied view |
| `409 REQUEST_ID_CONFLICT` | ID already binds different bytes; original receipt retained |
| `410 RETIRED_SCOPE` | Worker generation changed |
| `422 PROPOSAL_REFUSED` | Original reducer refused the proposed transition |
| `503` | Boundary unavailable, invalid clock, clock rollback or output bound |
| Client status `0 UNKNOWN` | POST transport/response failure; commit outcome is uncertain |

Receipt lookup returns the original submission's HTTP status, including a prior
refusal. A missing receipt is only absence in this local ledger. After an unknown
POST, look up its ID or deliberately retry **the same bytes and ID** while the
capability remains valid. The client never retries or follows redirects for you.
It exits 3 for transport uncertainty, 2 for refusal and 0 for a successful call.
Expired, revoked or retired callers cannot retrieve even cached receipts; the
operator can inspect the retained disposition without renewing their access.

## Bounds and trust

| Resource | Bound |
| --- | --- |
| Bind address | Literal `127.0.0.1`; default ephemeral port |
| Capabilities | 128 retained per DB; no pruning or automatic renewal |
| TTL | 1–3,600 seconds; checked against trusted UTC on each access |
| Submission attempts | 1–64 per capability; at most 8,192 retained attempts |
| Request ID | 1–64 ASCII letters, digits, hyphen or underscore |
| Body | 32,768 UTF-8 bytes; some escaped representations of valid text exceed this |
| Response | 2 MiB; overlarge task views refused |
| Connections | Eight active handlers; five-second socket timeout |
| SQLite writer wait | Ten seconds, inherited from the original workshop |

The service persists a UTC high-water mark. A backward clock step refuses
participant access and issuance until the clock catches up; operator revocation
and local inspection remain available. Advancing the clock can expire a grant
early. This is not a trusted-time implementation. Original keeper halt/revoke
commands remain available independently of B1 and its quota.

The transport rejects browser Origin requests, transfer encoding, Expect,
duplicate framing/authentication headers, wrong Host values and unknown routes.
It serves no files and grants no CORS access. HTTP headers also have the standard
library's parser limits. Resource bounds do not establish resistance to denial
of service or malicious local administrators.

**Possession of a bearer is not verified human identity, independent review or
legitimate appointment.** Same-user processes are not isolated. A trusted host
can forge a complete locally consistent history. Copying the DB forks token
and receipt consumption; there is no global exactly-once guarantee. A holder
can submit bad ideas, exfiltrate its own view, or place secrets in its purpose
text. The service does not automatically copy the issued token into logs or
records, but cannot protect a secret deliberately submitted as content.

Do not expose or forward this service beyond the trusted local host. It uses
plaintext loopback HTTP and the standard library server; it is neither OAuth
nor a production identity service. OS isolation, protected host deployment,
independent issuers, authenticated evidence and real mandate review remain work
for a separate design. B1 is no authorization for external actions or a new
package release. `commonwealth readiness` continues to report research-only.

## Primary technical references

Reviewed on 2026-10-30. These references inform implementation constraints;
they do not certify this implementation.

- [Python HTTP server documentation](https://docs.python.org/3/library/http.server.html):
  the module has basic security checks and is unsuitable for production use.
- [SQLite transactions, section 2.2](https://www.sqlite.org/lang_transaction.html):
  `BEGIN IMMEDIATE` starts a write transaction; competing writers can yield busy
  errors. B1 keeps related records in one transaction and rolls back on error.
- [RFC 9110, section 9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2):
  retrying non-idempotent requests requires knowledge of their semantics or that
  the first request was not applied. B1 instead exposes uncertainty and receipts.
- [RFC 6750, sections 1 and 5](https://www.rfc-editor.org/rfc/rfc6750.html):
  bearer possession is sufficient for use; disclosure, replay and recipient
  confusion require attention. That OAuth specification requires TLS. B1's
  local plaintext protocol does **not** implement or claim conformance to it.
