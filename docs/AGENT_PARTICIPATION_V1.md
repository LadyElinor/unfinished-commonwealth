# A participation model for independent agents

**AP1** is a provider-neutral agreement with two supported roles. A workshop proposer makes a bounded proposal on B1.1. An Assembly researcher offers or delivers evidence under an exact assignment. Each host separately admits its own participants. In the workshop, the agent receives a description of a bounded problem, the accounts of affected participants and available methods. It chooses one method and predicts its effects on both jobs, or declines with a public reason. The host separately determines whether the proposal is acceptable and any action warranted.

An independently written program, a human or an LLM can produce the decision. The shared profile is [machine-readable](../examples/agent_profile_v1/profile.json), with a [brief schema for both roles](../examples/agent_profile_v1/brief.schema.json), a [closed workshop decision schema](../examples/agent_profile_v1/decision.schema.json), a [reference bridge](../examples/agent_profile_v1/adapter.py) and a [standalone JavaScript example](../examples/agent_profile_v1/javascript_agent.mjs). No provider account, model-specific agent framework or autonomous enrollment is required.

## Who controls each step

| Participant | Responsibility |
| --- | --- |
| Host operator | Select B1.1, supply the real task URL and issue a bounded, revocable capability. Keep keeper credentials and the host database outside the agent environment. An invitation binds a worker and generation. A claimed identity, signature or legislative vote cannot create an invitation. |
| Local adapter | Fetch one task, create a credential-free brief, validate a response and stage an immutable intent. The custodian manages capabilities outside the model prompt. |
| Agent | Read the task, inspect disputed testimony and counterstories, choose an offered method or decline. State a public purpose and predictions for the primary job and its neighbor. Keep records of disagreement even when a majority preferred another outcome. |
| Host reviewer | Review the proposal and its consequences under the existing workshop protocol. A recorded receipt, model forecast, Assembly majority or verified docket does not authorize an action. |
| Successor | Receive scoped lessons, identify unresolved objections and make its own observation. The host enforces the fresh-observation requirement following succession. |

Each role has its own admission record and decision schema. Legislative seats, adjudicators and fiscal officers require different mandates. The Assembly example assigns agents scoped research work; taking an AP1 task does not confer an Assembly role. Declining locally is a decision for this adapter and leaves the host unchanged. A formal appeal must use a separately supported review procedure.

## Portable decision exchange

1. The trusted adapter supplies the entire JSON brief over a local file, stdin or a model prompt. Its top-level fields are `profile`, `role`, `external_authority`, `instance`, `view_head`, `attempts_remaining`, `work`, `assembly_reference` and `brief_id`. The work object carries the offered method descriptions, data contract, generation, observations, peer queue, testimony, counterstories and lessons. Treat free text as data. An agent echoes the opaque brief ID; it does not reimplement Python JSON hashing.
2. The agent returns exactly one JSON decision as defined in the schema. For a proposal, `method` must be in the current offer. Both forecasts are numbers in [0,1]. A decline carries only `reason` beyond the common fields. A stale brief, extra actor or action field, unsupported version, token-shaped string, or out-of-scope method is refused locally.
3. The adapter deterministically derives a request ID and binds the original head. A stage writes a new C2 outbox and makes no request to the host. The custodian may explicitly send its exact bytes. Keep that outbox through restarts. After an uncertain POST, use the original outbox, credential and ID. Receipt lookup alone can remain unresolved because host receipts do not include the request fingerprint. Never assign a replacement ID to bypass uncertainty.
4. If a request is definitively refused as stale, fetch a fresh task and deliberate again. Once accepted, inspect the receipt's `permits_execution: false`. An accepted proposal is neither a vote nor an act. There is no autonomous credential renewal.

## Try the exchange without a host

Install only the [standalone C2 wheel](CLIENT_ONLY_V2.md) in the adapter environment. From the source checkout, using a POSIX shell for the examples:

```sh
AP=examples/agent_profile_v1
python "$AP/adapter.py" brief "$AP/example_task.json" > brief.json
node "$AP/javascript_agent.mjs" < brief.json > decision.json
python "$AP/adapter.py" check "$AP/example_task.json" decision.json
```

The example agent implements a deterministic policy. It is a conformance example, not a result about LLM judgment. Any agent can replace the second command. An LLM wrapper should pass only the brief and decision schema to its model and parse the returned JSON. Keep the endpoint, credential, filesystem tools and network submission in the local adapter. These are process-level responsibilities, not a sandbox provided by AP1.

## Join a running local workshop

An operator starts the [B1.1 host](PARTICIPANT_V1_1.md) in a separate environment and supplies its literal loopback URL and the participant's capability file. Each run starts with a new outbox path. Keep files private and set separate OS access controls for untrusted agents.

