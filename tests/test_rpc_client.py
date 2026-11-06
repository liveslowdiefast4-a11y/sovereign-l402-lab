import unittest
from unittest.mock import patch
from sovereign_l402.rpc_client import ReadOnlyRPC
from sovereign_l402.evm_settlement import SettlementDenied

class DummyResponse:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, n): return b'{"jsonrpc":"2.0","id":1,"result":"0x14a34"}'

class RPCClientTests(unittest.TestCase):
    def test_https_only(self):
        for url in ("http://example.org", "file:///etc/passwd",
                    "https://user:secret@example.org", "https://example.org/#fragment"):
            with self.assertRaises(SettlementDenied):
                ReadOnlyRPC(url)
    def test_method_allowlist(self):
        client = ReadOnlyRPC("https://example.org")
        with self.assertRaises(SettlementDenied):
            client("eth_sendRawTransaction", [])
    def test_rpc_envelope(self):
        client = ReadOnlyRPC("https://example.org")
        with patch("sovereign_l402.rpc_client.urllib.request.urlopen", return_value=DummyResponse()) as mocked:
            self.assertEqual(client("eth_chainId", []), "0x14a34")
            self.assertTrue(mocked.called)
    def test_transport_failure(self):
        client = ReadOnlyRPC("https://example.org")
        with patch("sovereign_l402.rpc_client.urllib.request.urlopen", side_effect=TimeoutError()):
            with self.assertRaises(SettlementDenied):
                client("eth_chainId", [])
