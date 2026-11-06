"""Read-only authenticated HTTPS JSON-RPC adapter for EVM settlement evidence.

No signing, wallet custody, or transaction broadcasting.
"""
import json
import ssl
import urllib.request
from urllib.parse import urlsplit
from .evm_settlement import SettlementDenied

ALLOWED_METHODS = frozenset({
    "eth_chainId", "eth_blockNumber", "eth_getTransactionReceipt", "eth_getBlockByNumber"
})

class ReadOnlyRPC:
    def __init__(self, endpoint, timeout=8):
        p = urlsplit(endpoint)
        if p.scheme != "https" or not p.hostname or p.username or p.password or p.fragment:
            raise SettlementDenied("RPC endpoint must be authenticated HTTPS")
        if not (0 < timeout <= 30):
            raise SettlementDenied("unsafe RPC timeout")
        self.endpoint = endpoint
        self.timeout = timeout
        self.context = ssl.create_default_context()

    def __call__(self, method, params):
        if method not in ALLOWED_METHODS or not isinstance(params, list):
            raise SettlementDenied("RPC method is not read-only/allowed")
        payload = json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode()
        req = urllib.request.Request(self.endpoint, data=payload,
                                     headers={"Content-Type":"application/json",
                                              "Accept":"application/json"},
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.context) as resp:
                if resp.status != 200:
                    raise SettlementDenied("RPC HTTP failure")
                content = resp.read(1024 * 1024 + 1)
                if len(content) > 1024 * 1024:
                    raise SettlementDenied("RPC response exceeds limit")
            parsed = json.loads(content)
        except (OSError, TimeoutError, ValueError, TypeError) as exc:
            raise SettlementDenied("RPC transport unavailable or malformed") from exc
        if not isinstance(parsed, dict) or parsed.get("jsonrpc") != "2.0" or parsed.get("id") != 1:
            raise SettlementDenied("malformed RPC envelope")
        if "error" in parsed or "result" not in parsed:
            raise SettlementDenied("RPC returned error")
        return parsed["result"]
