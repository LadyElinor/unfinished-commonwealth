# B1 frozen candidate: local proposal-only participant boundary

Baseline: `efc78c42190aeb66796c60a2909b72aeb2907863`. This design is recorded
before implementation results. The candidate is a separately versioned local
transport and durable receipt layer over the existing protocol-2 workshop.
It leaves all earlier reducers, fixtures and research matrices unchanged.

## Question and scope

Can a participant without workshop filesystem access retrieve a minimized task
and submit a bounded proposal without choosing its own authority, changing the
keeper's state directly, or duplicating a submission after a lost response?

The proposed transport is HTTP on literal IPv4 loopback only, using opaque,
random bearer capabilities issued by the local operator. It is not OAuth, a
production web server, a remote service or a sandbox. The operator, interpreter,
filesystem, database and clock remain trusted. The participant must be a
separately restricted OS principal without database, credential-issuer or raw
CLI access for this to be an actual isolation boundary. Same-user processes
are not isolated by a token. Real human identity, independence and legal mandate
remain unestablished. No model provider or external action is part of this work.

## Fixed mechanism

- A capability binds the workshop instance, current worker and generation,
  expiry and submission-attempt ceiling. Only token digests are stored in SQLite;
  the issuer writes the token once to a newly created private credential file.
- The service exposes task retrieval, proposal submission and receipt lookup.
  It derives the actor and action server-side. No approval, execution, arbitrary
  command, path, code, URL or credential-management endpoint exists.
- A submission contains a protocol version, stable request ID, exact viewed
  journal head, and the method/prediction/purpose proposal fields. A changed
  history requires a fresh task view. The existing reducer remains authoritative.
- Proposal event, workshop snapshot, capability use, attempt record and response
  receipt commit in one SQLite transaction. Identical retries with the same
  valid capability and request bytes return the original receipt; reusing an ID
  for different bytes is refused. No failed transport is silently retried.
- Authentication, expiry, revocation and generation are rechecked before receipt
  redelivery. Revoked or expired participants need operator help to inspect an
  uncertain outcome. The host can inspect the original receipt without granting
  another capability. There is no global exactly-once promise across cloned DBs.
- Unknown responses are reported as unknown. A receipt proves a local recorded
  disposition, not model quality, a real-world effect or independent attestation.
- UTC rollback blocks participant access and issuance until the clock catches
  up. Operator revocation remains available during rollback. Original keeper
  halt/revoke procedures remain independent of transport or participant quotas.
- Requests, responses, credentials, capabilities, attempts and concurrent
  connections have fixed bounds. Browser Origin requests, redirects, non-loopback
  URLs, duplicate framing headers and transfer encoding are refused. No browser
  cookies or CORS grants are used. This is not a denial-of-service defense.

## Necessary gates and controls

Before any usefulness claim, require executable checks for:

1. Wrong/missing/revoked/expired capabilities, actor spoofing and forbidden actions
   producing no workshop mutation.
2. Exact view binding, generation retirement and unknown protocol refusal.
3. Concurrent identical requests causing one proposal, with identical receipts.
4. Failure at event, snapshot, attempt or receipt persistence rolling back all
   related state; replay through the unchanged workshop verifier afterward.
5. A dropped response followed by receipt lookup, including server restart,
   without inventing a new request ID or executing another submission.
6. Invalid authenticated submissions consuming the declared attempt budget;
   exact receipt redelivery not consuming it again; keeper correction unaffected.
7. Secret-free server output and persistent records, bounded ingress, no file
   serving, no redirect following and refusal of remote binding.
8. A real loopback client submitting a legitimate proposal; only a separate host
   action can approve and execute it. Measure local transport latency separately
   from synthetic decision slots, without claiming model latency or efficacy.
9. Installed-wheel operation and unchanged historical study outputs.

Negative controls must preserve the limits: a stolen bearer can act as its
holder; an operator can forge/rebuild local records; cloning the database can
fork request consumption; successful transport does not make a bad proposal
correct. Current cases remain exposed development tests, never a holdout.

## Stop conditions

No model calls, public deployment, paid services, arbitrary subprocess runner,
network effect adapters or changes to real access rules. Do not add sophistication
until the concrete transport and transaction gates pass. If a boundary cannot be
demonstrated, document the failure and keep the capability unavailable.
