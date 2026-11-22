import json
from contextlib import closing
from copy import deepcopy
from fractions import Fraction

from calibration.store import CalibrationStore
from intake.catalog import get_receipt, list_station_pieces
from intake.receive import receive
from intake.routes import route
from issue.encoding import decode_piece
from issue.freeze import freeze
from issue.register import IssuanceRegister
from reports.lookup import read
from tests import LedgerCase


class StationPieceTests(LedgerCase):
    def test_freeze_receive(self):
        parents = self.original_pair()
        self.assertEqual([p.station for p in parents], ['A', 'B'])
        self.assertNotEqual(parents[0].receipt_id, parents[1].receipt_id)
        for parent in parents:
            listed, = list_station_pieces(self.intake, parent.station)
            loaded = get_receipt(self.intake, listed.receipt_id).piece
            self.assertEqual((loaded.station, loaded.revision_id, loaded.piece_id),
                             (parent.station, parent.revision_id, parent.piece_id))
            self.assertEqual(listed.revision_id, parent.revision_id)
            self.assertEqual(listed.piece_id, parent.piece_id)
            self.assertEqual(self.counts(self.station_path(parent.station), 'issuance'), (1,))

    def test_disclosure_scope(self):
        batch = self.sample['original']['A']
        revision, piece = self.issue_batch(batch)
        receipt = receive(self.intake, 'A', piece.data)
        self.assertEqual(get_receipt(self.intake, receipt).piece.revision_id, revision)
        b = self.accept_batch(self.sample['original']['B'])
        a, = list_station_pieces(self.intake, 'A')
        signed = self.assess((a, b), route(self.intake, self.sample['route']))
        export = read(self.ledger, signed.report_id, export=True)
        public = json.loads(piece.data)
        self.assertEqual(set(public), {'station', 'revision', 'piece_id', 'version', 'body'})
        self.assertEqual(public['version'], 1)
        private_values = [batch['batch']]
        for state in batch['states']:
            private_values.append(state['name'])
            for record in state['records']:
                private_values.extend((record['record'], record['piece']))
        for value in private_values:
            self.assertNotIn(value, piece.data.decode())
            self.assertNotIn(value, export)
        self.assertEqual(json.loads(export)['parents'][0]['piece_id'], piece.piece_id)
        with closing(CalibrationStore(self.station_path('A'))) as source:
            self.assertEqual(source.load_source('A', revision), batch)

    def test_behavior_distinction(self):
        original = self.sample['original']['A']
        correction = self.sample['correction']

        def marginal(batch, outlet):
            return sum(Fraction(row['weight']) * Fraction(record['probability'])
                       for row in batch['states'] for record in row['records'] if record['outlet'] == outlet)

        for outlet in ('ok', 'send'):
            self.assertEqual(marginal(original, outlet), Fraction(1, 2))
            self.assertEqual(marginal(correction, outlet), Fraction(1, 2))
        _, first = self.issue_batch(original)
        _, second = self.issue_batch(correction)
        a = receive(self.intake, 'A', first.data)
        b = receive(self.intake, 'A', second.data)
        self.assertNotEqual(get_receipt(self.intake, a).piece.body, get_receipt(self.intake, b).piece.body)

    def test_revision_identity(self):
        original = self.sample['original']['A']
        identical_behavior = deepcopy(original)
        identical_behavior['batch'] = 'A-new-source-same-behavior'
        old_revision, first = self.issue_batch(original)
        new_revision, second = self.issue_batch(identical_behavior)
        self.assertEqual(decode_piece(first.data).body, decode_piece(second.data).body)
        self.assertNotEqual(first.piece_id, second.piece_id)
        old_receipt = receive(self.intake, 'A', first.data)
        new_receipt = receive(self.intake, 'A', second.data)
        self.assertNotEqual(old_receipt, new_receipt)
        self.assertEqual(receive(self.intake, 'A', first.data), old_receipt)
        self.assertEqual([(row.receipt_id, row.revision_id) for row in list_station_pieces(self.intake, 'A')],
                         [(old_receipt, old_revision), (new_receipt, new_revision)])
        path = self.station_path('A')
        with closing(CalibrationStore(path)) as source, closing(IssuanceRegister(path)) as register:
            self.assertEqual(freeze(source, register, 'A', old_revision), first)
        self.assertEqual(self.counts(path, 'issuance'), (2,))

    def test_wrong_station(self):
        _, piece = self.issue_batch(self.sample['original']['B'])
        with self.assertRaises(ValueError):
            receive(self.intake, 'A', piece.data)
        self.assertEqual(self.counts(self.intake_path, 'station_receipt'), (0,))
        valid = receive(self.intake, 'B', piece.data)
        with self.assertRaises(ValueError):
            receive(self.intake, 'A', piece.data)
        self.assertEqual(list_station_pieces(self.intake, 'A'), ())
        self.assertEqual([row.receipt_id for row in list_station_pieces(self.intake, 'B')], [valid])

    def test_corrupt_body(self):
        _, first = self.issue_batch(self.sample['original']['A'])
        _, second = self.issue_batch(self.sample['correction'])
        tampered = json.loads(first.data)
        tampered['body'] = json.loads(second.data)['body']
        encoded = json.dumps(tampered, sort_keys=True, separators=(',', ':')).encode()
        self.assertEqual(decode_piece(encoded).piece_id, first.piece_id)
        with self.assertRaisesRegex(ValueError, 'content does not match'):
            receive(self.intake, 'A', encoded)
        for malformed in (b'', b'{broken', first.data + b'\n'):
            with self.subTest(value=malformed), self.assertRaises(ValueError):
                receive(self.intake, 'A', malformed)
        self.assertEqual(self.counts(self.intake_path, 'station_receipt'), (0,))
