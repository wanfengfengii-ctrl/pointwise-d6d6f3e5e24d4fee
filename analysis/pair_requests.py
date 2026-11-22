from dataclasses import dataclass

from intake.catalog import get_receipt
from intake.compatibility import CheckedSelection, check_selection
from intake.routes import get_route
from intake.store import IntakeStore

from analysis.requests import ReviewRequest


@dataclass(frozen=True)
class PairReviewRequest:
    left_request: ReviewRequest
    right_request: ReviewRequest
    left: tuple[str, int]
    right: tuple[str, int]


def _receipt_pair(receipt_ids) -> tuple[int, int]:
    if type(receipt_ids) not in (tuple, list) or len(receipt_ids) != 2:
        raise ValueError('provide exactly two ordered receipt numbers')
    return receipt_ids[0], receipt_ids[1]


def _plan(plan) -> tuple[str, int]:
    if type(plan) not in (tuple, list) or len(plan) != 2:
        raise ValueError('each pair plan needs an entry station and a route number')
    return plan[0], plan[1]


def _prepare_side(store: IntakeStore, pieces, entry, route_id) -> ReviewRequest:
    snapshot = get_route(store, route_id)
    return ReviewRequest(check_selection(pieces, entry, snapshot))


def prepare_pair_request(store: IntakeStore, receipt_ids, left, right) -> PairReviewRequest:
    first, second = _receipt_pair(receipt_ids)
    left_entry, left_route = _plan(left)
    right_entry, right_route = _plan(right)
    pieces = (get_receipt(store, first), get_receipt(store, second))
    left_request = _prepare_side(store, pieces, left_entry, left_route)
    right_request = _prepare_side(store, pieces, right_entry, right_route)
    return PairReviewRequest(left_request, right_request, (left_entry, left_route),
                             (right_entry, right_route))
