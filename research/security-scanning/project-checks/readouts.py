"""Check two visible published readouts and exact boundary cases with no external dependencies."""
from fractions import Fraction
import json
import math


def spread(u: tuple[int, int], v: tuple[int, int]) -> Fraction:
    """Squared sine between two nonzero planar rays with integer components."""
    ux, uy = u
    vx, vy = v
    q_product = (ux * ux + uy * uy) * (vx * vx + vy * vy)
    if q_product == 0:
        raise ValueError("spread is undefined for a zero ray")
    return Fraction((ux * vy - uy * vx) ** 2, q_product)


def compare():
    # RD-62 image: x in mm on the D scale. Test only the transcribed cursor position.
    cursor_mm = 125 * math.log10(4)
    assert abs(cursor_mm - 75.257) <= 0.0005
    # Exact geometric reference for a future reading of the quadrance/spread scales.
    # Rays (3, 0) and (3, 4) have cross product 12 and squared lengths 9 and 25.
    reference_spread = spread((3, 0), (3, 4))
    assert reference_spread == 1 - Fraction(9**2, 9 * 25)
    # THRUST image: metric tonnes, kN, sea-level standard gravity in m/s².
    twr = 6780 / ((22.84 + 140.44) * 9.80665)
    assert abs(twr - 4.23) <= 0.005
    return dict(rd62_cursor_mm=cursor_mm, geometry_reference_spread=str(reference_spread),
                thrust_initial_twr=twr, thrust_delta_v_verified=False)


if __name__ == '__main__':
    print(json.dumps(compare(), indent=2))
