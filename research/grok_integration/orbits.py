"""Two-body circular orbit reference calculations, SI units only.

These are educational analytical references, not mission planning or flight control.
"""
from math import pi, sqrt, isfinite

def circular_orbit(mu_m3_s2: float, radius_m: float) -> dict:
    mu, radius = float(mu_m3_s2), float(radius_m)
    if not all(isfinite(v) and v > 0 for v in (mu, radius)):
        raise ValueError("mu and radius must be finite positive SI quantities")
    return {"velocity_m_s": sqrt(mu / radius),
            "period_s": 2 * pi * sqrt(radius ** 3 / mu)}

def hohmann_transfer(mu_m3_s2: float, r1_m: float, r2_m: float) -> dict:
    mu, r1, r2 = map(float, (mu_m3_s2, r1_m, r2_m))
    if not all(isfinite(v) and v > 0 for v in (mu, r1, r2)):
        raise ValueError("mu and radii must be finite positive SI quantities")
    a = (r1 + r2) / 2
    v1, v2 = sqrt(mu / r1), sqrt(mu / r2)
    transfer1 = sqrt(mu * (2 / r1 - 1 / a))
    transfer2 = sqrt(mu * (2 / r2 - 1 / a))
    return {"burn1_m_s": transfer1 - v1,
            "burn2_m_s": v2 - transfer2,
            "total_delta_v_m_s": abs(transfer1 - v1) + abs(v2 - transfer2),
            "transfer_time_s": pi * sqrt(a ** 3 / mu)}
