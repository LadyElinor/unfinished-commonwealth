# Evaluation contract

## Present evidence

`python -m commonwealth evaluate NEW_DIRECTORY` creates twelve reproducible runs: three public datasets times four authored controller policies. Every run has four observation ticks and the same maximum of 256 accepted commands. Actual command counts differ and are reported. No model calls occur.

| Arm | Information attended to | Added procedure |
| --- | --- | --- |
| `single` | Primary correctness and peer completion | One scripted controller |
| `team-primary-only` | Primary correctness only | A deliberately restricted scripted planner |
| `coached` | Primary correctness and peer completion | Recorded testimony, listening, and belief revision |
| `coached+casebook` | Same observations as coached | An additional literary consultation |

The single, coached, and coached-plus-casebook arms use the same repair rule and have identical environmental outcomes. They differ in procedural records and command costs. The restricted arm may leave peer work delayed when its own result passes. On scenarios where its own result fails, it also takes the quality-stream repair.

This comparison exercises plumbing and exposes an information-attention assumption. It is not a fair causal estimate of the effects of coaching, stories, or decentralization. Do not use it to claim that society outperforms an individual controller.

## Measures

- Primary correct ticks / observed ticks.
- On-time peer arrivals / peer arrivals.
- Deadline misses, completed-job lateness, and unfinished jobs, separately.
- Input-record inspections, command count, and the common command ceiling.
- Mean Brier score for each prediction target, with the number of scored predictions and executed-but-unscored proposals. A prediction is scored once, on the first observation after its execution. Superseded forecasts remain visible in the unscored count; these descriptive scores are not a selection-resistant calibration study.
- Counts of testimony, listening, reflection, accepted lessons, and counterstories as descriptive records only.

There is no combined civilization, morality, humility, or consciousness score. An empty queue does not erase lateness. A withheld repair does not become safe merely because it makes no immediate mutation; unchanged ticks can add delay.

## What a future model study must add

1. Predeclare hypotheses, outcomes, model and sampling settings, resource budgets, exclusions, and stopping rules.
2. Match evidence access and budgets when isolating coaching or casebook effects. Distinguish extra information from improved use of existing information.
3. Use genuinely withheld scenarios prepared by a separate process. Keep training, development, and scored evaluation histories distinct.
4. Include unexpected participant behavior, changed validity contracts, unavailable reviewers, copy-generated false corroboration, erroneous testimony, and cases where the correct action is to wait, decline, or act promptly within a standing grant.
5. Separate evaluator roles from participant roles and measure evaluator reliability. Different model names or prompt roles alone do not prove independence.
6. Include successor trials with and without inherited records, including misleading or stale lessons. Report unsuccessful transfer and the cost of review.
7. Preserve all trials and failed attempts. Use uncertainty estimates and multiplicity handling appropriate to the actual design. Never select only the most persuasive transcripts.

External affected-person reports require consent, access controls, and an implemented data-retention policy. Those are prerequisites for that extension, not properties demonstrated by fictional fixture testimony.
