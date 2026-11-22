from dataclasses import dataclass

from issue.encoding import PieceEnvelope, decode_piece
from intake.store import IntakeStore


@dataclass(frozen=True)
class AcceptedPiece:
    receipt_id: int
    piece: PieceEnvelope


@dataclass(frozen=True)
class ReceiptSummary:
    receipt_id: int
    station: str
    revision_id: int
    piece_id: str


def get_receipt(store: IntakeStore, receipt_id: int) -> AcceptedPiece:
    if type(receipt_id) is not int or not 0 < receipt_id < 2**63:
        raise ValueError('invalid receipt number')
    data = store.load_receipt(receipt_id)
    if data is None:
        raise LookupError(f'no station receipt {receipt_id}')
    return AcceptedPiece(receipt_id, decode_piece(data))


def list_station_pieces(store: IntakeStore, station: str) -> tuple[ReceiptSummary, ...]:
    if type(station) is not str or not station.isprintable() or station != station.strip():
        raise ValueError('invalid station label')
    return tuple(ReceiptSummary(*row) for row in store.list_receipts(station))
