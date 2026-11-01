# C1 durable client intent and receipt validation

Baseline: `5d268390abca2ba69061c2f667161c0316b12802`.
The candidate preserves B1, B1.1, U1 and earlier runtime/evidence files.

## Question and fixed scope

Can a participant retain one exact submission across its own restart, avoid
changing its ID after an uncertain response, and refuse a response that does
not match retained intent or claims execution authority?

The existing B1 transport checks only response protocol, not receipt semantics.
A local malformed-success response can therefore be returned as HTTP 200 by
that historical client. C1 will independently validate full receipt shape,
status, request ID, accepted instance and absence of execution authority.
It will not authenticate an adversarial host or prove substantive correctness.

## Fixed mechanism and gates

Stage a single bounded immutable intent before networking: exact request bytes,
endpoint, request ID, expected workshop instance and capability ID plus bearer
digest. Never store bearer text or obtain new credentials. Stage receives a
caller-supplied task view and cannot independently establish its authenticity.
A second stage must not overwrite the first file. Retained intent has a digest
for accidental-corruption detection, not protection from a hostile local owner.

A SQLite outbox records operation start before networking. The operation is
explicitly either receipt lookup or exact-byte retry. No automatic retry, token
renewal, new request ID, updated task view, approval or execution is allowed.
Concurrency serializes receipt recording, and B1's same-capability/same-byte
idempotency remains the server-side duplicate-effect guard.

A staged intent is UNRESOLVED even when never sent. Transport loss, missing
receipt, expiry/revocation, conflicting ID and malformed responses retain that
state. Only a validated identical-POST receipt becomes RECORDED. B1 GET receipts lack
a request digest, so lookup alone requires an explicit exact-byte retry. A cached recorded observation
is historical information, not current permission, liveness or access. B1
rejection receipts lack instance binding; this must be explicit. Host trust is
not replaced by syntactic validation.

Required controls: overwrite refusal, wrong token/instance/request ID, malformed
success and authority claims, corrupted saved intent, crash before send and
after server commit, dropped reply/restart, conflicting reused ID, concurrent
recovery, expired/revoked credentials and an intentionally forged matching host
receipt. Validate installed-wheel behavior and all prior preservation manifests.

A fixed ceiling of 256 operation starts keeps local history bounded; exhaustion
leaves status readable and the obligation unresolved, without new authority.

Only committed SQLite records survive the modeled restart; tests do not prove
storage durability under actual power loss or arbitrary filesystem semantics.
No model calls, effect adapters, external services or production claim.
