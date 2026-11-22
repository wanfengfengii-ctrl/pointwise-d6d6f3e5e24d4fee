from dataclasses import dataclass

from analysis.behavior import build_behavior
from analysis.pair_requests import prepare_pair_request
from analysis.pair_result import make_pair_result
from analysis.pairing import Matrix, solve_pair_matrix
from analysis.requests import prepare_request
from analysis.result import make_review_result
from analysis.terminal import TerminalMass, solve_terminal
from intake.store import IntakeStore
from reports.ledger import ReportLedger
from reports.publish import publish_pair_report, publish_report


@dataclass(frozen=True)
class SignedReview:
    report_id: int
    mass: TerminalMass


@dataclass(frozen=True)
class SignedPairReview:
    report_id: int
    matrix: Matrix


def review(intake: IntakeStore, ledger: ReportLedger, receipt_ids: tuple[int, int] | list[int],
           entry: str, route_id: int) -> SignedReview:
    request = prepare_request(intake, receipt_ids, entry, route_id)
    mass = solve_terminal(build_behavior(request))
    result = make_review_result(request, mass)
    report_id = publish_report(ledger, result.entry, result.route_id, result.mass, result.parents)
    return SignedReview(report_id, result.mass)


def review_pair(intake: IntakeStore, ledger: ReportLedger, receipt_ids: tuple[int, int] | list[int],
                left, right) -> SignedPairReview:
    request = prepare_pair_request(intake, receipt_ids, left, right)
    matrix = solve_pair_matrix(request.left_request, request.right_request)
    result = make_pair_result(request, matrix)
    report_id = publish_pair_report(ledger, result.left, result.right, result.matrix, result.parents)
    return SignedPairReview(report_id, result.matrix)
