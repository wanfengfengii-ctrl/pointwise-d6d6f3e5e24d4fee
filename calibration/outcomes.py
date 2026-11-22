from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class StateOutcome:
    name: str
    weight: Fraction
    outlets: tuple[tuple[str, Fraction], ...]


def require_label(value: object, field: str) -> str:
    if type(value) is not str or not value.isprintable() or value != value.strip():
        raise ValueError(f'{field} must be nonempty printable text')
    return value


def _probability(value: object, field: str) -> Fraction:
    if type(value) not in (int, str):
        raise ValueError(f'{field} must be an exact rational')
    try:
        probability = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f'invalid {field}') from exc
    if not 0 <= probability <= 1:
        raise ValueError(f'{field} must lie between zero and one')
    return probability


def _count_outlets(records: list, outlets: tuple[str, ...], seen: set[str]):
    if type(records) is not list or not records:
        raise ValueError('each state needs calibration records')
    totals = dict.fromkeys(outlets, Fraction(0))
    for row in records:
        if type(row) is not dict or row.keys() != {'record', 'piece', 'outlet', 'probability'}:
            raise ValueError('invalid calibration record fields')
        record = require_label(row['record'], 'record ID')
        require_label(row['piece'], 'piece ID')
        outlet = require_label(row['outlet'], 'record outlet')
        if record in seen or outlet not in totals:
            raise ValueError('duplicate record ID or undeclared outlet')
        seen.add(record)
        totals[outlet] += _probability(row['probability'], 'outlet probability')
    if sum(totals.values()) != 1:
        raise ValueError('each state outlet distribution must sum to one')
    return tuple(totals.items())


def summarize_outcomes(outlets: tuple[str, ...], states: list) -> tuple[StateOutcome, ...]:
    if type(states) is not list or not 1 <= len(states) <= 3:
        raise ValueError('a station must have one to three states')
    seen_names = set()
    seen_records = set()
    outcomes = []
    for state in states:
        if type(state) is not dict or state.keys() != {'name', 'weight', 'records'}:
            raise ValueError('invalid state fields')
        name = require_label(state['name'], 'state name')
        if name in seen_names:
            raise ValueError('state names must be unique within a batch')
        seen_names.add(name)
        weight = _probability(state['weight'], 'state weight')
        distribution = _count_outlets(state['records'], outlets, seen_records)
        outcomes.append(StateOutcome(name, weight, distribution))
    if sum(outcome.weight for outcome in outcomes) != 1:
        raise ValueError('state weights must sum to one')
    return tuple(outcomes)
