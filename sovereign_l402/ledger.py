"""Dependency-free Lightning-themed atomic budget ledger research prototype.

This is NOT a wallet, payment processor, Bitcoin node interface or audited system.
Atomicity is per one SQLite database file and is not cross-datacenter consensus.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

class BudgetError(ValueError):
    pass

class BudgetLedger:
    def __init__(self, path: str):
        self.path = str(Path(path))
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS budgets (
              scope TEXT PRIMARY KEY,
              cap_msat INTEGER NOT NULL CHECK(cap_msat>=0),
              spent_msat INTEGER NOT NULL DEFAULT 0 CHECK(spent_msat>=0),
              reserved_msat INTEGER NOT NULL DEFAULT 0 CHECK(reserved_msat>=0),
              CHECK(spent_msat + reserved_msat <= cap_msat)
            );
            CREATE TABLE IF NOT EXISTS reservations (
              request_id TEXT PRIMARY KEY,
              scope TEXT NOT NULL REFERENCES budgets(scope),
              amount_msat INTEGER NOT NULL CHECK(amount_msat>0),
              status TEXT NOT NULL CHECK(status IN ('RESERVED','SETTLED','CANCELED'))
            );
            """)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=20, isolation_level=None)
        try:
            db.execute('PRAGMA busy_timeout=20000')
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA foreign_keys=ON')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create_budget(self, scope: str, cap_msat: int):
        if not scope or cap_msat < 0:
            raise BudgetError('invalid scope or cap')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT cap_msat FROM budgets WHERE scope=?', (scope,)).fetchone()
            if existing is not None and existing[0] != cap_msat:
                raise BudgetError('existing cap mismatch; migration required')
            db.execute('INSERT OR IGNORE INTO budgets(scope,cap_msat) VALUES (?,?)',
                       (scope,cap_msat))
            db.commit()

    def reserve(self, scope: str, request_id: str, amount_msat: int) -> bool:
        """True if new; False for exact idempotent replay; collisions forbidden."""
        if not scope or not request_id or amount_msat <= 0:
            raise BudgetError('invalid reservation')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT scope,amount_msat,status FROM reservations WHERE request_id=?',
                                  (request_id,)).fetchone()
            if existing is not None:
                if existing[:2] != (scope,amount_msat):
                    raise BudgetError('idempotency key collision')
                db.commit()
                return False
            changed = db.execute('''UPDATE budgets SET reserved_msat=reserved_msat+?
                WHERE scope=? AND cap_msat-spent_msat-reserved_msat>=?''',
                (amount_msat,scope,amount_msat)).rowcount
            if changed != 1:
                raise BudgetError('insufficient budget or unknown scope')
            db.execute('INSERT INTO reservations VALUES (?,?,?,?)',
                       (request_id,scope,amount_msat,'RESERVED'))
            db.commit()
            return True

    def finish(self, request_id: str, outcome: str) -> bool:
        """Atomic transition to SETTLED or CANCELED. These are synthetic statuses."""
        if outcome not in ('SETTLED','CANCELED'):
            raise BudgetError('invalid outcome')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            item = db.execute('SELECT scope,amount_msat,status FROM reservations WHERE request_id=?',
                              (request_id,)).fetchone()
            if item is None:
                raise BudgetError('unknown request')
            scope,amount,status=item
            if status == outcome:
                db.commit()
                return False
            if status != 'RESERVED':
                raise BudgetError('terminal transition forbidden')
            if outcome == 'SETTLED':
                db.execute('UPDATE budgets SET reserved_msat=reserved_msat-?, spent_msat=spent_msat+? WHERE scope=?',
                           (amount,amount,scope))
            else:
                db.execute('UPDATE budgets SET reserved_msat=reserved_msat-? WHERE scope=?',
                           (amount,scope))
            db.execute('UPDATE reservations SET status=? WHERE request_id=?',
                       (outcome,request_id))
            db.commit()
            return True

    def snapshot(self, scope: str):
        with self._connect() as db:
            row=db.execute('SELECT cap_msat,spent_msat,reserved_msat FROM budgets WHERE scope=?',
                           (scope,)).fetchone()
            if row is None:
                raise BudgetError('unknown scope')
            return dict(zip(('cap_msat','spent_msat','reserved_msat'),row))
