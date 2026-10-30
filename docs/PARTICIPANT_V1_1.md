# B1.1 clock-floor correction and operator migration

**Use `commonwealth.participant_v1_1` for new participant hosts.** The historical
`commonwealth.participant_v1` module remains available only to reproduce B1,
including its expired-bearer revival counterexample. It is not silently patched.
The package version remains 0.1.3; the boundary version is `participant-1.1.0`.

The wire protocol, participant request files and tables are unchanged. B1.1
commits a validated clock observation before authentication and operation work.
A refused expired token, missing receipt or failed issuance no longer discards
that observed time. Workshop mutations and quota/receipt writes remain atomic
in a separate transaction. See [design and counterexample](PARTICIPANT_V1_1_DESIGN.md).

## New workshop

Create a workshop using the ordinary CLI, then select B1.1 explicitly:

```bash
python -m commonwealth init .local/workshop.sqlite
python -m commonwealth.participant_v1_1 install .local/workshop.sqlite
python -m commonwealth.participant_v1_1 issue .local/workshop.sqlite .local/participant-token
python -m commonwealth.participant_v1_1 serve .local/workshop.sqlite
```

Use the actual printed loopback URL for `task`, `submit` and `receipt` as in
[the B1 operator guide](PARTICIPANT_V1.md), replacing its module name with
`commonwealth.participant_v1_1`. No automatic credential rotation occurs.

## Existing B1 database

Stop the historical participant server and other operators before migration.
Retain any backup under the same protected access policy as the live database.
Then run:

```bash
python -m commonwealth.participant_v1_1 upgrade .local/workshop.sqlite
python -m commonwealth.participant_v1_1 audit .local/workshop.sqlite
python -m commonwealth.participant_v1_1 serve .local/workshop.sqlite
```

Upgrade verifies the existing journal, validates current time and commits a
new boundary metadata version plus clock floor. It retains the instance,
capabilities, receipts, attempts and workshop history. It is idempotent.
Historical B1 operator commands now refuse this database, including an old
server's subsequent requests. Use B1.1 for revocation and operator receipt
inspection too. The original workshop keeper CLI still works independently.
Unknown versions and clocks below the retained floor refuse migration.

Fresh installation creates the tables and corrected metadata in one transaction.
An interrupted installation leaves either no installed boundary or the corrected
version, never an intermediate historical B1 boundary. There is no downgrade
command. A copied old database remains independent and is not protected by
migrating another copy. Earlier observations B1 lost cannot be reconstructed.

## Exact scope

An operation observes time at its initial verified transaction and durably
commits that floor before any operation work. After acquiring the second lock,
it observes time again so waiting cannot authorize an expired token at an old
time. A savepoint separates operation writes from that second clock update:
refusal rolls back only operation writes, then commits the new floor. No time is
inferred for input rejected before transaction entry. If the floor cannot be
persisted, no operation success is returned. Abrupt process loss before a
commit can lose that uncommitted observation; the earlier committed floor
survives. SQLite/system failure is not proof that a returned UNKNOWN operation
had no effect; use the original receipt/identical-retry procedure.

Revocation, audit and operator receipt inspection work during rollback without
lowering the floor. These are host-only operations, not new participant powers.
A bad forward clock can deny service until time catches up. The host, OS clock,
SQLite filesystem durability and protected deployment remain trusted. The host
can rewrite the database. This is not secure time or rollback-resistant storage.

Run the exposed local checks:

```bash
python -m commonwealth.participant_v1_1 demo
python -m unittest discover -s tests -p test_participant_v1_1.py -v
python scripts/verify.py
python scripts/package.py .local/b11-release
```

The demo uses real loopback HTTP but an injected clock. The separate U1 hosted
UID observations continue to exercise historical B1, not B1.1. Portable B1.1
checks do not establish a new cross-UID result, production security, model
competence or hidden-reference evaluation. Public fixture exposure remains.

## Recorded validation (2026-10-30)

Local Linux checks pass **403 tests**: all 383 prior tests and 20 B1.1 tests.
The source-distribution checks and clean offline wheel installation pass,
including the installed B1.1 loopback/expiry/restart demonstration. The prior
preservation manifests pass without modifying their tracked runtime, examples
or test data. Independent review also reproduced the original B1 counterexample
and checked a delay across the two transactions that advances time past expiry.

The crash check injects an exception after a successful clock commit. It is not
an actual process kill, storage power-loss or kernel-failure test. All scenarios
are exposed development tests. Hosted results belong to the exact published
commit and are recorded in PR #1, not inferred from these local results.
