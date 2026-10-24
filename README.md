# The Unfinished Commonwealth

**A persistent workshop for learning to cooperate, attend to consequences, and pass experience to successors.**

The research question is practical: can a community improve its cooperation as its participants, circumstances, and procedures change?

Version **0.1.2** provides a working local research seed. It runs real integer-data transformations inside a bounded workshop, shares a record-inspection budget between two jobs, records testimony and predictions, and passes a tested practice to a successor working on different data. Python 3.11 or later is sufficient. Runtime and tests use the standard library.

The included participants are **scripted fixture roles**, with an additional proposal-only JSON interface for a separately operated model or human. No model-backed study has been run. This repository does not establish independent machine persons, autonomous civilization, or authority outside its local workshop.

## Run the workshop

```bash
python -m commonwealth demo .local/demo.sqlite --report .local/demo.md
python -m commonwealth status .local/demo.sqlite
python -m commonwealth verify .local/demo.sqlite
python -m unittest discover -s tests -v
```

On Windows, use `py -3` if necessary. Run from the checkout root. A database or report that already exists is never overwritten; choose a new path to repeat a demonstration. Optional `python -m pip install .` adds the `commonwealth` command; installation may fetch the setuptools build dependency.

For the full local check, run `python scripts/verify.py`. To produce a source archive and wheel, verify the source distribution, and smoke-test a clean offline installation, run `python scripts/package.py .local/release`. Packaging additionally requires locally installed setuptools (68 or later), wheel, pip, and venv; it never downloads build dependencies. See [build and validation](docs/BUILD.md) and [release 0.1.2](docs/RELEASE_0_1_2.md).

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

Reflection consumes a command but no simulated time. `quality-stream` implements the fixtures' expected answer and works across every included case, so these scenarios cannot demonstrate adaptive method selection.

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
- **Reproducible comparisons:** twelve exposed scripted runs with outcome and cost measures reported separately.

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
| `commonwealth/data/` | Three explicitly public development fixtures |
| `tests/` | Behavioral, persistence, concurrency, and failure tests |
| `docs/` | Design, casebook, trust boundary, provenance, and research plan |
| `examples/` | Proposal schema, sample inputs, and a reproduced run record |

## Growing the project

The next useful step is a separately controlled model-backed study with predeclared comparisons, a fixed resource budget, and genuinely withheld scenarios. More elaborate stories or more agent names cannot substitute for it. [Roadmap](ROADMAP.md).

[Metanoia](https://github.com/LadyElinor/Metanoia), [Adiona](https://github.com/LadyElinor/Adiona), and [CORTAC](https://github.com/LadyElinor/CORTAC) informed the design. This is new code with **no operational adapters or compatibility claim** for those projects. Their authority contracts remain unchanged. [Integration boundaries](docs/INTEGRATION.md).

Contributions can add a failing case, an affected participant's account, a repair, or a competing interpretation. Each should say what evidence could change its conclusion. See [CONTRIBUTING.md](CONTRIBUTING.md).

Licensed under the [MIT License](LICENSE). External references and the full manuscript are not bundled or relicensed by this repository.
