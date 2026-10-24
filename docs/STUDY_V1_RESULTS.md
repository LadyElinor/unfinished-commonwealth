# Study-v1 deterministic development results

Harness 1.0.0, design revision D1, built separately on workshop baseline
`9a41f4c98260621f130ddc9fd4c1b46f49c339ac`. The independent reference regression
tests were run before the harness comparisons. [Design and frozen rules](STUDY_V1_DESIGN.md).

**The simple evidence selector suffices. No institutional or adaptive benefit
has been demonstrated.** This is a reproducible exercise of deterministic rules,
not a model experiment or an independent held-out evaluation.

## Full matrix and negative outcomes

The matrix crosses 12 authored environments, 18 arms and two resource models:
432 runs, each with eight decision attempts, up to two observation grants and
48 total inspection credits. All 432 complete journals replay. Every constant
method, the direct selector, evidence selector, always-inspect controller, and
the participant's full 2-by-6 coaching/inheritance factorial are included.
The committed [summary](../examples/study-v1-summary.json) includes **every**
arm under **both** clocks, plus design and implementation digests. Reproduction
also writes every attempt, refusal, actual inspection, review grant and
unresolved obligation to its own journal.

The following counts use the decision-slot clock. Cases have different purposes
and constraints; these are descriptive totals, not success-rate estimates.

| Arm | Correct at end / 12 | Correct on time / 12 |
| --- | ---: | ---: |
| Constant quality-stream | 4 | 4 |
| Constant zero-fill | 7 | 6 |
| Constant positive-only | 3 | 3 |
| Direct contract selector | 9 | 8 |
| Evidence-requesting selector | 11 | 10 |
| Always inspect, then evidence selector | 11 | 8 |
| Participant without inheritance/coaching | 11 | 10 |
| Participant with inheritance, each of five conditions | 11 | 8 |
| Participant with coaching only | 10 | 8 |
| Participant with inheritance and coaching, each condition | 10 | 6 |

The no-capacity case cannot complete any nonempty primary job. In the overload
case, the selector completes the primary result but peer deadlines are still
missed. Coaching can leave primary work unfinished at the attempt limit.
All arms retain ten peer historical misses across the decision-clock matrix;
none has demonstrated a peer-outcome improvement. Reduced refusal counts in
advice arms reflect fewer early review requests, not additional authority.

## Specific falsifiable observations

1. **Different legitimate answers:** `[10, null, 20]` gives exactly 15 for the
   valid-reading mean and 10 for scheduled-slot yield. The independent reference
   also handles signed readings, invalid numeric readings and undefined means.
   The suite rejects coincident definitions or a universal constant solution.
2. **Unnecessary inspection can be harmful:** on an urgent complete-information
   case, propose/review/execute completes at slot 3, exactly on deadline.
   Prepending inspection completes at slot 4. Arithmetic correctness returns,
   but the original deadline miss remains. Coaching and inheritance consultation
   can impose the same kind of delay.
3. **Evidence resolves actual initial ambiguity:** uncertain mean/yield twins
   have identical initial public views and require different outputs. Requesting
   the task order reveals the label, at the same cost and under the same limit
   for all arms. Inspection of already visible readings does not reveal it.
   The ordinary evidence selector resolves both cases without memory or coaching.
4. **Guarded inheritance prevents wrong transfer, but adds no benefit:** changing
   from a mean contract to yield makes the old mean lesson out of scope. The
   participant obtains the current order and selects zero-fill. Disputed and
   suspended advice is withheld; the original objection and keeper decision
   remain visible. Correct advice still costs a listening step. All five advice
   conditions produce the same arithmetic results under this guarded policy.
   A donor/successor regression also transfers a practice with an actual successful
   predecessor journal head into a yield episode: the predecessor remains intact,
   a fresh keeper grant is required, the method changes correctly, and consultation
   misses the urgent deadline that the memory-free successor meets.
5. **Waiting is not approval:** reviewer readiness is environmental, but only a
   recorded keeper grant on a specific pending proposal permits execution.
   Waiting, inherited recommendations, wrong-role requests and an expired
   episode cannot manufacture a grant. Premature requests remain costed refusals.
6. **Repairs do not erase history:** an independently tested trace completes a
   wrong primary result at slot 3 and repairs it at slot 6. Repair latency is 3,
   the missed deadline remains, and both outputs remain in the record.

The observation-clock control advances only on observe/inspect/evidence
attempts. Therefore it can leave scheduled peers unarrived and reviewer readiness
unreached, and cannot express delay during listening or reflection. Those future
obligations remain reported. Its results must not be pooled with decision-slot
outcomes. This harness control is separately named; it does not redefine the
historical workshop clock or its rejection semantics.

## What these results cannot show

The guarded participant uses the same explicit contract-to-method mapping as
the evidence selector. Its tie is expected by construction, not evidence that
it has learned to interpret a contract. Its scope check requires current
contract evidence; correct inherited advice contains no extra validated fact
that the baseline cannot request. The advice records are authored treatments,
not learned practices. This tranche tests transfer between separately initialized
contract episodes, guards and consultation costs; it does not test autonomous
practice acquisition or contract changes during a single episode.

No semantic inference from ambiguous language, statistical treatment effect,
coaching efficacy, institutional advantage, generalization, adaptive intelligence
or real-world resource saving follows. All fixtures and policies are exposed.
No model adapters, model-provider calls, deployment or new execution authority
have been introduced. Actor names and in-process policy views are simulator
boundaries, not credential authentication or adversarial process isolation.
Synthetic ticks and inspection credits are not measured seconds, tokens or joules.

## Reproduction and compatibility

```bash
python scripts/verify.py
python scripts/reproduce.py .local/original-reproduction
python -m commonwealth.study_v1 run .local/study-v1
python -m commonwealth.study_v1 replay .local/study-v1/journals/decision-slots-v1--yield-urgent--always-inspect.json
python scripts/package.py .local/study-v1-package
```

Use new output directories. The source manifest in
`tests/data/study-preserved-v013.json` freezes all existing workshop Python
modules, fixtures, historical replay inputs and original example records.
The original fifteen comparisons and v1/v2 replay tests continue to run.
The package check tests the source distribution and installed wheel independently,
including the new module entry point and a preserved failure journal.

Executed locally on 2026-10-24 with Python 3.12.14, setuptools 84.1.0 and wheel
0.48.0:

- `python scripts/verify.py`: exit 0, **144 tests pass** (96 existing, 48 new),
  packaged JSON and documentation links pass.
- Original reproduction: exit 0, **15 comparisons**, 24-event demo replay,
  unchanged head `96baf584d179654e5abc836d127afdac80d916a08c05bcb482f732a01c0acb0a`.
- Separate harness: exit 0, **432 runs**, all journals replay; generated and
  committed summary files are byte-identical.
- Urgent failure journal: exit 0, 8 replayed events, head
  `6bba80a2a6591062c4236e1fe199c10983e85814fa0dc1fa37d5953cf1dfba89`.
- Offline source/archive and clean wheel verification: exit 0, source tests
  pass, installed original and new entry points execute, readiness stays at
  exit 2 / `LOCAL_RESEARCH_ONLY`, model calls remain zero.

The configured CI matrix also checks Linux Python 3.11/3.12/3.13 and Windows
Python 3.12. Local execution alone does not establish those hosted results.
