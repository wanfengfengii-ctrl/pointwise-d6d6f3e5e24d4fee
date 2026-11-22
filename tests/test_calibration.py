from contextlib import closing
from copy import deepcopy
from fractions import Fraction as F

from calibration.imports import revise
from calibration.lookup import require_revision
from calibration.store import CalibrationStore
from issue.freeze import freeze
from issue.register import IssuanceRegister
from tests import LedgerCase, make_batch


class CalibrationTests(LedgerCase):
    def _assert_rejected_correction(self, invalid):
        original = self.sample['original']['A']
        path = self.station_path('A')
        with closing(CalibrationStore(path)) as store, closing(IssuanceRegister(path)) as register:
            keep_id = revise(store, original)
            with self.assertRaises(ValueError):
                revise(store, invalid)
            self.assertEqual(store.load_source('A', keep_id), original)
            self.assertEqual(self.counts(path, 'calibration_batch', 'calibration_revision'), (1, 1))
            self.assertTrue(freeze(store, register, 'A', keep_id).data)

    def test_reject_weights(self):
        invalid = deepcopy(self.sample['correction'])
        invalid['states'][1]['weight'] = '1/4'
        self._assert_rejected_correction(invalid)

    def test_invalid_outcomes(self):
        invalid = deepcopy(self.sample['correction'])
        invalid['states'][1]['records'][0]['probability'] = '2/5'
        self._assert_rejected_correction(invalid)

    def test_unknown_revision(self):
        path = self.station_path('A')
        with closing(CalibrationStore(path)) as store, closing(IssuanceRegister(path)) as register:
            revision_id = revise(store, self.sample['original']['A'])
            for station, unknown in [('A', revision_id + 1), ('B', revision_id)]:
                with self.subTest(station=station, revision=unknown), self.assertRaises(LookupError):
                    freeze(store, register, station, unknown)
            self.assertEqual(self.counts(path, 'issuance'), (0,))
            self.assertEqual(require_revision(store, 'A', revision_id).station, 'A')

    def test_invalid_raw_values_and_shapes_do_not_seal(self):
        path = self.station_path('A')
        with closing(CalibrationStore(path)) as store:
            for invalid_value in (None, True, 0.5, '1/0', '-1/2'):
                invalid = deepcopy(self.sample['original']['A'])
                invalid['states'][0]['records'][0]['probability'] = invalid_value
                with self.subTest(value=invalid_value), self.assertRaises(ValueError):
                    revise(store, invalid)
            empty_records = deepcopy(self.sample['original']['A'])
            empty_records['states'][0]['records'].clear()
            undeclared = deepcopy(self.sample['original']['A'])
            undeclared['states'][0]['records'][0]['outlet'] = 'unlisted'
            for invalid in (empty_records, undeclared):
                with self.assertRaises(ValueError):
                    revise(store, invalid)
            self.assertEqual(self.counts(path, 'calibration_batch', 'calibration_revision'), (0, 0))

    def test_sparse_calibration_and_multiple_records_per_outlet(self):
        batch = make_batch('A', ['ok', 'send'], [(1, {'ok': '1/3'})])
        batch['states'][0]['records'].append(
            {'record': 'additional', 'piece': 'part-second', 'outlet': 'ok', 'probability': '2/3'},
        )
        with closing(CalibrationStore(self.station_path('A'))) as store:
            revision_id = revise(store, batch)
            state, = require_revision(store, 'A', revision_id).states
            self.assertEqual(dict(state.outlets), {'ok': F(1), 'send': F(0)})
            self.assertEqual(store.load_source('A', revision_id), batch)
