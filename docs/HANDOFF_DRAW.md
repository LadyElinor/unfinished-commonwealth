# Prospective synthetic successor draw

This supplementary draw tests the frozen successor policies on new workshop instances. It uses the protocol-2 quality-flags contract and shared FIFO peer queue. The study team wrote the design with knowledge of the methods. The exact instances are generated only after freezing both the runner and this generator.

The 24 workshops balance four types of readings against two resource conditions, with three replicates per cell. Compatible positive readings permit the inherited positive-only method. A valid zero, a valid negative, or an invalid positive reading changes what that method includes. Tight budgets can finish either primary method but complete the arriving peer job on the one-pass method only. Slack budgets fit both primary methods and the peer job. The study examines these particular conditions. By construction, the one-pass quality-stream control can obtain the reference mean and meet the immediate peer workload in every cell. This cohort cannot estimate how often these situations occur elsewhere.

Case names disclose only order, descriptions are constant, and row positions, readings, peer workloads and capacities vary by seed. The host requires an explicit reference. The generator computes that reference as an exact fraction from the valid input readings.

**Draw once.** Record the source revisions of the generator and runner before obtaining 32 fresh bytes from the operating system. Publish the seed and packet digest with all cases. Reproduce the packet with `python scripts/draw_successor_handoffs.py SEED NEW_PACKET.json`; use the handoff measurement command on that file. Preserve the initially drawn cohort, including input validation failures. A change to eligibility, fixture interpretation or scoring after the draw requires disclosure.

Read the primary outcome and peer deadline at the successor's decision tick together with the cost of the required fresh observation, accumulated peer delay and outstanding work. Compare every matched case with both current advice and the direct no-advice control. Record unresolved objections separately. A revised handoff that merely recovers the no-advice result has shown the cost of stale advice under these conditions. It has not earned an improvement over the direct policy.

## Results of the single draw

The [protocol, runner and generator](https://github.com/LadyElinor/unfinished-commonwealth/commit/c598c02859df184dccd8198634fec9d23048720d) were committed before the operator drew seed `435620de2a2f7a70f70cb0c7e038e29c8e13b20056b395aea320d419e402f93e`. All 24 generated fixtures were admitted. The [input packet](../examples/successor-handoff-draw-packet.json) and [per-case output](../examples/successor-handoff-draw-results.json) include all 72 arm results.

| Handoff | Correct primary batches / 72 | Neighbor deadlines missed / 72 | Neighbor batches completed / 72 | Primary inspections | Neighbor inspections |
| --- | ---: | ---: | ---: | ---: | ---: |
| Direct, no inherited advice | 72 | 0 | 72 | 468 | 504 |
| Follow the donor | 18 | 36 | 53 | 936 | 408 |
| Check the lesson against the new shift | 72 | 0 | 72 | 516 | 504 |

Each arm received 1,437 inspection credits across the scored ticks and completed all 72 primary calculations. Following the donor left 19 unfinished neighbor batches with 96 inspections outstanding, in addition to 17 batches that eventually finished late. Elapsed lateness was 18 ticks for completed batches and 9 through the horizon for unfinished batches. Revised advice directed the successor away from the donor method in 21 workshops. In the other three it followed the donor and used more primary inspections than the direct selector. Every final state retained the same unresolved neighbor objection.

The three repeated ticks follow one decision per workshop. They are not 72 independently sampled workshops. The 24 fresh observation ticks are separate, shared pre-decision observations. All 24 computed an incorrect zero-fill mean, using 156 primary inspections. All 24 neighbor batches finished on time using 168 inspections, with a total fresh allowance of 479. No policy received an extra observation.

A separate arithmetic recount checked the primary means as exact fractions and computed completion times from FIFO service capacity and batch size, across all 216 scored ticks. All row outcomes, all 97 donor/checkpoint/arm journals, matched journal prefixes, fresh references and keeper approvals verified. Regenerating the packet and rerunning the frozen comparison reproduced the committed packet and report byte for byte. The experimenters controlled the generator, policies and evaluation. The draw tests the declared conditional scenarios and establishes no improvement over the direct selector.

| SHA-256 scope | Digest |
| --- | --- |
| Case generator source bytes | `e89508e734b9216cae4f05a683592db495a3971981a5ccebf018cca5ec0df482` |
| Frozen runner source bytes | `6165f8779b5076538a63d1be37bbaed5ead4f156a098de6eb9c58ff78b5fa18a` |
| Generated packet file bytes | `5457025437979a9d7e51b01437c5196d4018f374250b12d9535ad0405a8c64ba` |
| Packet canonical JSON used by the runner | `db0db6edfb7621df6c9e68b42bf759b77b1d6e6a6199b200030c7be0baf948d3` |
| Full result file bytes | `56e8c9f8e367c26fc2d56bead51f394f881fab805c2d9d38d72b8a8d7315d02c` |

```sh
python scripts/draw_successor_handoffs.py 435620de2a2f7a70f70cb0c7e038e29c8e13b20056b395aea320d419e402f93e packet.json
python -m commonwealth.measurement_v1.handoff .local/successor-draw --cases packet.json
python -m scripts.check_successor_draw .local/successor-draw
```