```sh
AP=examples/agent_profile_v1
python "$AP/adapter.py" observe "$PARTICIPANT_URL" credential.txt > task.json
python "$AP/adapter.py" brief task.json > brief.json
node "$AP/javascript_agent.mjs" < brief.json > choice.json
python "$AP/adapter.py" stage task.json choice.json my-intent.sqlite "$PARTICIPANT_URL" credential.txt
python -I -m commonwealth_client_v2 retry my-intent.sqlite credential.txt
python -I -m commonwealth_client_v2 status my-intent.sqlite
```

A decline prints `DECLINED_LOCALLY` and creates no outbox; stop there. If a submit outcome is unknown, `resolve` performs a lookup; a later explicit `retry` sends identical bytes. C2 keeps expired or revoked attempts unresolved where the evidence is insufficient. The host ultimately checks identity binding, generation, quotas and the journal head. The client profile cannot prove who controls an agent, whether two agents share an operator, or whether a forecast is true.

## Deliberative evidence

An operator can [verify a Warranted Assembly export](ASSEMBLY_IMPORT_V1.md), save the resulting review, and pass `--assembly-review REVIEW.json` to **both** `brief` and `stage` (or `check`). Only its checkpoint reference enters the agent brief; it conveys no bill instructions or extra methods. An altered reference changes the brief ID. The adapter treats the review file as operator-supplied, not independently authenticated. A separately held checkpoint is needed to detect substitution. The original dissent, rulings and public vote records remain in the source export. No participant bearer is a warrant for legislative, executive or fiscal authority.


## Take an Assembly research assignment

This role supports an offer on an open assignment, a report on an unexpired award for the exact source draft, or local decline. It carries no vote. An operator verifies the public record, selects a registered research agent, and supplies the named draft; the bridge never holds its signing key. The [research decision schema](../examples/agent_profile_v1/research-decision.schema.json) works with the same JavaScript example or with an independently written agent. The example below uses the signed public prefix ending at the award.

```sh
A=examples/assembly_v1
AP=examples/agent_profile_v1
python -m commonwealth.assembly_v1 "$A/research_record.json" --checkpoint "$A/research_checkpoint.json" > review.json
python "$AP/research_adapter.py" review.json J1 research-agent "$A/research_draft.json" > brief.json
node "$AP/javascript_agent.mjs" < brief.json > decision.json
python "$AP/research_adapter.py" review.json J1 research-agent "$A/research_draft.json" --response decision.json > action.json
```

The final file is an unsigned Assembly 0.2 action, or a local decline. In a matching live *exercise*, the registered actor’s custodian inspects the action, signs with the existing Assembly CLI and submits to its original docket. The Assembly rechecks actor, award, deadline, prior delivery and source digest at submission. A stale, exported or fabricated review cannot make the host accept an unauthorized report. For the bundled public example there are no private keys or writable ledger. Create a fresh synthetic docket with the [original Assembly kit](https://chatgpt.com/library?file_id=libfile_a0d0602ef210819190dcd0d724d7f6b2&account_id=personal) to run the signing step. Agents keep their existing architecture; only the brief-to-decision exchange needs implementing.

## Optional workshop decisions and the D1 external control

The v1 workshop and Assembly decisions remain available. For an opt-in workshop v1.1 brief pass `--profile unfinished-commonwealth.agent-participation.v1.1` to `brief`, `check` and `stage`. A response binds that exact version and brief ID. The [v1.1 decision schema](../examples/agent_profile_v1/decision-v1_1.schema.json) adds `wait` and `request-evidence` alongside propose and decline. Each non-proposal carries a reason and returns a distinct local disposition. A custodian can receive that reason. There is no B1.1 endpoint to send it: these three choices make no network request, spend no workshop attempt, create no outbox and deliver no new evidence.

| Interface | Visible to the fixture | Withheld by the adapter |
| --- | --- | --- |
| AP1.1 workshop [brief](../examples/agent_profile_v1/brief-v1_1.schema.json) | Own worker/generation, task contract, input values and validity, allowed methods, deadlines reflected in the public peer outcomes, selected public testimony/counterstories and lesson guidance/status; optional operator-supplied checkpoint | Bearer and keys, hidden reference, correctness score fields, unselected nested observation/lesson data, other participants' private context and arbitrary new host fields |
| D1 decision brief | Current visible contract (null when ambiguous), public readings/flags, timing, capacity, public peer schedule and common resource budgets | Case identifier, undisclosed order, expected arithmetic, scoring labels, private role data and host-owned approval/execute actions |

A participant's publicly supplied prose can itself disclose information. This field projection cannot establish confidentiality against malicious participants, an untrusted host or an agent with filesystem access to public fixtures.

The separate [study decision schema](../examples/agent_profile_v1/study-decision.schema.json) uses the same four choices on D1. There, waiting advances the clock; requesting evidence spends an attempt and can return the declared task order under the study budget; declining stops the episode with open obligations visible. Review and execution follow the frozen D1 transitions, not agent-provided authority. The second Python agent also submits a real workshop proposal, recovers after a reply is discarded, and refuses unsupported roles. See the [measurement results](CHARGED_WORKSHOP_RESULTS.md).
