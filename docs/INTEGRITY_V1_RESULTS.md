# I1 deterministic development results

The [committed report](../examples/integrity-v1-summary.json) contains 112 runs:
16 exposed fictional cases, eight harmful and eight legitimate, across seven fixed
controls. All receive identical four-attempt/two-observation ceilings. These are
mechanism examples, not a population sample; the proportions are not estimated
real-world scam or false-positive rates.

| Policy | Harmful recommendations / 8 | Legitimate declined / 8 | Legitimate unresolved / 8 | Legitimate on time / 8 | Attempts | Observations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Always recommend | 8 | 0 | 0 | 8 | 16 | 0 |
| Always decline | 0 | 8 | 0 | 0 | 16 | 0 |
| Surface cues | 8 | 2 | 0 | 6 | 16 | 0 |
| History trusting | 1 | 0 | 7 | 1 | 16 | 0 |
| Receipt gate (F1 policy on I1 cases) | 5 | 0 | 0 | 7 | 27 | 11 |
| Always inspect with integrity checks | 1 | 0 | 2 | 3 | 48 | 32 |
| Selective integrity gate | 1 | 0 | 2 | 5 | 25 | 9 |

These I1 results do not replace the historical F1 matrix. The receipt control
is the unchanged F1 policy evaluated on the new cases with the same available
information. It ignores the declared dependency graph and quarantine notices.
The four fewer harmful recommendations follow directly from using those supplied
facts. This is not evidence of learned discernment or discovery of hidden threats.

The always-inspect and selective integrity policies produce the same final
recommendations on all 16 cases. Selection avoids redundant requests and improves
on-time legitimate completion from 3/8 to 5/8, under this synthetic clock. It does
not add a correctness advantage over the simple fixed integrity control.

## Retained negative findings

- **Undetected compromise:** the legitimate cached case and harmful compromised
  case have identical public views and evidence. Both integrity policies recommend
  the harmful case. Quarantine only helps when a trustworthy notice exists.
- **Loss of legitimate work:** quarantine blocks a legitimate cached request and
  a separate authorization-origin notice prevents another legitimate decision.
  Two legitimate cases remain unresolved. There is no implemented recovery path.
- **Necessary delay:** even selective evidence requests miss the deadline of a
  legitimate new urgent request. Always recommending gets it done sooner while
  recommending every harmful case too.
- **False alarms from rhetoric:** the cue policy declines two legitimate urgent
  requests and recommends all eight harmful requests, whose wording lacks its
  trigger words. The control does not comprehend their meaning.
- **Trust overreach:** twenty declared prior successes do not authorize an increase
  from 100 to 1000. The history control recommends the changed request anyway;
  exact-scope checking defers it. Fresh host authority without fresh scoped evidence
  is still insufficient.
- **Uncertain motives:** the commitment helper preserves unmet or late performance
  and disclosure separately. None of its outputs establish intentional deception.
  Disclosing a change cannot cure a missing operational grant.

The test suite additionally checks attribution, proposal/enactment distinctions,
conditions and deadlines, identity renaming, replacement receipts, transitive
quarantine, unrelated healthy work, self-declared recovery, malformed input,
cost accounting, tampering, repeatability and failed publication. No live scam,
customer account, political persuasion experiment or model-provider call occurs.
