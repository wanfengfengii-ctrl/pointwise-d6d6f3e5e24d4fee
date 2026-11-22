from fractions import Fraction

from calibration.outcomes import StateOutcome, require_label
from calibration.revisions import SealedRevision
from calibration.store import CalibrationStore


def require_revision(store: CalibrationStore, station: str, revision_id: int) -> SealedRevision:
    require_label(station, 'station')
    if type(revision_id) is not int or not 0 < revision_id < 2**63:
        raise ValueError('invalid revision number')
    snapshot = store.load_revision(station, revision_id)
    if snapshot is None:
        raise LookupError(f'no sealed revision {revision_id} at {station}')
    outlets = tuple(snapshot['outlets'])
    states = tuple(
        StateOutcome(row['name'], Fraction(row['weight']),
                     tuple((outlet, Fraction(row['outlets'][outlet])) for outlet in outlets))
        for row in snapshot['states']
    )
    return SealedRevision(station, revision_id, outlets, states)
