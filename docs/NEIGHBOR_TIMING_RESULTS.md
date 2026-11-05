# When listening changed the outcome

A neighbor's warning helped when it identified which batch needed the reserved slot, the primary job could afford the consultation, and the signal was informative. Even then, fewer misses did not necessarily mean less total delay.

## Matched reservation comparison

Each row below covers the same 16 cells with primary work due at slot 3. Eight peers are urgent. The coin policy and the policy that asks the peer each reserve slot 2 in eight cells and each misses eight primary deadlines. The coin policy never consults. The other policy pays one slot to consult in every cell.

| Warning reliability | Peer misses with the coin | Peer misses after asking | Total peer slots late with the coin | Total peer slots late after asking |
| --- | ---: | ---: | ---: | ---: |
| 2/4 | 4 | 4 | 4 | 8 |
| 3/4 | 4 | 2 | 4 | 4 |
| 4/4 | 4 | 0 | 4 | 0 |

A missed urgent batch under the coin policy finishes in slot 3, one slot late. If the warning understates urgency, consultation has already used slot 1. The primary then runs in slots 2 and 3 and the peer finishes in slot 4, two slots late. At 3/4 reliability, this explains how two fewer misses can leave total peer lateness unchanged. Across the 16 cells, primary completion times sum to 48 slots under the coin policy and 56 after asking.

## Deadline boundaries and controls

At the tight primary deadline of 2 and reliability 3/4, immediate start meets all 16 primary deadlines but misses all eight urgent peer deadlines. Always asking misses all 16 primary deadlines and two peer deadlines. At the ample primary deadline of 4, reserving without asking meets every deadline for both parties. These comparisons retain time-to-completion separately; meeting a deadline does not eliminate the cost of waiting.

The selective rule using a peer and the same rule using an instrument have identical completion times, misses, reservation counts and consultation costs in all 144 matched cells. The warning is stipulated to have the same reliability, timing and price in both conditions. This study identifies an information and scheduling effect. It cannot establish an advantage of a peer's testimony over another source of the same information.

## Reproduction and limits

The [design](NEIGHBOR_TIMING_DESIGN.md) was committed and pushed before scoring. The test exhausts seven fixed policies across 144 declared conditions each. Signal variants are equally weighted constructed cases, not independent empirical samples. There is no fitted policy, model call, secret evaluation set or exercise of authority. The operator can rewrite the scheduler, evidence, verifier and report together.

Run from the project root with a new destination:

```sh
python -m commonwealth.measurement_v1 neighbor .local/neighbor
```

The command writes all 1,008 case decisions and outcomes in `episodes.jsonl`, followed by `results.json` with the SHA-256 of those exact rows and separate totals in all 63 policy/deadline/reliability strata. CI compares the resulting file to the [published summary](../examples/neighbor-timing-results.json).
