import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from fractions import Fraction as F

from calibration.store import CalibrationStore
from intake.catalog import list_station_pieces
from intake.receive import receive
from intake.routes import get_route
from issue.freeze import freeze
from issue.register import IssuanceRegister
from reports.lookup import read
from reports.publish import PublicationError
from tests import LedgerCase


OLD_MASS = (F(1, 2), F(1, 2), F(0))
NEW_MASS = (F(2, 3), F(1, 3), F(0))


class ReportTests(LedgerCase):
    def _two_shifts(self):
        (a, b), route_id, old = self.signed_original()
        self.reopen_center()
        changed = self.accept_batch(self.sample['correction'])
        new = self.assess((changed, b), route_id)
        return (a, b, changed), route_id, old, new

    def test_revision_readback(self):
        (a, b, changed), route_id, old, new = self._two_shifts()
        self.assertNotEqual(old.report_id, new.report_id)
        self.assertEqual((old.mass, new.mass), (OLD_MASS, NEW_MASS))
        self.reopen_center()
        saved_old = read(self.ledger, old.report_id)
        saved_new = read(self.ledger, new.report_id)
        self.assertEqual((saved_old.mass, saved_old.parents, saved_old.route_id), (OLD_MASS, (a, b), route_id))
        self.assertEqual((saved_new.mass, saved_new.parents, saved_new.route_id), (NEW_MASS, (changed, b), route_id))

    def test_select_by_receipt(self):
        (a, b, changed), route_id, _, _ = self._two_shifts()
        path = self.station_path('A')
        with closing(CalibrationStore(path)) as source, closing(IssuanceRegister(path)) as register:
            old_piece = freeze(source, register, 'A', a.revision_id)
        self.assertEqual(old_piece.piece_id, a.piece_id)
        self.assertEqual(receive(self.intake, 'A', old_piece.data), a.receipt_id)
        self.assertEqual([row.receipt_id for row in list_station_pieces(self.intake, 'A')],
                         [a.receipt_id, changed.receipt_id])
        repeated = self.assess((b, a), route_id)
        record = read(self.ledger, repeated.report_id)
        self.assertEqual((repeated.mass, record.mass, record.parents), (OLD_MASS, OLD_MASS, (b, a)))

    def test_read_and_export(self):
        (a, b, changed), route_id, old, new = self._two_shifts()
        self.reopen_center()
        for signed, parents, mass in [(old, (a, b), OLD_MASS), (new, (changed, b), NEW_MASS)]:
            with self.subTest(report_id=signed.report_id):
                record = read(self.ledger, signed.report_id)
                self.assertEqual((record.entry, record.route_id, record.mass, record.parents),
                                 ('A', route_id, mass, parents))
                expected = {'report_id': signed.report_id, 'entry': 'A', 'route_id': route_id,
                            'mass': [str(value) for value in mass], 'parents': [asdict(parent) for parent in parents]}
                self.assertEqual(json.loads(read(self.ledger, signed.report_id, export=True)), expected)
        for export in (False, True):
            with self.assertRaises(LookupError):
                read(self.ledger, new.report_id + 10, export=export)

    def test_initialize_reopen(self):
        (a, b, changed), route_id, old, new = self._two_shifts()
        self.reopen_center()
        self.reopen_center()
        path = self.station_path('A')
        with closing(CalibrationStore(path)) as source, closing(IssuanceRegister(path)) as register:
            self.assertEqual(source.load_source('A', changed.revision_id), self.sample['correction'])
            self.assertEqual(source.load_source('A', a.revision_id), self.sample['original']['A'])
            self.assertEqual(freeze(source, register, 'A', changed.revision_id).piece_id, changed.piece_id)
        self.assertEqual(self.counts(path, 'calibration_revision', 'issuance'), (2, 2))
        self.assertEqual(self.counts(self.intake_path, 'station_receipt', 'fixed_route'), (3, 1))
        self.assertEqual(self.counts(self.reports_path, 'report', 'report_parent'), (2, 4))
        self.assertEqual(get_route(self.intake, route_id).mappings, self.sample['route'])
        self.assertEqual(read(self.ledger, old.report_id).parents, (a, b))
        self.assertEqual(read(self.ledger, new.report_id).parents, (changed, b))
        self.assertEqual(self.assess((changed, b), route_id).mass, NEW_MASS)

    def _install_trigger(self, sql):
        with closing(sqlite3.connect(self.reports_path)) as db, db:
            db.execute(sql)

    def test_publish_rollback(self):
        parents, route_id, old = self.signed_original()
        old_snapshot = read(self.ledger, old.report_id)
        self._install_trigger('''CREATE TRIGGER reject_report BEFORE INSERT ON report
                                 BEGIN SELECT RAISE(ABORT, 'report write failed'); END''')
        with self.assertRaises(PublicationError) as error:
            self.assess(parents, route_id)
        self.assertEqual(str(error.exception.__cause__), 'report write failed')
        self.reopen_center()
        self.assertEqual(self.counts(self.reports_path, 'report', 'report_parent'), (1, 2))
        self.assertEqual(read(self.ledger, old.report_id), old_snapshot)
        with self.assertRaises(LookupError):
            read(self.ledger, old.report_id + 1)

    def test_after_first_parent(self):
        (a, b), route_id, old = self.signed_original()
        old_snapshot = read(self.ledger, old.report_id)
        changed = self.accept_batch(self.sample['correction'])
        self._install_trigger('''CREATE TRIGGER reject_second_parent BEFORE INSERT ON report_parent
            WHEN NEW.position = 1
            BEGIN
                SELECT CASE WHEN EXISTS (
                    SELECT 1 FROM report_parent WHERE report_id = NEW.report_id AND position = 0
                ) THEN RAISE(ABORT, 'second parent rejected after first')
                  ELSE RAISE(ABORT, 'first parent missing at write') END;
            END''')
        with self.assertRaises(PublicationError) as error:
            self.assess((changed, b), route_id)
        self.assertEqual(str(error.exception.__cause__), 'second parent rejected after first')
        self.reopen_center()
        self.assertEqual(self.counts(self.reports_path, 'report', 'report_parent'), (1, 2))
        self.assertEqual(read(self.ledger, old.report_id), old_snapshot)
        self.assertEqual(old_snapshot.parents, (a, b))
        with self.assertRaises(LookupError):
            read(self.ledger, old.report_id + 1)
        self._install_trigger('DROP TRIGGER reject_second_parent')
        recovered = self.assess((changed, b), route_id)
        self.assertEqual(read(self.ledger, recovered.report_id).parents, (changed, b))
        self.assertEqual(recovered.mass, NEW_MASS)
