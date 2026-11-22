import sqlite3
from dataclasses import dataclass
from fractions import Fraction


_SCHEMA = '''
CREATE TABLE IF NOT EXISTS report (
    report_id INTEGER PRIMARY KEY,
    entry TEXT NOT NULL,
    route_id INTEGER NOT NULL,
    pass_mass TEXT NOT NULL,
    reject_mass TEXT NOT NULL,
    unfinished_mass TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS report_parent (
    report_id INTEGER NOT NULL REFERENCES report(report_id),
    position INTEGER NOT NULL CHECK (position IN (0, 1)),
    receipt_id INTEGER NOT NULL,
    station TEXT NOT NULL,
    revision_id INTEGER NOT NULL,
    piece_id TEXT NOT NULL,
    PRIMARY KEY (report_id, position),
    UNIQUE (report_id, station)
);
'''


@dataclass(frozen=True)
class ParentReference:
    receipt_id: int
    station: str
    revision_id: int
    piece_id: str


@dataclass(frozen=True)
class ReportRecord:
    report_id: int
    entry: str
    route_id: int
    mass: tuple[Fraction, Fraction, Fraction]
    parents: tuple[ParentReference, ParentReference]


class ReportLedger:
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

    def commit_report(self, entry: str, route_id: int, mass: tuple[Fraction, Fraction, Fraction],
                      parents: tuple[ParentReference, ParentReference]) -> int:
        with self._db:
            inserted = self._db.execute(
                '''INSERT INTO report (entry, route_id, pass_mass, reject_mass, unfinished_mass)
                   VALUES (?, ?, ?, ?, ?)''', (entry, route_id, *map(str, mass)),
            )
            report_id = inserted.lastrowid
            for position, parent in enumerate(parents):
                self._db.execute(
                    '''INSERT INTO report_parent (report_id, position, receipt_id, station, revision_id, piece_id)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (report_id, position, parent.receipt_id, parent.station, parent.revision_id, parent.piece_id),
                )
        return report_id

    def load_report(self, report_id: int) -> ReportRecord | None:
        row = self._db.execute(
            'SELECT entry, route_id, pass_mass, reject_mass, unfinished_mass FROM report WHERE report_id = ?',
            (report_id,),
        ).fetchone()
        if row is None:
            return None
        parents = self._db.execute(
            '''SELECT position, receipt_id, station, revision_id, piece_id FROM report_parent
               WHERE report_id = ? ORDER BY position''', (report_id,),
        ).fetchall()
        if [parent[0] for parent in parents] != [0, 1]:
            raise sqlite3.DatabaseError('incomplete report parent snapshot')
        entry, route_id, passed, rejected, unfinished = row
        mass = (Fraction(passed), Fraction(rejected), Fraction(unfinished))
        first, second = (ParentReference(*parent[1:]) for parent in parents)
        return ReportRecord(report_id, entry, route_id, mass, (first, second))
