---
name: research-prioritization
description: Prioritize candidates transparently using adjustable expert-judgment weights.
---
# Research Prioritization

## When to use
Prioritize candidates transparently using adjustable expert-judgment weights.

## Mandatory procedure
1. Define the research question, target, and permissible scope.
2. Score relevance, security/governance value, evidence quality and implementation potential 0–100. Normalize weights; retain raw inputs, uncertainty and rationale. Never label prioritization a security rating.
3. Record primary and independent sources separately, with retrieval dates and stable IDs.
4. Distinguish claims, direct observations, independent reproduction, and open questions.
5. Write `priorities.json` and cite supporting sources; leave unknown fields null.
6. Record limitations and next authorized steps.

## Safety and integrity gates
- Public documentation permits reading, not intrusive testing.
- Never discover or enumerate suspected private app hostnames, bypass access controls, or access other users' data.
- Security tests run only in owned or explicitly authorized isolated environments using synthetic data.
- Robotic command tests use simulated, non-operational interfaces only.
- No invented reviewer signatures, approval records, timestamps, hashes or security assurances.
- Escalate suspected real exposure through responsible disclosure without further probing.

## Project integration
Outputs are advisory inputs to Unfinished Commonwealth and CORTAC; they confer no operational authority. Space ROS, Marscraft and Lunar Weevil integration must remain simulation-first.
