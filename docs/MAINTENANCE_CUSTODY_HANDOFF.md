# Taking custody of the maintenance study

The [study protocol](MAINTENANCE_STUDY_PROTOCOL.md) fixes the question, budgets, assignments and outcomes. This handoff can be rehearsed on an ordinary checkout with Python 3.11 or later. Actual intake starts when an independent custodian and a separate grading lead have agreed to serve, documented their access, and had the pre-intake freeze witnessed. There are 48 sessions across 24 lineages, with up to $96 in model charges and eight reviewer hours across both arms. Intake, grading and administration require additional labor. The budget owner confirms funding and the cost recorder before execution.

A volunteer can identify a role, availability, and relevant conflicts in the [public custody coordination issue](https://github.com/LadyElinor/unfinished-commonwealth/issues/7). Exchange private contact details and cases through a channel controlled by the accepted custodian. Contributors can publicly rehearse the handoff without seeing a proposed case.

## Rehearse before accepting a case

Run from the root of the checkout.

```sh
python -m unittest discover -s tests -p test_maintenance_custody.py -v
python -m scripts.maintenance_custody code-pins
```

The test builds a disposable freeze, roster, blinding map, grade export and observer checkpoint from public examples. It exercises assignment, recount, a changed grade, and a balanced substitution of both arm orders. In the v2 rehearsal, relabeling one incorrect acceptance as a decline and rehashing the final export changed the plain arm's incorrect acceptances from 1 of 2 to 0 of 1. Its primary difference bounds stayed at [0, +25] percentage points. The v3 rehearsal rejects this edit against the observer's locked decision. The historical public rehearsal remains available at its [original checkpoint](../examples/maintenance_pairs/README.md).

At [`c532350`](https://github.com/LadyElinor/unfinished-commonwealth/commit/c532350ef10185e35ca26b838f1b0c0164e34af8), a contributor reported 17 custody tests passing in 5.606 seconds from a detached checkout and 30 passing when the maintenance-pair tests were included. The timed log covers the 17 custody tests.

The current custody suite also runs the same 56 single-field edits against both freeze versions across eight public sessions. Each edit changes one closure reason (33 cases), reviewer decision (15 cases), or deviation list (8 cases), then recomputes only the final export checksum. V2 accepts all 56 and gives the same primary difference bounds each time. Eleven edits change the number of accepted patches. Seven of those also change the false-acceptance bounds, five in the plain arm and two in the governed arm. V3 rejects every edit at the affected session and field while the observer's checkpoint is held fixed.

For each v2 edit, a hand-counted oracle checks both arms' exact accepted counts,
grade counts and false-acceptance bounds, including unchanged results. Its 15
reviewer-decision cases are keyed by task, arm and new decision. Expected bounds
are specified as rational values and converted only for comparison with the
report's JSON numbers. This checks the public rehearsal's arithmetic, not
independent custody or performance on private cases.

## Interpreting 24 assigned pairs

The primary estimate is the difference between governed and plain **on-time correct deliveries** over all 24 assigned defects. With complete outcomes, three net additional correct deliveries give +3/24, or **+12.5 percentage points**. With uncertain delivery or grading, first report the full range of differences compatible with the records.

The frozen conditional 95% interval extends the compatible range by `sqrt(2 * ln(40) / 24)` on either side and clips the endpoints to [−1, 1]. For the hypothetical fully observed +3/24 result, the radius is **55.4 percentage points** and the interval runs from **−42.9 to +67.9 percentage points**. It includes material harm and benefit. If independence of the defect lineages is doubtful, the protocol calls for descriptive bounds alone. See the [frozen analysis and stopping rules](MAINTENANCE_STUDY_PROTOCOL.md).

A pilot of this size can document whether intake, blinding, review and repair are feasible, which failures occurred, what reviewers spent, and which patches arrived on time. The four public rehearsal pairs are constructed arithmetic examples and supply no observations for the prospective estimate.

## Four handoffs

| When | Who holds the evidence | What is retained |
| --- | --- | --- |
| Before intake | Custodian and independent witness | Timestamped freeze bytes and digest, actual model/configuration, tools, environment, acquisition prices, reviewer allocation, grading procedure, budget owner, controller and conflict declarations, access log policy |
| After intake, before any session | Custodian retains the ordered roster. Witness retains its digest before drawing the seed | Consecutive intake and exclusion log, task packets, private rubric/checks, one independently drawn uniform 32-byte seed, resulting manifest digest and time. Draw once. A shortage, collision or exposure is recorded. |
| Before grading and unblinding | Custodian retains the private blinding map and its checkpoint. Grading lead retains the blind grade checkpoint. Observer retains session meters, billing lines, timed submissions, and each session's decision, closure and deviations. | At grading handoff bind each submission to its patch bytes and a fresh random 32-byte blind ID. Give the grader randomized blind items and the applicable rubric. Keep workflow, task order and mapping with the custodian. Give the observer ledger digest to the witness and lock grades before releasing the mapping. Explicitly record an unknown grade. |
| After joining records | Custodian and witness retain the final outcome export checkpoint | Join the locked grades and measured charges, verify correspondence to raw receipts, retain the final export bytes and digest, then run the custody recount. Archive the report, deviations and failures. |

Independent control, witnessing times and freedom from prior exposure require direct confirmation by the people filling those roles. A person who can replace all files and checkpoints can still manufacture a consistent record. A change before lock needs a documented version decision. After execution begins, keep the original records and disclose deviations according to the frozen protocol.

## Private packet formats

All checkpoint digests are lowercase SHA-256 over exact file bytes. Archive the exact checkout and environment. The rehearsal in [the custody tests](../tests/test_maintenance_custody.py) contains complete executable examples. These files stay in the custodian's study directory.

| File | Fields and meaning |
| --- | --- |
| `freeze.json` | For a new handoff use `schema = maintenance-custody-freeze-v3`, `kind = prospective` (or `public-rehearsal`), the three fields from `code-pins`, `custody_plan_sha256`, `grading_procedure_sha256`, and `pins` with `agent`, `environment`, `reviewer_pool`, `plain`, `governed`. These last seven digests identify archived materials. The custody plan includes the agreed roles, prices, funding and metering arrangements. |
| `roster.json` | `schema = maintenance-custody-roster-v1`, `freeze_sha256`, `rubric_sha256` for the locked collection of private case rubrics/checks, and `tasks` in witnessed intake order. Each task has an opaque `id`, `lineage` and `packet_sha256`. |
| `map.json` | `schema = maintenance-blinding-map-v1`, `manifest_sha256`, and `entries`. Each entry has `task`, `arm`, one-based `submission`, `blind_id` and `patch_sha256`. Identical patch bytes in separate sessions have separate blind IDs. |
| `grades.json` | `schema = maintenance-blinded-grades-v1` and `entries`. Each entry has `blind_id`, `patch_sha256` and `grade` (`correct`, `incorrect` or `unknown`). Retain the blinded adjudication record for each entry. |
| `observer.json` | A v3 freeze requires `schema = maintenance-observer-ledger-v2`, `manifest_sha256`, and one entry in `sessions` per assigned task and arm. Each entry adds `disposition`, `closure` and `deviations` to the `task`, `arm`, `meters`, `charges` and ordered `submissions` of the [v1 public observer example](../examples/maintenance_pairs/observer.json). |
| `outcomes.json` | Use the [study outcome format](../examples/maintenance_pairs/outcomes.json). Include every assigned session and every submission, even with missing timestamps, charges or grades. The observer reconciles measured costs, raw ledgers and the source of each grade. |

### Preparing the observer ledger

Construct the observer file from the retained observations before the keeper joins the final export. The six meters are elapsed ms, reviewer ms, public checks, model requests, input tokens and output tokens. Use nonnegative integers or null. Copy each observed submission's patch digest and elapsed ms in submission order, preserving missing timestamps. Include sessions that never started.

At session close, record the reviewer's final disposition (`accept`, `decline` or `unresolved`), the closure reason (`completed`, `declined`, `timeout`, `tool_error`, `unknown` or `not_started`), and the contemporaneous deviation entries in their recorded order. Obtain these from the session and review records before seeing the grades. The disposition refers to the last retained submission, even if it arrived late. For a nonstart record `not_started`, `unresolved`, an empty submission list and any reasons observed. Preserve uncertainty about a decision as `unresolved` and uncertainty about closure as `unknown`. Record missing source material in the deviations.

The `charges` object contains a boolean `complete` flag and a `lines` list. The flag describes coverage of the allocation list. For billing, assign each charge or credit exactly once under the frozen prices and allocation rule. A billing entry has an opaque `id` unique across all sessions and a signed integer `micro_usd` amount or null. Include charges for failed or retried requests when billed. Use a documented allocation ID for each part of a shared invoice line and retain the original invoice and split. An observer who knows only a session total may record one reconciled allocation for that session with the source retained.

| Evidence held by the observer | `charges` value | Session cost in the export |
| --- | --- | --- |
| Confirmed no charges | Complete, empty list | 0 |
| Complete list of allocations with known amounts | Complete, all amounts known | Sum of charges and credits |
| Known allocations with an unpriced item | Complete, at least one null amount | null |
| Partial or unavailable allocation list | Incomplete, include every observed line | null |

The frozen export represents nonnegative session nets. If verified refunds produce a negative session net, retain the receipts and disclose the format mismatch. The recount rejects that value. For each arm, `billing_line_coverage` reports the net of the individually observed amounts, the known and unknown line counts and sessions with incomplete allocation lists. Its observed net is null when no line has a known amount. An unknown credit or charge can move the final bill in either direction.

## Execute the handoffs

The example uses shell variables for checkpoint values supplied by their holders. Use absolute paths for private files when running outside the study directory. Run these commands from the repository checkout or an environment with the checkout on the Python module path.

```sh
python -m scripts.maintenance_custody assign freeze.json roster.json manifest.json \
  --freeze-sha256 "$FREEZE" --roster-sha256 "$ROSTER" --seed "$SEED"
```

The command writes a new complete manifest and prints its SHA-256. An identical rerun succeeds. A conflicting file is preserved and reported. The output directory must support hard links. Give the published digest to the witness before releasing a task.

For assignment version 1, rank each zero-based roster position by SHA-256 over the ASCII bytes of `unfinished-commonwealth/maintenance-assignment/v1`, one zero byte, the 32 seed bytes, the 32 roster digest bytes and the index as four big-endian bytes. The lowest half run plain first. A tie stops assignment. The public test vector uses seed bytes 0 through 31 and a roster digest of 32 bytes of hexadecimal 11. The plain-first positions among four entries are 1 and 3, counted from zero. The witness must generate an unpredictable seed after roster lock. Replay alone cannot detect a custodian shopping for a seed.

```sh
python -m scripts.maintenance_custody recount freeze.json roster.json manifest.json outcomes.json map.json grades.json \
  --freeze-sha256 "$FREEZE" --roster-sha256 "$ROSTER" --seed "$SEED" \
  --manifest-sha256 "$MANIFEST" --map-sha256 "$BLIND_MAP" --grades-sha256 "$BLIND_GRADES" --outcomes-sha256 "$OUTCOMES" \
  --observer-ledger observer.json --observer-sha256 "$OBSERVER"
```

Recount checks the assignment and the one-to-one correspondence among submitted patch digests, blind grades and exported grades, including explicitly unknown grades. Both v2 and v3 freezes match every session's meters, recomputed bill and ordered submissions to the observer's checkpoint. Under v3, `observer_replay.matched_closeouts` counts the sessions whose disposition, closure and full deviation list also matched. A v2 freeze uses the v1 observer ledger and makes no closeout check.

The observer still reconciles native receipts, clocks, allocation completeness and invoices. The custodian verifies each final `receipt_sha256` against the separately retained attempt ledger, which includes grading provenance, and supports the reported lineage assessment. Neither claim is independently checked by the pre-unblinding observer file. Independent custody and completeness of the original records require external review.

A v1 freeze supports its original grade-and-assignment recount and reports `observer_replay.status = not_supplied` when the observer inputs are omitted. Both observer arguments together enable the additional check on a v1 freeze made with the current tools. Replay older freezes from the exact source revision committed in their pins. The freeze version is chosen before intake. The standalone analyzer also accepts `--outcomes-sha256` for checking an existing export. Its `outcome_checkpoint` field distinguishes a supplied matching value from an ordinary local recount.
