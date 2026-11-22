import json
import sqlite3
from contextlib import closing
from copy import deepcopy
from dataclasses import asdict
from fractions import Fraction as F

from analysis.review import review, review_pair
from intake.routes import route
from reports.lookup import read
from reports.publish import PublicationError
from tests import LedgerCase, make_batch


def matrix(cells):
    return tuple(tuple(F(cells.get((row, column), 0)) for column in range(3)) for row in range(3))


class PairReviewTests(LedgerCase):
    def setUp(self):
        super().setUp()
        self.fair_a = self.accept_batch(make_batch('A', ['ok', 'send'], [(1, {'ok': '1/2', 'send': '1/2'})]))
        self.fixed_a = self.accept_batch(self.sample['original']['A'])
        self.b = self.accept_batch(self.sample['original']['B'])
        regular = self.sample['route']
        self.direct = ('A', route(self.intake, {**regular, 'A': {'ok': 'pass', 'send': 'reject'}}))
        self.flipped = ('A', route(self.intake, {**regular, 'A': {'ok': 'reject', 'send': 'pass'}}))
        self.regular = ('A', route(self.intake, regular))
        self.mixed = ('A', route(self.intake, {**regular, 'B': {'back': 'A', 'scrap': 'A'}}))
        self.closed = ('A', route(self.intake, {'A': {'ok': 'B', 'send': 'B'},
                                               'B': {'back': 'A', 'scrap': 'A'}}))

    def sign(self, parents, left, right):
        return review_pair(self.intake, self.ledger,
                           tuple(parent.receipt_id for parent in parents), left, right)

    def assert_saved(self, parents, left, right, signed, expected):
        self.assertEqual(signed.matrix, expected)
        self.assertTrue(all(type(mass) is F for row in signed.matrix for mass in row))
        self.assertEqual(sum(mass for row in signed.matrix for mass in row), F(1))
        record = read(self.ledger, signed.report_id)
        self.assertEqual((record.report_id, record.left, record.right, record.matrix, record.parents),
                         (signed.report_id, left, right, expected, parents))
        export = json.loads(read(self.ledger, signed.report_id, export=True))
        self.assertEqual(export, {
            'report_id': signed.report_id, 'left': list(left), 'right': list(right),
            'matrix': [[str(mass) for mass in row] for row in expected],
            'parents': [asdict(parent) for parent in parents],
        })

    def test_same_plan_agrees_with_single(self):
        parents = (self.b, self.fair_a)
        signed = self.sign(parents, self.direct, self.direct)
        self.assert_saved(parents, self.direct, self.direct, signed,
                          matrix({(0, 0): '1/2', (1, 1): '1/2'}))
        single = review(self.intake, self.ledger, (self.b.receipt_id, self.fair_a.receipt_id),
                        *self.direct)
        self.assertEqual(tuple(sum(row) for row in signed.matrix), single.mass)

    def test_flipped_outlets_transpose(self):
        parents = (self.b, self.fair_a)
        signed = self.sign(parents, self.direct, self.flipped)
        self.assert_saved(parents, self.direct, self.flipped, signed,
                          matrix({(0, 1): '1/2', (1, 0): '1/2'}))

    def test_different_entries_and_swap(self):
        parents = (self.b, self.fair_a)
        left_from_a = ('A', self.regular[1])
        right_from_b = ('B', self.regular[1])
        forward = self.sign(parents, left_from_a, right_from_b)
        self.assert_saved(parents, left_from_a, right_from_b, forward, matrix({(0, 0): '1/3', (0, 1): '1/3', (1, 1): '1/3'}))
        swapped = self.sign(parents, right_from_b, left_from_a)
        self.assertEqual(swapped.matrix,
                         tuple(zip(*forward.matrix)))

    def test_single_and_double_loop(self):
        parents = (self.b, self.fixed_a)
        loop = self.sign(parents, self.direct, self.mixed)
        self.assert_saved(parents, self.direct, self.mixed, loop, matrix({(0, 0): '1/2', (1, 2): '1/2'}))
        closed = self.sign(parents, self.closed, ('B', self.closed[1]))
        self.assertEqual(closed.matrix, matrix({(2, 2): 1}))

    def test_parents_follow_request_order(self):
        parents = (self.fair_a, self.b)
        signed = self.sign(parents, self.direct, self.direct)
        self.assertEqual(signed.report_id, read(self.ledger, signed.report_id).report_id)
        self.assertEqual(read(self.ledger, signed.report_id).parents, parents)

    def test_shared_pair_reports_coexist_with_singles(self):
        single = review(self.intake, self.ledger, (self.b.receipt_id, self.fair_a.receipt_id),
                        *self.direct)
        pair = self.sign((self.b, self.fair_a), self.direct, self.direct)
        self.assertNotEqual(single.report_id, pair.report_id)
        self.reopen_center()
        self.assertEqual(read(self.ledger, single.report_id).mass, single.mass)
        self.assertEqual(read(self.ledger, pair.report_id).matrix, pair.matrix)

    def test_correction_does_not_change_signed_pair(self):
        parents = (self.b, self.fixed_a)
        signed = self.sign(parents, self.direct, self.mixed)
        before = read(self.ledger, signed.report_id, export=True)
        self.reopen_center()
        changed = self.accept_batch(self.sample['correction'])
        newer = self.sign((self.b, changed), self.direct, self.mixed)
        self.assertNotEqual(newer.report_id, signed.report_id)
        self.reopen_center()
        self.assertEqual(read(self.ledger, signed.report_id, export=True), before)
        self.assertEqual(read(self.ledger, signed.report_id).parents, parents)

    def test_invalid_and_missing_inputs(self):
        parents = (self.b, self.fair_a)
        missing_route = deepcopy(self.sample['route'])
        del missing_route['B']['scrap']
        partial = ('A', route(self.intake, missing_route))
        ids = (self.b.receipt_id, self.fair_a.receipt_id)
        for receipts, left, right, error in [
            (ids, self.direct, partial, ValueError),
            (ids, self.direct, ('A', partial[1] + 100), LookupError),
            ((ids[0],), self.direct, self.direct, ValueError),
            (ids, ('C', self.direct[1]), self.direct, ValueError),
            ((ids[0], 100), self.direct, self.direct, LookupError),
            (ids, self.direct, self.direct[:1], ValueError),
        ]:
            with self.subTest(receipts=receipts, left=left, right=right), self.assertRaises(error):
                review_pair(self.intake, self.ledger, receipts, left, right)
        self.assertEqual(self.counts(self.reports_path, 'report', 'report_parent'), (0, 0))

    def _install_trigger(self, sql):
        with closing(sqlite3.connect(self.reports_path)) as db, db:
            db.execute(sql)

    def test_pair_publish_rollback(self):
        signed = self.sign((self.b, self.fair_a), self.direct, self.direct)
        snapshot = read(self.ledger, signed.report_id, export=True)
        self._install_trigger('''CREATE TRIGGER reject_pair BEFORE INSERT ON pair_cell
                                 BEGIN SELECT RAISE(ABORT, 'pair write failed'); END''')
        with self.assertRaises(PublicationError) as error:
            self.sign((self.b, self.fair_a), self.direct, self.flipped)
        self.assertEqual(str(error.exception.__cause__), 'pair write failed')
        self.reopen_center()
        self.assertEqual(self.counts(self.reports_path, 'report', 'report_parent'), (1, 2))
        self.assertEqual(read(self.ledger, signed.report_id, export=True), snapshot)
        with self.assertRaises(LookupError):
            read(self.ledger, signed.report_id + 1)
