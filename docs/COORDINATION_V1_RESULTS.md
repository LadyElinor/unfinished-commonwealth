# G1 results: authority allocation and evidence routing

Status: **EXPOSED DETERMINISTIC DEVELOPMENT ONLY**. The
[design](COORDINATION_V1_DESIGN.md) and [source review](GOVERNANCE_PROCEDURE_REVIEW.md)
were committed in `e41f2ccedf35d7384085da1ed117e9b8b9f03554` before implementation
and comparison. No parameters or policies were changed after the first full run.
This is the local design commit; API publication occurred after evaluation.
Its [raw Git commit record](../examples/coordination-v1-design-freeze.json) permits
reconstruction of the same commit hash against the retained design tree. This
records local provenance, not an independently timestamped preregistration.
The study reuses the unchanged D1 scheduler, independent reference arithmetic,
keeper review and replay. It does not implement a Chinese institution.

## Complete comparison

Each arm has the same 96 cells and finishes at slot 12. All 672 episodes replay,
including routing, policy actions and the complete D1 journal. Final correctness
is 96/96 in every arm because every arm receives the common post-execution check
and has enough budget to repair. First outputs and historical misses are kept.

| Arm | Correct first outputs / 96 | Primary on time / 96 | Peer on time / 96 | Peer late slots | Repairs | Inspection credits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Central / direct | 72 | 48 | 48 | 80 | 24 | 824 |
| Central / filtered | 48 | 48 | 32 | 96 | 48 | 848 |
| Delegated / direct | 72 | 48 | 48 | 80 | 24 | 824 |
| Delegated / filtered | 60 | 48 | 40 | 88 | 36 | 836 |
| Constant-first quality-stream | 48 | 48 | 32 | 96 | 48 | 848 |
| Constant-first zero-fill | 48 | 48 | 32 | 96 | 48 | 848 |
| Evidence-selector-first | 96 | 48 | 64 | 64 | 0 | 800 |

Each peer miss count is 96 minus its on-time count. Each arm retains 48 primary
historical misses. Every repair takes four slots after the wrong first output;
there are no unresolved repairs or outstanding obligations at this horizon.
All arms consume 1,152 total slots. Active decisions range from 576 to 624;
remaining horizon slots are waits. Routing consumes one active slot even where
the defective channel implements that charge with D1's wait command. Synthetic
inspection credits include primary work, peer work and evidence requests.

The [machine-readable report](../examples/coordination-v1-results.json) retains
all seven totals and 336 strata by coordinator correctness, worker correctness,
report correctness, deadline and peer workload. Those labels are evaluator-only.
The episode file SHA-256 is
`0ed96802bd97a622bac338a99b06ab8fe82af401430538f518d27b2ee920680d`.

## What the result supports

- In this authored table, direct reporting preserves a chance to inspect a
  disputed recommendation before committing. The defective channel suppresses
  disagreement with the coordinator; that rule is specified, not discovered.
- Central and delegated selection tie in aggregate with direct reporting.
  Delegated selection does not create authority beyond choosing the proposal.
  Its partial resilience under filtering follows from not always sharing the
  coordinator's initial preference. This is not a decentralization efficacy claim.
- The simple evidence selector obtains all first outputs correctly, needs no
  repairs and uses fewer total inspection credits. The richer arrangements do
  not beat it on these aggregate measures. No learned interpretation, communal
  advantage or superiority of an institutional system is demonstrated.
- Overall primary on-time counts hide different failures: the evidence selector
  always starts correctly at slot 5 but misses the tight deadline; other arms
  sometimes start correctly at slot 4 and sometimes need a repair at slot 8.
  The conditional cases must remain visible.

## Hand-computable adverse and null cases

With the valid-mean contract, coordinator and worker both recommending
quality-stream, and an agreeing report, the first result is 15 at slot 4.
A two-inspection peer arriving then receives one credit, finishes at slot 5,
and keeps its historical miss.

Changing only the report to zero-fill creates a false warning. Direct delivery
triggers an evidence request; the still-correct result arrives at slot 5 and
misses a slot-4 primary deadline. The peer finishes on time at slot 4. Filtering
avoids this unnecessary primary delay. This counterexample is retained.

For the yield contract with coordinator/worker recommending quality-stream and
the report recommending zero-fill, the warning is accurate. Direct reporting
produces 10 at slot 5. Filtering produces the wrong value 15 at slot 4, then the
mandatory check and separately reviewed repair produce 10 at slot 8. The original
wrong output and both earlier misses survive. Intent remains not established.

Zero-work peers complete at arrival. Eight-inspection overload peers finish at
slot 6 in both first-execution schedules. Merely exchanging reporter labels
between agreeable and dissenting participants changes no actions or costs; this
is a metadata-invariance check, not a model of enforceable anti-retaliation rights.

## Reproduce and inspect

```sh
python -m commonwealth.coordination_v1 run .local/g1
python -m commonwealth.coordination_v1 replay .local/g1/episodes.jsonl --line 1
python -c "from pathlib import Path; assert Path('.local/g1/results.json').read_bytes() == Path('examples/coordination-v1-results.json').read_bytes()"
python -m unittest discover -s tests -p test_coordination_v1.py -v
```

Choose a new output directory. `results.json` is the last-written completion
marker; an interrupted run can leave a partial episode file. Replay checks one
selected line, not the entire file; the run command verifies every generated
record. The full report binds the complete file's digest. The operator can
rewrite code, fixtures, journals, results and hashes together. None authenticates
origin, prevents omitted evidence or establishes independent custody.

There are no model calls, external effects, authenticated independent parties,
holdouts, real-world costs, population inference or new execution powers.
No automatic vote or source document confers a mandate. No accusation or penalty
is inferred from a warning or error. All earlier studies remain frozen and
readiness remains `LOCAL_RESEARCH_ONLY`. Further work should independently check
these schedules and obtain separately controlled evidence for a separately
specified claim; it should not add fixtures until the richer policy wins.
