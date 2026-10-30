"""Hand arithmetic is the oracle; candidate agreement is a separate check."""

import unittest
from unittest.mock import patch

from commonwealth.study_v1.contracts import CONTRACTS, SLOT_YIELD, VALID_MEAN, reference
from commonwealth.study_v1.methods import aggregate


def exact(n, d=1):
    return {"status": "defined", "value": {"numerator": n, "denominator": d}}


class ReferenceTests(unittest.TestCase):
    def test_same_input_requires_fifteen_and_ten(self):
        self.assertEqual(reference([10, None, 20], [True, False, True], VALID_MEAN), exact(15))
        self.assertEqual(reference([10, None, 20], [True, False, True], SLOT_YIELD), exact(10))

    def test_signed_values_are_not_filtered(self):
        self.assertEqual(reference([-6, None, 12], [True, False, True], VALID_MEAN), exact(3))
        self.assertEqual(reference([-6, None, 12], [True, False, True], SLOT_YIELD), exact(2))

    def test_present_invalid_readings_still_count_for_yield(self):
        values, flags = [10, 999, None, 20], [True, False, False, True]
        self.assertEqual(reference(values, flags, VALID_MEAN), exact(15))
        self.assertEqual(reference(values, flags, SLOT_YIELD), exact(1029, 4))

    def test_empty_and_all_missing_have_explicit_distinct_results(self):
        undefined = {"status": "undefined", "value": None}
        for contract in CONTRACTS:
            self.assertEqual(reference([], [], contract), undefined)
        self.assertEqual(reference([None], [False], VALID_MEAN), undefined)
        self.assertEqual(reference([None], [False], SLOT_YIELD), exact(0))
        self.assertEqual(reference([5], [False], VALID_MEAN), undefined)

    def test_reference_never_calls_candidate(self):
        with patch("commonwealth.study_v1.methods.aggregate", side_effect=AssertionError):
            self.assertEqual(reference([10, None, 20], [True, False, True], VALID_MEAN), exact(15))

    def test_exact_large_integer_arithmetic(self):
        n = 10**100
        self.assertEqual(reference([n, None, n + 1], [True, False, True], VALID_MEAN), exact(2*n + 1, 2))

    def test_reject_malformed_inputs(self):
        for values, flags in [([None], [True]), ([1], []), ([True], [True]),
                              ([1.2], [True]), ([1], [1])]:
            for contract in CONTRACTS:
                with self.subTest(values=values, flags=flags, contract=contract):
                    with self.assertRaises(ValueError):
                        reference(values, flags, contract)
        with self.assertRaises(ValueError):
            reference([1], [True], "quality-flags-v1")

    def test_candidates_meet_only_their_respective_contract(self):
        values, flags = [10, None, 20], [True, False, True]
        self.assertEqual(aggregate(values, flags, "quality-stream"),
                         {"answer": exact(15), "inspections": 3})
        self.assertEqual(aggregate(values, flags, "zero-fill"),
                         {"answer": exact(10), "inspections": 3})
        self.assertEqual(aggregate(values, flags, "positive-only"),
                         {"answer": exact(15), "inspections": 6})


if __name__ == "__main__":
    unittest.main()
