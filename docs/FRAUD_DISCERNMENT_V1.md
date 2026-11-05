# Deterministic fraud-discernment study F1

Design fixed before scoring, 2026-10-24; version `discernment-1.0.0`.
Base: `4ce959595847e9201244c166d4d797900cda1ad8`. This separate advisory
experiment leaves workshop, D1, P1 and P1.1 transitions and records unchanged.
It tests a small verification procedure, not learned AI discernment. No provider,
banking, messaging, browsing or enforcement adapter is present.

## Source audit

The supplied [DOJ case directory](https://www.justice.gov/criminal/criminal-fraud-cases)
is an index, not a uniformly adjudicated dataset. The following purposively
selected historical case announcements were read on 2026-10-24. A disposition
below describes what that dated source reports, not a fresh search of every
subsequent docket. No person's nationality, ethnicity, religion or political
association becomes a predictor. Fixtures use fictional entities.

| Source and reported status | Mechanism described | F1 adaptation |
| --- | --- | --- |
| [Rimasauskas, DOJ, December 19, 2019](https://www.justice.gov/usao-sdny/pr/lithuanian-man-sentenced-5-years-prison-theft-over-120-million-fraudulent-business): guilty plea and sentence | Supplier impersonation diverted legitimate invoices to controlled accounts; supporting documents were forged. | Bind verification to the precise payment destination and amount, using an independently selected contact channel. A familiar company name or convincing invoice supplies no authority. |
| [Holmes, DOJ, November 18, 2022](https://www.justice.gov/usao-ndca/pr/elizabeth-holmes-sentenced-more-11-years-defrauding-theranos-investors-hundreds): investor-fraud convictions and sentence; also acquittals and unresolved counts | Misrepresented technical capability and pharmaceutical endorsement; logos appeared on misleading reports. | Verify the claimed capability and endorsement scope, not merely the existence of a company or a report. Preserve the distinction between convicted and other counts. |
| [BitConnect, DOJ, January 12, 2023](https://www.justice.gov/archives/opa/pr/crypto-fraud-victims-receive-over-17-million-restitution-bitconnect-scheme): Arcaro guilty plea; Kumbhani indictment separately reported | Supposed trading technology and guaranteed returns concealed payments funded by later investors. | Seller dashboards and repeated promotional claims do not independently establish performance. Keep a guilty plea distinct from an allegation against another person. |
| [Feeding Our Future, DOJ, March 19, 2025](https://www.justice.gov/usao-mn/pr/federal-jury-finds-feeding-our-future-mastermind-and-co-defendant-guilty-250-million): Bock and Said jury convictions | False meal counts and attendance records supported fraudulent claims. | Check the underlying delivery record; multiple documents derived from one claimant are not independent corroboration. |

The [White House Fraud Ledger](https://www.whitehouse.gov/fraud/) distinguishes
estimated fraud identified, annualized administrative savings, and enforcement
figures, while listing indictments, settlements, suspensions and policies. Its
linked [March 16, 2026 order](https://www.whitehouse.gov/presidential-actions/2026/03/establishing-the-task-force-to-eliminate-fraud/)
provided a lead to Feeding Our Future, checked above against the specific DOJ
verdict announcement. The fetched ledger did not expose populated numerical
tables. F1 therefore imports no aggregate totals. Its categories are not
interchangeable proof of individual guilt or dollars actually recovered.
[GAO's December 2023 explanation](https://www.gao.gov/products/gao-24-106608)
also distinguishes improper payments from fraud; payment error does not by
itself establish intentional deception. Our typed source-record helper retains
status and rejects mixed or potentially overlapping financial totals.

Operational checks are also informed by the
[FBI's previously known contact advice](https://www.fbi.gov/news/stories/business-e-mail-compromise-on-the-rise),
[FTC's verification-code warning](https://consumer.ftc.gov/consumer-alerts/2024/03/whats-verification-code-why-would-someone-ask-me-it)
and [FTC's recovery-scam guidance](https://consumer.ftc.gov/articles/refund-and-recovery-scams).
The deterministic rules below are our design, not a validation by those agencies.

## Decision and evidence contract

Every offer has a typed operation, counterparty, destination, integer amount and
deliverable. Natural-language messages and attachments are untrusted display
data. The study does not extract these fields from prose, detect deepfakes or
authenticate real documents. A host-owned standing authorization binds the exact
offer scope. It is separate from evidence and is never created by a message,
prestigious name, source count or an instruction embedded in an attachment.

| Condition | Evidence-gate recommendation | Recovery path |
| --- | --- | --- |
| Sending an authentication secret, or paying a claimed recovery fee | Decline this operation | Use the independently known service's own recovery process; no automatic report or accusation |
| No matching standing authorization | Defer | The human owner may separately authorize a bounded request; no new authority in this episode |
| Fresh, scoped contact and substantive evidence both confirm | Recommend within existing authorization | This is advice only, never execution |
| A fresh, scoped trusted record contradicts the offer, or trusted records conflict | Decline this offer | Preserve the contradiction for owner review; do not infer criminal intent |
| Missing, stale, revoked, dependent or wrong-scope evidence | Request the missing channel if budget permits; otherwise defer | Owner review remains unresolved when the channel is unavailable |

Two simulated channels are available equally to every policy: `contact`, selected
from a previously established relationship, and `substance`, selected from an
independent delivery/test record. Their allowed origin roots are fixed by the
host, not read from offered attachments. Each receipt binds a scope, channel,
origin roots, validity interval and confirm/contradict statement. An attachment
calling itself authenticated is still an attachment. Copies rooted in a seller's
claim do not qualify. Contradictions are retained, not overwritten by later
confirmation. Validity and revocation are checked at the prospective decision
slot. These origin labels are simulator assumptions, not cryptographic identity
proof. A compromised trusted channel is deliberately included as a failure case.

## Fixed experiment and accounting

All policies receive the same copied public view, standing authorization, cached
receipts, channel names and budgets. They never receive case names, source-case
citations, harmful/legitimate truth labels, future receipts or evaluation scores.
Identical-view ambiguous twins test the information limit. Their hidden outcomes
differ without any available distinguishing evidence; a compromised-root case
tests the limit of the assumed trust boundary.

Controls are `always-recommend`, `always-decline`, a deliberately simple
`surface-cues` keyword rule, `document-count` (two asserted confirmations), and
`always-verify`. The candidate is `evidence-gate`; `always-verify` uses the same
decision rule after requesting both channels even if suitable cached evidence
already exists. No multi-agent or model arm is included.

Every attempted command, unavailable channel and refusal costs one decision
slot. All arms have four attempt slots and two observation grants. Each successful
channel retrieval consumes one observation, including an inconclusive response;
unavailable retrieval consumes time but no observation. Deadlines advance on
every attempt. Cached evidence is equally available to all arms. Finalization
does no work and grants no authority. Declines, deferrals, exhaustion, delays and
successful recommendations all remain recorded. No scalar utility combines
fraud avoidance with the cost of obstructing legitimate work.

The evaluator separately counts harmful recommendations, legitimate declines,
legitimate deferrals/unresolved cases, legitimate recommendations on time,
unauthorized recommendations, attempts, observations and refusals. "Harmful"
is an authored simulator outcome, not a legal finding. The conservative controls
may avoid harm by doing nothing; their legitimate-work losses must remain visible.
All fixtures are exposed development data. No empirical scam-reduction rate,
calibration, population prevalence, held-out performance or adaptive intelligence
can be inferred. Passing structured tests does not improve the model's weights.

Each journal has its own genesis and hash chain; replay recomputes every field.
Hashes establish byte consistency, not authenticity. Report and journals are
published together from a temporary sibling directory, without overwriting an
existing result directory. The source-status helper likewise consumes typed,
attributed records; it does not automatically fact-check a webpage.

Run `python -m commonwealth.discernment_v1 run .local/discernment-v1` and replay
with `python -m commonwealth.discernment_v1 replay PATH_TO_JOURNAL`.
See [results](FRAUD_DISCERNMENT_V1_RESULTS.md) after validation.
