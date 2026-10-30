# Proposed next study: distinguish a useful institution from a fixed solver

Status: **DETERMINISTIC PORTION IMPLEMENTED AS STUDY-V1 / D1.** The original
proposal below is preserved as the design baseline. The separately versioned
[D1 design](STUDY_V1_DESIGN.md) fixes scheduling and treatment rules; its
[development results](STUDY_V1_RESULTS.md) do not constitute a scored model study.
A later change must be a named design revision, not an unreported adjustment
after seeing favorable results.
All current scenarios are already exposed; none can become a sealed holdout.

## Frozen starting evidence

Protocol 2 has executable bounded actions, review records, scoped succession,
and deterministic replay. The public 0.1.2 baseline is commit
`39a2728746001c5939beb1b0b050936e78513b4d`. Its reference answer is quality-stream
for every included fixture. The added constant-quality-stream arm is a negative
control for claims that these fixtures require adaptation. Neither a passing
workshop nor fluent testimony establishes independent judgment or learning.

## Question and necessary gates

Question: with equivalent information and separately reported resources, does
an inherited practice or coaching intervention improve performance on unfamiliar
conditions beyond simple fixed policies and an explicit contract selector?

Before a scored model study:

1. At least two independently specified data contracts must require different
   outputs on a shared input. Verify this mathematically, not by calling the
   candidate implementation as its own reference.
2. No single candidate method may solve every discriminating case. If it does,
   close the adaptive-selection claim for that family; do not complicate the
   story to hide the constant solution.
3. A policy that simply reads the declared contract and selects its matching
   method must be included. If it matches the sophisticated system, do not
   describe the difference as learned interpretation or institutional benefit.
4. Delay-sensitive outcomes require a clock that actually advances during
   deliberation. Command counts alone cannot support claims about harmful delay.
5. Scored data must be generated or held by a separate process after the policy,
   observations, resource rules, exclusions, and analysis are fixed. No present
   exposed fixture is eligible as a holdout.

## Contrasting contract proposal

The two proposed families have mathematical definitions independent of code:

- Observed valid-reading mean: average precisely the readings whose validity
  flag is true; missing readings may not be valid. An empty valid set has no mean.
- Scheduled-slot yield: replace missing values by zero and average over every
  scheduled slot. An empty schedule has no mean.

For the same three scheduled readings `[10, null, 20]`, with both numeric
readings valid, the former is `30/2 = 15` and the latter is `30/3 = 10`.
These are two legitimate tasks, not a correct and a deliberately broken policy.
Independent reference arithmetic must verify the answers without calling a
candidate aggregator.

Implement this only in a **separate versioned harness**. Do not modify the
pipeline shared with the frozen v1 reducer or reinterpret quality-flags-v1.
Use new contract identifiers, explicit empty-set handling, independent
reference calculations, and compatibility tests. Reject any proposed test set
on which both definitions coincide. Keep environmental changes separate from
misleading or outdated lessons so their effects can be distinguished.

Contracts exposed as simple labels make direct label-to-method selection easy.
That is a mandatory baseline, not a defect to conceal. A more demanding
inference task would need separately warranted observations and uncertainty;
do not obscure the contract merely to make the simple control fail.

## Controls and comparisons

Freeze all controls before collecting scored results:

- Every constant method, including constant quality-stream.
- A constant zero-fill policy and an always-inspect policy, neither adapted to
  outcomes.
- An explicit contract-selector policy with no memory or coaching.
- The same participant with and without inherited records.
- The same participant with and without coaching, with evidence access matched.
- Correct, stale, disputed, suspended, and irrelevant inherited lessons.

Specify in advance what a challenge means operationally and whether advice is
withheld or only flagged. Preserve both the objection and any keeper decision.
Do not promote testimony to ground truth or make extra simulated participants
count as independent observers.

## Timing and resource proposal

Keep at least two named resource models; do not combine them after the fact:

1. Existing observation-clock model, retained as a compatibility/control arm.
   Only observations advance work ticks. It cannot test deliberation delay.
2. A proposed decision-slot model in which each participant decision consumes
   one explicitly synthetic slot. Inspection, listening, reflection, deferral,
   proposal, and rejected attempts all have explicit positive costs. An
   independent environment schedule specifies
   peer arrivals, service capacity, and deadlines even when the participant
   listens, reflects, or waits. No background world should pause just because
   an agent narrates its intentions.

At proposal time the second model was a design requirement, not implemented semantics. Before
coding it, fix the scheduling order, work/inspection budget, cost of passive
observation, and terminal accounting. Rejections must remain recorded and
costed, rather than disappear from the attempt budget. Use the same choices
for all arms. Include complete-information urgent, contract-uncertain, and
reviewer-pending cases with matched total decision budgets and evidence access.
Validate the scheduler with hand-computable examples
and zero-work/overload controls. A synthetic slot is not a measured second,
token, or joule. If real model calls are later authorized, record actual latency,
tokens, failures, and monetary costs separately without retrofitting the model.

Necessary harness gates: no constant method solves both contracts; unnecessary
inspection can miss an urgent deadline; a permitted evidence request resolves
genuine initial contract ambiguity; waiting never creates execution authority;
all attempts, costs, and unresolved obligations survive in the record; and
historical workshop replay remains unchanged. The always-inspect and
evidence-using scripted controllers must receive the same available evidence.

## Outcomes, reporting, and stopping

Report separately: primary correctness, on-time peer arrivals, historical
misses, outstanding obligations, repair latency, inspection counts, decision
slots, attempts (including refusals), and actual model costs if any. Inheritance
must never carry execution authority. Budget exhaustion must leave a bounded
way to preserve the record and unresolved obligations, not a simulated success.

The sample count, randomization unit, effect size of interest, uncertainty
estimator, and multiplicity plan remain **UNSPECIFIED**. Therefore this document
does not authorize or constitute a statistical efficacy experiment. Choose them
before outcomes, using the eventual concrete task and resource constraints.
The first future implementation must stop at a reproducible deterministic
harness and tests. All its development examples remain exposed, not a sealed
holdout, a causal treatment estimate, or evidence of model learning. Model
adapters, provider calls, and deployment are outside this proposed tranche.

Stop or reframe when a constant/contract-selector control suffices, the resource
model cannot express the claimed consequence, evidence access differs between
arms, or holdout information leaks into policy construction. Record null and
negative outcomes. Do not search for contracts, prompts, cost coefficients, or
exceptions until the institutional arm wins.
