# Start with one reproducible result

The Unfinished Commonwealth studies whether bounded cooperation practices change outcomes and costs. All current comparisons use exposed deterministic fixtures. No model-backed efficacy study or deployment has been completed. The host operator can rewrite code, inputs, journals and reports together.

## Which implementation to inspect

| Component | What it establishes | Entry point and evidence |
| --- | --- | --- |
| Workshop 0.1.3 | A repair and scoped succession retain the original peer deadline miss | `commonwealth/pipeline.py`, [historical evaluation](EVALUATION.md) |
| D1 contrasting-contract harness | Different contracts require different answers; consultation and refusals consume synthetic time | `commonwealth/study_v1/`, [design](STUDY_V1_DESIGN.md), [results](STUDY_V1_RESULTS.md) |
| C1c charged comparison | The same fifteen historical traces have different timing consequences under two declared schedules | `commonwealth/measurement_v1/workshop.py`, [results](CHARGED_WORKSHOP_RESULTS.md) |
| N1 neighbor warning | Paid information can reduce deadline misses without reducing total lateness | `commonwealth/measurement_v1/neighbor.py`, [design](NEIGHBOR_TIMING_DESIGN.md), [results](NEIGHBOR_TIMING_RESULTS.md) |
| AP1 participation | Independently written programs can exchange bounded JSON briefs and decisions | [profile and roles](AGENT_PARTICIPATION_V1.md), [C2 client](CLIENT_ONLY_V2.md) |

The historical runtime still reports 0.1.3. The package metadata says 0.1.4rc1 for the unpublished candidate containing these additions. The earlier [0.1.3 release](RELEASE_0_1_3.md) describes its frozen baseline. New measurements live in separate modules; reading only `pipeline.py` and `experiment.py` will not show D1 or N1.

## Reproduce the three measurement summaries

Run from the checkout root with Python 3.11 or later. No model account or provider credentials are needed. Each destination must be new; for another attempt, choose a new parent directory rather than deleting failed-run evidence.

```sh
git rev-parse HEAD
git status --short
python --version
python -m commonwealth.study_v1 run .local/first-reproduction/d1
python -m commonwealth.measurement_v1 neighbor .local/first-reproduction/neighbor
python -m commonwealth.measurement_v1 run .local/first-reproduction/charged --fixture-agent examples/agent_profile_v1/python_agent.py
```

Expected coverage is 432 D1 runs, 1,008 N1 episodes, and a charged report with 15 workshop rows plus 12 external-fixture comparisons. Compare all three summaries with the published files in one command.

```sh
python scripts/check_reproduction.py .local/first-reproduction
```

The command prints a line for each summary and exits 0 only when all three match byte for byte. `DIFFER` names the published file to compare. `UNREADABLE` includes the path that could not be read. Pass your own output directory if you used a different one.

For all behavioral, compatibility and local documentation checks:

```sh
python scripts/verify.py
```

The base suite uses the standard library. Some conformance checks are explicitly skipped without optional dependencies. To exercise those checks too, install the Assembly and schema libraries in your test environment and make Node.js available:

```sh
python -m pip install "cryptography>=41" "jsonschema>=4.18"
node --version
python scripts/verify.py
node scripts/audit_measurement.mjs study .local/first-reproduction/d1/journals .local/first-reproduction/d1/results.json
node scripts/audit_measurement.mjs assembly examples/assembly_v1/public_record.json
```

The JavaScript checker separately computes arithmetic, reconstructs peer service from recorded costs, and recounts public chamber votes. It does not verify signatures, independent custody or the truth of ballots. Installing dependencies may require network access; the experiments themselves make no model calls.

The [UID-boundary demonstration](UID_ISOLATION.md) is a separate opt-in Linux check with privileged setup on a disposable runner. Ordinary unit tests do not establish that it ran. `python -m commonwealth.measurement_v1 readiness` deliberately exits 2 with `LOCAL_RESEARCH_ONLY`; that result is expected.

## Choose one contribution

1. **Reproduce and report a result.** Record the commit, local modifications, OS, Python/Node versions, exact commands, exit codes, skipped checks and summary comparison. Report a failed attempt as well as a successful one. Rerunning this checkout is a replication of supplied code, not an independent reference implementation.
2. **Check sixteen N1 cells independently.** Use a spreadsheet, hand calculation or another implementation of the [frozen rules](NEIGHBOR_TIMING_DESIGN.md), at primary deadline 3 and warning reliability 3/4. Compare `coin` and `ask-peer`. Both should reserve eight slots and miss eight primary deadlines. Peer misses should be four versus two, while total peer lateness stays four slots in each arm. Retain every cell and explain any disagreement. Do not tune the rules after seeing a mismatch.
3. **Implement a JSON fixture agent.** Follow [AP1](AGENT_PARTICIPATION_V1.md) in another language and report the first ambiguous instruction. Exercise stale briefs, role mismatch, decline and recovery as well as acceptance. The scored C1c comparison intentionally accepts only its pinned Python fixture; use AP1 conformance for a new agent and propose a new frozen comparison before scoring it.

Use the reproduction-report template to share a result. If an instruction stopped you, the [contributor observation form](https://github.com/LadyElinor/unfinished-commonwealth/issues/new?template=observation.md) takes a brief description even if you never ran a command. English and Chinese reports are welcome. Publish only synthetic inputs and sanitized output. Keep credentials, private context and production databases out of reports.

## Read negative results first

The D1 evidence selector ties the uncoached participant. Coaching and inheritance do not demonstrate an advantage. C1c replays fixed decisions rather than testing agents responding to new deadlines. N1's peer and matched instrument give identical results with identical information and costs. None of these cases is a holdout, and a synthetic slot is not a measured second, token or joule.

The next experimental advance needs a prospectively specified question and controls, followed by independently controlled evidence where the claim requires it. See [NEXT_STUDY](NEXT_STUDY.md), [the roadmap](../ROADMAP.md) and [production blockers](PRODUCTION_READINESS.md).
