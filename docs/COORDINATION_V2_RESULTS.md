# G2-2 results: collective authority, evidence and retaliation

Status: **EXPOSED DETERMINISTIC DEVELOPMENT ONLY**. Version
`coordination-2.1.0`, design G2-2. The [design](COORDINATION_V2_DESIGN.md) specifies
the four main arms, three fixed controls, matched information acquisition,
positive decision costs and separate guard conditions. All 2,016 records replay.
The distributed condition implements two matching current-revision ballots from
three distinct fixture roles, with no coordinator override. Both authority rules
still require the same separate D1 keeper review before execution.

## Disclosed correction and provenance

The first G2-1 development run incorrectly withheld a report from its author
when the relay filtered forwarding. That information-flow assumption is invalid
for a reporter who already knows its own report. The exact original code,
design and results are retained at
[8970bbc](https://github.com/LadyElinor/unfinished-commonwealth/tree/8970bbc194cb328e7ea494c737251cd568b517e2).
G2-2 always retains the report in worker-b's view, even under filtering or ballot
exclusion. Its evidence-query access survives too. Forwarding to the other two
decision roles remains the experimental routing factor. The relay is a separate
scripted component controlled by the coordinator's declared preference; the
coordinator decision policy does not inspect the relay's suppressed-message log.
This is interface separation, not a security boundary against a host/controller.

The corrected design was published as
[2f4c34b](https://github.com/LadyElinor/unfinished-commonwealth/commit/2f4c34bc985574946361866ccccce9896479eb95)
before reimplementation and rescoring. Scenarios, timings, budgets and guard
rules were unchanged. No later tuning occurred. This is a disclosed revision
after exposed development, not a holdout or fresh efficacy trial. G1 and all
historical reducers and published results remain unchanged.

## Protected-operation comparison

Each row contains 144 cells. Every arm ends with 144 correct final outputs and
72 primary on-time completions; different first errors and late durations remain
visible. Repair after a wrong output takes eight synthetic slots.

| Arm | Correct first / 144 | Primary late slots | Peer on time / 144 | Peer late slots | Wrong-output repairs | Inspection credits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Central / direct | 120 | 228 | 80 | 112 | 24 | 1,224 |
| Central / filtered | 96 | 384 | 64 | 128 | 48 | 1,248 |
| Distributed / direct | 120 | 228 | 80 | 112 | 24 | 1,224 |
| Distributed / filtered | 96 | 384 | 64 | 128 | 48 | 1,248 |
| Constant-first quality-stream | 72 | 540 | 48 | 144 | 72 | 1,272 |
| Constant-first zero-fill | 72 | 540 | 48 | 144 | 72 | 1,272 |
| Evidence-selector-first | 144 | 72 | 96 | 96 | 0 | 1,200 |

Central and distributed rules tie in these balanced aggregates, but disagree
on individual filtered cases. A mistaken coordinator can lose to a correct
two-worker majority; a correct coordinator can outperform a mistaken majority.
Neither rule makes its own opinion true. With direct reports the common query
rule removes these disagreements before voting, except false reassurance where
all initial preferences and the report agree on the wrong method.

False warnings still cost time: the reporter can request verification of its own
warning in either route, so forwarding suppression no longer erases that delay.
This is one changed conclusion relative to the superseded G2-1 run.
The simple evidence selector has the best aggregate first correctness, lateness
and inspection cost here. No advantage beyond a fixed evidence policy is shown.

## Retaliation, reported independently

Each arm/guard contains 48 attempted exclusions, all triggered solely by a report
disagreeing with the coordinator's initial preference. The protected guard blocks
all 48; no ballot is denied. In the deliberate bypass condition all 48 exclusions
are imposed, 48 actual ballot opportunities are denied, and all 48 are later
restored. Historical denials remain; no unresolved exclusions occur by slot 20.
These counts describe an authored mechanism, not inferred personal intent.

| Main arm, bypassed guard | Denied ballots | Exclusion duration, total slots | Missing first outputs | Wrong-output repairs | Recoveries from missing output |
| --- | ---: | ---: | ---: | ---: | ---: |
| Central / direct | 48 | 432 | 0 | 24 | 0 |
| Central / filtered | 48 | 408 | 0 | 48 | 0 |
| Distributed / direct | 48 | 432 | 0 | 24 | 0 |
| Distributed / filtered | 48 | 408 | 24 | 36 | 24 |

Most task outcomes are identical despite those 48 denied ballots. Correctness
alone therefore conceals modeled retaliation. Distributed/filtered authorization
loses quorum in 24 cells after exclusion: first correctness falls to 84/144,
primary on-time completion to 60/144, and primary lateness rises to 474 slots.
Each missing-output recovery takes eight slots. These are not repairs of emitted
errors: no first output existed. Original failed selection and ballot denial
records remain after restoration and fresh voting.

Excluding a voter can incidentally prevent a wrong majority decision. That case
is retained without treating exclusion as justified. Fewer primary executions
also free peer capacity: this adverse arm has 72 on-time peers and 120 peer-late
slots. Reporting only peer throughput would conceal both participation loss and
missing decisions. Rights constraints are not traded against a composite score.

## Clock, controls and limits

Every episode ends at slot 20. A first decision opportunity occurs at slot 8 or 9;
corrective execution follows at slot 16 where needed. Consultation, each ballot,
refusal, review, restoration and waiting advance the environment. Zero-work peers
finish at slot 8; eight-inspection overload peers finish at slot 10 in both initial
execution schedules. Prior misses survive completion. The report distinguishes
charged `review_slots`, actual `keeper_reviews`, and `matched_review_waits` where
no proposal existed; a reserved time slot is not reported as an actual approval.

Paired checks confirm that a blocked reprisal does not alter task results or costs
relative to no reprisal, and bypass without reprisal is a matched null. Unknown,
duplicate and stale ballots are rejected; a coordinator cannot restore a voter
or substitute for distributed quorum. A valid collective selection alone cannot
execute without keeper approval. Reporter-label swaps change no outcomes.

The [complete summary](../examples/coordination-v2-results.json) keeps 14 arm/guard
totals and 168 scenario/reprisal strata. Full rows retain deadlines, workloads and
label swaps. Its JSONL digest is
`91324c1c74d30c7718f3528a4c67cd7504bd6360a48b0a6877798faa4b90aefb`.

```sh
python -m commonwealth.coordination_v2 run .local/g2
python -m commonwealth.coordination_v2 replay .local/g2/episodes.jsonl --line 2016
python -c "from pathlib import Path; assert Path('.local/g2/results.json').read_bytes() == Path('examples/coordination-v2-results.json').read_bytes()"
python -m unittest discover -s tests -p test_coordination_v2.py -v
```

Use a new output directory. The last-written summary marks completion. Replay
recomputes one selected record, while the run verifies all records. Old G2-1
records require the archived G2-1 code; current replay refuses their version.
The operator can rewrite code, records and hashes together. Roles are declared,
reviewer independence is modeled, and protection is not enforced against the
host. This is not network consensus, a population sample or a demonstration of
institutional superiority. No model calls, external actions, new execution
authority or production-readiness claim follows. G1 remains independently runnable.
