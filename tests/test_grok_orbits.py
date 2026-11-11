"""Independent analytic invariants for the offline orbital reference."""
import math
import unittest
from research.grok_integration.orbits import circular_orbit, hohmann_transfer

class OrbitalTests(unittest.TestCase):
    def test_circular_speed_and_period(self):
        mu, r = 3.986004418e14, 7000000
        result = circular_orbit(mu, r)
        self.assertAlmostEqual(result["velocity_m_s"] ** 2 * r, mu, delta=mu*1e-12)
        self.assertAlmostEqual(result["period_s"] * result["velocity_m_s"], 2*math.pi*r, delta=1e-6)

    def test_same_orbit_zero_burn(self):
        result = hohmann_transfer(3.986004418e14, 7000000, 7000000)
        self.assertAlmostEqual(result["total_delta_v_m_s"], 0, places=8)

    def test_transfer_reversibility(self):
        up = hohmann_transfer(3.986004418e14, 7000000, 9000000)
        down = hohmann_transfer(3.986004418e14, 9000000, 7000000)
        self.assertAlmostEqual(up["total_delta_v_m_s"], down["total_delta_v_m_s"], places=8)
        self.assertAlmostEqual(up["transfer_time_s"], down["transfer_time_s"], places=8)

    def test_invalid_inputs(self):
        for values in [(0,1), (1,-1), (float("nan"),1), (1,float("inf"))]:
            with self.assertRaises(ValueError):
                circular_orbit(*values)
        with self.assertRaises(ValueError):
            hohmann_transfer(1, 0, 2)

if __name__ == "__main__":
    unittest.main()
