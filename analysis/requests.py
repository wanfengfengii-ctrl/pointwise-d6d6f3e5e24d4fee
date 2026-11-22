from dataclasses import dataclass

from intake.catalog import get_receipt
from intake.compatibility import CheckedSelection, check_selection
from intake.routes import get_route
from intake.store import IntakeStore


@dataclass(frozen=True)
class ReviewRequest:
    selection: CheckedSelection


def prepare_request(store: IntakeStore, receipt_ids: tuple[int, int] | list[int],
                    entry: str, route_id: int) -> ReviewRequest:
    if type(receipt_ids) not in (tuple, list) or len(receipt_ids) != 2:
        raise ValueError('provide exactly two ordered receipt numbers')
    first, second = receipt_ids
    pieces = (get_receipt(store, first), get_receipt(store, second))
    snapshot = get_route(store, route_id)
    return ReviewRequest(check_selection(pieces, entry, snapshot))
