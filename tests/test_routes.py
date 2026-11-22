from copy import deepcopy
from fractions import Fraction as F

from analysis.review import review
from intake.routes import get_route, route
from reports.lookup import read
from tests import LedgerCase, make_batch


class RouteTests(LedgerCase):
    def test_unknown_destination(self):
        mappings = deepcopy(self.sample['route'])
        valid = route(self.intake, mappings)
        for destination in ('C', 'A', 'unknown-terminal'):
            mappings['A']['send'] = destination
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                route(self.intake, mappings)
        with self.assertRaises(ValueError):
            route(self.intake, {})
        self.assertEqual(self.counts(self.intake_path, 'fixed_route'), (1,))
        self.assertEqual(get_route(self.intake, valid).mappings, self.sample['route'])

    def test_station_scoped_outlets(self):
        a, b = (self.accept_batch(make_batch(station, ['X'], [(1, {'X': 1})])) for station in ('A', 'B'))
        route_id = route(self.intake, {'A': {'X': 'pass'}, 'B': {'X': 'reject'}})
        saved = get_route(self.intake, route_id)
        self.assertEqual((saved.mappings['A']['X'], saved.mappings['B']['X']), ('pass', 'reject'))
        for entry, expected in [('A', (F(1), F(0), F(0))), ('B', (F(0), F(1), F(0)))]:
            with self.subTest(entry=entry):
                signed = self.assess((b, a), route_id, entry=entry)
                record = read(self.ledger, signed.report_id)
                self.assertEqual(signed.mass, expected)
                self.assertEqual((record.entry, record.mass, record.parents), (entry, expected, (b, a)))

    def test_incompatible_selection(self):
        a, b = self.original_pair()
        missing = deepcopy(self.sample['route'])
        del missing['A']['ok']
        partial_route = route(self.intake, missing)
        exact_route = route(self.intake, self.sample['route'])
        a_id, b_id = a.receipt_id, b.receipt_id
        cases = [((a_id, b_id), 'A', partial_route, ValueError),
                 ((a_id, a_id), 'A', exact_route, ValueError),
                 ((a_id, b_id), 'C', exact_route, ValueError),
                 ((a_id,), 'A', exact_route, ValueError),
                 ((a_id, 100), 'A', exact_route, LookupError),
                 ((a_id, b_id), 'A', 100, LookupError)]
        for receipts, entry, route_id, error in cases:
            with self.subTest(receipts=receipts, entry=entry, route_id=route_id), self.assertRaises(error):
                review(self.intake, self.ledger, receipts, entry, route_id)
        self.assertEqual(self.counts(self.reports_path, 'report', 'report_parent'), (0, 0))
