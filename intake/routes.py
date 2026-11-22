from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from intake.store import IntakeStore


TERMINALS = frozenset({'pass', 'reject'})


@dataclass(frozen=True)
class RouteSnapshot:
    route_id: int
    mappings: Mapping[str, Mapping[str, str]]


def _is_label(label: object) -> bool:
    return type(label) is str and label.isprintable() and label == label.strip()


def route(store: IntakeStore, mappings: dict[str, dict[str, str]]) -> int:
    if type(mappings) is not dict or len(mappings) != 2:
        raise ValueError('a route needs exactly two station mappings')
    if any(not _is_label(station) or station in TERMINALS for station in mappings):
        raise ValueError('invalid route station label')
    stations = set(mappings)
    for station, outlets in mappings.items():
        if type(outlets) is not dict or not outlets:
            raise ValueError(f'{station} needs an outlet mapping')
        allowed = TERMINALS | (stations - {station})
        for outlet, destination in outlets.items():
            if not _is_label(outlet) or type(destination) is not str or destination not in allowed:
                raise ValueError(f'invalid outlet or destination at {station}')
    return store.save_route(mappings)


def get_route(store: IntakeStore, route_id: int) -> RouteSnapshot:
    if type(route_id) is not int or not 0 < route_id < 2**63:
        raise ValueError('invalid route number')
    mappings = store.load_route(route_id)
    if mappings is None:
        raise LookupError(f'no fixed route {route_id}')
    frozen = {station: MappingProxyType(outlets) for station, outlets in mappings.items()}
    return RouteSnapshot(route_id, MappingProxyType(frozen))
