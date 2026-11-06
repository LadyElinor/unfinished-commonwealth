# M1: CORTAC applied to repository maintenance

This exposed pilot uses Commonwealth baseline `3688dcdfa70b27531c8f0d3bd315a88736c87655`
and CORTAC `ea7a72456e00bd2b80aa4ccd9ae97262aedc3562`. The [plan](MAINTENANCE_PILOT_PLAN.md)
was committed locally before implementation. The same operator selected the task,
implemented the change and supplied the review. This is not a scored agent trial.

## Applicability result

S1's AP1.1 contract cannot admit a repository task or patch action. S2 cannot
schedule it without an admitted S1 journal. The pilot tests these refusals and
stops that route. No fake arithmetic task, controller independence, workshop
acceptance or authority is supplied to make a repository patch look supported.
The general CORTAC decision-record validator can check an advisory review of
this patch. Its result establishes structural completeness only.

## Concrete improvement

The old verifier returns success and prints that behavioral tests passed when
all discovered tests are skipped. The retained [baseline observations](../examples/maintenance_v1/baseline.json)
also correct an initial source-based prediction: **empty discovery already exited
5 in the observed Python 3.12.14 environment**. No zero-test defect was demonstrated
there. The new verifier makes both coverage boundaries explicit across supported
runtimes and preserves mixed skips instead of claiming full coverage.

The patch adds optional new-file JSON receipts with actual unittest result counts,
failures/errors, skipped IDs and reasons, expected failures and unexpected successes,
JSON/link-check status, elapsed verification time, and unauthenticated source
observations. The no-skips flag is required only by the already dependency-enabled
Ubuntu/Python 3.12 job. Runtime, client, studies, policies and published results
remain unchanged. No change to protected evidence can hide behind a higher test
count. See [verification details](VALIDATION.md).

## Reproduce the pilot

The pilot is frozen at `7d06de1ceb314879e5db5529db632a267581982d`.
Its binding describes that maintenance candidate, not a permanent prohibition on
future repository changes. The dedicated CI job checks out this exact snapshot;
ordinary verification checks current code. From a Git checkout containing that
commit and an unmodified checkout of the pinned CORTAC commit:

```sh
git worktree add --detach .local/m1-source 7d06de1ceb314879e5db5529db632a267581982d
python .local/m1-source/scripts/maintenance_pilot.py /path/to/CORTAC .local/maintenance-pilot
python scripts/verify.py --report .local/maintenance-verification.json
```

The pilot writes to a new directory, checks the candidate file digests and retained
baseline bytes, invokes the pinned CORTAC validator, exercises scope/record negative
controls, and runs old/new verifier fixtures. Every subprocess exit and measured
duration is retained. Original baseline observations remain historical; reruns can
differ across Python versions. No fixture is a sealed holdout.

The supplied review preserves an objection about same-operator control. Its
independent-review assessment is `UNKNOWN`, so CORTAC's all-assessments-pass result
must remain **false**. Record completeness does not resolve the objection or
prevent the ordinary user-authorized maintainer from proposing a PR. Only repository
maintainers decide whether to merge; neither the review nor the pilot does so.

The negative epistemic control is deliberately accepted: replacing all supplied
assessments with PASS produces a structurally passing record. The validator cannot
tell whether independent review occurred. The published actual review retains
UNKNOWN; the fabricated control never becomes its substitute.

The [retained pilot result](../examples/maintenance_v1/results.json) records eight
boundary checks and eleven verifier subprocess probes. The [local verification
receipt](../examples/maintenance_v1/verification.json) records 635 tests with zero
skips. Its source was a working tree, not a sealed or independently held snapshot.
Both files are outputs, deliberately excluded from the candidate input binding
to avoid circular hashes. The dedicated hosted job produces fresh observations
of the pinned pilot; the ordinary CI jobs verify the current checkout separately.

## What this tests and what it does not

| Question | Evidence and limit |
| --- | --- |
| Does the maintenance patch improve a demonstrated failure? | Old all-skipped success versus new refusal; positive/mixed/failure controls and ordinary regression suite |
| Can S1/S2 run repository-maintenance assignments? | Unsupported task/action refusals; S2 route is not attempted, because its admission prerequisite fails |
| Does CORTAC retain limitations in a real patch review? | Exact limit inventory, dissent consistency, missing-field/FAIL/UNKNOWN controls; all-pass remains false |
| Is this independent agent review or proof of better governance? | No. One assistant/operator, no matched workflow comparison, no independent evidence custody |
| Does it measure autonomous agent costs or peer harm? | No. Subprocess duration is measured; agent latency/tokens/money, peer harm and causal benefit remain unmeasured |

The practical next gap is an explicitly designed repository-task profile with
artifact bindings and a separately controlled reviewer. This pilot does not add
that profile or promote workshop permissions into repository permissions.
