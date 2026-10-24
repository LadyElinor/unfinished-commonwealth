# R1: balanced review of proposed service restrictions

Version `review-1.0.0`, based on commit
`7b47c84d1d6e9ead632ed0a1547925821883dfc3`. R1 is a separate deterministic
advisory process. It cannot prosecute people, determine guilt, execute a
restriction, lift an I1 quarantine or modify an older journal. All identities,
records and service impacts are fictional, host-supplied development inputs.

## Source and adaptation boundary

The [ABA Prosecution Function Standards, Fourth Edition (2017)](https://www.americanbar.org/groups/criminal_justice/resources/standards/prosecution-function/)
were inspected on 2026-10-24. Standard 3-1.1 describes professional guidance;
it does not replace binding jurisdictional rules. These are selected design
inspirations, not implemented criminal law:

| Standards | Relevant theme |
| --- | --- |
| 3-1.2, 3-4.3–3-4.4 | Justified action, continuing evidentiary basis, discretion and alternatives |
| 3-1.4–3-1.5 | Candor, correction and record preservation |
| 3-1.6–3-1.8 | Bias, conflicts and manageable workload |
| 3-5.4–3-5.5 | Seeking, identifying, disclosing and preserving contrary material |
| 3-5.6, 3-5.9 | Noncoercive process and recorded disposition reasons |
| 3-8.1–3-8.3 | Independent reconsideration and new evidence |

The algorithms, thresholds, resource units, actor roster and commands below are
this project's choices. They are not legal proof standards, ABA endorsement or
a finding of legal compliance.

## New decision process

1. **Intake and assignment.** The host supplies a proposed source quarantine,
   its exact scope, a bounded duration, a known evidence inventory and reviewers.
   A steward appoints a reviewer only when its declared controller differs from
   both parties, its conflict state is clear, it is available and its declared
   load is below capacity. An unavailable or overloaded office creates no
   emergency substitute. Appointment and substitution remain journal events.
2. **Collection and explicit disclosure.** An investigator must collect every
   currently available inventory item before notice. Contrary, mitigating,
   doubtful, excluded and wrong-target records are identified separately within
   the complete disclosure. A clerk cannot omit them by presenting only favorable
   support or bury them in an unmarked bulk list. Classifications are host labels;
   there is no extraction or investigation of the outside world.
3. **Response opportunity.** Local disclosure reaches the fixed proposer and
   affected-service roles. Replies are accepted through notice slot+2; a decision
   may occur at slot+3, or after both reply. Opposition is retained. Silence is
   never assent, and no response or appeal waiver action exists. Notice is refused
   unless two replies and a decision can fit in the remaining budget. This does
   not reserve or extend that budget.
4. **Record-bound disposition.** The appointed reviewer supplies reasons, the
   current packet digest, every record/reply ID addressed and every declared
   alternative considered. A new available record or changed reviewer makes old
   disclosure stale. Earlier notices, replies and refusals remain recorded.
5. **Separate reconsideration.** A closed decision can be reviewed once in a new
   episode with its own explicit ceiling and freshly supplied authority. The
   parent journal is replayed; its digest, original decision, costs and known
   inventory are bound into the child. Original records must remain unchanged.
   Additional or newly available material must actually be collected before a
   new merits decision. Merely naming a future record cannot satisfy that gate.
   Replay of the child requires the exact parent journal. No recursive chain of
   reconsiderations or implicit transfer to another target is allowed.

A proposer can withdraw with a reason before completion. Withdrawal preserves
uncollected material and costs; it does not label anyone innocent or guilty.
Without sufficient evidence or review capacity, exhaustion ends the episode
with unresolved work and no automatic adverse recommendation.

## Local criteria and consequences

| Proposed advice | Required conditions | Result if missing |
| --- | --- | --- |
| Restrict the declared source | Current scope authority; complete examined inventory; no unresolved credibility doubt or usable counterevidence; two usable supporting origin IDs for this target; estimated prevented service loss exceeds restriction loss; no adequate less costly declared alternative | Restrict is refused; a reasoned decline/defer remains possible after current disclosure and response opportunity |
| Prefer an alternative | Reliable examined evidence and the same review conditions; named alternative prevents at least the declared loss while costing less service | Unsupported alternative is refused; no execution authority is granted |
| Decline or defer | Assigned reviewer, current disclosure, reply opportunity and complete reasons/record references | Premature or incomplete disposition is refused |
| Withdraw | Proposer and a recorded reason | No forced escalation; unresolved inventory remains visible |

Impact numbers are synthetic service-work units, not valuations of human rights
or estimates of legal culpability. Two distinct origin IDs are a local minimum,
not proof of independence: actual control and evidence authenticity are not
discovered. Mitigation must be identified and addressed, but the program cannot
verify that prose reasons substantively evaluate it. The report preserves a
wrong recommendation despite complete procedure.

Every command attempt, including refusal, costs one decision slot. Each accepted
new collection costs one observation; duplicate, unavailable or over-budget
requests consume time without an observation. Default ceilings are 16 attempts
and four observations, bounded at 64 and eight respectively. These differ from
D1/F1/I1 and are never pooled with those matrices as matched comparisons.
The two R1 timing traces share identical evidence and ceilings.

All views are copied. They omit the hidden fixture truth and unretrieved evidence
contents. The host object and filesystem remain trusted. Untrusted accounts are
stored as text and cannot change the roster, evidence labels or authority.
Allegations of reviewer misconduct remain allegations in the record; text cannot
self-execute recusal. Real conflict investigation, confidentiality, protected
discovery, evidence retention/deletion policy and external service enforcement
are outside this model.

## Reproduce and review

```bash
python -m commonwealth.review_v1 run .local/review-v1
python -m commonwealth.review_v1 replay .local/review-v1/journals/false-but-procedurally-valid.json
python -m commonwealth.review_v1 replay .local/review-v1/journals/new-evidence-reconsideration.json --parent .local/review-v1/journals/false-but-procedurally-valid.json
```

Output publication is staged, locked and refuses existing destinations. Replay
recomputes commands, disclosure, costs, decisions and parent linkage; hashes
establish consistency, not authentic origins. Source manifests include R1 and
its shared serialization/validation helpers. No model providers or live services
are contacted. See [results](REVIEW_V1_RESULTS.md),
[repository review](REPOSITORY_REVIEW_2026_10_24.md) and [trust boundary](THREAT_MODEL.md).

R1 does not replace P1's notice/appeal reducer or I1's source-trust policy. A
recommendation to stop relying on an earlier restriction is advisory; it cannot
clear I1's host quarantine. Authenticated recovery, ongoing live compromise
monitoring and real-effect invalidation still require a separately warranted
implementation. All R1 traces are exposed development examples. No adaptive
intelligence, institutional advantage or independent held-out accuracy follows.
