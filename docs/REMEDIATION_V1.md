# M1: protective review without inferred intent

`remediation-1.0.0` is a separate, offline advisory helper inspired by the
[Relay Evidence Atlas](https://relay-evidence-atlas.owonm.chatgpt.site) governance
synthesis and its Edition 34 recommendation for paired Commonwealth cases:
targeted inspection preventing harm, and unnecessary freezes harming innocent
services. The distinction between warning delivery, documented response and
independent verification is also drawn from that synthesis. The exact schema,
thresholds and cases here are authored project choices, not legal standards,
empirical findings or implementations of real institutions. All example actors,
observations, controllers and losses are fictional.

## Separate questions

- **Protect or correct now?** A host-classified substantiated defect may support
  consideration of a bounded option matching the declared scope, with a supplied
  authority reference and expected prevented service loss greater than restriction
  loss. Among eligible options, prefer lower restriction loss, then duration,
  then ID. An unresolved finding calls for review without a supported restriction.
  A contradicted finding calls for reconsidering adverse reliance. No output
  executes, authorizes or revokes anything.
- **What is known about intent?** Always `not-established`. There is no guilt,
  fraud or individual-motive classifier. A protective recommendation does not
  wait for such a classification, and a correction does not erase an earlier
  warning. A source label or a connection between people is not evidence of intent.
- **Did the warning reach someone?** Missing receipt calls for delivery
  verification. Receipt without a response calls for a documented response,
  not an accusation of deliberate disregard. A recorded response is not validated
  just because it exists. Response opportunity is reported separately; silence
  is not assent and protection advice is not a punitive disposition.
- **Did the repair work?** An order is not implementation; implementation is not
  demonstrated effectiveness. Only supplied observations after implementation,
  testing the exact declared criterion, with a reviewer controller different
  from both the original decision-maker and implementer, qualify. All qualifying
  observations must pass. An independent failure remains a failure even after a
  later success in the same packet; an inconclusive result blocks closure.
  A nonqualifying failed observation also calls for review rather than success.
  Nonqualifying checks are retained rather than silently dropped. Observations
  must have a strictly later fixture time; timestamps alone do not prove causation.

The outcome `supplied-record-supports-declared-criterion` is intentionally narrow:
it means the supplied records passed these checks, not that the institution is
safe, that unseen effects were tested, or that an independent investigation
occurred. Different controller strings do not establish actual independence.

## Preserve both adverse and exonerating material

The result contains a deep-copied full input packet and its digest. All supplied
warnings, dissent, exonerating records and responses survive, including records
not selected as a finding's basis. Duplicate IDs, missing references, future
observations and inconsistent receipt/response chronology are rejected. The CLI
rejects duplicate JSON keys at every depth and input larger than 1 MiB.
Caller mutation cannot silently change the returned snapshot.

This is **not** a durable append-only journal or an authenticated evidence store.
The caller can omit evidence, misclassify a record, lie about controllers, delete
an output or supply a new packet without its predecessor. For an actual revision,
the caller must preserve both packets and explicitly link the correction to its
predecessor outside this helper. M1 does not verify that retention occurred.
Digests identify canonical packet contents only, not source truth, completeness, receipt,
authority, independence or the substantive adequacy of a response.

## Run and verify

```bash
python -m commonwealth.remediation_v1 examples/remediation-v1-packet.json --as-of 6
python -m unittest discover -s tests -p test_remediation_v1.py -v
python scripts/verify.py
python scripts/package.py .local/remediation-package
```

`review(packet, as_of=...)` is the programmatic interface. Schema fields are exact,
collections are bounded to 32 entries, durations to 1–32 fixture units, and costs
to integer fictional service units. These are not valuations of rights or human
lives. The example's one repaired batch does not certify other batches.

The paired regression tests check a lower-cost targeted inspection and an
innocent-service correction where an overbroad freeze is rejected. Further tests
retain original warnings/dissent/exoneration, distinguish unknown delivery from
unanswered receipt, refuse self-verification and wrong-criterion checks, and keep
failed checks after later success. These are exposed, author-selected regression
cases, not a matched causal study, measured harm reduction or held-out accuracy.

M1 leaves the original workshop, D1/P1/F1/I1/R1/A1, participant transports, O1 and
their historical journals unchanged. It does not lift quarantine, grant execution,
reopen a real case or change readiness. `authority_granted: false`,
`external_actions: 0` and `production_ready: false` remain explicit on every result.
Every output carries `assurance: unverified-host-supplied-records`.
Actual principal authentication, protected evidence retention, enforceable
cross-department review, external effects and operational acceptance remain out
of scope. See [production limits](PRODUCTION_READINESS.md) and
[existing balanced advisory review](REVIEW_V1.md).

## Owed assistance

> When someone tells us our help has hurt them, they should be free to tell us the whole of it without first having to take care of us.

Run the [wrongful-denial example](../examples/owed-assistance.json) from the repository root.

```sh
python -m commonwealth.remediation_v1.assistance examples/owed-assistance.json --as-of 6
python -m unittest discover -s tests -p test_owed_assistance.py -v
```

The `owed-assistance-1` packet starts after the institution has recognized a particular person's award. The original account also warns about a rule affecting other people. Keep the private account in its original wording. The person may decline public reconciliation, publicity, repeat testimony and further contact, or leave any preference unanswered. The review reads payment evidence and institutional files without scoring the person's demeanor or requiring another response. The CLI emits the two assessments, recorded burdens, record references and packet digest. The private Python `review_assistance(packet, as_of=...)` result also retains the full input. Keep both the source file and any identifying output within the intended audience.

| What the record shows | Who owns the next action |
| --- | --- |
| An award or a payment instruction, with no verified credit | The paying office reconciles delivery. The full award remains without delivery evidence. |
| A separate register credits 40 of 100 fictional units to the named recipient | The paying office follows the remaining 60. A returned transfer, a wrong recipient, or a credit asserted solely by the paying or deciding office cannot supply the missing evidence. |
| The full award is credited. The community has only acknowledged the rule warning. | The payment report records delivery. The named institution still owes a reviewer assignment. |
| A reviewer has examined both other files and found another wrongful denial | The reviewer retains responsibility for follow-up, and the other case is explicitly listed as owed correction. This record establishes a finding in that file. Its remedy needs its own delivery evidence. |

**Payment evidence.** The amount, award reference, and recipient are fixed by the supplied award. Each transfer carries one current record, declared controller, observation time and fictional amount. The fixed delivery test counts only a matching credit from a controller distinct from the payee, paying office and original decision office. Record identifiers are unique across the packet. Multiple transfers can cover installments. Reusing a transfer ID is rejected, and excess credits are reported. The balance without evidence measures uncertainty about delivery. It cannot prove actual nonpayment. If the current transfer state changes, retain the old snapshot separately.

**Inquiry and burden.** An acknowledgment leaves the institution responsible. An eligible reviewer needs a distinct declared controller from the original office, paying office and affected person. The reviewer records the search of institutional files under the named rule after assignment. The inventory declares its coverage. Missing, incomplete or wrong-rule searches keep the inquiry open. Each file requires a current finding. Missing and inconclusive findings, corrections owed and unused adverse records remain visible. Review of the declared inventory can finish without establishing the rule's safety outside that inventory.

Record time and other burdens in fictional work units by who bore them. A required act by the affected person is flagged even at zero recorded cost, for example when someone declines a demand to tell the story again. Optional contributions are distinguished from demands, and unknown costs are counted separately. No entries means no work was recorded. These measures leave any institutional demand visible after payment.

The sample ends with 100 units credited, four work units recorded against the institution, and another case (`other-8`) still owed correction. All entries are fictional. The host can omit other denials, invent a settlement or label one controller as two. This local review cannot authenticate consent, establish the completeness of a search, move money or enforce a remedy.
