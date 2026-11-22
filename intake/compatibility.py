from dataclasses import dataclass

from intake.catalog import AcceptedPiece
from intake.routes import RouteSnapshot


@dataclass(frozen=True)
class CheckedSelection:
    pieces: tuple[AcceptedPiece, AcceptedPiece]
    entry: str
    route: RouteSnapshot


def check_selection(pieces: tuple[AcceptedPiece, AcceptedPiece], entry: str,
                    snapshot: RouteSnapshot) -> CheckedSelection:
    if len(pieces) != 2 or {accepted.piece.station for accepted in pieces} != set(snapshot.mappings):
        raise ValueError('select one receipt for each station in the fixed route')
    if type(entry) is not str or entry not in snapshot.mappings:
        raise ValueError('entry must be a station in the fixed route')
    for accepted in pieces:
        piece = accepted.piece
        missing = set(piece.body.outlets) - snapshot.mappings[piece.station].keys()
        if missing:
            raise ValueError(f'fixed route omits declared outlets at {piece.station}: {sorted(missing)}')
    return CheckedSelection(pieces, entry, snapshot)
