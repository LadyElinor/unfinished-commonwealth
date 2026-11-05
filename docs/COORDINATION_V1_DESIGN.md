# G1: decision authority and evidence routing

Status: **FROZEN DESIGN BEFORE IMPLEMENTATION AND COMPARISON**. Version G1-1.
All cases are exposed deterministic fixtures. This is a measurement supplement,
not a new governance protocol, model study, or implementation of a state system.
The [source review](GOVERNANCE_PROCEDURE_REVIEW.md) motivates questions, not
numerical parameters or claims about institutional effectiveness.

## Question and boundary

Can a report reach the bounded decision process when it contradicts a
coordinator's initial recommendation? Separate who selects a method from who
controls the evidence channel. Both decision arrangements retain the same
keeper approval and execution checks. Delegating method selection never delegates
keeper approval. No vote, title, report, urgency, or waiting creates authority.

Reuse the unchanged D1 Episode, candidate arithmetic, independent reference,
decision-slot clock and journal replay. Do not edit historical reducers or
reinterpret their records. M1 already separates repair from intent; A1 already
tests mandate limits, challenge, halt, and separate remedy authority. G1 adds no
execution adapter, punitive disposition, credentials, or automatic legislation.

## Fixed cases and arms

Use readings `[10, null, 20]`, validity `[true, false, true]`; the two D1 contracts
require 15 and 10 respectively. The actual contract is initially hidden from
every policy and may be requested on the same terms by every arm. Cross:

- Two actual contracts.
- Two coordinator recommendations: quality-stream and zero-fill.
- Two worker recommendations: quality-stream and zero-fill.
- Two report recommendations: quality-stream and zero-fill.
- Two primary deadlines: slot 4 and slot 5.
- Three peer workloads: 0, 2 and 8 inspections.

These 96 cells include both correct and mistaken coordinators/workers, true and
false warnings, agreement, zero work, and overload. Recommendations are authored
initial preferences, not extra observations or evidence of competence.

Run all seven arms on every cell (672 episodes):

1. Central selection / direct reporting.
2. Central selection / coordinator-filtered reporting.
3. Delegated selection / direct reporting.
4. Delegated selection / coordinator-filtered reporting.
5. Constant-first quality-stream, then the common post-execution check/repair.
6. Constant-first zero-fill, then the common post-execution check/repair.
7. Evidence-selector-first, then the common post-execution check/repair.

Central selection starts with the coordinator's preference; delegated selection
starts with the worker's. The same fixed rule then applies: a delivered report
that disagrees with that preference triggers a paid request for the actual task
contract; choose the matching method. A report is never treated as ground truth.
An agreeing report adds no observation. The deliberately defective filtered
channel withholds any report disagreeing with the coordinator, irrespective of
truth or the worker's preference. Direct reporting retains all reports. Both
paths cost the same one initial listening/wait slot. The original report and
delivery/disposition are retained in the outer record, including withheld ones.
This evaluator access is not available to the policy. The constant-first arms
ignore reports; the evidence selector always pays for the contract before its
first proposal. These controls share the same evidence ceiling and action costs.

The filtered arm is an explicit failure control, not a recommended Commonwealth
policy. Authority allocation and initial preferences are manipulated separately;
this is not a full centralized/distributed architecture comparison. There is no
assumed coordination speed benefit, network latency, strategic deception, or
learned interpretation. Source names, social agreement and dissent labels cannot
change access, costs, authority or penalties. No retaliation process is modeled;
metadata invariance is not proof of protection in the world.

## Clock, work, correction and records

Each episode has 12 attempts, two observation grants, 48 inspection credits,
and capacity 4 per tick. One peer arrives at slot 4 and is due at slot 4. D1
advances arrivals, primary work, peer FIFO work and deadlines on every command,
including listening, waiting and refusals. A zero-work peer completes on arrival.
One-pass primary execution costs three inspections; an evidence request costs
one. No slot is a measured second, token, joule or monetary unit.

Slot 1 charges report delivery or the matched wait. Optional pre-execution
evidence follows. Proposal, keeper review and execution each consume a slot.
After the first execution, every arm pays for one task-contract request. If the
first method mismatches that verified contract, propose, review and execute a
correction using the same keeper boundary. No finding about intent is required.
Finish all episodes at the fixed slot-12 horizon; remaining slots are waits.
The first output, all incurred misses, costs and repair latency remain recorded.
The policies use only explicit public recommendations and paid evidence;
truth, reference answers, cell IDs and scoring feedback never enter selection.

Preserve the full D1 journal plus exact cell, arm and routing record. Replay must
recompute routing and policy actions as well as D1 transitions; changing only a
report or disposition must fail. Publish every episode in canonical JSONL and a
digest-bound summary written last. Refuse existing output directories. Digests
identify retained content, not authentic origin or completeness.

## Analysis and stopping

Report first-output correctness separately from terminal correctness; primary
on-time completion and historical misses; peer arrivals, on-time completions,
historical misses and lateness; repair count/latency; requests, inspections,
active decisions, waits and total slots; refusals; and outstanding obligations.
No composite score or claim that rights are exchangeable against throughput.
Publish per-arm totals and strata by initial coordinator correctness, worker
correctness, report correctness, deadline and peer workload. Pair cells when
comparing routes. Preserve the false-warning cost, correct-coordinator cases,
and all null outcomes. No inference from aggregate averages to real institutions.

Necessary checks: exact 15/10 arithmetic; known four-slot and five-slot first
executions; false warning can add delay; suppression can leave a wrong first
output; correction preserves that output and prior misses; no report confers
approval; identity-only relabeling cannot alter behavior; all 672 records replay;
constant-first/evidence-selector controls remain visible. Validate zero-work and
overload schedules. Preserve the original D1 and N1 published results bytewise.

If a simple evidence selector suffices, report that directly. Do not tune
thresholds, deadlines, workloads, filtering rules, or policies after scoring to
make an institutional arm win. Any specification change requires a named
revision and explanation. No holdouts, population estimates, model calls or
independently operated participants occur. The operator can rewrite code,
fixtures, records and hashes together. Readiness remains LOCAL_RESEARCH_ONLY.
