"""Durable, single-writer financial intent ledger for testnet ERC20 evidence.

Never controls a wallet or sends money. Contract execution is separate.
SQLite makes transitions atomic on one host; not multi-region consensus.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from .evm_settlement import verify_transfer, SettlementDenied

class FinanceDenied(ValueError):
    pass

def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()

@dataclass(frozen=True)
class Policy:
    chain_id: int
    token: str
    treasury: str
    fee_bps: int = 50
    max_single_amount: int = 1_000_000_000
    max_outstanding: int = 10_000_000_000
    max_payout: int = 1_000_000_000
    max_hourly_orders: int = 250
    def __post_init__(self):
        if type(self.chain_id) is not int or self.chain_id not in (84532, 421614):
            raise FinanceDenied("testnet only")
        from .evm_settlement import address
        address(self.token)
        address(self.treasury)
        if type(self.fee_bps) is not int or not 10 <= self.fee_bps <= 150:
            raise FinanceDenied("invalid fee rate")
        if any(type(x) is not int or x <= 0 or x > 2**63-1 for x in
               (self.max_single_amount, self.max_outstanding, self.max_payout, self.max_hourly_orders)):
            raise FinanceDenied("invalid risk limits")

class FinancialLedger:
    """Unique settlement evidence -> escrow liability -> approved payout intent.

    Funds still reside on-chain in an external contract or recipient wallet.
    Never claim this DB proves asset ownership, solvency or execution.
    """
    def __init__(self, path, policy):
        self.path = str(Path(path))
        self.policy = policy
        with self._db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
              id TEXT PRIMARY KEY,
              tenant TEXT NOT NULL,
              chain_id INTEGER NOT NULL,
              tx_hash TEXT NOT NULL,
              payer TEXT NOT NULL,
              provider TEXT NOT NULL,
              amount INTEGER NOT NULL,
              fee INTEGER NOT NULL,
              liability INTEGER NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('HELD','RELEASE_PENDING','REFUND_PENDING','RELEASED','REFUNDED')),
              decision_nonce TEXT,
              payout_tx TEXT,
              created INTEGER NOT NULL,
              UNIQUE(chain_id,tx_hash)
            );
            CREATE TABLE IF NOT EXISTS circuit_breaker (
              id INTEGER PRIMARY KEY CHECK(id=1),
              paused INTEGER NOT NULL CHECK(paused IN (0,1))
            );
            INSERT OR IGNORE INTO circuit_breaker VALUES(1,0);
            CREATE TABLE IF NOT EXISTS journal (
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              event TEXT NOT NULL,
              order_id TEXT NOT NULL,
              payload TEXT NOT NULL,
              prev_hash TEXT NOT NULL,
              entry_hash TEXT NOT NULL UNIQUE
            );
            """)
    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, isolation_level=None, timeout=15)
        try:
            db.execute("PRAGMA busy_timeout=15000")
            db.execute("PRAGMA journal_mode=WAL")
            yield db
        finally:
            db.close()
    def _event(self, db, event, order_id, details):
        last = db.execute("SELECT entry_hash FROM journal ORDER BY seq DESC LIMIT 1").fetchone()
        prev = last[0] if last else "0"*64
        payload = _canonical(details).decode()
        digest = hashlib.sha256(_canonical({"event":event,"order":order_id,"payload":payload,"previous":prev})).hexdigest()
        db.execute("INSERT INTO journal(event,order_id,payload,prev_hash,entry_hash) VALUES(?,?,?,?,?)",
                   (event,order_id,payload,prev,digest))
    def hold_verified(self, order_id, tenant, sender, recipient, provider, amount, tx_hash, rpc, confirmations=12):
        """Verify proof against pinned token/sender/recipient/amount before booking a liability.

        Pinned treasury is recipient. Caller must supply a TRUSTED RPC adapter and
        separately authenticate tenant, sender, provider and order from an approved mandate.
        """
        from .evm_settlement import ExpectedPayment, address
        if not isinstance(order_id,str) or not 8 <= len(order_id) <= 96 or not isinstance(tenant,str) or not 1 <= len(tenant) <= 96:
            raise FinanceDenied("invalid order reference")
        if type(amount) is not int or amount <= 0 or amount > 2**63 - 1:
            raise FinanceDenied("invalid integer base-unit amount")
        if address(recipient) != address(self.policy.treasury) or address(sender) == address(provider):
            raise FinanceDenied("mismatched recipient or self-payment")
        try:
            expected=ExpectedPayment(self.policy.chain_id,self.policy.token,sender,recipient,amount,confirmations)
            evidence=verify_transfer(rpc,tx_hash,expected)
        except (SettlementDenied, TypeError) as exc:
            raise FinanceDenied("settlement evidence rejected") from exc
        # Fee is floor in token base units; integers only, no floating point.
        fee=amount*self.policy.fee_bps//10000
        liability=amount-fee
        with self._db() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                self._check_breaker(db)
                if amount > self.policy.max_single_amount:
                    raise FinanceDenied("deposit amount exceeds cap")
                outstanding=db.execute("""SELECT COALESCE(SUM(amount),0) FROM orders
                  WHERE status IN ('HELD','RELEASE_PENDING','REFUND_PENDING')""").fetchone()[0]
                if outstanding + amount > self.policy.max_outstanding:
                    raise FinanceDenied("outstanding liability cap exceeded")
                hourly=db.execute("SELECT COUNT(*) FROM orders WHERE created>=?",(int(time.time())-3600,)).fetchone()[0]
                if hourly >= self.policy.max_hourly_orders:
                    raise FinanceDenied("deposit velocity cap exceeded")
                if db.execute("SELECT 1 FROM orders WHERE chain_id=? AND payout_tx=? LIMIT 1",
                              (self.policy.chain_id,tx_hash.lower())).fetchone():
                    raise FinanceDenied("settlement already used as payout")
                db.execute("""INSERT INTO orders
                  (id,tenant,chain_id,tx_hash,payer,provider,amount,fee,liability,status,created)
                  VALUES(?,?,?,?,?,?,?,?,?,'HELD',?)""",
                  (order_id,tenant,self.policy.chain_id,tx_hash.lower(),sender.lower(),provider.lower(),amount,fee,liability,int(time.time())))
                self._event(db,"HOLD",order_id,{"amount":amount,"fee":fee,"tx":tx_hash.lower(),"block":evidence["block_hash"]})
                db.commit()
            except sqlite3.IntegrityError as exc:
                db.rollback()
                raise FinanceDenied("duplicate order or settlement transaction") from exc
            except BaseException:
                db.rollback()
                raise
        return {"order_id":order_id,"status":"HELD","provider_liability":liability,"fee_liability":fee}

    def request_disbursement(self, order_id, actor, decision_nonce, refund=False):
        """Record a payer-authorized intent. Does not transmit funds."""
        from .evm_settlement import address
        if not isinstance(decision_nonce,str) or len(decision_nonce)<24 or len(decision_nonce)>128:
            raise FinanceDenied("invalid decision nonce")
        with self._db() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                row=db.execute("SELECT payer,status,amount,fee,liability,provider FROM orders WHERE id=?",(order_id,)).fetchone()
                if not row or row[1]!="HELD" or address(actor)!=row[0]:
                    raise FinanceDenied("payer authorization or open escrow required")
                self._check_breaker(db)
                status="REFUND_PENDING" if refund else "RELEASE_PENDING"
                amount_to_send=row[2] if refund else row[4]
                if amount_to_send > self.policy.max_payout:
                    raise FinanceDenied("payout cap exceeded")
                db.execute("UPDATE orders SET status=?,decision_nonce=? WHERE id=?",(status,decision_nonce,order_id))
                self._event(db,status,order_id,{"actor":actor.lower(),"decision_nonce":decision_nonce})
                db.commit()
                return {"order_id":order_id,"status":status,"recipient":row[0] if refund else row[5],
                        "amount":row[2] if refund else row[4], "treasury_fee":0 if refund else row[3]}
            except BaseException:
                db.rollback()
                raise

    def reconcile(self, order_id, payout_tx_hash, rpc, confirmations=12):
        """Confirm provider release or payer refund with real ERC20 RPC evidence.

        Treasury must have dispatched this transaction independently.
        Payout and deposit transactions cannot be reused on any order.
        """
        from .evm_settlement import ExpectedPayment, verify_transfer
        with self._db() as db:
            row=db.execute("""SELECT status,payer,provider,amount,liability,tx_hash
                                FROM orders WHERE id=?""",(order_id,)).fetchone()
        if not row or row[0] not in ("RELEASE_PENDING","REFUND_PENDING"):
            raise FinanceDenied("no pending payout")
        status,payer,provider,amount,liability,deposit_tx=row
        if not isinstance(payout_tx_hash,str) or payout_tx_hash.lower()==deposit_tx:
            raise FinanceDenied("payout cannot reuse deposit")
        destination=payer if status=="REFUND_PENDING" else provider
        due=amount if status=="REFUND_PENDING" else liability
        try:
            expected=ExpectedPayment(self.policy.chain_id,self.policy.token,self.policy.treasury,
                                     destination,due,confirmations)
            evidence=verify_transfer(rpc,payout_tx_hash,expected)
        except (SettlementDenied,TypeError) as exc:
            raise FinanceDenied("payout settlement not verified") from exc
        completed="REFUNDED" if status=="REFUND_PENDING" else "RELEASED"
        with self._db() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                self._check_breaker(db)
                current=db.execute("SELECT status FROM orders WHERE id=?",(order_id,)).fetchone()
                if not current or current[0]!=status:
                    raise FinanceDenied("payout state changed concurrently")
                collision=db.execute("""SELECT 1 FROM orders
                  WHERE chain_id=? AND (tx_hash=? OR payout_tx=?) LIMIT 1""",
                  (self.policy.chain_id,payout_tx_hash.lower(),payout_tx_hash.lower())).fetchone()
                if collision:
                    raise FinanceDenied("transaction already used")
                db.execute("UPDATE orders SET status=?, payout_tx=? WHERE id=?",
                           (completed,payout_tx_hash.lower(),order_id))
                self._event(db,completed,order_id,{"tx":payout_tx_hash.lower(),
                       "recipient":destination,"amount":due,"block":evidence["block_hash"]})
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return {"order_id":order_id,"status":completed,"settlement_tx":payout_tx_hash.lower(),
                "confirmed_amount":due}

    def _check_breaker(self, db):
        row=db.execute("SELECT paused FROM circuit_breaker WHERE id=1").fetchone()
        if not row or row[0]!=0:
            raise FinanceDenied("circuit breaker active")

    def emergency_pause(self):
        """Operator-only local control. Never expose this unauthenticated."""
        with self._db() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute("UPDATE circuit_breaker SET paused=1 WHERE id=1")
                self._event(db,"PAUSED","system",{"reason":"operator emergency stop"})
                db.commit()
            except BaseException:
                db.rollback()
                raise
    def is_paused(self):
        with self._db() as db:
            return db.execute("SELECT paused FROM circuit_breaker WHERE id=1").fetchone()[0]==1

    def snapshot(self):
        with self._db() as db:
            rows=db.execute("SELECT status,COUNT(*),COALESCE(SUM(amount),0),COALESCE(SUM(liability),0),COALESCE(SUM(fee),0) FROM orders GROUP BY status").fetchall()
            return [{"status":s,"orders":count,"gross":gross,"provider_liability":owed,"fee_liability":fees}
                    for s,count,gross,owed,fees in rows]
    def verify_journal(self):
        with self._db() as db:
            previous="0"*64
            for event,order,payload,prev,recorded in db.execute("SELECT event,order_id,payload,prev_hash,entry_hash FROM journal ORDER BY seq"):
                digest=hashlib.sha256(_canonical({"event":event,"order":order,"payload":payload,"previous":previous})).hexdigest()
                if prev!=previous or digest!=recorded:
                    return False
                previous=recorded
            return True
