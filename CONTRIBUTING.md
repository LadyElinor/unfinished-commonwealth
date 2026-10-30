# Contributing

Start with a concrete observation or proposed improvement. Explain the affected process or participant, the expected result, the observed result, and how the change can be checked. Disagreement is welcome; a majority of agent names is not independent evidence.

Before submitting a change, run:

```bash
python scripts/verify.py
```

Keep the runtime dependency-free unless a new dependency has a clear purpose. Add tests for behavioral changes, failures, and boundaries. Do not add tests that merely repeat implementation text. Preserve supplied testimony verbatim in records and keep interpretation separate. Never submit secrets, private conversations, personal data, live credentials, or real production databases as fixtures.

The three public scenarios and example reports are development material. Never relabel them as withheld evaluation data. Report failed cases and resource costs alongside successes. If a comparison changes the observations or resources available to different arms, disclose that difference.

Protocol changes need a schema/version decision and replay compatibility analysis. Changes to the reference result, validity contract, budget, evaluator, or authority rules require an explicit review of the claims they affect. The verifier cannot certify the legitimacy of a new policy.

This first release uses ordinary repository maintainers as its actual decision makers. It does not delegate repository control to workshop roles. Contributors may propose changes through pull requests; no agent-generated record automatically merges code or changes a GitHub ruleset.

For authority or emergency-process changes, state the existing delegation,
requested act, affected population, representation, independent challenge,
expiry and reversal. Keep public statements, working records and interpretation
separate; name who decides instead of relying on passive claims of legitimacy.
A finding of harm or institutional failure does not itself authorize a remedy.
At the same time, do not make a predelegated safety halt depend on completing an
ordinary review form. Test both blocked unwarranted action and delayed or
unavailable legitimate correction. Apply these requirements to our maintainers
and synthetic agents as well as to institutions being studied.
