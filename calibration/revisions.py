from dataclasses import dataclass

from calibration.outcomes import StateOutcome
from calibration.store import CalibrationStore


@dataclass(frozen=True)
class SealedRevision:
    station: str
    revision_id: int
    outlets: tuple[str, ...]
    states: tuple[StateOutcome, ...]


def seal_revision(store: CalibrationStore, station: str, batch_name: str,
                  outlets: tuple[str, ...], states: tuple[StateOutcome, ...], source_json: str) -> int:
    snapshot = {
        'outlets': list(outlets),
        'states': [
            {
                'name': state.name,
                'weight': str(state.weight),
                'outlets': {outlet: str(probability) for outlet, probability in state.outlets},
            }
            for state in states
        ],
    }
    return store.commit_revision(station, batch_name, source_json, snapshot)
