import http.client
import tempfile
import threading
import unittest
from pathlib import Path
from sovereign_l402.settlement_server import build_gateway, make_server

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = {
            "SOVEREIGN_CHAIN_ID":"84532",
            "SOVEREIGN_RECEIPT_KEY":"12"*32,
            "SOVEREIGN_TOKEN_ADDRESS":"0x"+"11"*20,
            "SOVEREIGN_SENDER_ADDRESS":"0x"+"22"*20,
            "SOVEREIGN_RECIPIENT_ADDRESS":"0x"+"33"*20,
            "SOVEREIGN_AMOUNT_BASE_UNITS":"100",
            "SOVEREIGN_TENANT":"example",
            "SOVEREIGN_DB":str(Path(self.tmp.name)/"ledger.db"),
            "SOVEREIGN_RPC_URL":"https://example.com/rpc",
        }
    def test_production_chain_refused(self):
        self.env["SOVEREIGN_CHAIN_ID"]="8453"
        with self.assertRaises(ValueError):build_gateway(self.env)
    def test_customer_funds_refused(self):
        self.env["SOVEREIGN_ENABLE_CUSTOMER_FUNDS"]="true"
        with self.assertRaises(ValueError):build_gateway(self.env)
    def test_lending_refused(self):
        self.env["SOVEREIGN_ENABLE_LENDING"]="yes"
        with self.assertRaises(ValueError):build_gateway(self.env)
    def test_yield_refused(self):
        self.env["SOVEREIGN_ENABLE_YIELD"]="yes"
        with self.assertRaises(ValueError):build_gateway(self.env)
    def test_http_denies_unpaid(self):
        gateway=build_gateway(self.env)
        server=make_server(gateway,port=0)
        t=threading.Thread(target=server.serve_forever,daemon=True)
        t.start()
        try:
            con=http.client.HTTPConnection("127.0.0.1",server.server_address[1],timeout=5)
            con.request("POST","/v1/verify",body=b'{}')
            response=con.getresponse()
            self.assertEqual(response.status,402)
            self.assertEqual(response.getheader("Cache-Control"),"no-store")
            response.read()
            con.close()
        finally:
            server.shutdown()
            server.server_close()
            t.join(timeout=5)
    def test_loopback_only(self):
        with self.assertRaises(ValueError):
            make_server(build_gateway(self.env),host="0.0.0.0",port=0)
