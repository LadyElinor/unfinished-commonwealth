# The Unfinished Commonwealth

**A persistent workshop for learning to cooperate, attend to consequences, and pass experience to successors.**

The research question is practical: can a community improve its cooperation as its participants, circumstances, and procedures change?

Version **0.1.3** provides a working local research seed. It runs real integer-data transformations inside a bounded workshop, shares a record-inspection budget between two jobs, records testimony and predictions, and passes a tested practice to a successor working on different data. Python 3.11 or later is sufficient. Runtime and tests use the standard library.

The included participants are **scripted fixture roles**, with an additional proposal-only JSON interface for a separately operated model or human. No model-backed study has been run. This repository does not establish independent machine persons, autonomous civilization, or authority outside its local workshop.

## Run the workshop

```bash
python -m commonwealth demo .local/demo.sqlite --report .local/demo.md
python -m commonwealth status .local/demo.sqlite
python -m commonwealth verify .local/demo.sqlite
python -m unittest discover -s tests -v
```

On Windows, use `py -3` if necessary. Run from the checkout root. A database or report that already exists is never overwritten; choose a new path to repeat a demonstration. Optional `python -m pip install .` adds the `commonwealth` command; installation may fetch the setuptools build dependency.

For the full local check, run `python scripts/verify.py`. To produce a source archive and wheel, verify the source distribution, and smoke-test a clean offline installation, run `python scripts/package.py .local/release`. Packaging additionally requires locally installed setuptools (68 or later), wheel, pip, and venv; it never downloads build dependencies. See [build and validation](docs/BUILD.md) and [release 0.1.3](docs/RELEASE_0_1_3.md).

The demonstration has five observed ticks:

| Tick | What happens | Primary result | Neighbor's new batch |
| --- | --- | --- | --- |
| 1 | Missing readings are replaced with zero | Incorrect | On time |
| 2 | A two-pass positive-only repair | Correct on this dataset | Misses its deadline |
| 3 | Listen, inspect the shared cost, use quality flags in one pass | Correct | On time; old backlog also completed |
| 4 | A new worker receives signed readings and starts with the original method | Incorrect | On time |
| 5 | The successor tests the inherited, scoped practice | Correct | On time |

The original missed deadline remains in the record. A counterstory preserves the neighbor's account after the repair. The successor receives a lesson and its evidence, not an inherited execution grant.

Inherited advice exposes disputes and the linked counterstories. Keeper reviews can retain, suspend, or retire a lesson; none certify that an account is true. Every successor must observe its own generation before proposing, then obtain separate approval before execution. After the 256-command operational limit, a bounded review allowance and terminal controls preserve accounts and unresolved obligations. [Protocol and limits](docs/PROTOCOL.md).

These are deterministic authored events. The data transformations and deferred queue processing actually execute; inspection credits model resource pressure and do not measure wall time, energy, or token cost.

In the original workshop, reflection consumes a command but no simulated time.
`quality-stream` implements every original fixture's expected answer, so those
scenarios cannot demonstrate adaptive method selection. The separate study
harness below uses contrasting contracts and a decision clock.

## Participate through a proposal

```bash
python -m commonwealth init .local/manual.sqlite
python -m commonwealth observe .local/manual.sqlite
python -m commonwealth agent-view .local/manual.sqlite
python -m commonwealth propose .local/manual.sqlite examples/proposal.json
python -m commonwealth approve .local/manual.sqlite propose-2
python -m commonwealth execute .local/manual.sqlite propose-2
python -m commonwealth observe .local/manual.sqlite
python -m commonwealth coach .local/manual.sqlite
```

The `propose-2` identifier applies to exactly the sequence above. Use the returned ID when your sequence differs. `agent-view` produces a bounded task packet suitable for a separate model session. `propose` accepts only strict proposal JSON. The broader `submit` command is an operator tool for testimony, listening, reflection, lessons, and counterstories; it is not a protected agent endpoint.

**Actor names are supplied fixture identities, not authentication.** A person with CLI or database access can act as `keeper`. Proposal/approval separation exercises a protocol; production credential separation is unimplemented. See [the trust boundary](docs/THREAT_MODEL.md).

## What is implemented

- **Persistent experience:** transactional SQLite state and a hash-linked journal, with deterministic replay before every accepted mutation.
- **Consequences:** exact rational results, actual FIFO peer-job progress, a fixed shared inspection budget, deadline misses, and prediction scores.
- **Coaching:** invitations to observe, listen, inspect an assumption, act within existing bounds, and return to check effects. Written reflection is not scored as understanding.
- **Bounded transitions:** exact-action approval, revision and epoch binding, single-use consumption, logical-tick expiry, halt/resume, and revocation.
- **Succession:** retirement of the old worker, invalidation of pending authority, preservation of accounts and counterstories, and retrieval of scoped lessons.
- **A literary casebook:** questions from *The Codex of Unfinished Minds*, kept distinct from executable evidence and open to competing interpretations.
- **Reproducible comparisons:** fifteen exposed scripted runs, including an explicit constant-quality-stream control with outcome and cost measures reported separately.

```bash
python -m commonwealth evaluate .local/comparison
python -m commonwealth readiness
```

`readiness` deliberately exits **2** and reports `LOCAL_RESEARCH_ONLY`. The suite is not a deployment gate that can be passed by collecting more green tests.

In the included comparison, the single controller and coached controller produce identical environmental outcomes. Consulting a story adds a record but no outcome benefit. The restricted team baseline ignores peer outcomes unless the primary result also fails. Those authored assumptions do **not** identify a causal coaching, literary, or decentralization advantage. [Evaluation contract](docs/EVALUATION.md).

## Project map

