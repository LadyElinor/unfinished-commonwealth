# Integration boundaries

The Unfinished Commonwealth is a new implementation. It imports no code from the following repositories and calls none of their APIs. A similar field name or authority concept is not a compatibility claim.

| Project | Relevant concept | Required work before integration |
| --- | --- | --- |
| [Metanoia](https://github.com/LadyElinor/Metanoia) | Distinguish claims, evidence, grants, and execution; disclose correlated control | A versioned adapter, externally configured principals, protected enforcement, and explicit evidence classification |
| [Adiona](https://github.com/LadyElinor/Adiona) | Bounded transitions, revocation, exact capability use, and governed recovery | Map action/state digests and policies without promoting a workshop observation to an Adiona warrant |
| [CORTAC](https://github.com/LadyElinor/CORTAC) | Institutional constraints, review, amendment, and supplied controller domains | A separately validated bridge preserving synthetic scope and distinguishing role assignments from actual appointment |

The present workshop uses fixture maintainer approval. It does not issue Metanoia attestations, Adiona capabilities, or CORTAC appointments. Its records always retain `external_authority: NONE`.

An integration should first run as a read-only exporter with a closed, versioned schema. Tests must reject missing provenance, mismatched state or policy, expired/revoked grants, source scope promotion, and incompatible versions. Only after the receiving project's actual requirements are satisfied should a bridge be allowed to propose effects. No receiving project should trust a source record merely because both projects use the word "warrant".

For substantive work, the human operator must configure legitimate principals and scoped permissions. The repository's ordinary contributors and fictional workshop participants are different populations.

## A1 review-packet input compatibility

`commonwealth.authority_v1 review` accepts the bounded `warranted-authority-review-1`
input packet from Relay Atlas Edition 17 and Terra coordinator 0.2.1. This is a
tested read-only input contract, not an execution bridge or compatibility claim
for result envelopes, Terra warrants or CORTAC schemas. The output is a separate
Commonwealth review result and always denies execution authority. See
[A1](AUTHORITY_V1.md) for byte limits and the exact frozen sample provenance.

The Warranted Constitution mapping remains conceptual: diagnosis to Epistemic,
mandate/representation to Normative and Decision, scoped action to Execution,
and challenge/remedy to Audit. No constitutional amendment is ratified by code
passing tests, an operator possessing credentials or this repository accepting
a pull request.

## B1 local participant transport

The [B1 endpoint](PARTICIPANT_V1.md) accepts only its own versioned proposal
envelope for the existing bounded data workshop. Bearers authorize task retrieval,
proposal submission and receipt lookup; they do not establish an A1 mandate or
issue Metanoia attestations, Adiona capabilities or CORTAC appointments. A local
receipt records a disposition, not an external effect or independent fact.

Relay research packets and their allegations are not accepted as direct commands.
Evidence interpretation remains separate from host review and execution. No
network centrality, shared affiliation, emergency label or persuasive language
changes B1's action set or supplies authority to act on people or institutions.
