import json
import sqlite3


_SCHEMA = '''
CREATE TABLE IF NOT EXISTS station_receipt (
    receipt_id INTEGER PRIMARY KEY,
    piece_id TEXT NOT NULL UNIQUE,
    station TEXT NOT NULL,
    revision_id INTEGER NOT NULL,
    data BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS station_receipt_by_station ON station_receipt (station, receipt_id);
CREATE TABLE IF NOT EXISTS fixed_route (
    route_id INTEGER PRIMARY KEY,
    mappings_json TEXT NOT NULL
);
'''


class IntakeStore:
    def __init__(self, path):
        self._db = sqlite3.connect(path)
        try:
            self._db.executescript(_SCHEMA)
        except sqlite3.Error:
            self._db.close()
            raise

    def close(self):
        self._db.close()

    def accept_piece(self, piece_id: str, station: str, revision_id: int, data: bytes) -> int:
        with self._db:
            self._db.execute(
                '''INSERT INTO station_receipt (piece_id, station, revision_id, data)
                   VALUES (?, ?, ?, ?) ON CONFLICT (piece_id) DO NOTHING''',
                (piece_id, station, revision_id, data),
            )
            receipt_id, = self._db.execute(
                'SELECT receipt_id FROM station_receipt WHERE piece_id = ?', (piece_id,),
            ).fetchone()
        return receipt_id

    def load_receipt(self, receipt_id: int) -> bytes | None:
        row = self._db.execute('SELECT data FROM station_receipt WHERE receipt_id = ?', (receipt_id,)).fetchone()
        return None if row is None else row[0]

    def list_receipts(self, station: str) -> list[tuple[int, str, int, str]]:
        return self._db.execute(
            '''SELECT receipt_id, station, revision_id, piece_id FROM station_receipt
               WHERE station = ? ORDER BY receipt_id''', (station,),
        ).fetchall()

    def save_route(self, mappings: dict[str, dict[str, str]]) -> int:
        encoded = json.dumps(mappings, sort_keys=True)
        with self._db:
            inserted = self._db.execute('INSERT INTO fixed_route (mappings_json) VALUES (?)', (encoded,))
        return inserted.lastrowid

    def load_route(self, route_id: int) -> dict[str, dict[str, str]] | None:
        row = self._db.execute('SELECT mappings_json FROM fixed_route WHERE route_id = ?', (route_id,)).fetchone()
        return None if row is None else json.loads(row[0])
