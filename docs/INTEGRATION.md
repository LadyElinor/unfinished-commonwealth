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
