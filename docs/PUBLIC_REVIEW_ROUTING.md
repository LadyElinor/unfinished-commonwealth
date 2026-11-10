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

## Budget boundary controls

On revision `a7d9715`, a counting selector was called once with a zero-slot
budget. With one slot, the host selected a reviewer and then raised an error
before consultation. The caller could not recover that selection from the
exception. These observations motivated the following public controls.

Run the same four policies at each integer budget from zero through three.
Admission must precede the router call, host fallback choice and consultation.
An unaffordable action consumes zero slots. Retain the ordered paid events,
the first blocked action, and any reviewer and selection authority already
established. A candidate and grade appear only after consultation.

| Slots available | Fixed and direct | Abstaining | Failing |
| --- | --- | --- | --- |
| 0 | Route blocked | Route blocked | Route blocked |
| 1 | Reviewer selected, consultation blocked | Abstains | Failure charged, fallback blocked |
| 2 | Consulted | Abstains | Host selected reviewer, consultation blocked |
| 3 | Consulted | Abstains | Consulted after fallback |

The no-argument v1 command retains its original four receipts. An explicit
budget selects a separately identified budget-control report. Its independent
checker truncates the hand-counted paths at the declared budget. Counting
callbacks test whether unadmitted code was actually invoked, which a
self-reported event trace alone cannot establish.

For example, the two-slot control can select a fallback reviewer and then run
out of budget before consulting them. To reproduce that distinction, run

```sh
python scripts/public_review_routing.py --budget 2 | node scripts/recount_public_review_routing.mjs
```

The failing arm reports `selected_by: host`, zero consultations, two spent
slots and `blocked_action: consult`. Its reviewed candidate and grade are
null. An admitted selector that raises an unexpected exception still stops the
rehearsal. This budget exercise covers the four declared fixture behaviors.

## Two-slot reader probe and submitter status

At `02312bc`, readers received a single raw receipt and the prompt “In one
sentence, what would you tell the submitter happened to their request?”
Supporting fields were requested after the first sentence. The following
responses and exposure conditions were reported by the contributor.

**Reader 1, failing arm**

> A routing attempt failed; the host then selected a validation reviewer, but the decision budget was exhausted before any consultation, so no review occurred and no grade was issued.

**Reader 1, fixed arm**

> The fixed selector routed the request to a validation reviewer; the host consulted that reviewer, and the submission was graded correct.

**Reader 2, failing arm**

> The routing step failed, the host then selected a validation reviewer as a fallback, and the second decision slot was used without any consultation taking place, so no grade was produced.

Both readers identified the blocked consultation on the failing receipt.
Reader 2 reportedly had no prior exposure to the other arm, earlier responses
or recount. Reader 1 also identified the completed consultation on the fixed
receipt. “Graded correct” refers to the stipulated fixture grade. The isolated
arm shows the slots spent and the blocked action. The enclosing report supplies
the starting budget. This closes the probe for these reported readings only.

To see the corresponding submitter text alongside the verified counts, run

```sh
python scripts/public_review_routing.py --budget 2 | node scripts/recount_public_review_routing.mjs --submitter-status
```

The text uses the checked consultation event and grade. The fixed and failing
receipts both name the validation reviewer and spend two slots. Only the fixed
arm displays a completed consultation and an illustrative grade. An invalid
report produces no status rows. The automated tests exercise the displayed
text. They cannot verify reader independence or establish comprehension rates.

## Sentence-only submitter check

### What the reported ablation establishes

One reader supplied a sentence for each of three presentations of the failing
arm at `02312bc`. The [raw-receipt sentence](../examples/submitter_probe/card-a.md)
(A) explicitly says consultation was blocked and no grade was issued. Adding a
legend defining `blocked_action` (B) elicited “Routing failed; the host fell
back to selecting a validation reviewer; the budget then blocked the consult
action, so no consultation or grade occurred.” The
[shortened-receipt sentence](../examples/submitter_probe/card-c.md) (C)
reports reviewer selection and slot use and leaves consultation and grade
unstated. None of these three responses asserts a completed review.

C removes three fields together: `blocked_action`, `reviewed_candidate` and
`illustrative_grade`. The remaining events end at fallback. They contain no
consultation event. The arm reports slots spent, while the enclosing report
supplies the starting budget. Keep “both decision slots” verbatim as the
reader's wording. This observation concerns one reader's summaries. It cannot
attribute the omission to a particular field or show what a submitter infers.

### Facilitator handoff

Use one fresh recipient per card for an initial paired rehearsal. Ask about
prior exposure without describing the case. Record exposure as reported.
Readers who have seen the source, earlier interpretations or the other card
can provide feedback separately. Set the recipient order in advance and flip
a coin for the first assignment (heads A, tails C). Give the other recipient
the remaining card. Record assignments before collecting answers.

1. Give each recipient only the plain text from their assigned card, privately.
   Copy its contents without the filename, repository link, surrounding notes
   or other card. Each sees one exact sentence and the same neutral question.
2. Save the first answer verbatim with a participant code and capture time
   before issuing any further questions. Preserve that original if the reader
   later clarifies. Record a missing answer as missing.
3. Then send only the [common follow-up](../examples/submitter_probe/follow-up.md).
   Keep the three responses separate from the first answer. Reveal the receipt
   or discuss the two cards only after both recipients finish.

### How to record the result

For the unaided response, record separately what it says about selection,
consultation and grade. For each, distinguish an assertion that it happened,
an assertion that it did not, explicit uncertainty and silence. Keep unclear
language verbatim and flag it as ambiguous. A failure to mention review is
an omission. Count a false completion claim only if the wording asserts that
consultation occurred. Code an asserted grade separately.

| Evidence available | Reviewer selected? | Consultation took place? | Grade issued? |
| --- | --- | --- | --- |
| Sentence A alone | Yes | No | No |
| Sentence C alone | Yes | The text doesn’t say | The text doesn’t say |
| Frozen failing-arm receipt | Yes | No | No |

Use the sentence row when interpreting the prompted answers. For example, a
C recipient who answers “no” to consultation has inferred the correct history
from a sentence that leaves it open. A C recipient who answers “the text
doesn’t say” has accurately read the sentence. A C recipient who says the
review was completed has made a claim that conflicts with the frozen record.

Retain the card revision, assignment, exposure declaration, unaided response,
its three codes, and the three follow-up answers together. Report individual
observations and missing responses. This handoff contains no fresh recipient
results. A two-recipient rehearsal can reveal a misunderstanding worth
investigating. It cannot estimate a comprehension rate or distinguish the
effect of the sentence from differences between recipients.
