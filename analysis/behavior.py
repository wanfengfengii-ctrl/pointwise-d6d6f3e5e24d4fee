from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from typing import NamedTuple

from analysis.requests import ReviewRequest
from issue.encoding import PublicState


class StationTransition(NamedTuple):
    passed: Fraction
    rejected: Fraction
    forwarded: Fraction


@dataclass(frozen=True)
class WeightedPair:
    weight: Fraction
    entry: StationTransition
    other: StationTransition


@dataclass(frozen=True)
class RouteBehavior:
    pairs: tuple[WeightedPair, ...]


def _map_destinations(state: PublicState, destinations, other: str) -> StationTransition:
    totals = dict.fromkeys(('pass', 'reject', other), Fraction(0))
    for outlet, probability in state.probabilities:
        if probability:
            totals[destinations[outlet]] += probability
    return StationTransition(totals['pass'], totals['reject'], totals[other])


def build_behavior(request: ReviewRequest) -> RouteBehavior:
    selection = request.selection
    by_station = {accepted.piece.station: accepted.piece for accepted in selection.pieces}
    entry = selection.entry
    other, = by_station.keys() - {entry}
    entry_rows = [
        (state.weight, _map_destinations(state, selection.route.mappings[entry], other))
        for state in by_station[entry].body.states if state.weight
    ]
    other_rows = [
        (state.weight, _map_destinations(state, selection.route.mappings[other], entry))
        for state in by_station[other].body.states if state.weight
    ]
    # Each pair describes an entire workpiece trajectory, including every later return.
    return RouteBehavior(tuple(
        WeightedPair(entry_weight * other_weight, entry_step, other_step)
        for (entry_weight, entry_step), (other_weight, other_step) in product(entry_rows, other_rows)
    ))
