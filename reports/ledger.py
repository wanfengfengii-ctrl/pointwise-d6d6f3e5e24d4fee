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

_PAIR_SCHEMA = '''
CREATE TABLE IF NOT EXISTS pair_report (
    report_id INTEGER PRIMARY KEY REFERENCES report(report_id),
    right_station TEXT NOT NULL,
    right_route_id INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS pair_cell (
    report_id INTEGER NOT NULL REFERENCES report(report_id),
    row INTEGER NOT NULL CHECK (row IN (0, 1, 2)),
    column INTEGER NOT NULL CHECK (column IN (0, 1, 2)),
    mass TEXT NOT NULL,
    PRIMARY KEY (report_id, row, column)
);
'''

Matrix = tuple[tuple[Fraction, Fraction, Fraction],
               tuple[Fraction, Fraction, Fraction],
               tuple[Fraction, Fraction, Fraction]]


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


@dataclass(frozen=True)
class PairReportRecord:
    report_id: int
    left: tuple[str, int]
    right: tuple[str, int]
    matrix: Matrix
    parents: tuple[ParentReference, ParentReference]


def _migrate(db: sqlite3.Connection) -> None:
    columns = {row[1] for row in db.execute('PRAGMA table_info(report)')}
    if 'kind' not in columns:
        db.execute("ALTER TABLE report ADD COLUMN kind TEXT NOT NULL DEFAULT 'single'")
    db.executescript(_PAIR_SCHEMA)


class ReportLedger:
    def __init__(self, path):
        self._db = sqlite3.connect(path)
        try:
            self._db.execute('PRAGMA foreign_keys = ON')
            self._db.executescript(_SCHEMA)
            _migrate(self._db)
        except sqlite3.Error:
            self._db.close()
            raise

    def close(self):
        self._db.close()

    def commit_report(self, entry: str, route_id: int, mass: tuple[Fraction, Fraction, Fraction],
                      parents: tuple[ParentReference, ParentReference]) -> int:
        with self._db:
            inserted = self._db.execute(
                '''INSERT INTO report (kind, entry, route_id, pass_mass, reject_mass, unfinished_mass)
                   VALUES ('single', ?, ?, ?, ?, ?)''', (entry, route_id, *map(str, mass)),
            )
            report_id = inserted.lastrowid
            self._insert_parents(report_id, parents)
        return report_id

    def commit_pair_report(self, left: tuple[str, int], right: tuple[str, int], matrix: Matrix,
                           parents: tuple[ParentReference, ParentReference]) -> int:
        row_totals = tuple(sum(matrix[row][column] for column in range(3)) for row in range(3))
        with self._db:
            inserted = self._db.execute(
                '''INSERT INTO report (kind, entry, route_id, pass_mass, reject_mass, unfinished_mass)
                   VALUES ('pair', ?, ?, ?, ?, ?)''',
                (left[0], left[1], *map(str, row_totals)),
            )
            report_id = inserted.lastrowid
            self._db.execute(
                'INSERT INTO pair_report (report_id, right_station, right_route_id) VALUES (?, ?, ?)',
                (report_id, right[0], right[1]),
            )
            for row in range(3):
                for column in range(3):
                    self._db.execute(
                        'INSERT INTO pair_cell (report_id, row, column, mass) VALUES (?, ?, ?, ?)',
                        (report_id, row, column, str(matrix[row][column])),
                    )
            self._insert_parents(report_id, parents)
        return report_id

    def _insert_parents(self, report_id: int, parents: tuple[ParentReference, ParentReference]) -> None:
        for position, parent in enumerate(parents):
            self._db.execute(
                '''INSERT INTO report_parent (report_id, position, receipt_id, station, revision_id, piece_id)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (report_id, position, parent.receipt_id, parent.station, parent.revision_id, parent.piece_id),
            )

    def _load_parents(self, report_id: int) -> tuple[ParentReference, ParentReference]:
        parents = self._db.execute(
            '''SELECT position, receipt_id, station, revision_id, piece_id FROM report_parent
               WHERE report_id = ? ORDER BY position''', (report_id,),
        ).fetchall()
        if [parent[0] for parent in parents] != [0, 1]:
            raise sqlite3.DatabaseError('incomplete report parent snapshot')
        first, second = (ParentReference(*parent[1:]) for parent in parents)
        return (first, second)

    def load_report(self, report_id: int) -> ReportRecord | PairReportRecord | None:
        row = self._db.execute(
            '''SELECT kind, entry, route_id, pass_mass, reject_mass, unfinished_mass
               FROM report WHERE report_id = ?''',
            (report_id,),
        ).fetchone()
        if row is None:
            return None
        kind, entry, route_id, passed, rejected, unfinished = row
        parents = self._load_parents(report_id)
        if kind == 'pair':
            right_row = self._db.execute(
                'SELECT right_station, right_route_id FROM pair_report WHERE report_id = ?',
                (report_id,),
            ).fetchone()
            if right_row is None:
                raise sqlite3.DatabaseError('incomplete pair report snapshot')
            cells = self._db.execute(
                'SELECT row, column, mass FROM pair_cell WHERE report_id = ? ORDER BY row, column',
                (report_id,),
            ).fetchall()
            if [(row_index, column) for row_index, column, _ in cells] != [
                    (row_index, column) for row_index in range(3) for column in range(3)]:
                raise sqlite3.DatabaseError('incomplete pair report matrix')
            matrix = tuple(
                tuple(Fraction(cells[row_index * 3 + column][2]) for column in range(3))
                for row_index in range(3)
            )
            return PairReportRecord(report_id, (entry, route_id),
                                    (right_row[0], right_row[1]), matrix, parents)
        if kind != 'single':
            raise sqlite3.DatabaseError('unknown report kind')
        mass = (Fraction(passed), Fraction(rejected), Fraction(unfinished))
        return ReportRecord(report_id, entry, route_id, mass, parents)
