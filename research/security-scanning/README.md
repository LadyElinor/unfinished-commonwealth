# GhostShares, aerospace and robotics research register

The 11 November 2026 intake covers documented AI applications, aerospace software, robotics, agent authority, industrial control and clinical evidence provenance. Start with the [citation register](citation-register.json), [software inventory](source-inventory.json), [public app shortlist](public-apps.json) and [four finding records](findings.json). The [interactive priority matrix](priority-matrix.html) works as a single file in a local browser.

## Citation identities

The first published six-skill package already assigned identifiers. Retain them across editions. The conflicting labels below are section-specific aliases from the supplied protocol. A bare ambiguous label from that draft should be resolved using the source title or URL.

| Source | Canonical ID | Conflicting draft reference |
|---|---|---|
| NASA F Prime | AERO-01 | Section 3, AERO-03 |
| NASA cFS | AERO-02 | Section 3, AERO-04 |
| Space ROS project | AERO-03 | Section 3, AERO-01 |
| NASA Space ROS project overview | AERO-04 | Section 3, AERO-02 |
| OPA documentation | GOV-01 | Both sections agree |
| OPA source repository | GOV-02 | Section 3 agrees |
| Microsoft Agent Governance Toolkit | GOV-03 | Section 2, GOV-02 |

GS-01 identifies Claroc's first-hand investigation. GS-02 identifies Unite.AI's account of that investigation. Count those as one observation lineage. Claroc distinguishes reachable apps, publicly readable apps and sensitive examples. Its before-and-after team-authorization experiment used its own app. Preserve that attribution in any downstream report. [Claroc](https://blog.claroc.io/ghostshares-grok-build-apps/) · [Unite.AI](https://www.unite.ai/claroc-research-finds-35-578-grok-apps-accessible-without-sign-in/)

## Run a scan

1. Record the question, date, search query, publisher, candidate URL and project fit. Search published technical material, official repositories and public notices. Example queries for this pass appear in [discovery](discovery.json). Record origin, redirects, scope and evidence gaps.
2. Classify scope before evaluation. Reachability is an observation. Publication intent needs an owner announcement, public showcase or equivalent source. Misconfiguration needs evidence of intended policy and a discrepancy. Confirmed unauthorized disclosure needs case-specific evidence of actual disclosure outside authority. These are separate properties that can coexist. For an unknown property use JSON null.
3. Inspect a candidate's repository and documentation at a known revision. Capture language, release, archived flag, commit date, license text, dependency manifests, security policy and test evidence. A missing path in this inventory means that this pass did not identify it. A manifest is a pointer for dependency review. An archived flag, recent commit or passing upstream test cannot certify readiness. Review individual components and licenses before reuse.
4. For an authorized static review, record who owns the software, what was permitted and where the evidence came from. Read public documents within their published scope. Keep any interactive security work on an owned, isolated synthetic fixture. If a source describes an accidental disclosure, record the public report and use the owner's published contact process for any necessary disclosure. Keep identifying details and private source material out of the register.
5. Make a falsifiable prediction for a synthetic case, including both an allowed action and a denied action. Bind the fixture, implementation revision, expected effects and journal evidence. Record the status of halt, correction, appeal and audit custody separately. The local gate records decisions only. CORTAC adds a disposable transaction and a scoped revocation. External actuation, emergency-stop timing, affected-party remedy delivery and immutable custody remain unverified here.
6. Preserve separate source claims, local observations, hypotheses and unresolved questions. File a record against the [finding schema](finding.schema.json). Hash the exact named artifact bytes where available. Preserve null when the underlying evidence is missing. A separately controlled reviewer supplies their own identity, inputs and discrepancies before a finding is marked independently reproduced.
7. Report limits, mitigations and verification evidence. Use the [reproduction instructions](verification/README.md) to repeat the defensive benchmark. A local replay supports a claim about these fixtures only.

The imported procedures cover [source discovery](public-source-discovery/SKILL.md), [prioritization](research-prioritization/SKILL.md), [static review](authorized-security-review/SKILL.md), [robotics](aerospace-robotics-assessment/SKILL.md), [governance](agent-governance-audit/SKILL.md) and [verification](research-evidence-verification/SKILL.md).

## Refresh repository metadata

Run `python research/security-scanning/refresh_inventory.py SAFE-01 GOV-02` to compare the public Ogma and OPA repository metadata against this inventory. Omit the IDs to check all inventoried repositories. The command reads public GitHub project metadata, latest release and default-branch revision, prints dated JSON, preserves per-source errors and returns a nonzero status on partial failure. Review changed source trees and licenses at their new revision before adopting the new observations. A refresh leaves the checked-in baseline intact.

## Priorities and cadence

The supplied illustrative totals are OPA 100, Ogma 96, F Prime 94, Space ROS 90, Nav2 87 and MoveIt 2 84. The original per-dimension ratings are unknown. The [matrix](priority-matrix.html) preserves the reference column and calculates a separate ranking once ratings are entered for every positively weighted dimension. Relevance, governance, evidence and implementation start at 35, 30, 20 and 15. Zero total weight produces no score. Ties share rank. The score prioritizes research effort.

| Proposed interval | Review | Deliverable |
|---|---|---|
| Weekly | Published projects, official advisories and new releases | Dated sources, search log, deduplicated backlog |
| Monthly | Revisions, dependencies, licenses, disclosed flaws and authority boundaries | Versioned deltas, changed claims and unresolved questions |
| Quarterly | Owned synthetic access, revocation, rollback and command scenarios | Replay, independent reviewer record when available and comparison with the previous baseline |

The cadence is guidance for contributors. The current snapshot records ordinary source inspection and the local benchmark. No background collection is configured.

The [mathematics, engineering and programming inspection](project-checks/README.md) checks two published numerical readouts, compares an authored orbital simulation with a separate integrator, and traces an argument-rewrite lesson into the local authority gate.

The [Grok runtime comparison](grok-runtime-comparison.md) traces an argument rewrite through three authority models and identifies where an external effect gateway would have to enforce approval.
