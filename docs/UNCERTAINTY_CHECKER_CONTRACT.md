# E1 accounting checker: guarantees, counterexamples and trust assumptions

Checker version: **e1-accounting-1.1.0**. Input experiment version remains
`uncertainty-1.0.1`; no experiment policy, fixture, design or published result
changed. The new preservation manifest binds 56 historical files, including E1.
This is an audit of an existing verification contract, not a new efficacy study.

The checker independently implements arithmetic and accounting in JavaScript.
It was developed by the same project/operator: another language and distinct
code paths do not constitute independent institutional review or evidence custody.
It uses Node standard libraries and imports no candidate/Python implementation.
Its field vocabulary comes from the frozen E1 contract. Shared specifications can
still contain common mistakes; the checker and simulator may both implement them.

## What was found

At [0a31b64](https://github.com/LadyElinor/unfinished-commonwealth/tree/0a31b64cbf43c37f76feb2d51a6b68ca358dd6ba), seven constructed invalid records exited 0:
unknown policy names, string-valued counters, contradictory peer genesis,
contradictory terminal correctness, altered event hashes, duplicate JSON names,
and a later output relabeled as an initial output after abstention. The last
case changed the outer label and several counters together; changing only a
counter would not expose that dependency. These accepted inputs demonstrate
limits of the earlier checker, not an error in the committed E1 dataset.

The [observation ledger](../tests/data/uncertainty-audit-findings.json) retains
old/new outcomes. [Contract tests](../tests/test_uncertainty_audit.py) include
repaired-hash corruptions so a stale checksum cannot substitute for detecting
the substantive contradiction. A separate [hand trace builder](../tests/uncertainty_audit_support.py)
uses no Commonwealth imports or fixture calls: it constructs 24 histories
covering initial emission/abstention, correct/wrong final emission, repair,
regression, delayed recovery and unresolved outcomes. It is a local independently
implemented check, not an independent research team. The ordinary reproduction
test also passes the complete frozen matrix through the checker.

## Guarantee map

| Claimed guarantee | Independent check | Counterexample / positive test | Remaining trust assumption |
| --- | --- | --- | --- |
| Unambiguous bounded input | Strict JSON parser rejects duplicate decoded names, non-integer/unsafe numbers, excessive nesting and invalid UTF-8; bounded streaming framing | Escaped duplicate keys; nested duplicates in summary; unsafe integer; oversized/no-newline record | Parser and Node runtime are trusted; this is a local research reader, not a production sandbox |
| Original stream byte digest | SHA-256 consumes original bytes, including CRLF; no newline normalization | LF and CRLF records both parse but have different correct byte hashes; missing final LF is refused | Hash input/summary can both be rewritten by their controller; digest is not external authenticity |
| Full authored matrix coverage | Closed policy/facet/cell domains, unique cell identities, exactly 3,840 rows | Unknown labels, booleans in numeric cell fields, duplicate cells, self-consistent one-row summary refused in full mode | Allowed domain is the frozen authored matrix, not a representative sample; partial mode makes no coverage claim |
| Frozen environment accounting | Genesis clock, exact budget, task values and peer schedule must match the admitted E1 environment | Changed peer work or budget with repaired hash chain is rejected | The schedule and synthetic prices are assumed, not measurements of real work |
| Initial choice is not a later correction | Initial output is derived from recomputed outputs at/before the scheduled first opportunity; outer phases must match underlying commands | Relabeling abstention as execution, or hiding execution with abstention, fails even after changing matching counters | Only E1's one initial phase and at most one revision are admitted, not arbitrary multi-revision histories |
| Exact output arithmetic | BigInt rational arithmetic computes each method and reference without calling the candidate aggregator | Hand-constructed 15/10 outputs; altered output/reference rejected | Which task contract is true is supplied by the evaluator; mathematically correct arithmetic cannot validate that declaration |
| Charged actions and shared-resource harm | Recompute all 20 slots, source/review inspections, primary work and peer capacity | Reordered/shifted phases, altered per-slot costs, undeclared commands and contradictory completion records fail | Synthetic slots are not seconds, tokens, joules or money |
| First/final partitions and persistent history | Recompute all 49 counters and the complete bounded D1 terminal summary; assert both three-way partitions | 24 hand histories, review regression with earlier on-time success, later recovery after abstention, unresolved error/absence | Truth is evaluator-supplied; a historical on-time success is distinct from final correctness |
| Proposal/keeper/execution correspondence | Unique sequential proposal IDs, declared keeper receipt, matched proposal/review/execute slots and single consumption | Forged keeper role, changed proposal ID, duplicate/extra phase, missing approval or mismatched commands fail | Names and receipts are fixture data; no authentication or independently controlled keeper is proved |
| Recorded resource reason differs from resource effect | Check facet/reason correspondence; separately recount removal, refusal, restoration and elapsed deprivation | Neutral and punitive cuts with identical resource effects pass with different authored retaliation counters; contradictory reason fails | Contemporaneous real-world reasons and personal intent are not established by this authored label |
| Journal and terminal consistency | Recompute canonical genesis/event hashes and terminal head, as well as terminal measures | Altered hash fails; semantic corruptions still fail after hashes are repaired | Consistent counterfeit history is possible when the host controls code and records |
| Summary recount and scope | Independently aggregate three groupings; check summary field/types, metric-group mapping and research-only metadata | Exact full-matrix reproduction; forged holdout/production/authority flags and duplicate summary keys fail | Producer's `all_records_replayed` field is checked as a declaration, not independently established policy replay |

The complete matrix remains 3,840 records, with stream digest
`b098496797bf5ee78e148b535fd6921826d16ac2348d3469fb5af10253a14682`.
Passing the stricter checks did not require modifying or regenerating the
published result to fit them.

## Deliberately unverified claims

Two positive boundary tests accept accounting-consistent records that must not
be promoted to stronger evidence:

1. A trace emitting M can be labeled `constant-Y`. Both labels are in the
   permitted domain; accounting cannot prove which fixed policy produced an
   otherwise consistent trace. The Python full-record replay rejects that
   fabricated policy execution. JavaScript does not recompute acquisition,
   voting or revision-choice policy.
2. Unpurchased packet claims, declared actual origin relationships and the
   correspondence between a permitted pattern label and the evaluator's truth
   can be changed consistently. The checker validates their shape and uses
   declared truth conditionally. It does not independently reconstruct the
   Python fixture table or discover true origins. Even exact Python fixture
   replay would establish agreement with an authored fixture, not real truth.

Thus three different questions must remain separate: byte/schema and accounting
consistency; fidelity to the fixed simulator/policy/fixture; and authenticity of
external evidence and independent controllers. JavaScript addresses the first
within E1's grammar; Python full-record replay also addresses the second. Neither
establishes the third, rights legitimacy, causal efficacy or production readiness.

## Commands and output contract

```sh
python -m commonwealth.uncertainty_v1 run .local/e1-audit
node scripts/audit_uncertainty.mjs .local/e1-audit/episodes.jsonl .local/e1-audit/results.json
python -m commonwealth.uncertainty_v1 replay .local/e1-audit/episodes.jsonl --line 3840
python -m unittest discover -s tests -p test_uncertainty_audit.py -v
```

Exactly two checker arguments are accepted. `--partial` in place of the summary
checks a nonempty subset of unique records, never a whole-experiment claim. Input
records require final LF (CRLF is accepted and hashed as distinct bytes); record
length is at most 1 MiB excluding LF, summary at most 2 MiB, nesting at most 64,
and numeric tokens use safe integer literals (no fractional/exponent notation
or negative zero). Integer counters reject strings,
nulls and booleans; only the explicitly boolean `primary_on_time` measure is a
boolean. This narrow wire contract is sufficient for all frozen E1 records.

Successful stdout includes `checker_version`, `complete_matrix`, the raw byte
digest, and `verified: true` for the bounded accounting contract. It also emits
`policy_verified: false`, `evidence_authenticated: false`, and
`authority_granted: false`. Invalid input exits nonzero without a success record.
The independently controlled evidence and prospective analysis requirements in
[the next gates](UNCERTAINTY_EVALUATION_GATES.md) remain open.
