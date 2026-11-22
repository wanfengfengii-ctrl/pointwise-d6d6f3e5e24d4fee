from dataclasses import dataclass
from fractions import Fraction

from analysis.behavior import _map_destinations
from analysis.requests import ReviewRequest
from analysis.terminal import TerminalMass, _conditioned_terminal
from issue.encoding import PublicState


# Row is the left route, column the right route.  Axes are pass, reject, unfinished.
Matrix = tuple[tuple[Fraction, Fraction, Fraction],
               tuple[Fraction, Fraction, Fraction],
               tuple[Fraction, Fraction, Fraction]]

_TERMINAL_INDEX = {'pass': 0, 'reject': 1}


def _other_station(stations: tuple[str, str], station: str) -> str:
    first, second = stations
    return second if station == first else first


def _round_outcome(mappings, entry: str, other: str, draws: dict[str, str]) -> str:
    """Outcome of one route inside one round of visits.

    A route visits its entry station first and only reaches the other station
    when the entry draw forwards there.  ``draws`` carries one shared outlet
    draw per station for this visit index, so both routes read the same entry.
    """
    destination = mappings[entry][draws[entry]]
    if destination in _TERMINAL_INDEX:
        return destination
    destination = mappings[other][draws[other]]
    return destination if destination in _TERMINAL_INDEX else 'F'


def _state_support(state: PublicState) -> tuple[tuple[str, Fraction], ...]:
    return tuple((outlet, mass) for outlet, mass in state.probabilities if mass)


def _round_table(left: ReviewRequest, right: ReviewRequest,
                 states: dict[str, PublicState],
                 stations: tuple[str, str]) -> dict[tuple[str, str], Fraction]:
    first, second = stations
    table: dict[tuple[str, str], Fraction] = {}
    for first_outlet, first_mass in _state_support(states[first]):
        for second_outlet, second_mass in _state_support(states[second]):
            draws = {first: first_outlet, second: second_outlet}
            key = (
                _round_outcome(left.selection.route.mappings, left.selection.entry,
                               _other_station(stations, left.selection.entry), draws),
                _round_outcome(right.selection.route.mappings, right.selection.entry,
                               _other_station(stations, right.selection.entry), draws),
            )
            table[key] = table.get(key, Fraction(0)) + first_mass * second_mass
    return table


def _route_continuation(states: dict[str, PublicState], request: ReviewRequest,
                        stations: tuple[str, str]) -> TerminalMass:
    selection = request.selection
    entry = selection.entry
    other = _other_station(stations, entry)
    entry_step = _map_destinations(states[entry], selection.route.mappings[entry], other)
    other_step = _map_destinations(states[other], selection.route.mappings[other], entry)
    return _conditioned_terminal(entry_step, other_step)


def _state_pair_matrix(left: ReviewRequest, right: ReviewRequest,
                       states: dict[str, PublicState],
                       stations: tuple[str, str]) -> Matrix:
    rounds = _round_table(left, right, states, stations)
    both_forward = rounds.get(('F', 'F'), Fraction(0))
    cells = [[Fraction(0), Fraction(0), Fraction(0)] for _ in range(3)]
    if both_forward == 1:
        # Every shared draw of every round forwards both routes: neither can stop.
        cells[2][2] = Fraction(1)
        return tuple(tuple(row) for row in cells)

    stops = 1 - both_forward
    left_tail = _route_continuation(states, left, stations)
    right_tail = _route_continuation(states, right, stations)

    for left_outcome in ('pass', 'reject'):
        for right_outcome in ('pass', 'reject'):
            cells[_TERMINAL_INDEX[left_outcome]][_TERMINAL_INDEX[right_outcome]] += (
                rounds.get((left_outcome, right_outcome), Fraction(0)) / stops)
    for left_outcome in ('pass', 'reject'):
        share = rounds.get((left_outcome, 'F'), Fraction(0)) / stops
        if share:
            row = _TERMINAL_INDEX[left_outcome]
            for column, mass in enumerate(right_tail):
                cells[row][column] += share * mass
    for right_outcome in ('pass', 'reject'):
        share = rounds.get(('F', right_outcome), Fraction(0)) / stops
        if share:
            column = _TERMINAL_INDEX[right_outcome]
            for row, mass in enumerate(left_tail):
                cells[row][column] += share * mass
    return tuple(tuple(row) for row in cells)


def solve_pair_matrix(left: ReviewRequest, right: ReviewRequest) -> Matrix:
    left_pieces = {accepted.piece.station: accepted.piece for accepted in left.selection.pieces}
    right_pieces = {accepted.piece.station: accepted.piece for accepted in right.selection.pieces}
    if set(left_pieces) != set(right_pieces) or len(left_pieces) != 2:
        raise ValueError('both routes must run over the same two stations')
    stations = tuple(sorted(left_pieces))
    for station in stations:
        if left_pieces[station].piece_id != right_pieces[station].piece_id:
            raise ValueError('both routes must use the same accepted piece per station')

    first, second = stations
    totals = [[Fraction(0), Fraction(0), Fraction(0)] for _ in range(3)]
    for first_state in left_pieces[first].body.states:
        if not first_state.weight:
            continue
        for second_state in left_pieces[second].body.states:
            if not second_state.weight:
                continue
            weight = first_state.weight * second_state.weight
            states = {first: first_state, second: second_state}
            contribution = _state_pair_matrix(left, right, states, stations)
            for row in range(3):
                for column in range(3):
                    totals[row][column] += weight * contribution[row][column]
    matrix = tuple(tuple(row) for row in totals)
    if (any(type(mass) is not Fraction or mass < 0 for row in matrix for mass in row)
            or sum(mass for row in matrix for mass in row) != 1):
        raise ValueError('pair matrix must be exact, nonnegative and sum to one')
    return matrix
