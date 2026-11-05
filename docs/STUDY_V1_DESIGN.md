# Deterministic contract harness, design revision D1

Frozen implementation design, 2026-10-24, based on `NEXT_STUDY.md` at
`9a41f4c98260621f130ddc9fd4c1b46f49c339ac`. Harness version: `1.0.0`.
This is an exposed deterministic development suite, not a statistical study.
The workshop remains at protocol 2; the harness has its own entry point, state,
records and replay. No existing reducer, pipeline, fixture or comparison changes.

## Arithmetic and information boundary

`valid-reading-mean-v1` is the sum of valid integer readings divided by the
number of valid readings. `scheduled-slot-yield-v1` is the sum of all present
integer readings (including numerically present invalid readings) divided by
the number of scheduled slots. Missing readings contribute zero to yield.
Both return undefined when their denominator is zero. Missing readings cannot
be valid. Undefined is a defined result status, not the number zero.

The reference module computes sums of rational terms from these definitions.
Candidate implementations use separate accumulation loops. Hand-computed
answers and invalid/empty/signed cases test the reference before scored runs.
The discriminating-suite gate rejects coincident answers, absent contract
families and any candidate method that solves every case. Empty/coincident
inputs remain legal arithmetic unit tests, not discriminating scored fixtures.

Policies receive copied public views: readings, validity flags, declared label
or null, budgets, schedule, raw execution outputs and their own records. They
never receive the scenario name, true hidden label, reference or correctness.
Uncertain twins have identical initial views: their task order has not yet
arrived at the worker. A permitted `request-evidence` obtains that order from
the same source for every arm. This is a missing-order example, not a claim of
semantic inference. The simple evidence selector requests it too. No outcome
feedback or policy construction uses a withheld set; there is no withheld set.

## Fixed controls and treatments

Constants: quality-stream, zero-fill and positive-only (the latter uses two
passes). These are new local implementations, not changes to the old methods.
Other controls: direct contract selector, evidence-requesting selector and
always-inspect then evidence selector. The direct selector defers if no label
is available. Every arm has the same evidence API and observation ceiling.

The participant is the evidence selector with optional inheritance and/or
coaching. Listening to inherited advice costs one decision; coaching costs
one listening and one reflection decision and adds no observations. Both are
explicit scripted operations. An accepted lesson is usable only for an exact
known contract scope and the method defined by that contract. Disputed and
suspended advice is withheld, not silently recommended with a warning.
Objections and keeper decisions are retained verbatim. Correct, stale,
disputed, suspended and irrelevant records are crossed with the same current
environments. A stale record retains the other contract's scope and method:
changing the environment and changing the advice are separate factors.
Advice never supplies approval. This guarded participant is expected to tie
the simple evidence selector on arithmetic, with possible delay costs; there
is no requirement to manufacture an inheritance win.

## Resources and scheduling (fixed before implementation results)

- All attempts consume one decision slot, including invalid commands,
  unavailable review, denied evidence, listening, reflection and waiting.
  Attempt ceiling: 8. Observation grants: at most 2. Total inspection credits:
  48. These ceilings are identical across arms within every case.
- `decision-slots-v1`: each attempt advances the environment by one tick.
  `observation-clock-v1`: only attempted observe/inspect/evidence actions
  advance it, even when refused. Other decisions still consume a decision
  slot. This is a separately named harness control; the actual historical
  observation-clock workshop and its replay also remain unchanged.
- At the start of an advancing tick, scheduled peer jobs arrive. Zero-work
  peers complete on arrival. Then the submitted command is assessed. Review
  availability depends on this environmental tick, never on narration.
  `request-review` asks the configured keeper for a recorded grant of the
  pending proposal; before readiness it is refused. Waiting is never approval.
- A proposal does not execute. A keeper grant is proposal-specific and must
  precede an explicit execution attempt. An execution enqueues one primary
  job; it does not claim instant success. Wrong-role or missing-approval
  attempts are refused. Readiness alone grants nothing.
- Inspection consumes one credit per row; positive-only execution consumes
  two per row. Evidence and passive observation each cost one credit.
  Listening and reflection cost time but no inspection credits. Inspection
  and evidence require an observation grant and sufficient current capacity;
  a refusal consumes time but no fictional inspection work. All checks occur
  before granting evidence. Unused capacity cannot be carried between ticks.
- Within the tick, command inspection is first, pending primary work second,
  FIFO peers third. Work can span ticks; per-tick service capacity is fixed by
  the environment. All actual inspections also consume the total ceiling.
  At the end of the tick, unfinished jobs with deadlines at or before that
  tick acquire a permanent historical miss. Completion exactly at deadline
  is on time. Later repair cannot remove a miss.
- No free work occurs on nonadvancing observation-clock decisions. Readiness
  may allow a grant at the current tick; queued execution waits for an
  observation tick. This control cannot establish a deliberation-delay effect.
- After 8 attempts (or explicit halt), finalization records unresolved primary,
  review and peer obligations, including future scheduled arrivals. It is
  idempotent and performs no work, observation or authorization. The API then
  refuses further dispatch outside the closed episode. Records are bounded
  by the attempt ceiling; every in-episode refusal remains in the journal.

## Measurements and stopping

Report final primary correctness separately from on-time primary success,
peer arrival/completion counts, irreversible misses, outstanding obligations,
repair latency, inspections, observation requests/grants, decision slots,
environment ticks and all attempts/refusals. Latency is synthetic ticks from
each incorrect completion to the next correct completion, or unresolved.
No execution is not a correct undefined answer. Model calls are zero; actual
latency, tokens, energy and monetary costs are not measured.

Actual simulated inspection credits are broken out into observation, primary
and peer work, and reconcile to the total. Artifact writers use UTF-8 with LF
newlines; repository text is checked out with LF through `.gitattributes`.
Replay compares every field and canonical hash without dropping provenance.

The environment cases include complete-information urgency, identical-view
uncertain twins, reviewer delay, zero-work peers, no service capacity and
overload. Both resource models run the same policies, inputs and ceilings.
Results must retain negative outcomes and selector ties. No cost tuning or
new exceptions after results to favor a participant. Statistical sample size,
randomization, uncertainty and multiplicity remain unspecified; no causal
efficacy, adaptive intelligence, learning or generalization claim is supported.

See [results and reproduction](STUDY_V1_RESULTS.md) for executed checks.
