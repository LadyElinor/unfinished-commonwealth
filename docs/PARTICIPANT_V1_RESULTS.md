# B1 implementation results and limits

Baseline: `efc78c42190aeb66796c60a2909b72aeb2907863`.
Candidate: [the frozen B1 design](PARTICIPANT_V1_DESIGN.md).
These are exposed implementation tests, authored alongside the code. They are
not held-out research, an independent security audit or a model comparison.

The 35 B1 tests exercise real loopback sockets and SQLite transactions. The
standard package check also runs the demonstration from an installed wheel
outside the checkout. Reproduce using:

```bash
python -m unittest discover -s tests -p test_participant_v1.py -v
python -m commonwealth.participant_v1 demo
python scripts/verify.py
python scripts/package.py .local/b1-release
```

Local validation on 2026-10-30 passed all **379 tests** (344 prior and 35 B1),
packaged JSON/documentation checks, source-distribution verification and a clean
offline wheel installation. The installed check also reproduced all earlier
study matrices and replay gates. No package-version change or release is implied.
The 69 baseline runtime/example/test-data files retain their original hashes.

## Observations

| Gate | Observed result |
| --- | --- |
| Valid participant | One authenticated proposal; approval/execution require separate host calls |
| Concurrent retries | Six concurrent identical HTTP requests return identical receipts with one proposal and one attempt |
| Transaction failures | Injected failures at event, snapshot, quota, attempt and receipt writes roll back all related state |
| Lost response | A response dropped after commit yields `UNKNOWN`; restart, receipt lookup and identical retry preserve the one original proposal |
| Authority forgery | Supplied actor/action, extra fields and unknown protocols are refused; instructions in purpose remain stored data |
| Staleness and retirement | Changed journal head requires a fresh view; old-generation capabilities cannot submit or retrieve receipts |
| Expiry and revocation | Both deny cached receipt redelivery; the operator can still inspect locally |
| Clock rollback | The retained high-water mark survives restart; access/issuance are refused while operator revocation works |
| Accounting | Malformed authenticated submissions and semantic refusals count; identical receipt redelivery does not; keeper halt survives exhausted participant quota |
| Transport | Wrong host, Origin, duplicate headers, transfer encoding, oversized/truncated bodies, redirects and forbidden routes are refused |
| Credentials | Exclusive file creation, POSIX mode, failed-write rollback, no automatic token inclusion in DB, event journal, audit or server output |
| Local consistency | Audit detects attempt count mismatch and missing accepted receipts; original workshop replay still verifies |

The demonstration records five events: genesis, proposal, host approval, host
execution and observation. An identical submission adds no event. Local
task-plus-submit latency is measured with a monotonic performance counter and
reported per run; it is deliberately not pinned to one timing value or mixed
with earlier synthetic decision-slot costs.

## Negative controls retained

1. A copied bearer successfully submits as the same scoped worker. The credential
   authenticates possession, not the person or organization using it.
2. A DB copied before submission accepts the same token/request in both copies.
   Atomic idempotency is local to one retained database, not a global guarantee.
3. A host rewrites an event, snapshot and receipt into a consistent replacement
   history; replay and audit pass. These checks cannot attest against the host.
4. An authenticated `zero-fill` proposal, separately approved and executed by the
   host, remains incorrect on the missing-data scenario. Transport reliability
   is not evidence quality, discernment, learning or institutional legitimacy.

## What remains open

B1 makes the separately operated proposal interface usable, but does not set up
OS accounts, container isolation, TLS, independently controlled issuers, signed
external evidence or real-world effect adapters. Its host and clock remain
trusted. There is no demonstration of a hostile participant isolated at the OS
level, no provider integration, and no efficacy or fairness estimate.

The next useful gate is an independently operated participant under an explicit
OS access policy, with measured attempts, uncertainty and end-to-end cost on a
fixed task. Any model study still needs its own authorization, frozen analysis
plan and independently supplied unseen cases. Adding more names or more curated
examples would not supply that evidence.

The preservation manifest in `tests/data/participant-preserved-baseline.json`
binds every previously tracked runtime file, example and test-data record to
its baseline SHA-256. Historical implementations, summaries and testimony are
not reclassified or rewritten by B1. See [usage and trust](PARTICIPANT_V1.md).
