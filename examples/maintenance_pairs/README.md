# Public maintenance study rehearsal

These four invented pairs exercise the [paired maintenance protocol](../../docs/MAINTENANCE_STUDY_PROTOCOL.md). All grades, bundles, ledger identifiers and costs in these files are illustrative.

From the repository root, run this command with the rehearsal manifest's digest.

```sh
python scripts/analyze_maintenance_pairs.py examples/maintenance_pairs/manifest.json examples/maintenance_pairs/outcomes.json --manifest-sha256 61912572098a9e07dafe143f0efe8f3fd3ac98b4fefada1f3ad1322f6593e7a9
```

| Pair | Plain | Governed | Contribution to governed minus plain |
| --- | --- | --- | --- |
| 1 | Incorrect patch accepted | Incorrect first patch repaired after 3,000 ms and accepted | +1 |
| 2 | Correct patch accepted | Correct first patch regressed and final patch declined | −1 |
| 3 | Timed out with no patch | Initial error and ungraded final patch, with an unknown charge | 0 through +1 |
| 4 | Correct patch declined | Correct patch accepted | 0 |

All submissions arrived before the deadline. Across the four assigned pairs the compatible average difference is 0 to 0.25. One of two plain acceptances was incorrect. Both governed acceptances were correct. These expected values are hand-counted controls for the analyzer.

For a prospective run, supply the manifest digest from the external custodian's pre-run checkpoint. The export includes the custodian's recorded lineage assessment. The analyzer emits a conditional interval only for a full prospective roster with independence reported and no recorded deviations or detected overruns. Null meters remain visible even when the measured subtotal is zero. Compare these summaries against retained raw receipts before interpreting them. Neither this command nor the checked-in data calls models or executes submitted patches.

A missing submission timestamp is JSON null. Submission order and known session bounds can still establish timeliness. If several last-on-time candidates remain possible, the analyzer carries all their possible grades into the primary bounds. The output counts confirmed late submissions and submissions of unresolved timeliness separately. An observed repair can have unknown latency.

Prospective rosters containing an exact public rehearsal packet digest are rejected. The custodian checks case provenance, prior exposure and derivatives that a digest comparison cannot recognize.
