# Grok-inspired engineering and authorization research tranche

Status: **offline, experimental, non-operational**. This tranche is not an integration with Grok-hosted applications and does not grant agents authority.

## Source-to-feature mapping

- Grok Build hooks: pre-tool policy checks and post-tool evidence inspired a separate **pure authorization decision** interface. The hook documentation explicitly warns that hook failures can fail open; this prototype denies on absent or malformed policy. Production enforcement requires an external, independently controlled gateway.
- THRUST: motivated a reference thrust-to-weight calculation and explicit distinction between exact mass ratio and approximate logarithmic delta-v. No THRUST code was copied and its model has not been validated.
- Operation Galileo: motivates future orbital mechanics benchmarks; **no orbital propagation is implemented here**.
- RD-62: motivates exact rational numerical fixtures; no RD-62 code was copied.
- Physics Playground / Mars Colony: motivate simulation benchmarks; **no collision engine, terrain model or habitat system is implemented here**.
- GhostShares: motivates publication approval and resource-scoped grants using synthetic data only.

## Run

```sh
python -m unittest tests.test_grok_integration -v
python -m unittest discover -s tests
```

## Boundaries

The policy function is a deterministic prototype, not a cryptographically authenticated approval service. Approval identifiers in test fixtures are untrusted strings; a production system needs signed approvals, identity verification, replay protection, durable event logs, separation of duties, and a gateway outside agent control. The robot_command action is **never connected to hardware**. No network requests, publication or command execution occur in this module.

## Next experiments

1. Integrate signed approvals with the existing authority-review contracts without fabricating missing records.
2. Add independently validated Kepler propagation and rocket-equation numerical benchmarks.
3. Add synthetic web publication fixtures and prove denial under missing policy, changed resource, and invalid approvals.
4. Compare test outcomes against independent checkers and preserve regressions.
5. Keep all new physical simulations disconnected from real control systems until separately reviewed.

## Sources

- https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/10-hooks.md
- https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/08-skills.md
- https://blog.claroc.io/ghostshares-grok-build-apps/
- https://thrust1.grok.me
- https://rd-1-rational-slide-rule.grok.me
- https://caworman.com
