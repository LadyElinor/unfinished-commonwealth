# C1 durable participant outbox

C1 is a separately versioned client for the [corrected B1.1 host](PARTICIPANT_V1_1.md).
It saves **one immutable intent before networking**, bound to the endpoint,
workshop instance, capability digest, request ID and exact request bytes.
It sends no approval or execution command and does not renew credentials.
C1 does not negotiate or attest the host implementation version; selecting
B1.1 is an operator requirement. Historical clients remain unchanged; select `commonwealth.client_outbox_v1`
explicitly to use these checks. Package version 0.1.3 is unchanged.

## Use

Obtain a task view with B1.1 and prepare the ordinary B1 request envelope. Use the
actual printed URL, not the placeholder below. Retain the task response and
request files under the participant's existing private access policy.

```bash
python -m commonwealth.participant_v1_1 task http://127.0.0.1:PORT credential.txt > task.json
python -m commonwealth.client_outbox_v1 stage outbox.sqlite http://127.0.0.1:PORT credential.txt task.json request.json
python -m commonwealth.client_outbox_v1 retry outbox.sqlite credential.txt
python -m commonwealth.client_outbox_v1 status outbox.sqlite
```

`stage` performs no network operation and never overwrites a file. The task
response's instance and journal head must match the request. The caller and host
supply this view; C1 cannot independently authenticate it. Initial state is
UNRESOLVED, even before sending, so a crash is never mistaken for proof that
nothing happened. `retry` means exactly one POST with the retained bytes and ID.
It works for the first send as well as a later explicit retry.

After a lost response or participant restart:

```bash
python -m commonwealth.client_outbox_v1 resolve outbox.sqlite credential.txt
python -m commonwealth.client_outbox_v1 retry outbox.sqlite credential.txt
```

`resolve` performs one GET for the retained ID. **Lookup alone cannot complete
recovery:** B1 receipts do not contain the original request fingerprint. A
matching lookup therefore stays UNRESOLVED with
`RECEIPT_REQUIRES_EXACT_RETRY`. Only an explicit identical POST binds the server
receipt to those exact request bytes through B1's conflict check. If a different
request already used that capability/ID, POST conflicts rather than claiming it
is the retained intent. No automatic second network call occurs.

A validated POST receipt becomes RECORDED, including a valid refusal such as
STALE_VIEW. This means a disposition was recorded, not that a proposal succeeded
or is correct. Accepted receipts must match instance and ID and explicitly deny
execution authority. Rejection receipts have no instance field; they rely on
the endpoint and trusted host, not cryptographic instance attestation.

Once RECORDED, further C1 calls return the cached historical observation without
networking. This does not assert current authorization, capability validity,
server liveness or continued receipt access. Inspect `recorded.http_status` and
`recorded.receipt.disposition`; exit zero does not imply proposal acceptance.
Stage/status exit zero on a valid local record. Resolve/retry exit three while
unresolved and two on local refusal/error. No HTTP error implies server rollback.

## Safety and unresolved outcomes

- Wrong or replacement credentials fail before sending. C1 stores only their
  digest and public capability ID, never their bearer text. It rejects that
  bearer inside the request too, including JSON-escaped forms. Request content
  itself may contain other sensitive data; this is not a general secret scrubber.
- Expiry, revocation, unavailable/missing receipt, ID conflict and malformed or
  authority-claiming replies retain UNRESOLVED. Seek operator inspection using
  the original capability/ID; do not obtain another token or invent a new ID
  merely to get a successful retry. C1 does not import operator attestations.
- Local operation-start count is committed before networking. A restart can show
  incomplete operations. These counts are not server attempt usage: receipt
  lookups, local interruptions and identical retries have different accounting.
- Concurrent recovery serializes local receipt recording; the server's original
  same-capability/same-byte deduplication prevents duplicate proposals. No global
  exactly-once claim applies to cloned host or outbox databases.
- Each outbox allows at most 256 recorded operation starts. Exhaustion leaves
  unresolved work visible through `status`; it does not grant permission, clear
  the intent or renew the budget. Operator inspection remains separate.
- A failed write or commit may occur after the server has accepted a proposal.
  Preserve the original outbox and use exact-byte recovery. Do not delete or
  replace an unresolved intent. Partial/corrupt files fail closed; automated
  repair and recovery of lost disks are not implemented.

C1 uses SQLite and an exclusively created local file (mode 0600 on POSIX). The
local owner, directory policy, SQLite, filesystem and host remain trusted. It
does not change OS policy, establish cross-UID separation, secure time or prove
power-loss durability. The local digest checks catch accidental inconsistency;
a malicious owner can rewrite consistent data. A malicious host can fabricate
a structurally valid matching receipt. Both are outside this client's assurance.

## Tests and results

```bash
python -m commonwealth.client_outbox_v1 demo
python -m unittest discover -s tests -p test_client_outbox_v1.py -v
python scripts/verify.py
python scripts/package.py .local/c1-release
```

The exposed demo drops a real HTTP response after host commit. A fresh Outbox
object observes the receipt and then explicitly retries the identical bytes,
recovering one proposal and one server attempt after three client operations.
Tests cover malformed success, wrong scope, persistence faults, concurrent
recovery, expired/revoked credentials, conflicting bytes and host forgery.
A subprocess test abruptly exits after a real POST and before local recording;
restart plus exact retry recovers without a duplicate. This is a process-exit
test, not hardware power loss. All cases remain authored/exposed development
fixtures. No model calls, real-world effects, efficacy or production-security
claim follows. See [fixed design](CLIENT_OUTBOX_V1_DESIGN.md).