| Path | Purpose |
| --- | --- |
| `commonwealth/pipeline.py` | Executable aggregation and shared-budget queue |
| `commonwealth/engine.py` | Typed, replayable protocol transitions |
| `commonwealth/legacy_v1.py` | Frozen historical transitions for replay only |
| `commonwealth/store.py` | Atomic persistence, journal verification, and replay |
| `commonwealth/coach.py` | Coaching cues and scoped inherited advice |
| `commonwealth/interface.py` | Proposal-only external participant packet |
| `commonwealth/experiment.py` | Scripted demonstration and exposed comparisons |
| `commonwealth/study_v1/` | Separate contrasting-contract harness, scheduler, controls and replay |
| `commonwealth/data/` | Three explicitly public development fixtures |
| `tests/` | Behavioral, persistence, concurrency, and failure tests |
| `docs/` | Design, casebook, trust boundary, provenance, and research plan |
| `examples/` | Proposal schema, sample inputs, and a reproduced run record |

## Growing the project

A separate **study harness 1.0.0** now implements the deterministic portion of the
[next-study specification](docs/NEXT_STUDY.md). It leaves the original workshop,
fifteen comparisons and historical replay unchanged. Run it independently:

```bash
python -m commonwealth.study_v1 run .local/study-v1
python -m commonwealth.study_v1 replay .local/study-v1/journals/decision-slots-v1--yield-urgent--always-inspect.json
```

Its 432 exposed runs cross 12 environments, 18 control/treatment arms and two
resource models. The two contracts require 15 and 10 from the same readings.
No constant method solves the discriminating suite; the simple evidence selector
matches the uncoached participant. Unnecessary inspection and advice can miss
urgent deadlines. These results demonstrate harness behavior, not intelligence
or institutional benefit. See the [fixed design](docs/STUDY_V1_DESIGN.md),
[negative results and limits](docs/STUDY_V1_RESULTS.md) and
[complete aggregate record](examples/study-v1-summary.json).

No model-provider calls or independent held-out evaluation are included. A
future model-backed study would require separate authorization, a fixed analysis
plan and genuinely withheld scenarios. More elaborate stories or more agent
names cannot substitute for those gates. [Roadmap](ROADMAP.md).

An opt-in [procedural review extension](docs/PROCEDURAL_REVIEW_V1.md), informed
by the Congressional Record and federal court rules, adds recorded notice,
response opportunities, specific objections, reasoned rulings, revision-bound
grants, separate appeals, prospective stays and corrections that preserve the
original record. It uses the same costed decision scheduler and leaves D1 frozen.
Its P1.1 version renews notice after new material, preserves both parties'
petitions and replies in one bounded appeal, and refuses truncated notice
windows. Old P1 journals retain their original replay rules.

```bash
python -m commonwealth.procedure_v1 run .local/procedure-v1
python -m commonwealth.procedure_v1 replay .local/procedure-v1/journals/terminal-appeal.json
```

Its [eight exposed traces](docs/PROCEDURAL_REVIEW_V1_RESULTS.md) retain denials,
unresolved appeals, delay costs and a procedurally approved wrong answer.
Procedural conformity does not establish truth, legal compliance or efficacy.

A separate [fraud-discernment study](docs/FRAUD_DISCERNMENT_V1.md) translates
documented fraud mechanisms into bounded, advisory evidence checks. Its 150
exposed runs compare fixed controls on forged invoices, borrowed endorsements,
dependent corroboration, missing authority and legitimate urgent requests.
It preserves source status and tests false alarms, delay, abstention and a
compromised-verifier failure. This is deterministic software research; it does
not train an AI or establish a real-world scam-reduction rate.

```bash
python -m commonwealth.discernment_v1 run .local/discernment-v1
python -m commonwealth.discernment_v1 replay .local/discernment-v1/journals/compromised-trusted-roots--evidence-gate.json
```

See the [discernment results and limits](docs/FRAUD_DISCERNMENT_V1_RESULTS.md).
The [October 2026 Korean finance incident review](docs/INCIDENT_REVIEW_2026_10_KOREAN_FINANCE.md)
adds negative regressions for receipt replacement and missing origin quarantine.

The separate [I1 integrity extension](docs/INTEGRITY_V1.md) adds structured
commitment/action review and tests declared issuer quarantine, shared evidence
dependencies and trust overreach in 112 exposed runs. Its [source audit](docs/INTEGRITY_SOURCE_REVIEW.md)
separates political criticism from demonstrated discrepancies. The
[results](docs/INTEGRITY_V1_RESULTS.md) retain undetected compromise, legitimate
requests blocked by quarantine and deadline misses.

```bash
python -m commonwealth.integrity_v1 run .local/integrity-v1
```

The [R1 review extension](docs/REVIEW_V1.md) adds explicit contrary-evidence
disclosure, declared conflict/capacity checks, alternatives and separate
reconsideration of closed advice. Its [14 exposed traces](docs/REVIEW_V1_RESULTS.md)
retain wrong restrictions, delays and unresolved reviews. The
[repository review](docs/REPOSITORY_REVIEW_2026_10_24.md) records coverage and remaining gaps.

```bash
python -m commonwealth.review_v1 run .local/review-v1
```

[Metanoia](https://github.com/LadyElinor/Metanoia), [Adiona](https://github.com/LadyElinor/Adiona), and [CORTAC](https://github.com/LadyElinor/CORTAC) informed the design. This is new code with **no operational adapters or compatibility claim** for those projects. Their authority contracts remain unchanged. [Integration boundaries](docs/INTEGRATION.md).

Contributions can add a failing case, an affected participant's account, a repair, or a competing interpretation. Each should say what evidence could change its conclusion. See [CONTRIBUTING.md](CONTRIBUTING.md).

Licensed under the [MIT License](LICENSE). External references and the full manuscript are not bundled or relicensed by this repository.
