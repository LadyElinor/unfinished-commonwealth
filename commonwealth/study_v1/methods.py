"""Candidate methods. These do not import or call the reference evaluator."""

from fractions import Fraction

from .contracts import answer, validate

METHODS = ("quality-stream", "zero-fill", "positive-only")


def aggregate(values, valid, method):
    validate(values, valid)
    if method not in METHODS:
        raise ValueError("unknown study method")
    total = count = inspections = 0
    if method == "positive-only":
        selected = []
        for value in values:
            inspections += 1
            selected.append(value is not None and value > 0)
        flags = selected
    else:
        flags = valid
    for value, flag in zip(values, flags):
        inspections += 1
        if method == "zero-fill":
            total += 0 if value is None else value
            count += 1
        elif flag:
            total += value
            count += 1
    return {"answer": answer(Fraction(total, count) if count else None),
            "inspections": inspections}
