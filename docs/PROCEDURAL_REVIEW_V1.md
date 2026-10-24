# Procedural review extension P1

Version `procedure-1.0.0`, design P1, 2026-10-24. This is an opt-in deterministic
extension of study-v1, not an amendment to workshop protocol 2 or study design D1.
All D1 source files, its 432 runs and its recorded results remain unchanged.
P1 addresses missing procedure; it does not claim better arithmetic or confer
legal jurisdiction. Existing authorized routine work receives no new gate.

## Source-grounded gap audit

The Congress.gov Congressional Record index and a linked Congress.gov PDF could
not be fetched in this session. The Record itself was read through the official
Government Publishing Office copy. Sources below were checked on 2026-10-24.
The U.S. Courts current-rules page links the December 1, 2025 compilations;
pending amendments are not treated as effective rules.

| Source observation | Gap in D1 | P1 adaptation (our design) |
| --- | --- | --- |
| [Congressional Record, May 20, 2025, H2158–H2159](https://www.govinfo.gov/content/pkg/CREC-2025-05-20/html/CREC-2025-05-20-pt1-PgH2158-6.htm) separately records the resolution, consent request, objection opportunity, disposition and reconsideration. | A proposal contains only a method. | Motions specify grounds, requested relief and evidence; disposition is separate from filing and silence. |
| [Senate floor record, May 21, 2025](https://www.periodicalpress.senate.gov/wednesday-may-21-2025/) distinguishes a point of order, appeal and motion to table. | No appeal path. | An appeal names a specific ruling and requested relief; a different fixture reviewer affirms, vacates or remands. No voting or tabling machinery is imported. |
| [FRCP 5, 6 and 7(b)(1)](https://www.uscourts.gov/sites/default/files/document/federal-rules-of-civil-procedure.pdf) cover service, time computation and particularized motions. | Availability alone permits review without a response opportunity. | Recorded local service to worker and neighbor, a two-slot response period, and a defined decision boundary. These are synthetic slots, not federal filing deadlines. |
| FRCP 52(a)(1) distinguishes findings and conclusions in specified trials; 52(a)(3) generally exempts motions. | Approvals have no explanation or record binding. | P1 deliberately imposes its own stronger rule: every disposition needs findings, a local-rule basis, reasons, a current packet digest and responses to all filed objections. |
| [FRE 103 and 106](https://www.uscourts.gov/sites/default/files/document/federal-rules-of-evidence.pdf) address preservation of objections and related context. | No live objection or context record. | Specific objections and linked context remain in full; acknowledgment neither proves nor excludes their content. Rulings bind the complete shared packet. |
| FRCP 60 separates clerical corrections from substantive relief; 60(c)(2) gives specified relief motions no automatic suspensive effect. | No correction/reconsideration semantics. | Corrections are annotations; changing a method requires an amendment. Appeals do not themselves stay execution; a separate prospective stay is recorded. This is a local choice, not a claim that all federal appeals lack stays. |

These sources inform procedural structure, not truth tests. P1 does not transplant
criminal process, discovery compulsion, contempt, sanctions, parliamentary
majorities, a presumption of unanimous consent, or emergency waiver powers.
Full legal compliance, privacy redaction and adjudicative fairness are not claimed.

## Fixed P1 rules

`P1-MOTION`: only the worker may propose or amend. Both require a method, grounds,
requested relief and existing evidence IDs. Each revision binds the exact input,
method and episode. Amendments retain earlier revisions, invalidate prior approval,
and require new notice and review. There is one unexecuted motion at a time;
a denial must be addressed by amendment or appeal on that docket, rather than
opening a parallel request for the same work.

`P1-NOTICE`: the clerk records local delivery to the fixed worker/neighbor roster.
Service is a simulator event, not an external message. If service occurs at slot
t, responses are timely through t+2 inclusive; a ruling may occur at t+3. Earlier
disposition requires explicit responses from both parties. A party may oppose.
Silence never counts as assent or approval. Failure to respond does not cause
automatic approval, and missing notice cannot be waived by a timeout.

`P1-RECORD`: the initial public view and paid observations have stable evidence
IDs. Party statements are marked accounts or context, not independent sensor
observations. Context references an existing record and preserves its full parent.
The complete packet contains all such records, all current responses and objections,
and correction annotations. A reviewer cannot rely on a packet from before a new
objection, response, record or correction. This is record integrity, not proof that
the reviewer read it or that its contents are true.

`P1-RULING`: only the keeper may approve or deny, after readiness and notice rules
are met. The command states findings, local rule IDs, reasons, the current packet
digest and exactly the current objection IDs it addresses. Denial leaves the
requested work undone. Approval remains a single-use, revision-bound grant. The
old bare `request-review` cannot bypass this path in P1. An objection before
disposition must be addressed; an objection after disposition uses the appeal path.

`P1-APPEAL`: either party may appeal a ruling through ruling slot+4 inclusive,
once per ruling. The independent *fixture role* `reviewer` must receive an explicit
request and give a reasoned, record-bound disposition. Distinct role names do not
establish independent human operators. Affirmance creates no new grant; vacatur
or remand invalidates any unconsumed grant. A new revision and fresh keeper review
are required before later execution. Results already produced remain historical.
An amendment cannot extinguish a timely appeal of an older ruling. Such an
appeal remains bound to that older revision; its disposition cannot grant or
revoke execution for a different revision. A pending appeal or unlifted stay
on the current revision blocks amendment of that revision.
The public view exposes every revision and its current packet digest so an
older-ruling appeal does not depend on private state or the appellant's memory.

`P1-STAY`: an appeal alone does not block an existing grant. The reviewer can
explicitly stay an unexecuted proposal while reviewing it. Lifting that stay also
requires an explicit reasoned reviewer action. A stay cannot recall already
dispatched work; the model refuses such a request and retains the work and cost.
It is a prospective permission gate, not a cancellation or rollback mechanism.

`P1-CORRECTION`: only the clerk can attach a reasoned correction to a prior event.
It never edits that event, its hashes, the method, outcomes or permission. Merits
changes use amendment/appeal. Correction requests remain visible and cost time.

`P1-TERMINAL`: the keeper may close out with a reason and follow-up note. Exhaustion
also finalizes without extra work. Pending notice, objections, appeals, stays and
work obligations survive. Finalization grants no extension or successful outcome.

## Cost, version and trust boundaries

P1 subclasses the frozen study-v1 scheduler through its existing command and view
interfaces. Every motion, service, response, objection, ruling, appeal, correction,
wait and refusal costs one shared decision slot and advances the environment.
Peer arrivals, capacity and deadlines continue. Default ceilings remain eight
attempts, two observation grants and 48 inspection credits. Longer procedural
regressions specify their larger ceiling before execution and do not join D1.
P1 uses only the decision-slot clock; it does not reinterpret the old observation
clock. Its genesis and replay version are distinct and cross-version imports fail.

Observations retain D1's costs and access. Clerical accounts add no oracle answer
or extra physical observation. The initial public contract may be unknown. Neither
a reasoned ruling nor an appeal certifies arithmetic correctness. Scripts, not
models or courts, supply the decisions. The Python objects and fixture names are
not an authenticated or adversarially isolated execution service.

## Commands

Every command has `action`, `actor` and exactly the listed fields. Text is bounded
to 4,000 characters. A `revision` and `proposal` identify the pending question.
`packet` is the digest of the current public docket packet, available from the
view. Local rule lists contain only the P1 IDs above.

| Action | Actor | Additional fields |
| --- | --- | --- |
| `propose` | worker | method, grounds, relief, evidence |
| `amend` | worker | proposal, revision, method, grounds, relief, evidence |
| `serve` | clerk | proposal, revision |
| `respond` | worker or neighbor | proposal, revision, position, account |
| `object` | worker or neighbor | proposal, revision, grounds, evidence |
| `submit-record` | worker or neighbor | kind (account/context), account, parent |
| `rule` | keeper | proposal, revision, decision (approve/deny), findings, rules, reason, packet, addresses |
| `appeal` | worker or neighbor | proposal, revision, ruling, grounds, relief, evidence |
| `resolve-appeal` | reviewer | proposal, revision, appeal, decision (affirm/vacate/remand), findings, rules, reason, packet |
| `stay`, `lift-stay` | reviewer | proposal, revision, appeal, reason |
| `correct-record` | clerk | event, correction, reason |
| `closeout` | keeper | reason, follow_up |

Existing observation/listening/reflection/wait/halt and explicitly approved
execution actions remain available through the underlying scheduler. The P1
execution gate is additional to, and cannot substitute for, its keeper grant.

Reproduce the procedural traces with `python -m commonwealth.procedure_v1 run
.local/procedure-v1`; replay with `python -m commonwealth.procedure_v1 replay
PATH_TO_JOURNAL`. See [procedural results](PROCEDURAL_REVIEW_V1_RESULTS.md).
