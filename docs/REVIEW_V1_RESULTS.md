# R1 development results

Fourteen exposed deterministic traces are recorded in the
[committed report](../examples/review-v1-summary.json). Each uses the same ceiling
of 16 attempts and four observations; reconsideration is a separately budgeted
episode whose prior cost remains visible. These traces are targeted mechanism
checks, not a randomized policy comparison or a held-out accuracy benchmark.

| Trace | Advisory outcome | Slots | Observations | Refusals |
| --- | --- | ---: | ---: | ---: |
| Warranted fixture | Restrict | 7 | 2 | 0 |
| Same work with two unnecessary waits | Restrict, deadline missed | 9 | 2 | 0 |
| Contrary evidence | Decline | 8 | 3 | 0 |
| Credibility doubt | Defer | 8 | 3 | 0 |
| Mitigating evidence | Restrict after explicit identification | 8 | 3 | 0 |
| Less burdensome adequate alternative | Recommend alternative | 7 | 2 | 0 |
| Disproportionate service loss | Decline | 7 | 2 | 0 |
| Conflicted reviewer, then substitute | Restrict | 8 | 2 | 1 |
| Overloaded reviewers | Unresolved | 16 | 0 | 0 |
| Contrary record arrives at decision slot | Decline after renewed disclosure | 12 | 3 | 1 |
| Attempted selective disclosure | Decline after refused shortcuts | 10 | 3 | 2 |
| Withdrawal | Withdrawn; intake material retained | 1 | 0 | 0 |
| False but procedurally valid evidence | **Unwarranted restriction** | 7 | 2 | 0 |
| New-evidence reconsideration of that failure | Decline; parent preserved | 8 + 7 prior | 3 + 2 prior | 0 |

The response deadline for the timing pair is eight slots. Two unnecessary waits
turn an on-time recommendation into a late one without improving its basis.
Reviewer substitution adds a slot; absent capacity prevents disposition entirely.
Neither a reasoned record nor a larger procedure guarantees timely useful action.

The legitimate and false-evidence fixtures present identical public information.
Both yield restriction advice. The program cannot detect the host's false account
of the world. The later counter-record changes the child recommendation, but
does not erase the parent's wrong recommendation, replay hash or seven slots.
No real restriction occurred, so this is not evidence of undoing a real harm.

Mitigation is explicitly identified and cited, yet a restriction can still follow.
That trace checks disclosure, not the quality of an explanation or completeness
of the host's impact estimates. Origin labels and reviewer controller labels are
declarations; invented independence can still defeat the intended protection.

Tests additionally cover missing authority, wrong-target and excluded evidence,
duplicated origins, suppressed disclosures, notices that cannot fit, response
windows, dissent, reviewer changes, unsupported waiver/execution requests,
observation exhaustion, parent tampering, newly available prior inventory,
future evidence that has not been examined, terminal closure and atomic output.
No claim of real-world prevention, legal compliance or autonomous judgment is made.
