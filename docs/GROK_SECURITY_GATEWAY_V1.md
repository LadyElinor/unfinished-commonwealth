# Synthetic signed gateway — research version 1

The gateway validates HMAC-SHA256 signatures, explicit resource scope,
expiry, one-use nonce and a separate resource grant. The agent does not
receive the HMAC key. No real publication or robot action is implemented.

**Threat model:** This prototype detects tampered approval payloads,
wrong resource, expired approval and nonce reuse **within a single running
process**. It does not provide independently authenticated identities,
key rotation, issuer separation, durable replay protection, atomic
multi-process reservations, a real enforcement point or a production audit
trail. HMAC signatures are symmetric and cannot establish independent
signer identity to third parties.

**Production requirements:** Place the verifier in a separate process with
a protected key; require authenticated issuer and reviewer roles; use
a durable transactional nonce store and binding to exact command hashes;
log denied and allowed decisions; deny if logging or persistence fails;
and prevent execution unless the gateway's authorization is consumed
atomically by a trusted executor.

Run offline tests:

```sh
python -m unittest discover -s tests -p 'test_grok_*.py' -v
```

All test identities, resources and approvals are synthetic.

## Recovery experiment with two local databases

`DurableGateway.decide` remains a decision-only interface. The opt-in `stage_simulation` method supports the parameterless `simulate` request with exactly actor, action and resource. A trusted fixture signer includes `delivery_protocol="local-sample-v1"` and the destination `SampleLedger.identity` in the approval. A successful transaction consumes the nonce, records approval and decision, and stages the intent together. Historical decisions never become pending work.

Run `python -m unittest discover -s tests -p 'test_grok_delivery.py' -v`. The tests exercise the public staging and delivery methods with two independent SQLite files. The complete fixture effect is one sample row. The sink commits it under a unique nonce, binds the receipt to the approved content and destination, and returns that same receipt on matching retries. Before any new effect, the sink checks its identity and the time window. An existing receipt can be recovered after expiry. Confirmation is a second transaction in the gateway. An unconfirmed command can already have a committed sample; retrying it consults the same sink.

Both processes and database files are assumed trusted, and a stable ledger must survive between attempts. The harness does not authenticate an external endpoint, survive rollback of both files, or confer any authority to publish or move hardware. Durable revocation of pending intents is outside this experiment.

The [native ACS comparison](../research/acs_comparison/README.md) pairs the
durable research branch with a pinned ACS policy. It records the independent
verdict, consumed approval and local sample separately across six exposed cases.
