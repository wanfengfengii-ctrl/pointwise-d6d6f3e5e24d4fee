import json
import sqlite3
import unittest
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
from reports.ledger import ParentReference, ReportLedger


SAMPLE_PATH = Path(__file__).resolve().parents[1] / 'samples' / 'shift.json'


def make_batch(station, outlets, behaviors):
    states = []
    for index, (weight, probabilities) in enumerate(behaviors):
        states.append({
            'name': f'private-{station}-{index}', 'weight': weight,
            'records': [
                {'record': f'{station}-{index}-{name}', 'piece': f'material-{station}-{index}-{name}',
                 'outlet': name, 'probability': mass}
                for name, mass in probabilities.items()
            ],
        })
    return {'station': station, 'batch': f'fixture-{station}', 'outlets': outlets, 'states': states}


class LedgerCase(unittest.TestCase):
    def setUp(self):
        self.sample = json.loads(SAMPLE_PATH.read_text(encoding='utf-8'))
        self.work = Path(self.enterContext(TemporaryDirectory(prefix='retest-test-')))
        self.intake_path = self.work / 'intake.sqlite'
        self.reports_path = self.work / 'reports.sqlite'
        self.intake = self.enterContext(closing(IntakeStore(self.intake_path)))
        self.ledger = self.enterContext(closing(ReportLedger(self.reports_path)))

    def station_path(self, station):
        return self.work / f'{station}.sqlite'

    def issue_batch(self, batch):
        station = batch['station']
        path = self.station_path(station)
        with closing(CalibrationStore(path)) as source, closing(IssuanceRegister(path)) as register:
            revision_id = revise(source, batch)
            piece = freeze(source, register, station, revision_id)
        return revision_id, piece

    def accept_batch(self, batch):
        revision_id, piece = self.issue_batch(batch)
        station = batch['station']
        receipt_id = receive(self.intake, station, piece.data)
        return ParentReference(receipt_id, station, revision_id, piece.piece_id)

    def original_pair(self):
        return tuple(self.accept_batch(self.sample['original'][station]) for station in ('A', 'B'))

    def assess(self, parents, route_id, entry='A'):
        return review(self.intake, self.ledger, tuple(parent.receipt_id for parent in parents), entry, route_id)

    def signed_original(self):
        parents = self.original_pair()
        route_id = route(self.intake, self.sample['route'])
        return parents, route_id, self.assess(parents, route_id)

    def reopen_center(self):
        self.intake.close()
        self.ledger.close()
        self.intake = self.enterContext(closing(IntakeStore(self.intake_path)))
        self.ledger = self.enterContext(closing(ReportLedger(self.reports_path)))

    def counts(self, path, *tables):
        with closing(sqlite3.connect(path)) as db:
            return tuple(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in tables)
