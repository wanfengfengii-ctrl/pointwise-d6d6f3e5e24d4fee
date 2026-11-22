import json
from copy import deepcopy
from fractions import Fraction as F

from intake.routes import route
from reports.lookup import read
from tests import LedgerCase, make_batch


class ReviewTests(LedgerCase):
    def _direct_route(self, a):
        b = self.accept_batch(self.sample['original']['B'])
        mappings = {'A': {'p': 'pass', 'r': 'reject', 'x': 'B', 'unused': 'reject'},
                    'B': {'back': 'A', 'scrap': 'A'}}
        return (self.accept_batch(a), b), route(self.intake, mappings)

    def _assert_signed(self, parents, route_id, expected, entry='A'):
        signed = self.assess(parents, route_id, entry)
        self.assertEqual(signed.mass, expected)
        self.assertTrue(all(type(value) is F for value in signed.mass))
        self.assertEqual(sum(signed.mass), F(1))
        record = read(self.ledger, signed.report_id)
        self.assertEqual((record.mass, record.route_id, record.entry, record.parents),
                         (expected, route_id, entry, parents))
        return record

    def test_direct_termination(self):
        direct = {'p': '1/4', 'r': '3/4'}
        batch = make_batch('A', ['p', 'r'], [('1/3', direct), ('2/3', direct)])
        parents, route_id = self._direct_route(batch)
        self._assert_signed(parents, route_id, (F(1, 4), F(3, 4), F(0)))

    def test_exact_zero(self):
        batch = make_batch('A', ['p', 'r', 'x'], [
            ('1/2', {'p': '1/4', 'r': '3/4', 'x': 0}),
            ('1/2', {'p': '1/4', 'r': '3/4'}), (0, {'x': 1}),
        ])
        parents, route_id = self._direct_route(batch)
        self._assert_signed(parents, route_id, (F(1, 4), F(3, 4), F(0)))

    def _return_routes(self):
        original = route(self.intake, self.sample['route'])
        return_only = deepcopy(self.sample['route'])
        return_only['B']['scrap'] = 'A'
        return original, route(self.intake, return_only)

    def test_return_and_closed_loop(self):
        parents = self.original_pair()
        regular, closed = self._return_routes()
        self._assert_signed(parents, regular, (F(1, 2), F(1, 2), F(0)))
        self._assert_signed(parents, closed, (F(1, 2), F(0), F(1, 2)))

    def test_same_marginals(self):
        a, b = self.original_pair()
        changed = self.accept_batch(self.sample['correction'])
        regular, closed = self._return_routes()
        expected = [(F(1, 2), F(1, 2), F(0)), (F(2, 3), F(1, 3), F(0)),
                    (F(1, 2), F(0), F(1, 2)), (F(1), F(0), F(0))]
        inputs = [((a, b), regular), ((changed, b), regular), ((a, b), closed), ((changed, b), closed)]
        records = [self._assert_signed(parents, route_id, mass)
                   for (parents, route_id), mass in zip(inputs, expected)]
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': 'v6.same_marginals',
            'input': {'entry': 'A', 'route_ids': [route_id for _, route_id in inputs],
                      'a_receipts': [parents[0].receipt_id for parents, _ in inputs], 'b_receipt': b.receipt_id},
            'expected': [[str(value) for value in mass] for mass in expected],
            'actual': [[str(value) for value in record.mass] for record in records],
            'downstream_expected': [[parent.receipt_id for parent in parents] for parents, _ in inputs],
            'downstream_actual': [[parent.receipt_id for parent in record.parents] for record in records],
            'code_paths': ['issue/disclosure.py', 'analysis/behavior.py', 'analysis/terminal.py', 'reports/ledger.py'],
            'oracle': '按甲半数必过半数必送计质量。对照每轮可直接通过，按返送几何级数手算。',
        }, ensure_ascii=False, sort_keys=True))

    def test_independent_draws_and_entry_at_other_station(self):
        a = self.accept_batch(self.sample['original']['A'])
        b = self.accept_batch(make_batch('B', ['back', 'scrap'], [
            ('1/2', {'back': 1}), ('1/2', {'scrap': 1}),
        ]))
        route_id = route(self.intake, self.sample['route'])
        self._assert_signed((a, b), route_id, (F(1, 2), F(1, 4), F(1, 4)))
        self._assert_signed((a, b), route_id, (F(1, 4), F(1, 2), F(1, 4)), 'B')
