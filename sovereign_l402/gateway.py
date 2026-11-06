"""Fail-closed HTTP 402 verification gateway prototype.

PROTOCOL NOTE: Sovereign402 is NOT L402, x402, proof of payment, ZK, or
blockchain settlement. Signed receipts must come from an independently trusted
verification process. No HTTP endpoint mints receipts.
"""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

MAX_BODY = 65536
MAX_RECEIPT = 4096

class Denied(ValueError):
    pass

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def validate_receipt(document, *, key, tenant, path, request_digest, now):
    if not isinstance(document, dict) or set(document) != {"claim", "mac"}:
        raise Denied("invalid receipt envelope")
    claim, mac = document["claim"], document["mac"]
    if not isinstance(claim, dict) or set(claim) != {"version", "tenant", "path", "body_sha256", "nonce", "expires", "settlement_id"}:
        raise Denied("invalid receipt fields")
    if claim["version"] != 1 or claim["tenant"] != tenant or claim["path"] != path:
        raise Denied("receipt audience mismatch")
    if claim["body_sha256"] != request_digest or not isinstance(claim["nonce"], str) or len(claim["nonce"]) < 24:
        raise Denied("payload mismatch")
    if not isinstance(claim["settlement_id"], str) or len(claim["settlement_id"]) < 12:
        raise Denied("missing settlement attestation")
    expires = claim["expires"]
    if type(expires) is not int or not now <= expires <= now + 300:
        raise Denied("expired or future-dated receipt")
    if not isinstance(mac, str) or len(mac) != 64:
        raise Denied("invalid authentication code")
    expected = hmac.new(key, canonical(claim), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, mac):
        raise Denied("invalid receipt signature")
    return claim

class NonceStore:
    """One-database atomic replay fence; not distributed consensus."""
    def __init__(self, path):
        self.path = str(Path(path))
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS redeemed (nonce TEXT PRIMARY KEY, tenant TEXT NOT NULL, settlement_id TEXT NOT NULL UNIQUE, ts INTEGER NOT NULL)")
    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("PRAGMA journal_mode=WAL")
            yield db
        finally:
            db.close()
    def redeem(self, claim, now):
        with self.connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute("INSERT INTO redeemed VALUES (?,?,?,?)", (claim["nonce"], claim["tenant"], claim["settlement_id"], now))
                db.commit()
            except sqlite3.IntegrityError as exc:
                db.rollback()
                raise Denied("replay or double-spend blocked") from exc

@dataclass(frozen=True)
class Settings:
    tenant: str
    key: bytes
    sqlite_path: str
    amount_micro_usdc: int = 100
    def __post_init__(self):
        if not self.tenant or len(self.key) < 32 or self.amount_micro_usdc <= 0:
            raise ValueError("invalid security configuration")

class Gateway:
    def __init__(self, settings):
        self.settings = settings
        self.nonces = NonceStore(settings.sqlite_path)
    def challenge(self):
        token = secrets.token_hex(24)
        return 402, {"WWW-Authenticate": 'Sovereign402 challenge="' + token + '"',
                     "X-Payment-Amount": str(self.settings.amount_micro_usdc),
                     "X-Payment-Unit": "micro-USDC",
                     "Cache-Control": "no-store"}, b'{"error":"verified settlement required","protocol":"Sovereign402-prototype"}'
    def handle(self, method, path, body, receipt_header):
        if method == "GET" and path == "/healthz":
            return 200, {"Content-Type":"application/json", "Cache-Control":"no-store"}, b'{"status":"ok","mode":"verification-only"}'
        if method != "POST" or path != "/v1/verify":
            return 404, {"Content-Type":"application/json"}, b'{"error":"not found"}'
        if len(body) > MAX_BODY:
            return 413, {"Content-Type":"application/json"}, b'{"error":"payload too large"}'
        if not receipt_header:
            return self.challenge()
        try:
            if len(receipt_header) > MAX_RECEIPT:
                raise Denied("receipt too large")
            doc = json.loads(receipt_header)
            now = int(time.time())
            claim = validate_receipt(doc, key=self.settings.key, tenant=self.settings.tenant,
                    path=path, request_digest=sha(body), now=now)
            self.nonces.redeem(claim, now)
        except (Denied, ValueError, TypeError, UnicodeError):
            return self.challenge()
        return 200, {"Content-Type":"application/json", "Cache-Control":"no-store"}, canonical({
            "status": "receipt_accepted", "payload_sha256": sha(body),
            "settlement_id": claim["settlement_id"],
            "caveat": "signed receipt validation is not a ZK proof of execution"
        })

def serve(settings, host="127.0.0.1", port=8402):
    gateway = Gateway(settings)
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self): self.dispatch()
        def do_GET(self): self.dispatch()
        def dispatch(self):
            length = self.headers.get("Content-Length", "0")
            try:
                n = int(length)
                if n < 0 or n > MAX_BODY: raise ValueError("invalid size")
                body = self.rfile.read(n)
                if len(body) != n: raise ValueError("truncated body")
                status, headers, data = gateway.handle(self.command, urlsplit(self.path).path, body,
                                                      self.headers.get("X-Sovereign-Receipt"))
            except ValueError:
                status, headers, data = 400, {"Content-Type":"application/json"}, b'{"error":"bad request"}'
            self.send_response(status)
            for k,v in headers.items(): self.send_header(k,v)
            self.send_header("Content-Length",str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    ThreadingHTTPServer((host,port), Handler).serve_forever()

if __name__ == "__main__":
    secret = os.environ.get("SOVEREIGN_RECEIPT_KEY", "")
    if len(secret) != 64:
        raise SystemExit("SOVEREIGN_RECEIPT_KEY must be a 64-character hex secret; refusing to start")
    try: key = bytes.fromhex(secret)
    except ValueError: raise SystemExit("invalid hex secret")
    serve(Settings(os.environ.get("SOVEREIGN_TENANT","sandbox"), key,
                   os.environ.get("SOVEREIGN_DB","./sovereign402.db")))
