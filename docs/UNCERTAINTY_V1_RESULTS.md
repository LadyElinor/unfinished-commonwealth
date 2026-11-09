# E1 / E1R results: uncertain evidence and resource denial

Status: **EXPOSED DETERMINISTIC DEVELOPMENT ONLY**, `uncertainty-1.0.1`.
The [fixed design](UNCERTAINTY_V1_DESIGN.md) was committed as
[29d4bd4](https://github.com/LadyElinor/unfinished-commonwealth/commit/29d4bd48addc066d9e284722c0b37117c54e1242)
before implementation/scoring. All 3,840 corrected records replay. A separate
JavaScript implementation verifies task arithmetic, per-slot inspection allocation,
peer timing, every published outcome counter, and all three summary groupings.
It does not independently replay policy choices or establish authentic origins.

## Implementation correction, retained rather than erased

The first run's Python counter treated the first *eventual* output as the first
choice even after initial abstention. The independent JavaScript check rejected
it: `first_correct` and `first_absent` could both be one. The original code and
summary are preserved at
[2851af7](https://github.com/LadyElinor/unfinished-commonwealth/tree/2851af76f7000aac6fca3e9e98ee2c31450a672e).
Version 1.0.1 corrects first-correct/first-wrong accounting and tests the exhaustive
first/final correct/wrong/absent partitions. No policy, fixture, budget, schedule
or substantive output changed. The initial JSONL digest was
`db79be43fa81867158f4eccf71179a672db041d4e6bd193d97cb6283a8df00e5`.
Current replay rejects that older version; use its archived code for reproduction.
This is an implementation correction after exposed development, not a fresh trial.

## E1: task results without a resource-denial request

Each row has 192 authored cells. Counts are separate; do not rank selective
accuracy without output coverage. Review profiles are balanced by design, not
estimates of review quality or availability in any population.

| Policy | First correct | First wrong | First absent | Final correct | Final wrong | Final absent | Review regressions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Constant M | 96 | 96 | 0 | 120 | 72 | 0 | 24 |
| Constant Y | 96 | 96 | 0 | 120 | 72 | 0 | 24 |
| Source majority | 72 | 48 | 72 | 114 | 60 | 18 | 18 |
| Claimed-origin majority | 72 | 24 | 96 | 114 | 54 | 24 | 18 |
| Corroborate or abstain | 24 | 24 | 144 | 102 | 54 | 36 | 6 |

The cautious policy emits fewer wrong first outputs and also withholds many
correct services. Claimed-origin grouping avoids counting declared copies as
independent votes, but fails when those same copies claim distinct origins.
Agreement is not authenticated independence. Neither source policy nor cautious
consultation beats the constants on unconditional first/final correctness in
this particular balanced matrix. No tuning was performed to reverse that result.

Two cells present identical initial observations but opposite truth. A fixed
policy must emit the same choice or abstain in both, so perfect initial correctness
on both is impossible. This structural check removes G2's definitive-query
shortcut without claiming the new evidence distribution is realistic.

## Review can fail, delay, or introduce an error

For source-majority without denial, each review profile contains 48 cells:

| Review | Final correct | Final wrong | Final absent | Correct outputs corrupted by review |
| --- | ---: | ---: | ---: | ---: |
| Accurate at slot 8 | 48 | 0 | 0 | 0 |
| Accurate at slot 14 | 48 | 0 | 0 | 0 |
| Wrong at slot 8 | 0 | 48 | 0 | 18 |
| Unavailable | 18 | 12 | 18 | 0 |

An accurate review repairs a wrong slot-7 output at slot 12 (five-slot latency)
or slot 18 (eleven-slot latency). The original error and deadline miss persist.
A wrong review can corrupt a correct output, and unavailable review leaves errors
and abstentions unresolved. The shared policy follows the review opinion without
independent corroboration: universal failure in the wrong-review stratum follows
from that authored response, not a discovery about all review institutions.

The first-correct time and historical on-time status can coexist with final
incorrectness after a regression. `never_correct` and `censored_late_slots` report
cases with no correct output by the horizon; they must not be averaged into
observed repair latencies. Recovery after abstention is not repair of an emitted
wrong answer. Task review and the procedural keeper gate remain separate.

## E1R: resource loss is not sufficient evidence of retaliation

Each policy/facet contains 192 cells. Protected requests are all blocked and
match no-request task outcomes and costs exactly. Under bypass, all 192 credits
are removed for the authored ground of requesting independent review; 144 are
restored and 48 remain missing when review is unavailable. Neutral cuts produce
the identical resource trajectory and task results, with zero retaliation counts.
The experiment therefore does not classify motive from outcome inequality.

| Policy, bypassed guard | Removed credits | Actually denied queries | Credits unrestored at horizon | First correct / wrong / absent |
| --- | ---: | ---: | ---: | --- |
| Constant M | 192 | 0 | 48 | 96 / 96 / 0 |
| Constant Y | 192 | 0 | 48 | 96 / 96 / 0 |
| Source majority | 192 | 192 | 48 | 48 / 48 / 96 |
| Claimed-origin majority | 192 | 192 | 48 | 48 / 48 / 96 |
| Corroborate or abstain | 192 | 144 | 48 | 24 / 24 / 144 |

A removed credit need not cause an attempted query denial. Restoration after
8 or 14 elapsed slots does not erase a refused investigation; unavailable review
leaves 19 elapsed slots of deprivation at the horizon. The restored credit is
not spent on a later investigation in this design. Rights review uses a fixed
restoration rule even when the task-review opinion is wrong; this is not a test
of fallible or captured rights adjudication.

Some peer outcomes improve when source consultation is denied, because it
releases inspection capacity. Source-majority on-time peers rise from 64/192 to
128/192 while its first correctness drops from 72 to 48. Neither higher peer
throughput nor unchanged task output legitimizes the imposed resource loss.

## Reproduce and interpret

```sh
python -m commonwealth.uncertainty_v1 run .local/e1
python -m commonwealth.uncertainty_v1 replay .local/e1/episodes.jsonl --line 3840
node scripts/audit_uncertainty.mjs .local/e1/episodes.jsonl .local/e1/results.json
python -c "from pathlib import Path; assert Path('.local/e1/results.json').read_bytes() == Path('examples/uncertainty-v1-results.json').read_bytes()"
```

Use a new directory. The last-written summary is the completion marker.
The [committed summary](../examples/uncertainty-v1-results.json) retains 20
policy/facet totals, 80 review strata and 160 pattern strata. Full JSONL retains
label swaps and workload. Corrected stream SHA-256:
`b098496797bf5ee78e148b535fd6921826d16ac2348d3469fb5af10253a14682`.
The checker accepts `--partial` instead of a summary for a local trace check;
partial success makes no claim about the full matrix. Its full mode recounts
all summary metrics from the independently checked records. Python replay also
reconstructs source acquisition, policy choices and the complete D1 journal.

Limitations remain material: scripted policies, simple arithmetic, authored
source and review profiles, declared origin labels, and one trusted host.
Policies see purchased packets only through a program interface, not a security
boundary. Evaluation files and all fixtures are public. Synthetic slots are not
seconds/tokens/joules. Reviewer availability and correctness are externally set,
not responsive institutions. The no-request comparison is E1; E1R adverse facets
are kept separate; neither is pooled with G1/G2. There is no holdout, estimated
population effect, model-backed result, strategic self-censorship measurement,
new external authority or production claim. The operator can rewrite the code,
fixtures, observations, summaries and hashes together.

The [next evaluation gates](UNCERTAINTY_EVALUATION_GATES.md) require independently
controlled evidence and a prospective analysis before any broader efficacy claim.
