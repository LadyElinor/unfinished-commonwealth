# Mathematics, engineering and programming inspection

The [catalogue](catalog.json) preserves the nine user-supplied IDs and links each observation to its source. The [earlier twelve-project register](../public-apps.json) records broader candidates and their evidence levels. The November directory counts describe the curator's coverage at that date. Ownership and source licensing are established separately for each application.

## Two readouts with enough information to check

In **RD-62 Rational-Duplex**, one physical cursor links the algebra and geometry faces. The published image puts the D-scale cursor at 75.257 mm with an index of 4.0000. A 125 mm logarithmic decade gives 125 × log₁₀(4) = 75.257499 mm, consistent at the displayed precision. A separate exact reference gives spread 16/25 for the rays (3, 0) and (3, 4). The nonzero-ray condition matters. No geometry-face output or exported CAD plate was measured. [RD-62 screenshot](https://www.promptshipped.com/shots/13805d200750.webp)

In **THRUST**, the Yardbird Mk.I configuration shows 22.84 tonnes dry, 140.44 tonnes of propellant and 6,780 kN of thrust. Using the displayed masses as the complete loaded configuration, standard gravity gives 4.234245 for liftoff thrust-to-weight, which rounds to the displayed 4.23. The displayed delta-v of 6.41 km/s needs additional propulsion and staging information for a comparable check. The heat and reuse-cost displays have no independent comparison here. Both the THRUST and RD-62 live homepages returned 403 during this inspection. [THRUST screenshot](https://www.promptshipped.com/shots/e2f70c8204be.webp)

Run the offline reference checks from this directory with `python readouts.py`. Only the two screenshot readouts are comparisons to app output. Mathematical controls are marked as references.

## A numerically comparable orbital experiment

Operation Galileo is hosted by its author. The linked HTML contains a numerical core separate from rendering. Jupiter and four prescribed, circularly orbiting moons accelerate the spacecraft. The integrator uses fourth-order Runge–Kutta and selects step size from local dynamical timescales. Mission logic also has explicit periapsis and apoapsis windows. [Author's project](https://caworman.com/operation-galileo/)

Download the [pinned public HTML](https://caworman.com/wp-content/uploads/2026/10/operation-galileo.html?v=20261030), then run `node galileo.mjs /path/to/operation-galileo.html`. The checker requires the recorded SHA-256 before loading the numerical core. The local comparison starts at 850,000 km from Jupiter's center, at the two-body circular speed, and coasts for one hour with all four moons active. A separate velocity-Verlet implementation computes the same forces without calling the game's force or stepping functions.

| Quantity | Observed |
|---|---:|
| Game integration steps | 26 |
| Endpoint difference against the 0.5 s reference | 0.000383 m |
| Reference endpoint change when halving the step from 1 s to 0.5 s | 0.001132 m |
| Velocity difference against the finer reference | 2.80 × 10⁻⁹ m/s |

The comparison measures agreement under the game's shared physical assumptions. The submillimetre endpoint difference is smaller than the change between the two reference step sizes. It cannot establish absolute accuracy at that precision. Flybys, burns, docking, probe deployment and agreement with observed moon ephemerides remain untested.

## Two repository changes

**Command review.** In Grok Build revision `2bdd1d6`, project trust controls whether project hook sources may load. The pre-tool dispatcher validates rewritten arguments and rebuilds its envelope. An upstream regression checks that the permission prompt contains the rewritten path. We read the implementation and tests. Unfinished Commonwealth now models an argument-bearing grant in its existing synthetic gate. The harness pins the reviewed JSON object, records a digest of the effective arguments at check time, and refuses mismatches. An exact fresh grant can authorize the changed arguments. Original parameterless calls remain supported. These local observations complement CORTAC's existing change-after-approval cases. [Dispatcher](https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-grok-shell/src/session/acp_session_impl/tool_calls.rs) · [Permission-prompt test](https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-grok-shell/src/session/acp_session_tests/pre_tool_use_decision_tests.rs)

**Applied simulation settings.** Physics Playground exposes gravity and contact controls. EEQW Grid distinguishes reported and reference state in its operator-console concept. In Lunar Weevil we found a concrete reason for that distinction. Every positive requested slope selected the same 25° MuJoCo fixture. The revised path applies the scenario's signed incline, gravity and timestep, reads the terrain normal from the engine, and hashes the resolved XML in the receipt. The regression reopens the compiled binary and checks the plane at five inclinations. [Official showcase](https://x.ai/news/grok-build-for-everyone) · [EEQW Grid](https://glow-meadow-flora-daisy.grok.me/) · [Lunar Weevil implementation](https://github.com/LadyElinor/PerhapsThisBugWillDo/pull/7)

## Findings carried forward

Chance Lab's deterministic 20-trial run remains a calibration case for explanations. The earlier Mars Colony inspection suggests checking resource balances across save and reload. Orrery makes display-scale compression explicit, a useful convention when comparing Galileo's rendered scene with numerical distances. The prompt scanner publishes heuristic categories, and the notebook exposes read and edit controls. Neither a favorable scanner score nor an enabled UI control can issue a Commonwealth grant. No scanner accuracy rate was measured. Harbor Run and PharmacoScope interface observations remain in the earlier register.
