# I1: commitments and issuer integrity

Version `integrity-1.0.0` is a separate, offline research extension based on commit
`8b6992dd96d5179e899fe1fa9766246561ee6035`. It adds structured commitment review
and a fixed advisory policy over the frozen F1 simulator. Original workshop,
D1, P1/P1.1, F1 sources and recorded failures are unchanged. The package release
remains 0.1.3; I1 is not an operational deployment or a trained model.

The [source review](INTEGRITY_SOURCE_REVIEW.md) explains the political and consumer
fraud lessons and their limits. The [results](INTEGRITY_V1_RESULTS.md) include
failure and opportunity costs. All fixtures are authored, fictional and exposed.

## Commitments without inferred motives

`claims.review(commitment, action, as_of=...)` compares curated structured records.
The commitment carries actor, topic, an exact expected action token, specificity,
condition status, time, deadline and source reference. The action carries actor,
topic, an actual action token, procedural status, time, source, notice time and
explanation. Tokens describe what was actually done (for example, `veto-bill`),
not text appearing inside a proposed bill. Extraction and authentication are
outside this helper; a bad human encoding can produce a bad assessment.

It distinguishes fulfilled, fulfilled late, unmet in the supplied record,
pending with divergence, proposal only, insufficient specificity, unmet/unknown
conditions, another actor/topic, future observations and actions predating the
commitment. A notice flag is reported separately. It does not erase the original
expectation, validate the explanation or supply authorization. Every output keeps
`intent: not-established` and `authority_granted: false`. No classifier assigns
people guilt, ideological risk or permanent bad-actor status.

## Authority and evidence boundaries

The fixture host owns an acyclic dependency graph and dated quarantine notices.
Nodes represent declared issuers, services or controlling principals. An evidence
origin's closure includes itself and every ancestor. Nodes and dependencies must
exist; cycles, unknown quarantine roots and unsupported schema fields are rejected.
The host supplies a separate authorization origin. The program does not discover
these relationships or verify real-world identities.

| Condition | Integrity-gate behavior | Limitation/cost |
| --- | --- | --- |
| Exact offer scope lacks authority | Defer; history, labels, urgency and explanations cannot grant it | A changed amount needs separate host-supplied authority and evidence bound to the new scope |
| Evidence or authorization origin has a quarantined ancestor at the decision slot | Defer; cached and new receipt IDs are equally affected | A legitimate request can be blocked; a forged host notice can also harm availability |
| Contact and substance roots share an ancestor | Defer because independent corroboration is not established | Declared topology can be incomplete or overly broad |
| Healthy, distinct origins; valid scoped confirmations | Recommend | Undetected dishonest origins can still fool the policy |
| Healthy trusted contradiction | Decline | F1's contradiction and freshness rules still apply |
| Missing evidence with available grants | Request it through the fixed channel and account for the cost | No available evidence, exhausted grants or deadlines can leave a request unresolved |
| Claimed recovery in a message or attachment | No change to host trust state | Independent recovery is not implemented; no indefinite safety/availability guarantee follows |

Known quarantine takes precedence over evidence use. Other fixed controls can
still issue adverse recommendations for comparison: this is an advisory policy
experiment, not a mandatory execution firewall. All policies have access to the
same public view, graph, notices, declared history and ceilings; some controls
deliberately ignore fields. Hidden truth and future channel responses are absent
from views. Scheduled notices are declared inputs, applied prospectively at the
next decision slot. A completed advisory episode has no future effect to revoke.

Messages cannot mutate the host graph or notices. Direct object/filesystem access
remains trusted; this separation is not process isolation. The only actions are
F1 evidence requests, advisory decisions and waiting. Unsupported commands consume
a decision slot and are refused. There is no network, model-provider, financial,
remote-access or code-execution action.

## Fixed controls and reproduction

Sixteen cases cross seven fixed policies: always recommend, always decline,
surface cues, history trusting, F1 receipt gate, always inspect with the integrity
checks, and selective integrity gate. Each gets four attempts and two observation
grants. Both inspection and decision consume one slot; a deadline miss is retained.
The history control recommends after three declared prior successes. That threshold
is authored, not fitted. No policy learns or selects its rules from these results.

```bash
python -m commonwealth.integrity_v1 run .local/integrity-v1
python -m commonwealth.integrity_v1 replay .local/integrity-v1/journals/undetected-compromise--integrity-gate.json
python scripts/verify.py
python scripts/package.py .local/integrity-package
```

The writer refuses an existing destination, stages a complete result and uses
an exclusive writer lock. Journals bind the I1 assessment and F1 transition,
including each cost, to the supplied topology and case. Replay recalculates every
transition and terminal result. Digests identify source bytes and declared input;
they do not authenticate source authors or establish truth. The manifest covers
I1, F1 and the shared serialization/artifact helpers. The installed-wheel smoke
test runs all 112 comparisons and replays the retained undetected-compromise failure.

## What remains unsupported

There is no demonstrated adaptive intelligence, institutional advantage, real-world
scam reduction, independent held-out performance, semantic understanding, legal
judgment, principal authentication, discovery of concealed shared control or
automatic detection of compromise. All comparison differences are attributable
to authored fixed rules on exposed fixtures. A future extension needs an independent
recovery procedure, authenticated origin inventory, prospective invalidation of
any real effect authority, and separately controlled evaluation data before making
stronger claims. These tests do not establish a civilization's integrity.
