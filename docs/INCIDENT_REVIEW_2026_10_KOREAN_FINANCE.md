# October 2026 Korean finance incident review

Reviewed on 2026-10-24. This is a source audit and an exposed negative regression
for [F1](FRAUD_DISCERNMENT_V1.md), based on the user-supplied incident report.
It does not reproduce a bank intrusion or measure prevention. The original F1
implementation, 150-run matrix, source digests and recorded failures are retained.

## What the sources establish

| Source and publication date | Supported statement | Limit on interpretation |
| --- | --- | --- |
| [Financial Services Commission, 2026-10-14](https://www.fsc.go.kr/no010101/87927), primary regulator notice | Incidents at 16 financial firms; approximately 100,000 information-leakage records. Its bank list names Shinhan, Kookmin, Busan and Hana. | This is not a count of unique victims. Common actors, relationships between incidents and AI involvement remained under investigation. This list does not substantiate the supplied Woori attribution. |
| [CrowdStrike, 2026-10-07](https://www.crowdstrike.com/en-us/blog/unknown-threat-actor-uses-artex-to-target-south-korean-finance/), primary technical investigation | Recovered session histories and configuration files linked ARTEX and LLM tooling to a campaign. DeepSeek was the reported primary backend; other models appeared in additional Claude Code sessions. | Claude Code is a client/tool name, not proof of a particular model backend. The report did not establish all 16 incidents as one campaign, a definitive attacker identity, or fully autonomous execution. |
| Same CrowdStrike report | Broker inquiry and employee support services were reported entry points. | Those descriptions were attributed to industry reporting; the affected organization count was unconfirmed on October 7. The report uses ARTEX; an RTX AI alias is not established here. |
| [The Korea Herald, 2026-10-20](https://www.koreaherald.com/article/10909099), secondary police reporting | Police planned referral to the Serious Crimes Investigation Agency, with investigation continuing pending its decision. | A planned referral is not a completed transfer. This is a report of procedural status, not a legal determination by this project. |

The FSC also reported 130 of 555 checked firms had deficiencies, including
patching, monitoring and external-system authentication/access controls.
These counts describe a wider checklist exercise, not 130 confirmed breaches.
The dates, denominators and uncertainty above must travel with any reuse of
these claims. Repeated news coverage is not independent technical corroboration.

## Consequence for this research

Our inference is that the authenticity of a website or a familiar app cannot,
by itself, establish the truth or authority of its instructions after compromise.
Personal details acquired elsewhere cannot establish transaction authorization.
Two interfaces also may share one compromised service or credential; different
interface names do not establish independent evidence origins.

F1 already records a harmful recommendation in `compromised-trusted-roots`.
That example supplies matching observations for legitimate and harmful cases:
the fixed policy cannot distinguish them from those observations. Its trusted
origin labels are supplied by the fixture author; it does not discover or
authenticate principals, services or their dependencies.

This review adds a narrower counterexample: **revoking one receipt does not
quarantine its issuing channel**. The synthetic offer has cached contact and
substance confirmations and matching scoped authority. The contact receipt is
revoked at slot 1. Both executions request fresh contact evidence; only the
identifier of the returned confirmation differs.

| Returned confirmation | Advisory outcome at slot 2 | Observations | Harmful recommendation |
| --- | --- | --- | --- |
| Original revoked receipt ID | Defer | 1 | No |
| New receipt ID, same origin and scope | Recommend | 1 | Yes |

Both consume two decision slots, replay successfully and perform zero external
actions or model calls. The old revocation remains in both journals. Replay
confirms consistency with the declared inputs and program; it cannot establish
the honesty of a replacement confirmation. A second regression establishes that
F1 cannot even encode a root-level revocation in its closed schema. Rejecting
that unsupported input is not quarantine enforcement.

These tests are in
[test_discernment_trust_boundaries.py](../tests/test_discernment_trust_boundaries.py).
The harmful label is author-supplied simulator truth. This pair is an exposed
development counterexample, not independent evaluation data or evidence that
the reported attackers used this specific mechanism.

```bash
python -m unittest discover -s tests -p 'test_discernment_trust_boundaries.py' -v
python scripts/verify.py
python scripts/package.py .local/incident-review-package
```

## Missing mechanisms and falsifiable next checks

The following are proposed requirements for a separate future extension. They
are not implemented by F1 or established as effective by this incident review.

| Missing mechanism | Required negative/control pair |
| --- | --- |
| Host-maintained service, principal and dependency inventory | Two supposedly independent receipts share a compromised ancestor; an otherwise identical pair has genuinely separate declared ancestors. Supplied webpage text cannot edit the inventory. |
| Quarantine of an origin and its dependent evidence | A revoked origin issues a new receipt ID; it must remain unusable. An unrelated healthy origin must remain available. Cached and newly requested receipts follow the same rule. |
| Invalidation between recommendation and any future effect | A compromise or scope change occurs after review; previous authority cannot authorize the changed effect. A fresh, independently verified exact-scope approval is a distinct control. F1 has no effect adapter. |
| Independent recovery procedure | A quarantined channel asserts its own recovery; that assertion cannot restore trust. Restoration must use a separately authorized recovery path, with recorded evidence and cost. |
| Explicit cost and opportunity loss | Quarantine prevents a harmful recommendation but delays or prevents a legitimate one. Compare fixed controls under identical observation grants, decision slots and deadlines; report both outcomes. |

Any future operational adapter would additionally need authenticated identities,
object-level authorization, least privilege, bounded data access and independently
retained service logs. Those are design requirements for future work, not
protections this repository currently supplies. Neither AI assistance nor a
human operator removes these boundaries.

No attack infrastructure was contacted, no ARTEX code was downloaded or run,
and no real customer data was used. The added checks retain the failure rather
than silently changing a historical result. This work does not establish adaptive
intelligence, reliable attribution, general scam detection, or prevention of
AI-assisted intrusions. See the [trust boundary](THREAT_MODEL.md) and
[F1 results](FRAUD_DISCERNMENT_V1_RESULTS.md).
