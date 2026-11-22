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


def publish_report(ledger: ReportLedger, entry: str, route_id: int,
                   mass: tuple[Fraction, Fraction, Fraction],
                   parents: tuple[ParentReference, ParentReference]) -> int:
    if (not isinstance(mass, tuple) or len(mass) != 3
            or any(type(value) is not Fraction or value < 0 for value in mass) or sum(mass) != 1):
        raise ValueError('invalid final terminal masses')
    if (type(parents) is not tuple or len(parents) != 2 or not all(map(_valid_parent, parents))
            or len({parent.station for parent in parents}) != 2
            or len({parent.receipt_id for parent in parents}) != 2
            or len({parent.piece_id for parent in parents}) != 2):
        raise ValueError('a report requires two distinct station receipts')
    if type(entry) is not str or entry not in {parent.station for parent in parents} or not _valid_number(route_id):
        raise ValueError('invalid final entry or route reference')
    try:
        return ledger.commit_report(entry, route_id, mass, parents)
    except sqlite3.Error as exc:
        raise PublicationError('unable to commit report and both parents') from exc
