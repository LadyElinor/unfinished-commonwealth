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
