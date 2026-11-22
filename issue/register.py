import sqlite3


_SCHEMA = '''
CREATE TABLE IF NOT EXISTS issuance (
    piece_id TEXT PRIMARY KEY,
    station TEXT NOT NULL,
    revision_id INTEGER NOT NULL,
    format_version INTEGER NOT NULL,
    FOREIGN KEY (station, revision_id) REFERENCES calibration_revision(station, revision_id)
);
'''


class IssuanceRegister:
    def __init__(self, path):
        self._db = sqlite3.connect(path)
        try:
            self._db.execute('PRAGMA foreign_keys = ON')
            self._db.executescript(_SCHEMA)
        except sqlite3.Error:
            self._db.close()
            raise

    def close(self):
        self._db.close()

    def record_issuance(self, piece_id: str, station: str, revision_id: int, version: int) -> None:
        with self._db:
            self._db.execute(
                '''INSERT INTO issuance (piece_id, station, revision_id, format_version)
                   VALUES (?, ?, ?, ?) ON CONFLICT (piece_id) DO NOTHING''',
                (piece_id, station, revision_id, version),
            )
