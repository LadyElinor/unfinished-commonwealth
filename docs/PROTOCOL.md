# Local protocol v2

Every event is a JSON object with exactly `action`, `actor`, and the fields below. Unknown fields are rejected. Text fields are nonempty and at most 4,000 characters. `commonwealth propose` accepts only proposals; `commonwealth submit` is an unrestricted **operator interface**, not an authenticated model endpoint.

JSON input rejects duplicate object keys, nonfinite numbers, and more than 64
nested containers. Command files are limited to 65,536 bytes actually read.
Journal replay also checks JSON types: `false`, `0`, and `0.0` are not
interchangeable historical values. Sequence numbers must be integers.

| Action | Additional required fields | Fixture role |
| --- | --- | --- |
| `observe` | none | Any active fixture participant |
| `propose` | `method`, `prediction`, `purpose` | Current worker |
| `approve` | `proposal` | Keeper |
| `execute` | `proposal` | Current worker |
| `testify` | `observation`, `account` | Neighbor |
| `listen` | `testimony`, `acknowledgment` | Current worker |
| `reflect` | `evidence`, `before`, `after`, `next_check` | Current worker |
| `lesson` | `method`, `evidence`, `scope`, `guidance` | Current worker |
| `accept-lesson` | `lesson` | Keeper |
| `review-lesson` | `lesson`, `decision`, `reason` | Keeper |
| `counterstory` | `reference`, `account` | Any active fixture participant |
| `consult` | `case`, `interpretation` | Current worker |
| `handoff` | `scenario`, `fixture`, `note` | Keeper |
| `halt`, `resume`, `revoke` | `reason` | Keeper |
| `closeout` | `reason`, `follow_up` | Keeper, after operational exhaustion only |

Supported methods are `zero-fill`, `positive-only`, and `quality-stream`. Prediction keys are exactly `primary_correct` and `peer_on_time`, each a finite probability in [0, 1]. A forecast applies to the next observed tick following that proposal's execution. A later execution before any observation supersedes the prior unscored forecast; the original proposal remains in the journal.

Evidence is a nonempty array of unique observation/testimony IDs. Lessons currently support only `quality-flags-v1`. Acceptance certifies a local practice designation and a narrow supporting outcome, not a universal recommendation. Counterstories reference a lesson, observation, or testimony.

Inherited advice and the participant/report views include a derived `review_status`, all linked counterstories, unaddressed counterstory IDs, and prior reviews. A counterstory against a lesson or any of its cited evidence makes it `DISPUTED` until reviewed. It is still `ADVICE_ONLY`; a recorded account is not automatically a veto or a finding of truth. `review-lesson` accepts exactly `retain`, `suspend`, or `retire`, with a recorded reason. A review addresses all linked counterstories then present. Later challenges reopen review. Suspended and retired lessons are omitted from inherited recommendations; their evidence and accounts remain visible. Suspension can be reversed by another keeper review. Retirement is final for that record; a replacement requires a new lesson.

Accounts added after retirement remain in `unaddressed_counterstories`, but do
not imply the retired lesson can be reopened: `requires_review` and
`review_action_available` are false. The same availability field is false for a
lesson not yet accepted. It describes lifecycle eligibility for keeper review,
not whether someone may read or preserve an objection. Actor and remaining
command/review budget checks still apply when submitting an actual review.

Proposal IDs are `propose-N`, where N is the accepted command number. An approval expires when `tick >= expires_before_tick`, with expiry set to the proposal tick plus three. Ticks advance only on observation. Revocation, halt/resume, execution, and handoff invalidate prior operational bindings. No real-time expiry or cryptographic signature is implied.

The initial worker is `worker-1`; the keeper, affected neighbor, and coach are `keeper`, `neighbor`, and `coach`. Handoff increments the worker generation and retires the old worker. The keeper cannot silently discard unfinished peer work during handoff. Counterstories and accounts persist.

For every generation after the first, `propose`, `approve`, and `execute` require at least one observation in the current generation. This applies even if the worker omits any mention of inherited advice. New successor proposals record the latest such observation ID. Freshness here means **since the latest handoff**, not a guarantee of recent wall time, successful results, or understanding. Separate approval, epoch/revision binding, and expiry still apply. `observe` executes a bounded pipeline tick; it is not a passive read. Reflection consumes one command and advances no simulated time.

## Exhaustion and unresolved obligations

The first 256 accepted commands use the operational budget. After that, proposals, approvals, execution, observation, handoff, resume, consultation, lesson creation, and lesson acceptance remain blocked. Exhaustion grants no further execution authority.

There are then **32 additional review commands**, restricted to `testify`, `listen`, `reflect`, `counterstory`, and `review-lesson`, with their normal role and evidence checks. Independently, the keeper can record each of `halt`, `revoke`, and `closeout` **once after exhaustion**, even if the review allowance is already spent. Repeating a recorded terminal control is refused. Failed requests consume no allowance. The maximum journal size is 292 events: genesis, 256 operational commands, 32 review commands, and three terminal controls. `command_count` counts all accepted commands; `review_count` and `final_actions` explain the excess over `command_limit`.

`closeout` halts the workshop, invalidates pending bindings, and records the pending peer-job data, a reason, and an operator follow-up note. It neither completes nor discards that work, sends a message, transfers authority, nor starts another workshop. Pending jobs are explicitly `UNRESOLVED`. A note with no pending jobs reports only `NO_PENDING_PEER_JOBS`, not that every possible social obligation is settled. The remaining review allowance stays available; the operational budget never reopens. An operator must handle any subsequent work outside this exhausted run under separately established authority.

## Historical replay

Each accepted command atomically commits the snapshot and a journal envelope containing sequence, predecessor hash, command, result, and resulting state hash. Rejected transitions roll back and do not appear as accepted events. The seed does not retain a separate failed-attempt audit log; a future scored runner must record all submitted attempts externally.

New envelopes also contain integer `protocol: 2`. Unversioned historical envelopes replay with the frozen v1 reducer and retain their original hashes and schema-1 snapshots. The first successfully appended v2 event upgrades the working state to schema 2 atomically; historical rows are untouched. All new dispatches use v2, including those on old databases. Unknown protocol tags and a return to unversioned events after v2 are refused. Reading or refusing a command does not migrate a journal. Historical behavior may replay even where the same new command would now be refused. Older package versions cannot read newly appended v2 events; keep backups before opening an old journal for continued work.

Exit 0 means a local command completed. Exit 2 means invalid input, missing data, replay failure, or a deliberate `readiness` refusal. Read the accompanying structured status rather than treating an exit code as a governance verdict.
