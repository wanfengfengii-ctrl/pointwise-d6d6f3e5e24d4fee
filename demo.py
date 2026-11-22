import json
from contextlib import closing
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
from reports.ledger import ReportLedger
from reports.lookup import read


SAMPLE = Path(__file__).resolve().parent / 'samples' / 'shift.json'


def _issue(path, batch):
    with closing(CalibrationStore(path)) as calibration, closing(IssuanceRegister(path)) as register:
        revision_id = revise(calibration, batch)
        piece = freeze(calibration, register, batch['station'], revision_id)
    return revision_id, piece


def _parent(receipt_id, station, revision_id, piece):
    return {'receipt_id': receipt_id, 'station': station, 'revision_id': revision_id, 'piece_id': piece.piece_id}


def run(work: Path, sample: dict) -> dict:
    intake_path, report_path = work / 'intake.sqlite', work / 'reports.sqlite'
    rev_a, piece_a = _issue(work / 'A.sqlite', sample['original']['A'])
    rev_b, piece_b = _issue(work / 'B.sqlite', sample['original']['B'])
    with closing(IntakeStore(intake_path)) as intake, closing(ReportLedger(report_path)) as ledger:
        a = receive(intake, 'A', piece_a.data)
        b = receive(intake, 'B', piece_b.data)
        route_id = route(intake, sample['route'])
        first = review(intake, ledger, (a, b), 'A', route_id)
    new_rev, new_piece = _issue(work / 'A.sqlite', sample['correction'])
    with closing(IntakeStore(intake_path)) as intake, closing(ReportLedger(report_path)) as ledger:
        corrected = receive(intake, 'A', new_piece.data)
        second = review(intake, ledger, (corrected, b), 'A', route_id)
    with closing(ReportLedger(report_path)) as ledger:
        exports = [json.loads(read(ledger, signed.report_id, export=True)) for signed in (first, second)]
    expected = [['1/2', '1/2', '0'], ['2/3', '1/3', '0']]
    actual = [[str(value) for value in signed.mass] for signed in (first, second)]
    b_source = _parent(b, 'B', rev_b, piece_b)
    parents = [[_parent(a, 'A', rev_a, piece_a), b_source], [_parent(corrected, 'A', new_rev, new_piece), b_source]]
    expected_exports = [
        {'report_id': signed.report_id, 'entry': 'A', 'route_id': route_id, 'mass': mass, 'parents': references}
        for signed, mass, references in zip((first, second), expected, parents)
    ]
    if actual != expected or exports != expected_exports or first.report_id == second.report_id:
        raise RuntimeError(f'班次核对失败，实测概率为 {actual}，历史领取为 {exports}')
    return {
        'case_id': 'v7.read_and_export',
        'input': {'entry': 'A', 'route': sample['route'], 'receipts': [[a, b], [corrected, b]]},
        'expected': expected,
        'actual': actual,
        'downstream_expected': expected_exports,
        'downstream_actual': exports,
        'code_paths': ['calibration/imports.py', 'issue/freeze.py', 'intake/receive.py', 'analysis/review.py',
                       'analysis/terminal.py', 'reports/ledger.py', 'reports/lookup.py'],
        'oracle': '首班一半直通，另一半必送直至判废。勘误后每轮半数直通、四分之一判废、四分之一回到甲。',
    }


def main() -> None:
    sample = json.loads(SAMPLE.read_text(encoding='utf-8'))
    with TemporaryDirectory(prefix='retest-shift-') as directory:
        result = run(Path(directory), sample)
    print('POINTWISE_SCENARIO ' + json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
