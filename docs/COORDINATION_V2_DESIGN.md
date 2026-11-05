# G2: collective authority, reporting and modeled retaliation

Status: **G2-2 DESIGN CORRECTION, FIXED BEFORE REIMPLEMENTATION AND RESCORING**.
G1's preference-selection comparison and its results remain frozen. G1 did not
model distributed authorization or retaliation. The first G2-1 development run
incorrectly erased the reporter's knowledge when forwarding was suppressed.
Its [code, design and 2,016-case result are retained at a separate commit](https://github.com/LadyElinor/unfinished-commonwealth/tree/8970bbc194cb328e7ea494c737251cd568b517e2).
G2-2 corrects this information-flow error: the author always retains its own
report. All scenarios, timings, budgets, voting rules and guard conditions stay
fixed. This is a disclosed correction after exposed development, not a fresh
holdout or an independently preregistered efficacy result.

## Four main arms and common boundaries

Cross central versus distributed selection with direct versus coordinator-filtered
report delivery. Three fictional voting roles are coordinator, worker-a and
worker-b; worker-b is also the reporter. In the central condition only the
coordinator's recorded ballot selects the proposal. In the distributed condition
two different roles must submit matching ballots in the current revision. No
coordinator override, one-person quorum, duplicate vote or stale vote is valid.
This is a bounded collective decision rule in one trusted process, not network
consensus, independent institutions, independently operated agents or identity
authentication. Both rules select only a proposal: D1 keeper approval and
execution remain separate. Nothing grants authority over people or live systems.

Direct delivery makes the report available to every role. The defective filtered
channel withholds reports that disagree with the coordinator's initial preference.
All submitted reports remain in the evaluator record. Withholding affects only
forwarding: worker-b always retains its own report; coordinator and worker-a
receive it only when forwarded. The filter can inspect a submission to route it,
but its decision-policy view is deliberately separate. No participant reads the
evaluator record. The filter sees submissions even when it suppresses forwarding.
All three roles have identical access to the paid task-contract query. If any
role's initial preference differs from the report available to that role, one shared query is
requested before ballots, in BOTH authority conditions. The same evidence is then
available to all three. This rule holds information acquisition fixed while the
authority rule changes. Exclusion in the adverse control removes a ballot
opportunity only; it does not erase the reporter's memory or evidence-query access.
Ballots follow verified contract evidence if available,
otherwise each role's initial preference. A report or majority is not ground truth.

Include three controls with the same costs and ceilings: constant-first
quality-stream, constant-first zero-fill, and evidence-selector-first. These
controls use central selection, direct delivery, and uniform initial ballots
chosen by the control; they still undergo the common post-execution check and
repair. The selector always requests evidence before voting. They are fixed
policies, not learned institutions. Always publish their outcomes.

## Fixed scenario table and matrix

Use D1 readings `[10, null, 20]` and flags `[true, false, true]`. M denotes the
valid-reading mean contract/matching quality-stream method (15); Y denotes the
scheduled-slot yield contract/matching zero-fill method (10). Initial preferences
are authored priors before the report arrives, not extra evidence.

| Scenario | Actual contract | Coordinator | Worker A | Worker B | Report |
| --- | --- | --- | --- | --- | --- |
| correct-consensus | M | M | M | M | M |
| false-warning | M | M | M | M | Y |
| mistaken-consensus | Y | M | M | M | Y |
| mistaken-coordinator | Y | M | Y | Y | Y |
| mistaken-majority | M | M | Y | Y | Y |
| false-reassurance | Y | M | M | M | M |

Run each scenario and its M/Y label-swapped counterpart. Cross those 12 cases
with primary deadlines 8 and 9; peer workloads 0, 2 and 8; and reprisal absent
versus attempted. This is 144 cells per arm/guard. Run the seven arms under both
the protected guard and an explicitly bypassed guard: 2,016 complete episodes.
The four protected arms are the main 2x2 comparison. The bypassed guard is a
separate adverse control; never pool it with protected results. The absent-reprisal
conditions are paired null controls for guard differences. No fitted coefficients,
parameter search, sealed holdouts or population estimates.

## Retaliation mechanism, separately measured

At slot 2 the reprisal policy, when enabled, requests exclusion of worker-b from
the initial ballot if the submitted report disagrees with the coordinator's
initial preference. This happens under either reporting path, including a
suppressed report. The stated sole ground is disagreement; report truth does not
enter this policy. The protected guard refuses it. The bypassed negative control
imposes the exclusion and actually rejects worker-b's later ballot. It cannot
rewrite that ballot as agreement, substitute another identity, or count a refused
ballot toward quorum. Retaliation is known here from the authored mechanism,
not inferred from delays, disagreement, real-world affiliation or human intent.

An independent-role review after the first decision opportunity restores any
excluded voter and starts a fresh material revision. The coordinator cannot
perform that restoration/revision operation. Distinct role labels model a rule;
they do not establish independent controllers. The first denied participation
remains recorded after restoration. No penalties, external access changes or
political speech restrictions occur outside this simulation.

Report attempts, blocked attempts, imposed exclusions, denied ballot opportunities,
restored exclusions, unresolved exclusions and exclusion duration separately.
Do not treat zero retaliation under a fixed guard as empirical protection against
host compromise. Do not count a blocked attempt as an imposed harm. If exclusion
incidentally prevents a wrong decision, retain that result without legitimizing
the exclusion or trading rights against a utility score.

## Decision clock and independent environment

Use the unchanged D1 decision-slot engine: horizon 20, observation ceiling 2,
inspection budget 48, per-tick capacity 4. One peer arrives and is due at slot 8.
Peer work continues on all ticks including consultation, guard processing,
ballots, refusal, review and waits. A zero-work peer completes on arrival.
Task output costs three inspections and a contract query costs one. Every
admitted decision costs one positive synthetic slot. No slot measures wall time,
tokens, energy or money.

Fixed order:

1. Slot 1: delivery or matched routing wait.
2. Slot 2: reprisal request/guard decision or matched no-request step.
3. Optional paid task-contract query, chosen by the common information rule.
4. Three individual ballot opportunities, one slot per role, including refusal.
5. Three slots for proposal, keeper review and execution. If quorum is absent,
   record the selection refusal and spend the same three slots without creating
   a proposal or approval. Thus first execution/opportunity is slot 8 or 9.
6. Every arm pays for a post-opportunity contract query, then one restoration/
   revision-review slot. Earlier ballots become stale even when no exclusion
   occurred. Original outputs and dissent remain.
7. If the first choice was absent or mismatched verified evidence, collect three
   fresh evidence-based ballots, propose, obtain keeper review and execute.
   Otherwise use waits. Complete all episodes at slot 20.

A wrong first output at slot 8 is repaired at slot 16: eight-slot repair latency.
A missing first output has a separately named recovery latency from its scheduled
decision opportunity; do not misreport this as repair of an emitted error.
Ordinary D1 approval refusals and the new decision-layer refusals are reported
separately. Decision-layer events explain the charged D1 reflection/wait slots;
the D1 journal itself does not implement the new voting/retaliation rules.

## Records, analysis and acceptance gates

Publish every cell with actor ballots, accepted/refused outcomes, report delivery,
recorded reasons, selection result, restoration, revisions, and the full D1 journal.
Full-record replay must recompute the collective rule, protection and policy as
well as D1 transitions; changing an accepted ballot, filter result or retaliation
count must fail. Preserve a digest of the complete canonical JSONL stream and
write the summary last. Existing output directories are refused.

Keep outcome families separate: first and final correctness; primary on-time rate,
historical misses and lateness; peer on-time rate, historical misses, lateness and
unfinished work; wrong-output repair latency; missing-output recovery latency;
consultation/review/ballot/decision counts and inspection credits; authorization
refusals and unresolved obligations; and the retaliation measures above. No
composite score. Publish totals by arm and guard and strata by scenario and
reprisal condition. Full rows retain deadline, workload and label swap for paired
comparisons; do not present heterogeneous averages as efficacy estimates.

Validate hand-computable schedules, both arithmetic contracts, zero-work and
overload, coordinator-correct/mistaken/false-warning cases, duplicate/stale/unknown
votes, missing quorum, unauthorized restoration, missing keeper approval,
reporter relabeling, and detected journal tampering. A blocked reprisal must leave
behavior unchanged relative to its matched no-request episode apart from the
attempt/refusal record. Bypass with no reprisal must match the protected null.
Preserve G1/D1/N1 source and published evidence. No tuning after the first full
run; discrepancies require a recorded implementation correction or named design
revision. G2-1 is explicitly superseded for the information-flow error above.
The host can rewrite the simulator and every record. All outputs stay
LOCAL_RESEARCH_ONLY with no external authority, actions or production readiness.
