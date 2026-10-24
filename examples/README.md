# Reproduced examples

`proposal.json`, `proposal.schema.json`, and `testimony.json` are editable input examples. Use the actual IDs returned by your workshop rather than assuming an example's sequence number still applies.

The other files were reproduced locally with release 0.1.3 and protocol 2:

- `demo.md`: the five-tick narrative record, including the neighbor's counterstory.
- `demo-summary.json`: separate outcome, cost, and record measures.
- `replay.json`: a local deterministic replay receipt; not an independent attestation.
- `scripted-comparison.json`: fifteen exposed scripted runs with zero model calls.

Reproduce these in a fresh directory with `python scripts/reproduce.py .local/new-run`. The generated SQLite databases and current full event export remain local. Frozen 0.1.1 event exports in `tests/data/` are historical compatibility fixtures; their hashes differ from new protocol-2 runs and must not be regenerated with the new demo.

All accounts are authored fiction. All controller policies and fixtures are public. No result here supports a claim about model understanding, consciousness, independent judgment, or an empirical advantage from coaching or literature.
