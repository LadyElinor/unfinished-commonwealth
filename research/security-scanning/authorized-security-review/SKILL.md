---
name: authorized-security-review
description: Perform bounded static security review of owned or expressly authorized software.
---
# Authorized Security Review

## When to use
Perform bounded static security review of owned or expressly authorized software.

## Mandatory procedure
1. Define the research question, target, and permissible scope.
2. Confirm ownership and authorization first. Review authentication, tenant isolation, secrets, dependency risks, network bindings and command paths. Use synthetic fixtures only; do not test suspected exposed third-party apps.
3. Record primary and independent sources separately, with retrieval dates and stable IDs.
4. Distinguish claims, direct observations, independent reproduction, and open questions.
5. Write `security-review.md` and cite supporting sources; leave unknown fields null.
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
