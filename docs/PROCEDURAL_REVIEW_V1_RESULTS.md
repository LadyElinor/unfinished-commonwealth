# P1 procedural verification results

The [source audit and P1 rules](PROCEDURAL_REVIEW_V1.md) distinguish borrowed
procedural ideas from this simulator's own decisions. The Congressional Record
was accessed through its official GPO mirror; federal rules through U.S. Courts.
No scraped political assertions or court testimony become research ground truth.

## Exposed traces

These eight authored traces exercise procedure. They are not a new efficacy
sample or a replacement for the 432 frozen D1 runs. Every journal replays; every
in-episode refusal and actual simulated cost survives. The
[machine-readable report](../examples/procedure-v1-results.json) includes every
trace, its budgets, actions, outcomes, unresolved obligations and replay digest.

| Trace | Attempts | Primary completion | Correct | On time | Refusals |
| --- | ---: | ---: | --- | --- | ---: |
| D1 timing control | 8 | slot 3 | Yes | Yes | 0 |
| Notice and reasoned review | 8 | slot 6 | Yes | No | 0 |
| Procedure followed, wrong method approved | 8 | slot 6 | No | No | 0 |
| Contested denial | 8 | Unexecuted | No | No | 1 |
| Stale review packet, then fresh review | 8 | slot 7 | Yes | No | 1 |
| Appeal, remand, fresh revision and approval | 20 | slot 16 | Yes | No | 1 |
| Terminal unresolved appeal and stay | 8 | Unexecuted | No | No | 0 |
| Correction without overwriting original record | 8 | slot 7 | Yes | No | 0 |

The timing control and noticed-review trace use the exact same task, evidence
access and 8/2/48 decision/observation/inspection ceilings. P1 adds procedure,
which delays completion from slot 3 to slot 6 and misses the deadline. No
resource coefficient was changed to create a benefit. The longer appeal trace
declares its 20-attempt ceiling at creation; it must not be pooled as a matched
efficacy comparison with eight-attempt traces. All peer schedules continue
during motions, responses, rulings and refusals.

The wrong-method trace is intentionally retained: notice, evidence references
and reasons do not verify a substantive conclusion. A valid procedural grant
can authorize zero-fill on a valid-mean task and produce the wrong answer.
The independent arithmetic evaluator still marks that output incorrect.

## Regression coverage and limits

The added regressions test missing notice, response-window boundaries, silence,
opposition, specific objections, missing reasons, stale packets, missing evidence,
linked context, role separation, amended requests, old-ruling appeals, explicit
stays, unavailable reviewers, expiry, affirmance of denial, remand, correction,
exhaustion, read-only views and tampered replay. Three evasion routes are explicitly
blocked: amendment cannot extinguish a timely appeal of an older ruling, and
amendment cannot bypass an unlifted stay on the current revision. A denial also
cannot be bypassed by filing a parallel motion for the same unexecuted work.

Claims remain limited to local procedural invariants. There is no model call,
legal-compliance certification, operator authentication, independent reviewer
verification, evidence-admissibility classifier or proof of fair reasoning.
The source-inspired safeguards impose real modeled delay; they are opt-in and
do not replace the previously authorized workshop or D1 controls.

Reproduce with:

```bash
python scripts/verify.py
python -m commonwealth.procedure_v1 run .local/procedure-reproduction
python -m commonwealth.procedure_v1 replay .local/procedure-reproduction/journals/terminal-appeal.json
python scripts/package.py .local/procedure-package
```

Local validation on 2026-10-24 passed all 170 tests: the 96 baseline tests,
48 D1 tests and 26 P1 tests. JSON integrity and local documentation links passed.
All eight procedural journals replayed, and independent output directories
produced identical artifacts. Source-archive verification and clean wheel
installation passed, including all 15 original comparisons, all 432 D1 runs,
the eight P1 traces and replay of the terminal unresolved appeal. The installed
24-event workshop demonstration retains head
`96baf584d179654e5abc836d127afdac80d916a08c05bcb482f732a01c0acb0a`.
No workshop or D1 source, fixtures, reference results or historical records were
changed by P1. Hosted verification also runs these checks on Linux Python
3.11/3.12/3.13 and Windows Python 3.12; its status is reported by the pull request.
