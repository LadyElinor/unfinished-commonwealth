# Reproduced examples

`proposal.json`, `proposal.schema.json`, and `testimony.json` are editable input examples. Use the actual IDs returned by your workshop rather than assuming an example's sequence number still applies.

The other files were produced locally by the initial implementation:

- `demo.md`: the five-tick narrative record, including the neighbor's counterstory.
- `demo-summary.json`: separate outcome, cost, and record measures.
- `replay.json`: a local deterministic replay receipt; not an independent attestation.
- `scripted-comparison.json`: twelve exposed scripted runs with zero model calls.

Reproduce these in a fresh directory with `python scripts/reproduce.py .local/new-run`. The generated SQLite databases and full event export remain local. They are not included in the source tree because the text outputs and deterministic procedure suffice to reproduce them.

All accounts are authored fiction. All controller policies and fixtures are public. No result here supports a claim about model understanding, consciousness, independent judgment, or an empirical advantage from coaching or literature.
