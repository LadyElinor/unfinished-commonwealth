# A1: diagnosis, mandate, language and correction

`authority-1.0.0` is a separate offline research extension based on
`7a11f2ba587cc14b595e995e14d7b47a1e54a94d`. It changes only a fictional in-memory
maintenance flag. It cannot govern people, change a repository, issue a legal
finding or invoke another project's authority. The workshop and D1/P1/F1/I1/R1
implementations and their recorded examples remain frozen; 59 file hashes bind
that baseline.

## The distinctions being implemented

| Insight | A1 behavior | Remaining limit |
| --- | --- | --- |
| Diagnosing failure does not confer a mandate | Review, host delegation, steward authorization and execution are separate transitions | Host authority is declared, not authenticated or democratically ratified |
| Legitimacy has different meanings | Public acceptance, moral justification, electoral validity and legal authority remain separate labels | The software does not decide which institution is legitimate |
| Aspirational wording can obscure unanswered questions | Record the decision-maker, action, trigger, limits, expiry and remedy explicitly | Grammar, historical analogy and opportunity language do not establish intent |
| Public and private language need contextual comparison | Preserve public, working and analyst records; compare exact actor, decision, condition, period, stage and meaning | Curators supply the propositions; there is no semantic extraction or contradiction classifier |
| Proposals are not commitments or conduct | Review accepts a proposal while preserving its stage; execution needs separate authorization | An imported stage label proves no event happened |
| Coalition agreement is not universal representation | Require an explicit affected constituency and declared representation; retain each objection verbatim | These identities and selection claims are not verified; recorded dissent is not assent |
| Institutional self-protection can obstruct correction | Challenges invalidate outstanding review/grants; independent-controller review must address them | Referencing an objection does not prove a substantive answer |
| Emergency rhetoric cannot expand delegation | Exact request binding, expiry and revocation checks at authorization and execution | The fixed simulation host could supply a dishonest delegation |
| Stopping an action does not undo its consequences | Separate halt, revocation and observed simulated reversal; retain original effects and costs | Restoring a flag does not remedy real injury or irreversible harm |
| Our own systems must face the same tests | Operators and synthetic roles receive no exemption from scope, conflict and correction checks | Real maintainers still govern this repository through GitHub |

Earlier insights remain in their appropriate studies: F1 preserves legal source
statuses and refuses overlapping financial totals; I1 handles declared shared
control and issuer quarantine; R1 handles contrary material, alternatives,
proportionality and reconsideration. A1 does not replace those policies or pool
its cases with their efficacy measures. An association path, centrality score,
source count or rhetorical resemblance cannot issue a warrant here.

## Review packets and language records

```bash
python -m commonwealth.authority_v1 review examples/authority-review-packet.json
python -m commonwealth.authority_v1 compare examples/authority-language-records.json
```

The read-only `review` command accepts the `warranted-authority-review-1`
**input packet** used by Relay Atlas Edition 17 and Terra coordinator 0.2.1.
It accepts only `schema` and `answers`, the 23 known string fields and their
defined enum values. Missing values remain gaps. The input is limited to
120,000 UTF-8 bytes and each answer to 4,000 characters. This byte limit can be
stricter than the browser's character limit. Duplicate JSON keys, result flags
and reviewed-record envelopes are rejected. The returned Commonwealth result
schema is distinct and cannot be imported as an execution token. No ledger is
opened or modified. Full answers can be false even when every field is complete.

The synthetic interoperability sample is copied from Terra's input export at
source commit `754028746ba877e8bb7641183a6577b6dc5559df`. Tests cover this packet
contract only; no remote API integration, CORTAC adapter or constitutional
ratification is claimed. The implementation is new code in this repository.

`compare` consumes three curated records, each preserving a locator, version,
event/publication time, source group, source-review status and account text.
An analyst's stronger characterization never replaces the speaker's record.
Different actors, conditions, periods, stages or meanings create comparison gaps.
An excerpt is not silently promoted to a reviewed original. Repeated origin
groups do not become independent corroboration. Even a comparable difference
returns no conclusion about deception or intent. Source labels and exact
propositions are supplied by the caller and are not authenticated.

