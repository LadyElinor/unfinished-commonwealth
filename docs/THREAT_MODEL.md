# Trust boundary and limitations

## What is trusted

The local host, Python interpreter, source checkout, SQLite database, fixture keeper, reference fixture, and operator are trusted. The database stores fictional sample data and invented accounts. Human identity and control declarations remain supplied and unverified. The optional B1 service checks scoped bearer possession; it does not identify a person or establish controller independence.

Someone who can invoke the unrestricted CLI can claim to be `keeper`. Someone who controls the host can edit the verifier, fixtures, timestamps represented by logical ticks, database, and every hash. Hash linking and deterministic replay detect inconsistency relative to the retained program and history; they do not establish external authenticity, chronology, or independent testimony.

## What the program checks

| Boundary | Mechanism | Regression coverage |
| --- | --- | --- |
| Proposal to effect | Separate approval and single-use exact proposal execution | Missing approval, retargeting, repeat consumption, competing proposals |
| Changed circumstances | Operational revision, epoch, logical-tick expiry | Stale state, revocation, expiry boundary, halt/resume |
| Simultaneous use | SQLite `BEGIN IMMEDIATE` and atomic journal/snapshot commit | Concurrent consumption, failed event append, failed snapshot update |
| Historical continuity | Canonical envelopes, predecessor hashes, complete deterministic replay | Edited snapshot, altered result with recomputed hash, missing event |
| Supplied input | Closed command shapes, bounded strings, finite probabilities | Unknown fields, unknown actions, malformed numbers, duplicate JSON keys |
| Succession | Retire old worker and approvals; refuse handoff with pending peer work | Retired caller, inherited grant reuse, backlog loss |
| Evidence claims | Existing IDs and a narrow observed lesson support requirement | Invented evidence, unobserved lesson success, inconsistent fixture reference |

## What is not provided

- Human identity authentication, OS credential isolation, public-key attestation, real principal discovery, or proof of cognitive independence. B1 provides only local scoped bearer authentication.
- A sandbox for arbitrary Python, shell commands, model-generated code, or third-party plugins. Those operations are not in the action set.
- Remote network, messaging, financial, deployment, or production-system effect adapters. B1 is a local loopback proposal transport only.
- Tamper resistance against the operator, external receipts, or a protected governance root.
- Privacy-preserving collection, consent management, redaction, or deletion for real personal accounts. Do not use the seed for those records.
- A judgment that a reported experience is true, that a lesson's prose is sound, or that a procedure is legitimate.
- Unbounded operation: a workshop has 256 operational commands, then at most 32 review commands and three one-time terminal controls. None extends operational authority or resolves pending work by assertion. Public fixtures remain small. Replaying before each mutation is intentionally simple and not a scalable event store.

`agent-view` hides the explicit reference field and keeper commands from its task packet. That omission does not stop an agent with filesystem access from finding them. Isolation must be enforced outside this program before giving an untrusted process access to a real keeper or sensitive information.

Testimony and case text are untrusted data. The program stores them without executing them. A future model may still be susceptible to instructions embedded in those fields; a prompt warning is not a demonstrated prompt-injection defense.

The separate F1 discernment simulator trusts fixture-supplied origin labels.
Its revocations identify individual receipts; they do not quarantine an issuing
channel, principal or shared dependency. A replacement receipt ID can therefore
support a harmful recommendation even after the previous receipt was revoked.
The [Korean finance incident review](INCIDENT_REVIEW_2026_10_KOREAN_FINANCE.md)
records this negative regression and the unimplemented origin-quarantine boundary.

[I1](INTEGRITY_V1.md) separately tests a policy that applies host-declared
quarantine to an issuer and its descendants, including replacement receipt IDs.
This depends on a correct host inventory and trustworthy notices. Undetected
compromise still produces a harmful recommendation, and quarantine can block
legitimate work. Recovery and real effect-authority invalidation are absent.
Structured commitment review does not establish intent or grant authority.

[R1](REVIEW_V1.md) trusts host classifications of evidence, controller identities,
conflicts, workload and service impacts. It can require explicit disclosure and
references, but cannot prove evidence is true or reasons are fair. Reconsideration
requires the exact parent journal and preserves its decision; this checks lineage,
not authenticated history. Every R1 outcome is advisory and cannot mutate I1 trust.

No emergency exception exists. A report of urgency may justify choosing among already authorized actions; it cannot authorize a new action, bypass a required approval, or change a quorum.

## B1 participant transport

[B1](PARTICIPANT_V1.md) exposes only task, proposal and receipt routes. The
server derives actor/action, rejects stale views, checks expiry/revocation and
generation on every access, and atomically records proposal effects and receipt
accounting. It rejects non-loopback binding, browser Origin and ambiguous framing.
It uses plaintext loopback HTTP and Python's non-production server. Do not expose
or forward it outside the trusted host. The standard client follows no redirects
and makes no automatic retry; a failed POST response is an unknown outcome.

Keep the operator process, DB, raw CLI, issuer and credential directories outside
participant access. The program does not create that OS boundary. A same-user
process or host administrator can bypass it. Stolen bearers work; copied databases
fork consumption; a host can reconstruct a false but locally consistent journal;
an authenticated proposal can be wrong. All four limits have executable negative
controls. UTC rollback causes a fail-closed pause, not trusted-time attestation.
Request bounds are not a denial-of-service guarantee. See [results](PARTICIPANT_V1_RESULTS.md).
