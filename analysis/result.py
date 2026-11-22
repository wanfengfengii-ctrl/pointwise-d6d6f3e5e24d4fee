from dataclasses import dataclass
from fractions import Fraction

from analysis.requests import ReviewRequest
from analysis.terminal import TerminalMass
from reports.ledger import ParentReference


@dataclass(frozen=True)
class ReviewResult:
    entry: str
    route_id: int
    mass: TerminalMass
    parents: tuple[ParentReference, ParentReference]


def make_review_result(request: ReviewRequest, mass: TerminalMass) -> ReviewResult:
    if (not isinstance(mass, TerminalMass)
            or any(type(value) is not Fraction or value < 0 for value in mass)
            or sum(mass) != 1):
        raise ValueError('terminal masses must be exact, nonnegative and sum to one')
    selection = request.selection
    first, second = selection.pieces
    parents = tuple(
        ParentReference(accepted.receipt_id, accepted.piece.station,
                        accepted.piece.revision_id, accepted.piece.piece_id)
        for accepted in (first, second)
    )
    return ReviewResult(selection.entry, selection.route.route_id, mass, parents)
