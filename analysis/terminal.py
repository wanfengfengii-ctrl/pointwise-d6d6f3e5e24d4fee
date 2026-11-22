from fractions import Fraction
from typing import NamedTuple

from analysis.behavior import RouteBehavior, StationTransition


class TerminalMass(NamedTuple):
    passed: Fraction
    rejected: Fraction
    unfinished: Fraction


def _conditioned_terminal(entry: StationTransition, other: StationTransition) -> TerminalMass:
    round_trip = entry.forwarded * other.forwarded
    if round_trip == 1:
        return TerminalMass(Fraction(0), Fraction(0), Fraction(1))
    # The first two visits contribute the numerator. Repeating the pair gives a geometric series.
    stops_per_round = 1 - round_trip
    return TerminalMass(
        (entry.passed + entry.forwarded * other.passed) / stops_per_round,
        (entry.rejected + entry.forwarded * other.rejected) / stops_per_round,
        Fraction(0),
    )


def solve_terminal(behavior: RouteBehavior) -> TerminalMass:
    passed = rejected = unfinished = Fraction(0)
    for pair in behavior.pairs:
        conditional = _conditioned_terminal(pair.entry, pair.other)
        passed += pair.weight * conditional.passed
        rejected += pair.weight * conditional.rejected
        unfinished += pair.weight * conditional.unfinished
    return TerminalMass(passed, rejected, unfinished)
