# Release 0.1.2

This release fixes misleading scripted testimony, invisible disputes in inherited
advice, and the loss of terminal controls at the command ceiling. It also requires
current-generation observation before successor proposals. It adds no external
execution authority or model-backed research claim.

## Behavior

- Scripted testimony and acknowledgment describe the actual linked primary and
  peer outcomes. Failed primary outputs are no longer described as passing.
- Inherited advice, participant packets, and reports expose dispute status, linked
  counterstories, unaddressed challenges, and keeper review history. A keeper may
  retain, suspend, or retire an accepted lesson with a recorded reason. Suspension
  and retirement remove it from recommendations without deleting its history.
- After 256 accepted operational commands, up to 32 testimony/review commands
  remain. Halt, revoke, and closeout each have a separate one-use terminal slot.
  No additional pipeline operations are permitted. Closeout records unfinished
  peer work as unresolved, with a follow-up note; it does not perform that work.
- All successor proposals, approvals, and executions require an observation in
  the current generation. Applying the gate to every successor avoids relying on
  self-reported use of inheritance. New proposals record the observation ID;
  separate keeper approval and existing binding/expiry checks still apply.
- Advice, participant observations, and successor proposal evidence use numeric
  event/tick order, avoiding lexical reordering at IDs such as 9 and 10.

Counterstories remain unadjudicated accounts, not automatic vetoes. Retention
does not certify truth. The keeper role remains an unauthenticated fixture label.

## Replay

Unversioned events use the exact v1 reducer preserved in `legacy_v1.py`. Historical
rows and hashes are never rewritten. Every newly accepted event carries integer
`protocol: 2`; a mixed journal upgrades its working state atomically on its first
new event. Reads and refusals do not migrate state. Downgrades and unknown tags
are refused. Old versions cannot read a journal after v2 events are appended.

The frozen 0.1.1 demo still verifies to
`8c462114644fb93db2347d25ded1d8be77829289e6be71394cbc9e411ebb09b8`.
The new 24-event demo verifies to
`96baf584d179654e5abc836d127afdac80d916a08c05bcb482f732a01c0acb0a`.
A second frozen fixture preserves a historical successor execution without an
observation, demonstrating the difference between historical replay and the
requirements for a new command.

## Research limits retained

Reflection uses a command but no simulated time. Fresh observation means since
handoff, not a wall-time freshness guarantee. `quality-stream` defines the
reference answer for all exposed scenarios, so the comparisons still cannot
demonstrate adaptive method selection, causal coaching effects, or independent
machine civilization. See [evaluation](EVALUATION.md), [protocol](PROTOCOL.md),
and [validation](VALIDATION.md).
