"""Strict payment-gated HTTP402 handler using externally verified EVM transfer evidence.

This module never signs receipts, broadcasts transactions, or custodies funds.
A payment is redeemable only after an authenticated JSON-RPC witness accepts it.
The existing HMAC receipt must be issued separately; no unsigned claim authorizes work.
"""
from .gateway import Gateway, Denied, MAX_BODY, MAX_RECEIPT, canonical, sha, validate_receipt
from .evm_settlement import verify_transfer, SettlementDenied
import json
import time

class SettlementGateway(Gateway):
    def __init__(self, settings, expected_payment, rpc):
        super().__init__(settings)
        self.expected_payment = expected_payment
        if not callable(rpc):
            raise ValueError("RPC transport is required")
        self.rpc = rpc

    def handle(self, method, path, body, receipt_header):
        if method == "GET" and path == "/healthz":
            return 200, {"Content-Type": "application/json",
                         "Cache-Control": "no-store"}, b'{"status":"ok","mode":"settlement-verification"}'
        if method != "POST" or path != "/v1/verify":
            return 404, {"Content-Type":"application/json"}, b'{"error":"not found"}'
        if len(body) > MAX_BODY:
            return 413, {"Content-Type":"application/json"}, b'{"error":"payload too large"}'
        if not receipt_header:
            return self.challenge()
        try:
            if len(receipt_header) > MAX_RECEIPT:
                raise Denied("receipt too large")
            document = json.loads(receipt_header)
            claim = validate_receipt(document, key=self.settings.key,
                                     tenant=self.settings.tenant, path=path,
                                     request_digest=sha(body), now=int(time.time()))
            evidence = verify_transfer(self.rpc, claim["settlement_id"], self.expected_payment)
            self.nonces.redeem(claim, int(time.time()))
        except (Denied, SettlementDenied, ValueError, TypeError, UnicodeError, OSError):
            return self.challenge()
        return 200, {"Content-Type":"application/json", "Cache-Control":"no-store"}, canonical({
            "status":"settlement_evidence_accepted", "payload_sha256":sha(body),
            "chain_id":evidence["chain_id"],"transaction_hash":evidence["transaction_hash"],
            "block_number":evidence["block_number"],
            "confirmations_at_check":evidence["confirmations_at_check"],
            "caveat":"RPC evidence is not an execution proof or a final settlement guarantee"
        })
