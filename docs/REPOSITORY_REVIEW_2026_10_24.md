# Repository review, 2026-10-24

Scope: the research contracts, their trust boundaries, replay routes, packaging,
CI coverage and documentation at base commit
`7b47c84d1d6e9ead632ed0a1547925821883dfc3`, plus the R1 extension in this change.
This is a bounded engineering review, not a security certification or an assertion
that every future use is safe. No production adapters or provider calls were added.

| Area inspected | Finding and disposition |
| --- | --- |
| Original workshop and D1 | Existing invariant, reference, budget and replay tests retained. Original 15 comparisons and 432 D1 runs are unchanged. No adaptive advantage has been demonstrated. |
| P1/P1.1 procedure | Current notice/reply/appeal paths and legacy P1 reducer retained. Gaps around contrary-evidence collection, conflicts, declining action and post-terminal review are explored in separate R1 records; P1 histories are not reinterpreted. |
| F1/I1 integrity | Their source files, 150/112-run matrices and negative regressions remain frozen. R1 adds no bypass or automatic write to either policy. Authentic origin discovery, undetected compromise and recovery remain limitations. |
| R1 decision boundaries | Typed inventory, disclosure, scoped advice, reviewer eligibility, alternatives, budget exhaustion and a separately linked reconsideration process added with adversarial tests. Wrong substantive decisions remain possible. |
| Alternative proportionality | Final rule review found that a cheaper option could still cost more than it prevents. A regression reproduced acceptance at costs 10 and 5 for a benefit of 5. Alternatives now require their own strictly positive net benefit; the cost-4 control remains eligible. Existing fourteen journal outcomes and hashes are unchanged. |
| Build documentation | I1 commands and installed checks were absent from BUILD.md. Added I1/R1 reproduction and parent-linked replay instructions; distinguished runs from scenarios. |
| Hosted CI | I1 was tested through unit/package checks but lacked its own reproduction step. Added explicit I1 and R1 reproduction stages alongside the existing stages. Workflow pins and platform matrix remain unchanged. |
| Offline packaging | Added required R1 source/docs/test entries, installed 14-trace execution, and exact-parent reconsideration replay. Existing installed checks remain mandatory. |
| Evidence and claims | Source-status distinctions and all existing negative results retained. Source manifests, report equality and replay test internal consistency, not truth, identity, independence or real-world efficacy. |

Validation commands are `python scripts/verify.py` and
`python scripts/package.py .local/review-package`. The full suite includes 268
earlier tests plus R1 boundary and artifact tests. The package check verifies the
extracted source, builds from that source, installs offline outside the checkout,
and exercises every research extension. Hosted validation covers Linux Python
3.11, 3.12 and 3.13, plus Windows Python 3.12. See the associated pull request for
the exact commit and workflow outcome; green CI alone does not establish branch
protection, independent review or effective enforcement.

Remaining work is explicit: authenticated principals and evidence provenance;
independent discovery of compromised sources; independently operated reviewers;
recovery from quarantine; real-effect cancellation/compensation; privacy and
retention policies; resource calibration against actual workloads; and separately
controlled evaluation data after freezing rules. These are reasons to retain the
research-only readiness boundary, not to manufacture more passing toy cases.

No release, merge, deployment or extension of external authority is implied by
this review. The original protocol and package baseline remain at 0.1.3.
