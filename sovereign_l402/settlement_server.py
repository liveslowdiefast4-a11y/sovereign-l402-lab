"""Local-only, testnet-restricted read-only settlement gateway HTTP server.

Never broadcasts transactions, custodies assets, or provisions wallets.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .gateway import MAX_BODY, Settings
from .evm_settlement import ExpectedPayment
from .rpc_client import ReadOnlyRPC
from .settlement_gateway import SettlementGateway

TESTNETS = frozenset({84532, 421614})

def build_gateway(env):
    # No default keys, addresses, RPC URLs or financial instruments.
    chain = int(env["SOVEREIGN_CHAIN_ID"])
    if chain not in TESTNETS:
        raise ValueError("only Base Sepolia / Arbitrum Sepolia are enabled")
    if env.get("SOVEREIGN_ENABLE_CUSTOMER_FUNDS"):
        raise ValueError("customer funds must remain disabled")
    if env.get("SOVEREIGN_ENABLE_LENDING") or env.get("SOVEREIGN_ENABLE_YIELD"):
        raise ValueError("lending/yield must remain disabled")
    secret = env["SOVEREIGN_RECEIPT_KEY"]
    if len(secret) != 64:
        raise ValueError("64-character receipt secret required")
    key = bytes.fromhex(secret)
    policy = ExpectedPayment(
        chain_id=chain, token=env["SOVEREIGN_TOKEN_ADDRESS"],
        sender=env["SOVEREIGN_SENDER_ADDRESS"],
        recipient=env["SOVEREIGN_RECIPIENT_ADDRESS"],
        amount_base_units=int(env["SOVEREIGN_AMOUNT_BASE_UNITS"]),
        min_confirmations=int(env.get("SOVEREIGN_MIN_CONFIRMATIONS", "12"))
    )
    return SettlementGateway(Settings(env["SOVEREIGN_TENANT"], key,
                                      env["SOVEREIGN_DB"]), policy,
                             ReadOnlyRPC(env["SOVEREIGN_RPC_URL"]))

def make_server(gateway, host="127.0.0.1", port=8403):
    if host not in ("127.0.0.1", "::1", "localhost"):
        raise ValueError("only loopback binding is permitted")
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self): self.dispatch()
        def do_POST(self): self.dispatch()
        def dispatch(self):
            try:
                value = self.headers.get("Content-Length", "0")
                n = int(value)
                if n < 0 or n > MAX_BODY:
                    raise ValueError("invalid body size")
                body = self.rfile.read(n)
                if len(body) != n: raise ValueError("truncated body")
                status, headers, data = gateway.handle(
                    self.command, urlsplit(self.path).path, body,
                    self.headers.get("X-Sovereign-Receipt"))
            except (TypeError, ValueError):
                status, headers, data = 400, {"Content-Type":"application/json"}, b'{"error":"bad request"}'
            self.send_response(status)
            for k,v in headers.items(): self.send_header(k,v)
            self.send_header("Content-Length",str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def log_message(self, *args):
            pass
    return ThreadingHTTPServer((host,port), Handler)

if __name__ == "__main__":
    gateway = build_gateway(os.environ)
    make_server(gateway).serve_forever()
