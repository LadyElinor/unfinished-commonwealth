# B1.1: durable clock observations on refusal

Baseline: `6dbc913fb50c7cd733701f9f933d38a11ef739ec`.
This correction is separately versioned; B1, U1 and earlier records stay frozen.

## Reproduced defect

In B1, issue at time 1000 with TTL 60, attempt access at 1061 (refused expired),
then restart at 1050: the bearer works again. Authentication failure rolled back
the same transaction that recorded the later clock observation. Thus B1's
rollback protection did not retain every observed time, despite the broad
wording of its historical design. This is a counterexample, not an attack on
an external system. The test uses an injected clock and disposable database.

## Fixed mechanism

B1.1 retains the B1 schema and wire protocol but exposes a separate Boundary and
operator CLI. Before authentication/operation, it verifies the journal and
metadata, validates the clock and durably commits its maximum observed time.
It then opens a new transaction, re-verifies journal, metadata and instance, and
observes time again after acquiring the lock. A savepoint keeps operation writes
separate from this second clock update: refusal rolls back operation writes and
commits the new floor. Abrupt process loss can lose an uncommitted observation,
but cannot erase the earlier committed floor. Ordinary keeper operations remain separate.

Revocation and operator receipt/audit remain available during rollback; those
calls never lower the retained floor. An injected clock is still a trusted input,
and a host can alter the database or run historical B1. This is not secure time,
anti-rollback storage, an independently attested clock, or a production service.
The existing historical CLI is not silently redirected. Explicit upgrade changes
the metadata version so historical B1 refuses the upgraded database. Fresh install
creates corrected metadata atomically, without an intermediate historical version.

## Gates before claims

Reproduce the old counterexample, then require refusal after expiry, wrong-token
access, missing-receipt access and injected operation failures; restart and
rollback must not revive access. Verify exact boundary expiry, catch-up behavior,
operator recovery during rollback, concurrent floor changes, unchanged proposal
atomicity and B1 receipts, source/wheel operation and frozen baseline hashes.
The separate U1 experiment remains evidence for historical B1 only unless the
corrected implementation is explicitly selected and tested under those UIDs.
