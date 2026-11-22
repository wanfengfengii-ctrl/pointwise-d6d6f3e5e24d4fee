from dataclasses import dataclass
from fractions import Fraction

from analysis.pairing import Matrix
from analysis.pair_requests import PairReviewRequest
from reports.ledger import ParentReference


@dataclass(frozen=True)
class PairReviewResult:
    left: tuple[str, int]
    right: tuple[str, int]
    matrix: Matrix
    parents: tuple[ParentReference, ParentReference]


def _valid_matrix(matrix: object) -> bool:
    if type(matrix) is not tuple or len(matrix) != 3:
        return False
    if any(type(row) is not tuple or len(row) != 3 for row in matrix):
        return False
    return all(type(cell) is Fraction and cell >= 0 for row in matrix for cell in row)


def make_pair_result(request: PairReviewRequest, matrix: Matrix) -> PairReviewResult:
    if not _valid_matrix(matrix) or sum(cell for row in matrix for cell in row) != 1:
        raise ValueError('pair matrix must be exact, nonnegative and sum to one')
    parents = tuple(
        ParentReference(accepted.receipt_id, accepted.piece.station,
                        accepted.piece.revision_id, accepted.piece.piece_id)
        for accepted in request.left_request.selection.pieces
    )
    return PairReviewResult(request.left, request.right, matrix, parents)
