"""Attribution, status and incompatible totals must survive summarization."""

from copy import deepcopy
import unittest

from commonwealth.discernment_v1.source_records import STATUSES, describe, sum_comparable


def record(status):
    return {"subject": "Fictional Respondent", "scope": "Specified count A only", "status": status,
            "source": "https://example.invalid/record", "as_of": "2026-10-24"}


def amount(coverage, **changes):
    result = {"metric": "actual-recovery", "currency": "USD", "period": "2025",
              "amount_minor": 100, "coverage": coverage, "source": "https://example.invalid/record"}
    result.update(changes)
    return result


class SourceStatusTests(unittest.TestCase):
    def test_each_status_preserves_subject_scope_source_and_date(self):
        for status in STATUSES:
            source = record(status)
            result = describe(source)
            self.assertEqual({k: result[k] for k in source}, source)
            self.assertTrue(result["qualification"])

    def test_allegation_settlement_and_estimate_do_not_become_convictions(self):
        for status in ("allegation", "settlement", "estimate", "administrative-action", "deferred-prosecution", "improper-payment"):
            self.assertEqual(describe(record(status))["status"], status)
        self.assertIn("no finding of guilt", describe(record("allegation"))["qualification"])
        self.assertIn("not by itself", describe(record("settlement"))["qualification"])
        self.assertIn("intentional fraud is not established", describe(record("improper-payment"))["qualification"])

    def test_one_partys_plea_does_not_promote_anothers_allegation(self):
        first, second = record("guilty-plea"), record("allegation")
        second["subject"] = "Another Fictional Respondent"
        self.assertNotEqual(describe(first)["status"], describe(second)["status"])
        self.assertEqual(describe(second)["subject"], second["subject"])

    def test_unknown_status_is_refused_instead_of_assumed_true(self):
        with self.assertRaises(ValueError):
            describe(record("government-certified-fraudster"))

    def test_only_explicit_disjoint_comparable_amounts_are_summed(self):
        result = sum_comparable([amount(["case-A"]), amount(["case-B"], amount_minor=200)])
        self.assertEqual(result["amount_minor"], 300)
        self.assertEqual(result["metric"], "actual-recovery")
        self.assertIn("CURATOR_DECLARED", result["assurance"])

    def test_estimates_savings_orders_and_recoveries_cannot_be_mixed(self):
        for metric in ("alleged-loss", "estimated-loss", "annualized-savings", "restitution-ordered", "settlement-amount", "improper-payment"):
            with self.subTest(metric=metric), self.assertRaises(ValueError):
                sum_comparable([amount(["case-A"]), amount(["case-B"], metric=metric)])

    def test_overlap_missing_coverage_currency_period_and_float_are_refused(self):
        for changed in (amount(["case-A"]), amount([]), amount(["case-B"], currency="EUR"),
                        amount(["case-B"], period="2026"), amount(["case-B"], amount_minor=1.0),
                        amount(["case-B"], amount_minor=True)):
            original = deepcopy(changed)
            with self.assertRaises(ValueError):
                sum_comparable([amount(["case-A"]), changed])
            self.assertEqual(changed, original)


if __name__ == "__main__":
    unittest.main()
