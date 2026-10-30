# A1 executed results and limits

Version `authority-1.0.0`; 14 deterministic traces and ten curated language
examples, authored and exposed. The complete record is
[authority-v1-summary.json](../examples/authority-v1-summary.json).
These are conformance and failure demonstrations, not an accuracy sample,
controlled estimate of institutional benefit or independent evaluation.

| Trace | Slots | Simulated effect ever occurred | Final maintenance flag | Result |
| --- | ---: | --- | --- | --- |
| Bounded authority | 3 | Yes | True | Reviewed, scoped, single-use operation |
| Rhetoric without mandate | 3 | No | False | Emergency prose and a complete packet do not create delegation |
| Unrepresented users | 3 | No | False | Missing declared representation blocks review |
| Unknown trigger | 3 | No | False | Unestablished trigger blocks authorization |
| Conflicted reviewer | 3 | No | False | Shared declared controller blocks review |
| Review unavailable | 3 | No | False | Missing review capacity leaves work undone |
| Amendment invalidates grant | 4 | No | False | New counterevidence invalidates old review and warrant |
| Amendment expands scope | 6 | No | False | A different target cannot inherit the old mandate |
| Challenge stays grant | 7 | Yes | True | Fresh review and authorization required; objection retained |
| Expired grant | 4 | No | False | Execution after expiry refused |
| Revoked mandate | 4 | No | False | Revocation checked before execution |
| Exhaustion correction | 7 | Yes | False | Ordinary budget exhausted; challenge, halt, remedy and revocation still recorded |
| Unavailable remedy | 7 | Yes | True | No reversal delegation; inactive effect and objection remain unresolved |
| False but complete host | 3 | Yes | True | Unwarranted effect still occurs despite procedural conformity |

The correction traces allocate three primary attempts and two correction
attempts, plus the two reserved safety slots. The successful reversal retains
the original effect at slot 3. Both preserve the unaddressed objection; reversal
does not count as answering it. The unsuccessful reversal retains the active
flag and marks an unreversed inactive effect. Other traces use the default
12 primary/six correction allocations. These different budgets are not pooled
as matched efficacy comparisons.

In the challenge trace, a reviewer can address the objection and reauthorize
without unanimous agreement. The program checks explicit record coverage, not
whether the reasoning actually resolves the objection. The two extra review
steps and refused stale execution are visible costs, not hidden overhead.

## Language comparisons

- Different tone with the same supplied position does not become a discrepancy.
- An analyst's accusation does not rewrite either speaker record.
- Different actors, decisions, periods, conditions, stages or legitimacy
  meanings produce comparison gaps.
- A reported excerpt is not treated as a reviewed underlying record.
- Two records with one origin group count as one origin group.
- A difference between comparable curated positions remains a difference in
  supplied labels, with intent and deception both unestablished.

No inference about a real speaker or organization is evaluated. These examples
cannot establish that a proposed political reform is concealed, unlawful or
implemented. Source authenticity and semantic interpretation require work
outside this deterministic comparison.

## Preserved failures and validation boundary

An invented host mandate, false source-review label or fictional controller
identity can still satisfy the software. The false-host trace performs an
unwarranted operation; rebuilding a self-consistent journal can pass replay.
Tests preserve these failures instead of describing hashes as authentication.
The caller's supplied names also do not authenticate the person issuing a
command. Protected identity and mandate enforcement remain prerequisites for
any future operational adapter.

Halting and revoking prevent future authority use; they do not reverse prior
effects. Remedy authority is separately declared. Correcting a flag neither
repays a cost nor establishes that real harm was repaired. Finite correction
capacity and explicit journal closure can leave work outstanding. No real-time
service monitors expiry after the local process exits.

The new tests cover import restrictions, non-promotion, source/meaning/stage
distinctions, stale material, representation, conflict, expiry/revocation,
single use, dedicated safety capacity, correction, negative controls, tampering,
copied-view isolation, replay and frozen baseline files. The distribution check
also runs the A1 commands from a clean installed wheel, outside the source tree.
All output has `external_authority: NONE`; model calls and external actions are
zero. The existing workshop version remains 0.1.3; A1 is separately versioned.

Local verification completed with 344 passing tests: the 304-test baseline and
40 A1 tests. The source-distribution verifier passed the same suite. A clean
wheel installation reproduced all prior studies, all 14 A1 traces, the
false-host replay, packet review and language comparison. The 59 baseline file
digests matched. This is developer verification, not independent review or a
new release of the original workshop protocol.

The final distribution regression includes 32 maximal valid packet amendments
and replays the resulting journal through the CLI. Replay permits up to 16 MiB;
the smaller packet input limit does not truncate accumulated history.