## Synthetic delegation protocol

The trusted fixture host declares a roster, controller labels, affected people,
representation, trigger, mandate, and a separate reversal delegation. The
request is narrowly typed: set a single fictional service's maintenance flag
from false to true. The `warranted` outcome label is hidden from the policy view
and used only to expose authored failures in the final report.

1. A worker supplies a review packet and exact request. A changed packet or
   request increments the revision and invalidates review and warrant.
2. An available reviewer with a distinct declared controller records a review
   against the current material digest and every recorded challenge. Source and
   mandate declarations must be supplied; they are not verified by the program.
3. A steward can issue a synthetic single-use warrant only within an existing,
   active, exactly scoped host mandate, for an established host trigger. Expiry
   cannot extend that mandate. No prose request changes the host configuration.
4. The worker's execution rechecks the mandate, scope, revision, halt state,
   expiry and single-use flag. Success changes only in-memory state.
5. A challenge from any declared role preserves its text and stays future
   execution by invalidating the review and warrant. Fresh review must address
   every challenge before reauthorization. This does not require unanimity,
   erase the objection or establish that the reasons answer it adequately.
6. Any role may use its previously delegated safety halt. Only the steward
   revokes the mandate. Neither transition reverses an already applied effect.
7. The reviewer may restore the initial simulated state only under the separate
   host remedy delegation and a correction trigger. Expiry or revocation of the
   original mandate does not erase this separately delegated correction power.
   Missing remedy authority leaves the effect visibly unresolved.

No resume, emergency escalation, automatic renewal or host-roster modification
command exists. A new scope needs a separately configured episode/mandate; a
caller cannot amend a grant into another target. A safety halt does not require
waiting for the full review form. These are simulation design choices, not
claims about legal powers in any jurisdiction.

## Resource and record boundaries

The default ceiling is 12 primary attempts and six correction attempts; maxima
are 32 and 16. Challenges and remedies use the correction allocation. There are
also two dedicated one-shot safety slots: one halt and one revocation. Primary
work and challenge traffic cannot consume these slots. Accepted or refused
admitted commands consume a slot and advance the shared clock. Scope expiry is
inclusive; host revocation is effective at its stated slot.

Oversized inputs, invalid safety actors, duplicate one-shot safety actions,
commands outside their allocation and commands after explicit closure are
ingress rejections: they are not admitted journal events and do not advance time.
This bounded local ingress is not a network denial-of-service defense. Finite
correction capacity can still be exhausted, leaving challenges or remedy work
unresolved. `finish` explicitly closes the episode; it does not pretend a review
completed or erase outstanding effects. There is no real-time expiry service
after a process exits. Replay input is bounded at 16 MiB, accommodating the
maximum admitted command history plus genesis and terminal records. Review and
language input limits remain 120,000 bytes; repeated amendments do not make a
valid history unreadable by the replay command.

Replay recomputes transitions, costs and terminal results. Digests detect a
mismatch against the supplied journal, not a forged source. A host that rebuilds
a consistent history with invented identities can pass replay; a regression
test preserves this limitation. Reversal preserves the original effect event,
dissent, costs and an observed synthetic-state restoration. It is not evidence
of compensation, restored trust or real-world recovery.

## Research basis and exclusions

This extension adapts the design questions developed in Relay Atlas and Terra
on October 30, 2026. It imports no Democracy Files recordings or political
allegations as facts or test labels. The full archive and private recordings
were not authenticated in this work. The governance principles are proposals
for our software's review process, applied symmetrically to our own operators.
Public advocacy, contingency planning and unlawful interference remain distinct
questions requiring their own records.

```bash
python -m commonwealth.authority_v1 run .local/authority-v1
python -m commonwealth.authority_v1 replay .local/authority-v1/journals/false-but-complete-host.json
```

See [executed results](AUTHORITY_V1_RESULTS.md) and
[integration boundaries](INTEGRATION.md). All 14 traces and ten language cases
are authored, exposed development material. There are no model calls, live
actions, held-out observations or demonstrated institutional advantages.
