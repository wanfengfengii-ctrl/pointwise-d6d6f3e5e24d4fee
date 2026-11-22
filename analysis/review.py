from dataclasses import dataclass

from analysis.behavior import build_behavior
from analysis.requests import prepare_request
from analysis.result import make_review_result
from analysis.terminal import TerminalMass, solve_terminal
from intake.store import IntakeStore
from reports.ledger import ReportLedger
from reports.publish import publish_report


@dataclass(frozen=True)
class SignedReview:
    report_id: int
    mass: TerminalMass


def review(intake: IntakeStore, ledger: ReportLedger, receipt_ids: tuple[int, int] | list[int],
           entry: str, route_id: int) -> SignedReview:
    request = prepare_request(intake, receipt_ids, entry, route_id)
    mass = solve_terminal(build_behavior(request))
    result = make_review_result(request, mass)
    report_id = publish_report(ledger, result.entry, result.route_id, result.mass, result.parents)
    return SignedReview(report_id, result.mass)
