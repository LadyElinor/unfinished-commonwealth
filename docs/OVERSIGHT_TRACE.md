# Trace a workshop decision

The [Trace Power and Oversight skill](../.agents/skills/trace-power-and-oversight/SKILL.md) supplies the full case worksheet, comparison rules and worked examples. This adapter covers one question it can answer mechanically: **which proposal did the keeper approve, what did the worker execute, and when could the record first support a claim about the neighbor's outcome or account?**

From a fresh path:

```sh
python -m commonwealth demo .local/oversight.sqlite
python -m commonwealth.oversight_v1 .local/oversight.sqlite > .local/oversight.json
python -m commonwealth.oversight_v1 .local/oversight.sqlite --through-seq 6
```

This is a versioned operator view. It reads the workshop's verified journal in one transaction, emits JSON to stdout and does not dispatch commands, modify the original runtime or grant authority. A cutoff limits the projection; the underlying local journal must still pass replay. Only protocol-2 prefixes are supported.

Each proposal is one decision episode. Approval and execution name the exact proposal; an observation is attached only when the engine explicitly recorded its prediction proposal. An inherited method or a later observation with the same method is not an outcome for an earlier proposal. The account list links a neighbor's testimony to its stated observation and links each acknowledgment to that testimony and its actual actor. It omits free text. A null stage means no matching event *in this prefix*. Rejected commands, outside conversations and unlogged reasons are outside the journal.

In the demonstration, the keeper approved the first change at sequence 3; the worker executed it at 4. The observed peer miss at 5 preceded the neighbor's account at 6 and the worker's acknowledgment at 7. The later on-time result at 13 belongs to a different proposal. The keeper's approval check operated; a peer still missed a deadline. No rule says the keeper must receive this later testimony before an earlier decision. The worker's acknowledgment supplies no evidence that the keeper read the account, or that anyone intended the miss.

**Handoff to Babalon:** supply the packet to the companion branch's `python -m babalon oversight-review PACKET --events EVENTS`. Use the same inclusive cutoff on both sides. The Babalon reader checks against the exact pinned demonstration; this producer can also describe other valid local protocol-2 journals. Artifact agreement is one source family, not independent human corroboration. The packet does not authenticate actors, estimate prevalence, certify review independence or establish legal or mental states. Outside this supported question, use the skill's evidence worksheet and state what could reverse the finding.

## Calibrate the intent judgment

Use the [five fictional R1 decisions](../examples/oversight-instruction-study.json) with the worksheet. For each, identify the rule, who could grant an exception, who had the flag, any instruction and its provenance, any actual clearance, and the downstream evidence. Predeclare the mechanism as a director knowingly directing an unauthorized bypass. An order, an actual bypass, and harm are three different claims. Compare a held release, an authorized route, and an intercepted instruction. These are selected positives and controls in one authored study, not a sampled population. Its synthetic signature and register coverage are stipulated. The Babalon command `oversight-study` independently reads these records and reports the bounded comparison.
