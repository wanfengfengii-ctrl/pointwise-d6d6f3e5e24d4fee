import json
import sqlite3


_SCHEMA = '''
CREATE TABLE IF NOT EXISTS calibration_batch (
    batch_id INTEGER PRIMARY KEY,
    station TEXT NOT NULL,
    batch_name TEXT NOT NULL,
    source_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS calibration_revision (
    revision_id INTEGER PRIMARY KEY REFERENCES calibration_batch(batch_id),
    station TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    UNIQUE (station, revision_id)
);
'''


class CalibrationStore:
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

    def commit_revision(self, station: str, batch_name: str, source_json: str, snapshot: dict) -> int:
        snapshot_json = json.dumps(snapshot, sort_keys=True)
        with self._db:
            inserted = self._db.execute(
                'INSERT INTO calibration_batch (station, batch_name, source_json) VALUES (?, ?, ?)',
                (station, batch_name, source_json),
            )
            revision_id = inserted.lastrowid
            self._db.execute(
                'INSERT INTO calibration_revision (revision_id, station, snapshot_json) VALUES (?, ?, ?)',
                (revision_id, station, snapshot_json),
            )
        return revision_id

    def load_revision(self, station: str, revision_id: int) -> dict | None:
        row = self._db.execute(
            'SELECT snapshot_json FROM calibration_revision WHERE station = ? AND revision_id = ?',
            (station, revision_id),
        ).fetchone()
        return None if row is None else json.loads(row[0])

    def load_source(self, station: str, revision_id: int) -> dict | None:
        row = self._db.execute(
            '''SELECT b.source_json FROM calibration_revision AS r
               JOIN calibration_batch AS b ON b.batch_id = r.revision_id
               WHERE r.station = ? AND r.revision_id = ?''',
            (station, revision_id),
        ).fetchone()
        return None if row is None else json.loads(row[0])
