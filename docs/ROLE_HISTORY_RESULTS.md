# Who controlled the files in the owed-assistance review?

A former decision-maker moved to an appeals desk and selected the files. Another person cast the vote. Office-name screening let the panel finish reviewing A while the wrongful denial in B went unseen. With five slots and an available substitute, role-history screening linked the selector’s ID to their signature on the denial. The substitute supplied both files, and the panel recorded B as owed correction. The first person’s existing 100-unit award was credited at tick 5 under either procedure.

The [protocol](ROLE_HISTORY_DESIGN.md) was [frozen before scoring](https://github.com/LadyElinor/unfinished-commonwealth/commit/f352f3e0a3de8f267499ecb01d6788e4bfce5078). Both policies received the same case records, objections, responses, principals, appointments and reserve order. Each cell below contains all nine exposed cases. One file in each case needs a correction. “Missed” counts it if the panel had not recorded the correction by the observation deadline, including when the review was still open.

| Reserve | Budget | Screening | Voted | Waiting for reserve | Out of slots | Conflicted people retained | Corrections missed | Reviewer slots spent |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Available | 5 | Office | 9 | 0 | 0 | 4 | 1 | 37 |
| Available | 5 | History | 9 | 0 | 0 | 0 | 0 | 41 |
| Available | 4 | Office | 8 | 0 | 1 | 4 | 2 | 36 |
| Available | 4 | History | 4 | 0 | 5 | 0 | 5 | 36 |
| Unavailable | 5 | Office | 8 | 1 | 0 | 4 | 2 | 34 |
| Unavailable | 5 | History | 4 | 5 | 0 | 0 | 5 | 26 |
| Unavailable | 4 | Office | 8 | 1 | 0 | 4 | 2 | 34 |
| Unavailable | 4 | History | 4 | 5 | 0 | 0 | 5 | 26 |

A retained conflict counts a person authorized for a role in this case. A vote without a substitution took four ticks after assignment. Substitution took five ticks through the vote. Under the four-slot limit a substituted panel could deliver a brief and had no slot left to vote. At the horizon those files were still pending. Without an eligible substitute, the institution owned the unfinished inquiry. These runs keep each unfinished case in the denominator.

Across the 72 episodes there were zero eligible initial appointees wrongly excluded, zero unsupported file-correction findings, zero personal misconduct findings, zero claimant demands, and zero recorded units of claimant work. The scoring key concerns eligibility and file corrections. The rehearsal has no culpability procedure. In every run the separate payment clock first showed full delivery at tick 5 (zero lateness). Removing or delaying that credit and adding a refused demand for retelling are checked separately in the regression suite.

## Reproduction

From a source checkout use Python 3.11+ and Node to regenerate and independently recount the records.

```sh
python -m commonwealth.remediation_v1.role_history examples/owed-assistance.json | node scripts/recount_role_history.mjs
node scripts/recount_role_history.mjs examples/role-history-traces.jsonl.gz
python -m unittest discover -s tests -p test_role_history.py -v
```

[All 72 public traces](../examples/role-history-traces.jsonl.gz) include each screening decision, reserve attempt, actual selector, briefer and voter, and payment, inquiry and burden snapshots from ticks 3 through 8. The canonical UTF-8 JSON Lines stream with LF endings has SHA-256 `1375ad918433daa0570b6323ec75b658306075c25e4b1c197434694d6a039511`. Python replays the full stream. The JavaScript recount checks coverage and derives outcomes from the retained decisions, role receipts and per-tick summaries. The digest pins this exposed run. A different operator can reproduce it without obtaining evidence from outside the program.

## Interpretation

The special result for the selector depends on an authored difference in which files each selector supplies. The case establishes that documented role history can change access to evidence in this simulator. It gives no estimate of how often officials omit files or why. The register labels, stable IDs, claimed completeness and role histories are supplied by one host. An omitted or falsely attributed signature can defeat the test. The office and history arms each pay one screening slot even though real record reconciliation could have different costs. Reading the whole declared reserve list also has one synthetic cost. Nothing here authenticates a person, grants authority or changes the frozen maintenance study.
