# M1: use CORTAC on one repository maintenance change

Baseline: Unfinished Commonwealth `3688dcdfa70b27531c8f0d3bd315a88736c87655`.
CORTAC: `ea7a72456e00bd2b80aa4ccd9ae97262aedc3562` (S1/S2).

This is one exposed engineering pilot, selected after inspecting both sources.
It is not a preregistered efficacy study, independent review, or a comparison
between autonomous agents. The assistant and all local tools share one operator.

## Applicability gate

S1 admits AP1.1 workshop method proposals. A repository patch is outside that
contract, and S2 requires admitted S1 journals. Test refusal of a repository task
and of patch actions in a valid workshop brief. Do not fabricate a workshop,
independent controllers, acceptance receipt or mandate to route this patch.
Use CORTAC's existing general `cortac.decision.record.v1` only as an advisory
completeness check. Keep source evidence, supplied judgments and authority apart.

## Selected maintenance task

The current `scripts/verify.py` trusts unittest's exit status. Unittest exits
successfully with zero tests or with every test skipped. The script consequently
prints that behavioral tests passed in both situations. It exposes no structured
test counts or skipped-test inventory. These are source-based predictions to be
checked before implementation, not already observed outcomes.

Bound the patch to verification tooling, its regression tests, documentation and
CI invocation. Preserve runtime/client code, all studies, evaluators, budgets,
published results, and existing tests. No change to AP1/C2 or the CORTAC pin.

## Fixed checks and stopping rule

Run the old verifier in isolated minimal repository fixtures: empty discovery,
all skipped, a pass, a pass plus a skip, and a failing test. Retain every exit code.
The proposed verifier must reject empty/all-skipped discovery and failures;
accept a pass; disclose mixed skips by default; and offer an explicit no-skips
mode that refuses mixed skips. It must count actual unittest result objects,
not infer execution from console text. Broken JSON and documentation links must
still fail. A requested receipt must preserve failures and must not overwrite an
existing file. Failure to produce a requested receipt cannot report success.

Run the unchanged full suite plus focused regression tests. Require no skips in
the already dependency-enabled Ubuntu/Python 3.12 CI job; disclose optional skips
on other platforms. Record commands, source binding, outcome counts and elapsed
verification time separately. A verification duration is not an agent token,
monetary or decision-slot cost. No sealed holdout or new scored study is created.

## Protected limits and review

Bind the exact candidate files to the base commit and their byte digests. The
supplied review must address historical preservation, honest coverage, no new
authority, and independent review. The last assessment remains UNKNOWN in this
single-operator pilot. Check missing fields, a removed limit, erased recorded
dissent, FAIL and UNKNOWN controls. CORTAC may validate the record's shape while
its supplied-assessment pass result remains false. Neither result merges code.

The existing user-authorized maintainer workflow may produce an ordinary PR;
CORTAC does not authorize publication or ratify the patch. Stop after the bounded
fix, the applicability/advisory checks, and repository/CI validation. Report what
the code enforces and what remains unmeasured. Do not claim that CORTAC generated
the patch or improved its quality relative to an untested baseline workflow.
