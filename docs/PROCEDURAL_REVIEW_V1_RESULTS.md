# P1.1 procedural verification results

The [source audit and P1.1 rules](PROCEDURAL_REVIEW_V1.md) distinguish borrowed
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
| Stale review packet, renewed notice, then fresh review | 12 | slot 10 | Yes | No | 1 |
| Both parties' appeal, notice/replies, remand, fresh approval | 24 | slot 20 | Yes | No | 1 |
| Terminal unresolved appeal and stay | 8 | Unexecuted | No | No | 0 |
| Correction without overwriting original record | 8 | slot 7 | Yes | No | 0 |

The timing control and noticed-review trace use the exact same task, evidence
access and 8/2/48 decision/observation/inspection ceilings. P1 adds procedure,
which delays completion from slot 3 to slot 6 and misses the deadline. No
resource coefficient was changed to create a benefit. The renewed-notice trace
declares 12 attempts and the longer combined-appeal trace declares 24 attempts
at creation; neither may be pooled as a matched
efficacy comparison with eight-attempt traces. All peer schedules continue
during motions, responses, rulings and refusals.

The earlier P1 release used 8 and 20 attempts for those two traces, completing
at slots 7 and 16. P1.1 does not silently replace those histories: every original
journal is frozen in `tests/data/procedure-v100-journals.json` and replays under
its original version. The new budget choices explicitly accommodate additional
procedure, not an apparent improvement. The delays are longer and remain late.

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

P1.1 adds 30 adversarial notice/appeal regressions and four replay-preservation
checks. New evidence (including paid observations), corrections and objections
invalidate old service, not just old reviewer packets. Both parties can preserve
separate petitions, all replies remain visible, and the disposition must identify
every petition/reply. Fresh service is refused when its full response opportunity
and a disposition cannot fit in the remaining budget. Exhaustion remains finite
and leaves unresolved review rather than automatic permission or denial.

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

Local validation on 2026-10-24 passed all 204 tests: the 96 baseline tests,
48 D1 tests, 26 retained/adapted P1 tests and 34 new P1.1 checks.
JSON integrity and local documentation links passed.
All eight procedural journals replayed, and independent output directories
produced identical artifacts. Source-archive verification and clean wheel
installation passed, including all 15 original comparisons, all 432 D1 runs,
the eight P1.1 traces and replay of both current and historical unresolved/appeal
records. The installed
24-event workshop demonstration retains head
`96baf584d179654e5abc836d127afdac80d916a08c05bcb482f732a01c0acb0a`.
No workshop or D1 source, fixtures, reference results or historical records were
changed by P1. Hosted verification also runs these checks on Linux Python
3.11/3.12/3.13 and Windows Python 3.12; its status is reported by the pull request.
