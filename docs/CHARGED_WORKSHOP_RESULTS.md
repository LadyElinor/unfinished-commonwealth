# What charging deliberation changed

The constant quality-stream policy met every primary reporting target and every peer deadline in the original fixtures. Adding the case consultation to the coached script used one extra slot per run. Under the shared-lane assumption it doubled historical peer misses from three to six across the three datasets. When the peer could work independently during deliberation, every arm met every peer deadline.

These are fixed-trace comparisons. The decisions were made under the old clock and replayed on two different resource schedules. They measure when the same decisions would deliver results under those schedules. They do not measure how an agent would change its policy if it observed the new deadlines. No holdouts or live models were used.

## Original fifteen traces

The [prospective design](CHARGED_WORKSHOP_DESIGN.md) specified the schedules, resource ceilings, deadlines, measures and controls before scoring. Each row sums three runs with four observations and four arriving peer batches per run. Primary and peer inputs and methods match the original suite. Targets are study choices. A decision slot is a simulated elapsed-time unit.

| Policy | Command slots | Correct observations / 12 | Correct by target / 12 | Historical clock peer misses / 12 | Shared-lane peer misses / 12 | Independent-worker peer misses / 12 | Primary inspections |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Constant quality-stream | 21 | 12 | 12 | 0 | 0 | 0 | 96 |
| Single | 30 | 7 | 7 | 3 | 3 | 0 | 120 |
| Team attending only to primary failure | 27 | 7 | 7 | 5 | 2 | 0 | 136 |
| Coached | 39 | 7 | 7 | 3 | 3 | 0 | 120 |
| Coached plus casebook | 42 | 7 | 4 | 3 | 6 | 0 | 120 |

Listening and reflection consumed nine extra slots across the coached runs compared with single. Both had seven correct observations by their reporting targets. The extra casebook consultation pushed the third observation from slot 12 to slot 13 in each coached run, past its target. In the signed and flagged scenarios, time from the first wrong observation to a correct one was eight slots with single, eleven with coaching and twelve with coaching plus casebook. No incorrect observation remained without a subsequent correct observation. Every arm inspected all 96 peer records by the end of the 20-slot horizon in both schedules. Late completions still count as misses.

All rows, per-arrival deadlines and completion times, repair latencies, source journal heads, inspection counts and pending obligations are in the [published results](../examples/charged-workshop-results.json). The historical and charged clocks use different arrival schedules. The cross-clock totals must not be pooled. The two charged schedules do use identical exogenous arrivals.

## D1 and an external decision-maker

The [existing D1 results](STUDY_V1_RESULTS.md) reproduce byte-for-byte across all 432 exposed runs. Among the tested constant methods, none solves the two contrasting contracts throughout. Under its charged clock the direct selector finished correctly in 9/12 cases and on time in 8/12. The selector that requests the rule when it is missing finished correctly in 11/12 and on time in 10/12. The uncoached participant tied it. There is no demonstrated institutional advantage over this baseline.

A second, standalone [Python fixture agent](../examples/agent_profile_v1/python_agent.py) received JSON briefs on the twelve charged D1 cases. Its externally made decisions and separately costed host follow-through produced journals identical to the evidence selector on all twelve. Totals were 19/29 peer arrivals on time, ten peer historical misses, 96 decision slots, 112 inspections, 22 observation grants, eight refused attempts and ten outstanding obligations. The policy intentionally used the same declared mapping; the comparison tests interoperability. It adds no evidence of learning or of a benefit from multiple parties.

The [independent JavaScript audit](../scripts/audit_measurement.mjs) recomputed the D1 arithmetic for 432 journals and checked 345 completed primary outputs, including wrong results. It also recounted both chambers in both closed rounds of the published Assembly example. It uses exact integer ratios on these safe-integer fixtures. It checks published numbers; it does not verify signatures, the Python reducers, ballot truth or the operator's custody of checkpoints.

## Required machinery and optional surfaces

The modest workshop claim requires a trace, an actual shared queue and budget, durable recording of a missed deadline, and a scoped successor practice with fresh observation and separate approval. Brier scoring, coaching, literary consultation and the Assembly docket are optional research surfaces. The charged replay, D1 selector controls and external policy exchange can be inspected without adding a casebook, issuing a grant or changing a historical reducer.

The operator can rewrite fixtures, verifier, journals, hashes and reports together. A replay or a second numerical implementation cannot authenticate the operator's history. New C1c reports, the installed CLI evaluation and readiness output, and operational readiness include this limitation. Historical module commands and frozen D1 snapshots retain their original bytes and wording.

## Reproduce

Use new output directories. No provider credentials are required.

```sh
python -m commonwealth.study_v1 run .local/d1
python -m commonwealth.measurement_v1 run .local/charged --fixture-agent examples/agent_profile_v1/python_agent.py
node scripts/audit_measurement.mjs study .local/d1/journals
node scripts/audit_measurement.mjs assembly examples/assembly_v1/public_record.json
```

Compare the resulting D1 summary with `examples/study-v1-summary.json` and the charged report with `examples/charged-workshop-results.json`. The latter also regenerates and replays all original fifteen workshop SQLite journals. The frozen comparison accepts only the published fixture script’s SHA-256. The child receives the verified bytes, a temporary working directory and no inherited credentials; on Windows it also receives the system root path. Python isolated mode is not a security sandbox for arbitrary programs.
