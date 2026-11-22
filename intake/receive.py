from issue.encoding import decode_piece, encode_payload
from issue.identity import piece_id_for
from intake.store import IntakeStore


def receive(store: IntakeStore, expected_station: str, data: bytes) -> int:
    piece = decode_piece(data)
    payload = encode_payload(piece.station, piece.revision_id, piece.version, piece.body)
    if piece_id_for(payload) != piece.piece_id:
        raise ValueError('station piece content does not match its identity')
    if expected_station != piece.station:
        raise ValueError('station piece does not match the expected station')
    return store.accept_piece(piece.piece_id, piece.station, piece.revision_id, data)
