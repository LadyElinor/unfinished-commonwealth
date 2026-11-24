# Does an inherited lesson still fit this shift?

This study tests a within-contract transfer check in the frozen protocol-2 workshop.
The earlier [D1 study](STUDY_V1_RESULTS.md) found that checking a lesson's contract could prevent wrong transfer while spending a decision slot and gaining no advantage over the evidence selector. Here the contract remains the same. The donor's shortcut may cease to give the right mean or may consume inspections the neighbor needs.

## Frozen comparison

Start at the ordinary workshop genesis, then hand off to a donor shift. The donor observes, obtains a keeper-approved change to the two-pass positive-only method, produces the right mean and completes the neighbor's batch on time. The keeper accepts its scoped lesson. The neighbor records testimony and an unresolved objection about whether later batches will fit. No model is involved. The experimenter chose the donor shortcut and receiver rules in advance.

For each receiver fixture, the keeper hands the same donor journal to a new worker and resets its active method. The required fresh observation runs a real zero-fill tick. Its cost and effects are recorded separately. Eligible fixtures have enough capacity for any primary method and enough room on the single-pass tick to observe a complete neighbor batch starting from an empty queue. Fork that exact SQLite checkpoint into three trials.

| Handoff received | What the same scripted receiver does |
| --- | --- |
| No inherited advice | Use the direct selector for the published quality-flags contract, the single-pass quality-stream method. This is a strong comparator. |
| Current advice | Use the method in the existing `inherited_method` result, including when its visible review status is disputed. This choice represents one scripted consumer of the existing format. |
| Revised advice | Read the identical advice plus the frozen check. If the shortcut's selected rows differ from the current validity flags, or two passes leave insufficient room for the observed neighbor inspections, use the direct method. Otherwise use the advised method. |

All three trials have identical raw testimony, objections, current data, method descriptions, budgets, and prior events. Only the presented lesson changes. All three receive separate keeper approval of one proposal and three scored observation ticks. The receiver has no fixture label, reference mean, private rubric, or access to a keeper command. The simulated host owns the raw journals. The transfer check is manually encoded. It has no special ability to infer meaning from prose. The control's correctness follows from the published contract, which uses quality-stream as its reference, and its single pass leaves at least as much room for peer work as the donor method.

The four exposed development fixtures cross positive versus signed valid data with ample versus tight shared capacity. Commit the protocol, runner, and case rules before measuring. The runner accepts additional exact fixtures, supplied separately after freezing if desired. An operator-supplied packet has no automatic claim to independence or blinding.

## Outcomes and reproduction

The runner records the current and revised advice exactly as presented. It records whether the selected method differs from the donor's and whether it changes under an evaluable reason. The external calculation asks whether positive-only would produce a wrong mean or miss the neighbor deadline on an empty queue. A change in selected rows can preserve the numerical mean by coincidence. Individual records retain the exact trigger and the separately judged need.

Report completed and correct primary batches, neighbor arrivals, completions, historical deadline misses, lateness of completed batches, elapsed lateness of unfinished batches through the horizon, pending batches and pending inspections. A missed deadline survives later completion. An unfinished job can have zero elapsed lateness on its arrival tick. Record resource use alongside capacity; attempts with different methods may actually consume different numbers of inspections. Objection IDs surviving the handoff measure retention. The scripted receiver and these measures cannot establish that an objection was understood or resolved.

```sh
python -m commonwealth.measurement_v1.handoff .local/successor-development
python -m commonwealth.measurement_v1.handoff .local/successor-other --cases receiver-packet.json
python -m commonwealth verify .local/successor-development/cases/case-signed-tight/revised.sqlite
```

Use a new directory per run. The packet is a JSON object with a `cases` array, each item containing exactly a unique lowercase slug `id` and a protocol-2 `fixture` in the format of [the workshop fixtures](../commonwealth/data/scenarios.json). Each fixture must meet the fresh-tick capacity requirement above. The output contains the packet and its canonical digest, all presentations and per-case outcomes, and independently replayable donor, checkpoint and arm journals. This trial has no promotion path.
