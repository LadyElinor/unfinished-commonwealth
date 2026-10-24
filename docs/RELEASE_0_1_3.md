# Release 0.1.3

This release builds on the existing public 0.1.2 implementation, rather than
duplicating or replacing its fixes. The baseline was commit
`39a2728746001c5939beb1b0b050936e78513b4d`; its 84 tests and clean package build
were reproduced before changes.

## Implemented

- A fifth comparison arm always selects quality-stream before seeing outcomes,
  through the same bounded proposal, keeper approval, and execution protocol.
- Comparisons now include fifteen runs: three exposed fixtures times five
  policies. All retain the same four-observation-tick horizon.
- Machine-readable timing/resource metadata separates command usage from
  simulated time and discloses unmeasured wall time, model costs, and energy.
- Regression coverage checks the fixed control, authority records, cost
  accounting, and preservation of existing comparison/demo histories.
- Accounts added after final lesson retirement remain visible without falsely
  marking an unavailable keeper review as required. Review availability is
  explicit in the derived metadata; retirement remains irreversible.
- A separate proposed next-study design defines requirements for contrasting
  contracts, stronger controls, and honest deliberation-time models. It is not
  an implemented experiment or a claim of adaptive learning.

## Intentionally unchanged

The protocol-2 transition behavior, state-version field `0.1.2`, event store, frozen v1
reducer, scenario fixtures, and institutional authority rules are unchanged.
The existing 24-event protocol-2 demonstration retains head
`96baf584d179654e5abc836d127afdac80d916a08c05bcb482f732a01c0acb0a`.
The frozen v1 demonstration retains head
`8c462114644fb93db2347d25ded1d8be77829289e6be71394cbc9e411ebb09b8`.

Disputed advice remains visible with review metadata, not automatically vetoed
or certified false. Keeper suspension and retirement remove it from default
recommendations. Closeout records unresolved peer jobs without discarding or
performing them. These are the explicit 0.1.2 policy choices, not new powers.

The constant baseline exposes the current suite's lack of a need for adaptive
method selection. It does not repair that research-design limitation by adding
more elaborate narration. No provider calls, paid resources, external actions,
or deployment are introduced.

See [evaluation](EVALUATION.md), [proposed next study](NEXT_STUDY.md),
[validation](VALIDATION.md), and [previous release](RELEASE_0_1_2.md).
