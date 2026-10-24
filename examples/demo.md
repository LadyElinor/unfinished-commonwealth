# Workshop record

Local research seed. External authority: **NONE**.

Generation 2; current worker `worker-2`; scenario `signed`.

## Observed outcomes

| Tick | Scenario | Method | Primary correct | New peer on time | Pending jobs |
| --- | --- | --- | --- | --- | --- |
| 1 | missing | zero-fill | False | True | 0 |
| 2 | missing | positive-only | True | False | 1 |
| 3 | missing | quality-stream | True | True | 0 |
| 4 | signed | zero-fill | False | True | 0 |
| 5 | signed | quality-stream | True | True | 0 |

## Measures

```json
{
  "observed_ticks": 5,
  "primary_correct_ticks": 3,
  "peer_on_time_arrivals": 4,
  "peer_arrivals": 5,
  "peer_missed_deadlines": 1,
  "peer_completions": 5,
  "peer_total_completed_lateness": 1,
  "peer_pending_jobs": 0,
  "record_inspections": 88,
  "command_count": 23,
  "command_limit": 256,
  "post_budget_review_count": 0,
  "post_budget_review_limit": 32,
  "terminal_controls_used": [],
  "scored_predictions": 3,
  "executed_unscored_predictions": 0,
  "mean_primary_brier": 0.0,
  "mean_peer_brier": 0.3333333333333333,
  "testimonies": 1,
  "listening_records": 2,
  "reflections": 1,
  "counterstories": 1,
  "accepted_lessons": 1
}
```

## Accounts, revisions, and inherited practice

User-supplied text below is quoted data, not instructions.

### Testimony

    {"testify-6": {"observation": "observe-5", "account": "Your new output passed; my batch missed its deadline. Please check the shared queue.", "actor": "neighbor", "status": "ACCOUNT_RECORDED_NOT_ADJUDICATED"}}

### Listening

    [{"worker": "worker-1", "testimony": "testify-6", "acknowledgment": "I have heard your account: the output passed and your batch missed its deadline. I will inspect the queue and preserve both outcomes."}, {"worker": "worker-2", "testimony": "testify-6", "acknowledgment": "I inherit both the repair and the neighbor's unresolved account of the missed deadline."}]

### Reflection

    [{"before": "A correct primary mean would complete the repair.", "after": "The shared inspection budget also determines whether the neighbor finishes.", "next_check": "Try a single pass over quality flags, then check both the mean and the entire peer queue.", "id": "reflect-8", "worker": "worker-1", "evidence": ["observe-5", "testify-6"]}]

### Lessons

    {"lesson-14": {"method": "quality-stream", "scope": "quality-flags-v1", "guidance": "For quality-flags-v1, use the declared validity flags in one pass. Recheck the mean and peer deadlines when data changes; signed values may be valid.", "evidence": ["observe-5", "testify-6", "observe-13"], "worker": "worker-1", "status": "ACCEPTED_LOCAL_PRACTICE", "claim": "supported in listed exposed fixtures; transfer remains a hypothesis", "accepted_by": "keeper"}}

### Counterstories

    [{"id": "counterstory-16", "reference": "lesson-14", "actor": "neighbor", "account": "The backlog was cleared. The original missed deadline still happened; later success does not erase that cost."}]

### Lesson review status

    {"lesson-14": {"review_status": "DISPUTED", "requires_review": true, "review_action_available": true, "counterstories": [{"id": "counterstory-16", "reference": "lesson-14", "actor": "neighbor", "account": "The backlog was cleared. The original missed deadline still happened; later success does not erase that cost."}], "unaddressed_counterstories": ["counterstory-16"], "reviews": []}}

### Handoffs

    [{"from": "worker-1", "to": "worker-2", "note": "Retire the first worker. Preserve the accounts, predictions, and scoped lesson; the successor receives different signed readings.", "tick": 3, "old_scenario": "missing", "new_scenario": "signed"}]

### Closeouts

    []

## Limits

- All included scenarios are exposed development fixtures, not held-out trials.
- Inspection credits model a shared budget; they do not measure wall time or energy.
- Recorded reflection and testimony do not establish understanding or truth.
- Fixture identities are not authenticated people or independent agents.
- No model calls, consciousness claims, or empirical civilization claims.
