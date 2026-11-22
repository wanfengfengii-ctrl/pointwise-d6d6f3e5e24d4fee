import re
import sqlite3
from fractions import Fraction

from reports.ledger import ParentReference, ReportLedger


class PublicationError(RuntimeError):
    pass


def _valid_number(value: object) -> bool:
    return type(value) is int and 0 < value < 2**63


def _valid_parent(parent: object) -> bool:
    return (isinstance(parent, ParentReference)
            and _valid_number(parent.receipt_id)
            and _valid_number(parent.revision_id)
            and type(parent.station) is str
            and parent.station.isprintable()
            and parent.station == parent.station.strip()
            and parent.station not in ('pass', 'reject')
            and type(parent.piece_id) is str
            and re.fullmatch(r'[0-9a-f]{64}', parent.piece_id) is not None)


def _valid_parents(parents: object) -> bool:
    return (type(parents) is tuple and len(parents) == 2 and all(map(_valid_parent, parents))
            and len({parent.station for parent in parents}) == 2
            and len({parent.receipt_id for parent in parents}) == 2
            and len({parent.piece_id for parent in parents}) == 2)


def publish_report(ledger: ReportLedger, entry: str, route_id: int,
                   mass: tuple[Fraction, Fraction, Fraction],
                   parents: tuple[ParentReference, ParentReference]) -> int:
    if (not isinstance(mass, tuple) or len(mass) != 3
            or any(type(value) is not Fraction or value < 0 for value in mass) or sum(mass) != 1):
        raise ValueError('invalid final terminal masses')
    if not _valid_parents(parents):
        raise ValueError('a report requires two distinct station receipts')
    if type(entry) is not str or entry not in {parent.station for parent in parents} or not _valid_number(route_id):
        raise ValueError('invalid final entry or route reference')
    try:
        return ledger.commit_report(entry, route_id, mass, parents)
    except sqlite3.Error as exc:
        raise PublicationError('unable to commit report and both parents') from exc


def _valid_plan(plan: object) -> bool:
    return (type(plan) is tuple and len(plan) == 2 and type(plan[0]) is str
            and _valid_number(plan[1]))


def _valid_matrix(matrix: object) -> bool:
    return (type(matrix) is tuple and len(matrix) == 3
            and all(type(row) is tuple and len(row) == 3 for row in matrix)
            and all(type(cell) is Fraction and cell >= 0 for row in matrix for cell in row)
            and sum(cell for row in matrix for cell in row) == 1)


def publish_pair_report(ledger: ReportLedger, left: tuple[str, int], right: tuple[str, int],
                        matrix, parents: tuple[ParentReference, ParentReference]) -> int:
    if not _valid_plan(left) or not _valid_plan(right):
        raise ValueError('invalid final pair plan references')
    if not _valid_matrix(matrix):
        raise ValueError('invalid final pair matrix')
    if not _valid_parents(parents):
        raise ValueError('a report requires two distinct station receipts')
    if left[0] not in {parent.station for parent in parents} \
            or right[0] not in {parent.station for parent in parents}:
        raise ValueError('pair plans must name the report stations')
    try:
        return ledger.commit_pair_report(left, right, matrix, parents)
    except sqlite3.Error as exc:
        raise PublicationError('unable to commit pair report and both parents') from exc
