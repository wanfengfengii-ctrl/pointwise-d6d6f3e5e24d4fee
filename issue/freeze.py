from dataclasses import dataclass

from calibration.lookup import require_revision
from calibration.store import CalibrationStore
from issue.disclosure import build_public_body
from issue.encoding import FORMAT_VERSION, PieceEnvelope, encode_payload, encode_piece
from issue.identity import piece_id_for
from issue.register import IssuanceRegister


@dataclass(frozen=True)
class IssuedPiece:
    piece_id: str
    data: bytes


def freeze(store: CalibrationStore, register: IssuanceRegister,
           station: str, revision_id: int) -> IssuedPiece:
    revision = require_revision(store, station, revision_id)
    body = build_public_body(revision)
    identity = piece_id_for(encode_payload(station, revision_id, FORMAT_VERSION, body))
    envelope = PieceEnvelope(identity, station, revision_id, FORMAT_VERSION, body)
    data = encode_piece(envelope)
    register.record_issuance(identity, station, revision_id, FORMAT_VERSION)
    return IssuedPiece(identity, data)
