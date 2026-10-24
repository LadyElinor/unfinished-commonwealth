# Trust boundary and limitations

## What is trusted

The local host, Python interpreter, source checkout, SQLite database, fixture keeper, reference fixture, and operator are trusted. The database stores fictional sample data and invented accounts. All identity and control declarations are supplied and unverified.

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

- Authentication, credential isolation, public-key attestation, real principal discovery, or proof of cognitive independence.
- A sandbox for arbitrary Python, shell commands, model-generated code, or third-party plugins. Those operations are not in the action set.
- Network, messaging, financial, deployment, or production-system adapters.
- Tamper resistance against the operator, external receipts, or a protected governance root.
- Privacy-preserving collection, consent management, redaction, or deletion for real personal accounts. Do not use the seed for those records.
- A judgment that a reported experience is true, that a lesson's prose is sound, or that a procedure is legitimate.
- Unbounded operation: a workshop has 256 operational commands, then at most 32 review commands and three one-time terminal controls. None extends operational authority or resolves pending work by assertion. Public fixtures remain small. Replaying before each mutation is intentionally simple and not a scalable event store.

`agent-view` hides the explicit reference field and keeper commands from its task packet. That omission does not stop an agent with filesystem access from finding them. Isolation must be enforced outside this program before giving an untrusted process access to a real keeper or sensitive information.

Testimony and case text are untrusted data. The program stores them without executing them. A future model may still be susceptible to instructions embedded in those fields; a prompt warning is not a demonstrated prompt-injection defense.

No emergency exception exists. A report of urgency may justify choosing among already authorized actions; it cannot authorize a new action, bypass a required approval, or change a quorum.
