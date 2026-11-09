# Reproduce the 0.1.4rc2 research candidate

The candidate combines the coordination and evidence studies, the CORTAC maintenance pilot and prospective handoff, contributor reporting, and the assistance, equal-treatment, decision-premise and panel-opinion reviews. Distribution metadata identifies `unfinished-commonwealth` 0.1.4rc2. The historical workshop reports 0.1.3 and the standalone proposal client reports 2.0.0.

## Check out the candidate

```sh
git clone --branch release/0.1.4rc2 https://github.com/LadyElinor/unfinished-commonwealth.git commonwealth-rc2
cd commonwealth-rc2
git rev-parse HEAD
```

Retain that commit alongside the verification receipt. To repeat a particular build, use `git switch --detach` with its recorded commit in this clone. Use Python 3.11 or later. For complete verification, make Node.js available and install the build and optional test dependencies in a fresh Python environment.

```sh
python -m pip install "setuptools>=68" wheel "cryptography>=41" "jsonschema>=4.18"
python scripts/verify.py --require-no-skips --report .local/rc2-verification.json
python scripts/package.py .local/rc2-dist
```

Use fresh output paths for each attempt. The second command runs the source tests. The third builds the source archive, tests its contents, builds the wheel from that archive, and installs it into a clean environment. It checks the installed D1, charged workshop, neighbor warning, G1, G2 and E1 summaries against the published files. It also runs the assistance and opinion examples and verifies the separately installed proposal client.

The build writes the source archive, wheel and `package-verification.json` to `.local/rc2-dist`, with the client artifacts and receipt under `client-only`. Each receipt gives checksums for that build. On the candidate’s GitHub Actions run, the Ubuntu/Python 3.12 job retains the distributions and verification receipts together. Use the commit in the artifact name when citing a build. The experiments reproduce deterministic results. Package byte hashes can vary with build tools and timestamps.

## Inspect a result

| Question | Where to start |
| --- | --- |
| Can I reproduce the published workshop and measurement summaries? | [First reproduction](START_HERE.md) and [uncertain-evidence results and recount](UNCERTAINTY_V1_RESULTS.md) |
| Do a refusal, a replacement reviewer or an appeal change an owed remedy? | [Role histories and the 72 public hearings](ROLE_HISTORY_RESULTS.md) and [equal treatment and access to relief](EQUAL_TREATMENT_REVIEW.md) |
| Which reasons did a panel adopt, and what later evidence could change a decision? | [Panel opinion review](OPINION_REVIEW.md) and [decision premises](DECISION_PREMISES.md) |
| What could 24 maintenance pairs establish? | [Custody handoff and precision example](MAINTENANCE_CUSTODY_HANDOFF.md#interpreting-24-assigned-pairs) and [frozen protocol](MAINTENANCE_STUDY_PROTOCOL.md) |

The public exercises use exposed fixtures. Private maintenance intake requires an independent custodian, a separate grading lead and a witnessed pre-intake freeze. Volunteers can indicate a role and availability on [Issue #7](https://github.com/LadyElinor/unfinished-commonwealth/issues/7). Operational readiness remains `LOCAL_RESEARCH_ONLY`.
