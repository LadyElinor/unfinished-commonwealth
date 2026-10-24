# Local protocol v1

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
| `counterstory` | `reference`, `account` | Any active fixture participant |
| `consult` | `case`, `interpretation` | Current worker |
| `handoff` | `scenario`, `fixture`, `note` | Keeper |
| `halt`, `resume`, `revoke` | `reason` | Keeper |

Supported methods are `zero-fill`, `positive-only`, and `quality-stream`. Prediction keys are exactly `primary_correct` and `peer_on_time`, each a finite probability in [0, 1]. A forecast applies to the next observed tick following that proposal's execution. A later execution before any observation supersedes the prior unscored forecast; the original proposal remains in the journal.

Evidence is a nonempty array of unique observation/testimony IDs. Lessons currently support only `quality-flags-v1`. Acceptance certifies a local practice designation and a narrow supporting outcome, not a universal recommendation. Counterstories reference a lesson, observation, or testimony.

Proposal IDs are `propose-N`, where N is the accepted command number. An approval expires when `tick >= expires_before_tick`, with expiry set to the proposal tick plus three. Ticks advance only on observation. Revocation, halt/resume, execution, and handoff invalidate prior operational bindings. No real-time expiry or cryptographic signature is implied.

The initial worker is `worker-1`; the keeper, affected neighbor, and coach are `keeper`, `neighbor`, and `coach`. Handoff increments the worker generation and retires the old worker. The keeper cannot silently discard unfinished peer work during handoff. Counterstories and accounts persist.

Each accepted command atomically commits the snapshot and a journal envelope containing sequence, predecessor hash, command, result, and resulting state hash. Rejected transitions roll back and do not appear as accepted events. The seed does not retain a separate failed-attempt audit log; a future scored runner must record all submitted attempts externally.

Exit 0 means a local command completed. Exit 2 means invalid input, missing data, replay failure, or a deliberate `readiness` refusal. Read the accompanying structured status rather than treating an exit code as a governance verdict.
