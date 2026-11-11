"""Exact arithmetic reference fixtures; not a flight dynamics simulator."""
from fractions import Fraction

def constant_acceleration(distance, initial_velocity, acceleration, time):
    """Return (position, velocity) for one-dimensional constant acceleration."""
    x, v, a, t = map(Fraction, (distance, initial_velocity, acceleration, time))
    if t < 0:
        raise ValueError("time must be nonnegative")
    return x + v*t + a*t*t/2, v + a*t

def thrust_to_weight(thrust_newtons, mass_kg, gravity_m_s2):
    """Dimensionless T/W, with caller-supplied local gravity."""
    thrust, mass, gravity = map(Fraction, (thrust_newtons, mass_kg, gravity_m_s2))
    if thrust < 0 or mass <= 0 or gravity <= 0:
        raise ValueError("invalid physical inputs")
    return thrust / (mass * gravity)

def ideal_delta_v_exhaust_units(exhaust_velocity, initial_mass, final_mass):
    """Return exact mass ratio and exhaust velocity factor, not logarithmic delta-v.

    The actual ideal rocket delta-v is exhaust_velocity * ln(mass_ratio).
    Retaining the ratio avoids presenting an approximate logarithm as exact.
    """
    velocity, initial, final = map(Fraction, (exhaust_velocity, initial_mass, final_mass))
    if velocity <= 0 or final <= 0 or initial < final:
        raise ValueError("invalid rocket inputs")
    return initial / final, velocity
