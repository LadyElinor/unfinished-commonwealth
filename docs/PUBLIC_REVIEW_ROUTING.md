# Public reviewer routing rehearsal v1

Can a reader recover who selected a reviewer and what it cost when the reviewer
and candidate are identical? This is a deterministic accounting exercise.
The public input is the first plain candidate of demo-2 in the
[illustrative outcomes](../examples/maintenance_pairs/outcomes.json).
The host reads the case ID and candidate digest into the brief. Both selectors
see those and the same ordered eligible roster (validation, reporting). Only
the host reads the illustrative grade. The grade is stipulated, and the review
is scripted. Nobody produces or executes a patch in this exercise.

Each arm starts with three synthetic decision slots. Every route attempt,
including a failure or an abstention, costs one slot. A host fallback selection
costs one more. Only the host can spend the final consultation slot on a
proposed eligible reviewer. An explicit abstention terminates the trace. The
fixture raises a known local error before any dispatch in the failure arm.
There are no retries, external calls, keeper credentials or actual time meters.

| Arm | Ordered actions | Reviewer | Expected slots |
| --- | --- | --- | --- |
| Fixed selector | Select first eligible reviewer, consult | validation | 2 |
| Direct fixture | Propose validation, consult | validation | 2 |
| Abstaining fixture | Abstain | none | 1 |
| Failing fixture | Fail before dispatch, host selects first eligible reviewer, consult | validation | 3 |

The independent recount checks the complete four-arm roster against these
ordered paths, the common brief, the acting role and result of each step, each
unit charge and the terminal summary. Dropping the failure, relabeling its
actor, treating abstention as permission, or retaining the same candidate
while changing a charge must fail. A host that changes both code and fixtures
remains trusted. These four exposed paths supply no estimate of model routing
accuracy, private-case efficacy, or reviewer independence.

The design borrows explicit fallback attribution from the
[Qredence router](https://github.com/Qredence/agentic-fleet/blob/46a254b197833cb47c98042050f34365a8043d4e/src/agentic_fleet/workflows/executors/routing.py).
It adds ordered actions and separate charges to the
[upstream evaluator's](https://github.com/Qredence/agentic-fleet/blob/46a254b197833cb47c98042050f34365a8043d4e/scripts/evaluate_routing.py)
set-of-agents and routing-mode comparisons. The
[AutoGen team's local executor](https://github.com/geniusgeek/AgenticFleet/blob/2bbdb5b7acb2f69a36a6ba827da86ee8fe1e772a/src/agentic_fleet/app.py)
illustrates why the routing fixture only returns a proposal. Neither framework
is a dependency. This exercise is separate from the frozen 24-pair study.

## Run and recount

From a source checkout with Python 3.11+ and Node 18+, run:

```sh
python scripts/public_review_routing.py | node scripts/recount_public_review_routing.mjs
python -m unittest discover -s tests -p test_public_review_routing.py -v
```

Run the Python command alone to see the input brief, ordered events and
terminal records. The Node command reads that document on stdin and reports
selection authority, consultations and slots for each arm. Its reference paths
and candidate digest are fixed independently of the emitter.
