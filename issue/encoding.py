import json
import re
from dataclasses import dataclass
from fractions import Fraction


FORMAT_VERSION = 1


@dataclass(frozen=True)
class PublicState:
    weight: Fraction
    probabilities: tuple[tuple[str, Fraction], ...]


@dataclass(frozen=True)
class PublicBody:
    outlets: tuple[str, ...]
    states: tuple[PublicState, ...]


@dataclass(frozen=True)
class PieceEnvelope:
    piece_id: str
    station: str
    revision_id: int
    version: int
    body: PublicBody


def _wire_body(body: PublicBody) -> dict:
    return {
        'outlets': list(body.outlets),
        'states': [
            {'weight': str(state.weight),
             'outlets': {name: str(mass) for name, mass in state.probabilities}}
            for state in body.states
        ],
    }


def _payload(station: str, revision_id: int, version: int, body: PublicBody) -> dict:
    return {'station': station, 'revision': revision_id, 'version': version, 'body': _wire_body(body)}


def _canonical(document: dict) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(',', ':')).encode('utf-8')


def encode_payload(station: str, revision_id: int, version: int, body: PublicBody) -> bytes:
    return _canonical(_payload(station, revision_id, version, body))


def encode_piece(envelope: PieceEnvelope) -> bytes:
    document = _payload(envelope.station, envelope.revision_id, envelope.version, envelope.body)
    document['piece_id'] = envelope.piece_id
    return _canonical(document)


def _unique_object(pairs):
    document = {}
    for key, value in pairs:
        if key in document:
            raise ValueError('duplicate piece field')
        document[key] = value
    return document


def _is_label(value: object) -> bool:
    return type(value) is str and value.isprintable() and value == value.strip()


def _fraction(token: object) -> Fraction:
    if type(token) is not str:
        raise ValueError('piece probabilities need exact fraction strings')
    try:
        mass = Fraction(token)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('malformed piece probability') from exc
    if not 0 <= mass <= 1 or str(mass) != token:
        raise ValueError('invalid or noncanonical piece probability')
    return mass


def _read_body(document: object) -> PublicBody:
    if type(document) is not dict or document.keys() != {'outlets', 'states'}:
        raise ValueError('invalid piece body')
    outlets = document['outlets']
    if type(outlets) is not list or not outlets or not all(_is_label(name) for name in outlets):
        raise ValueError('piece needs declared outlets')
    declared = set(outlets)
    if len(declared) != len(outlets):
        raise ValueError('duplicate piece outlet')
    rows = document['states']
    if type(rows) is not list or not 1 <= len(rows) <= 3:
        raise ValueError('piece needs one to three behavior rows')
    states = []
    for row in rows:
        if type(row) is not dict or row.keys() != {'weight', 'outlets'}:
            raise ValueError('invalid piece behavior row')
        probabilities = row['outlets']
        if type(probabilities) is not dict or probabilities.keys() - declared:
            raise ValueError('piece behavior refers to an undeclared outlet')
        distribution = tuple((name, _fraction(token)) for name, token in sorted(probabilities.items()))
        if sum(mass for _, mass in distribution) != 1:
            raise ValueError('piece outlet masses must sum to one')
        states.append(PublicState(_fraction(row['weight']), distribution))
    if sum(state.weight for state in states) != 1:
        raise ValueError('piece behavior weights must sum to one')
    return PublicBody(tuple(outlets), tuple(states))


def decode_piece(data: bytes) -> PieceEnvelope:
    if type(data) is not bytes or not data:
        raise ValueError('a station piece must contain bytes')
    try:
        document = json.loads(data.decode('utf-8'), object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError('invalid station piece encoding') from exc
    if type(document) is not dict or document.keys() != {'piece_id', 'station', 'revision', 'version', 'body'}:
        raise ValueError('invalid station piece envelope')
    identity, station = document['piece_id'], document['station']
    revision_id, version = document['revision'], document['version']
    if type(identity) is not str or not re.fullmatch(r'[0-9a-f]{64}', identity):
        raise ValueError('invalid fixed piece identity')
    if not _is_label(station) or station in ('pass', 'reject'):
        raise ValueError('invalid piece station')
    if type(revision_id) is not int or not 0 < revision_id < 2**63:
        raise ValueError('invalid piece source revision')
    if type(version) is not int or version != FORMAT_VERSION:
        raise ValueError('unsupported piece format')
    envelope = PieceEnvelope(identity, station, revision_id, version, _read_body(document['body']))
    if data != encode_piece(envelope):
        raise ValueError('piece must use canonical encoding')
    return envelope
