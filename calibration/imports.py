import json
from dataclasses import dataclass

from calibration.outcomes import StateOutcome, require_label, summarize_outcomes
from calibration.revisions import seal_revision
from calibration.store import CalibrationStore


@dataclass(frozen=True)
class CalibrationBatch:
    station: str
    batch_name: str
    outlets: tuple[str, ...]
    states: tuple[StateOutcome, ...]
    source_json: str


def parse_calibration_batch(batch: dict) -> CalibrationBatch:
    if type(batch) is not dict or batch.keys() != {'station', 'batch', 'outlets', 'states'}:
        raise ValueError('a calibration batch needs station, batch, outlets and states')
    station = require_label(batch['station'], 'station')
    if station in ('pass', 'reject'):
        raise ValueError('terminal labels are reserved')
    batch_name = require_label(batch['batch'], 'batch name')
    if type(batch['outlets']) is not list or not batch['outlets']:
        raise ValueError('declare at least one outlet')
    outlets = tuple(require_label(outlet, 'outlet') for outlet in batch['outlets'])
    if len(set(outlets)) != len(outlets):
        raise ValueError('outlet declarations must be unique')
    states = summarize_outcomes(outlets, batch['states'])
    return CalibrationBatch(station, batch_name, outlets, states, json.dumps(batch, sort_keys=True))


def revise(store: CalibrationStore, batch: dict) -> int:
    parsed = parse_calibration_batch(batch)
    return seal_revision(store, parsed.station, parsed.batch_name, parsed.outlets,
                         parsed.states, parsed.source_json)
