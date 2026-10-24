"""Input contract and exact reference arithmetic, independent of candidates."""

from fractions import Fraction

VALID_MEAN = "valid-reading-mean-v1"
SLOT_YIELD = "scheduled-slot-yield-v1"
CONTRACTS = (VALID_MEAN, SLOT_YIELD)


def validate(values, valid):
    if len(values) != len(valid):
        raise ValueError("readings and validity flags must have equal lengths")
    if any(v is not None and type(v) is not int for v in values):
        raise ValueError("readings must be integers or null")
    if any(type(flag) is not bool for flag in valid):
        raise ValueError("validity flags must be booleans")
    if any(flag and v is None for v, flag in zip(values, valid)):
        raise ValueError("missing readings cannot be valid")


def answer(value):
    if value is None:
        return {"status": "undefined", "value": None}
    return {"status": "defined", "value": {
        "numerator": value.numerator, "denominator": value.denominator}}


def reference(values, valid, contract):
    """Definition as a sum of rational contributions, never candidate output."""
    validate(values, valid)
    if contract == VALID_MEAN:
        indices = [i for i, flag in enumerate(valid) if flag]
        terms = [Fraction(values[i], len(indices)) for i in indices]
        return answer(sum(terms, Fraction()) if indices else None)
    if contract == SLOT_YIELD:
        terms = [Fraction(v, len(values)) for v in values if v is not None]
        return answer(sum(terms, Fraction()) if values else None)
    raise ValueError("unknown study contract")
