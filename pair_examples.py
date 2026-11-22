import argparse
import json
from contextlib import closing
from copy import deepcopy
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis.review import review
from calibration.imports import revise
from calibration.store import CalibrationStore
from intake.receive import receive
from intake.routes import route
from intake.store import IntakeStore
from issue.freeze import freeze
from issue.register import IssuanceRegister
from reports.ledger import ParentReference, ReportLedger
from reports.lookup import read
from tests import make_batch


SAMPLE = Path(__file__).with_name("samples") / "shift.json"


def accept(work, intake, batch):
    station = batch["station"]
    path = work / f"{station}.sqlite"
    with closing(CalibrationStore(path)) as source, closing(IssuanceRegister(path)) as register:
        revision = revise(source, batch)
        piece = freeze(source, register, station, revision)
    return ParentReference(receive(intake, station, piece.data), station, revision, piece.piece_id)


def receipt_ids(parents):
    return tuple(parent.receipt_id for parent in parents)


def matrix(cells):
    return tuple(tuple(Fraction(cells.get((row, column), 0)) for column in range(3))
                 for row in range(3))


def sign_pair(submit, intake, ledger, name, parents, left, right, cells):
    expected = matrix(cells)
    signed = submit(intake, ledger, receipt_ids(parents), left, right)
    assert type(signed.matrix) is tuple and all(type(row) is tuple for row in signed.matrix), name
    assert all(type(mass) is Fraction for row in signed.matrix for mass in row), name
    assert signed.matrix == expected, (name, signed.matrix, expected)
    return name, signed.report_id, parents, left, right, expected


def check_pair(ledger, case):
    name, report_id, parents, left, right, expected = case
    saved = read(ledger, report_id)
    assert (saved.report_id, saved.parents, saved.left, saved.right, saved.matrix) == (
        report_id, parents, left, right, expected), name
    export = json.loads(read(ledger, report_id, export=True))
    assert export == {
        "report_id": report_id, "left": list(left), "right": list(right),
        "matrix": [[str(mass) for mass in row] for row in expected],
        "parents": [asdict(parent) for parent in parents],
    }, (name, export)
    return export


def expect_rejection(kind, submit, intake, ledger, parents, left, right):
    try:
        submit(intake, ledger, receipt_ids(parents), left, right)
    except kind:
        return
    raise AssertionError(f"expected {kind.__name__} for {left}, {right}")


def run(work, baseline=False):
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    report_path = work / "reports.sqlite"
    with closing(IntakeStore(work / "intake.sqlite")) as intake, closing(ReportLedger(report_path)) as ledger:
        fair_a = make_batch("A", ["ok", "send"], [(1, {"ok": "1/2", "send": "1/2"})])
        b = accept(work, intake, sample["original"]["B"])
        fair = (b, accept(work, intake, fair_a))
        fixed = (b, accept(work, intake, sample["original"]["A"]))
        regular = sample["route"]
        direct = ("A", route(intake, {**regular, "A": {"ok": "pass", "send": "reject"}}))
        flipped = ("A", route(intake, {**regular, "A": {"ok": "reject", "send": "pass"}}))
        returning = {"back": "A", "scrap": "A"}
        mixed = ("A", route(intake, {**regular, "B": returning}))
        closed_id = route(intake, {"A": {"ok": "B", "send": "B"}, "B": returning})
        regular_id = route(intake, regular)
        incomplete = deepcopy(regular)
        del incomplete["B"]["scrap"]
        incomplete_id = route(intake, incomplete)

        singles = [review(intake, ledger, receipt_ids(fair), *plan) for plan in (direct, flipped)]
        marginals = [[str(mass) for mass in signed.mass] for signed in singles]
        assert marginals == [["1/2", "1/2", "0"]] * 2, marginals
        if baseline:
            return {"single_route_marginals": marginals}

        from analysis.review import review_pair

        old_exports = {signed.report_id: read(ledger, signed.report_id, export=True) for signed in singles}
        thirds = {(0, 0): "1/3", (0, 1): "1/3", (1, 1): "1/3"}
        examples = [
            ("same", fair, direct, direct, {(0, 0): "1/2", (1, 1): "1/2"}),
            ("flip", fair, direct, flipped, {(0, 1): "1/2", (1, 0): "1/2"}),
            ("different_entries", fair, ("A", regular_id), ("B", regular_id), thirds),
            ("entries_swapped", fair, ("B", regular_id), ("A", regular_id),
             {(column, row): mass for (row, column), mass in thirds.items()}),
            ("single_loop", fixed, direct, mixed, {(0, 0): "1/2", (1, 2): "1/2"}),
            ("double_loop", fixed, ("A", closed_id), ("B", closed_id), {(2, 2): 1}),
        ]
        cases = [sign_pair(review_pair, intake, ledger, *example) for example in examples]
        expect_rejection(ValueError, review_pair, intake, ledger, fair, direct, ("A", incomplete_id))
        expect_rejection(LookupError, review_pair, intake, ledger, fair, direct, ("A", incomplete_id + 1))

        corrected = (b, accept(work, intake, sample["correction"]))
        cases.append(sign_pair(review_pair, intake, ledger, "corrected", corrected, direct, mixed,
                               {(0, 0): "1/2", (1, 0): "1/2"}))
        later = review(intake, ledger, receipt_ids(corrected), *mixed)
        assert later.mass == (Fraction(1), Fraction(0), Fraction(0))
        old_exports[later.report_id] = read(ledger, later.report_id, export=True)

    ids = list(old_exports) + [case[1] for case in cases]
    assert len(set(ids)) == len(cases) + 3, ids
    with closing(ReportLedger(report_path)) as ledger:
        for report_id, before in old_exports.items():
            assert read(ledger, report_id, export=True) == before, report_id
        return {case[0]: check_pair(ledger, case) for case in cases}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("baseline", "verify", "demo"))
    mode = parser.parse_args().mode
    if mode == "verify":
        from check_project import main as verify_original

        status = verify_original()
        if status:
            return status
    with TemporaryDirectory(prefix="retest-pair-") as directory:
        report = run(Path(directory), baseline=mode == "baseline")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
