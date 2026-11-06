import hashlib
import hmac
import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from sovereign_l402.gateway import Denied, Gateway, Settings, canonical, sha

class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.key = b"k" * 32
        self.gateway = Gateway(Settings("tenant-a", self.key, str(Path(self.tmp.name)/"ledger.db")))
        self.body = b'{"operation":"check"}'
    def ticket(self, **changes):
        claim = {"version":1,"tenant":"tenant-a","path":"/v1/verify",
                 "body_sha256":sha(self.body),"nonce":"n"*24,"expires":int(time.time())+60,
                 "settlement_id":"settlement-1234"}
        claim.update(changes)
        return json.dumps({"claim":claim, "mac":hmac.new(self.key, canonical(claim), hashlib.sha256).hexdigest()})
    def call(self, ticket=None, body=None):
        return self.gateway.handle("POST","/v1/verify",self.body if body is None else body,ticket)[0]
    def test_missing_402(self): self.assertEqual(self.call(),402)
    def test_valid_200(self): self.assertEqual(self.call(self.ticket()),200)
    def test_replay_402(self):
        t=self.ticket();self.assertEqual(self.call(t),200);self.assertEqual(self.call(t),402)
    def test_bad_mac_402(self):
        t=json.loads(self.ticket());t["mac"]="0"*64;self.assertEqual(self.call(json.dumps(t)),402)
    def test_wrong_tenant_402(self): self.assertEqual(self.call(self.ticket(tenant="attacker")),402)
    def test_wrong_path_402(self): self.assertEqual(self.call(self.ticket(path="/else")),402)
    def test_wrong_body_402(self): self.assertEqual(self.call(self.ticket(),b"changed"),402)
    def test_expiry_402(self): self.assertEqual(self.call(self.ticket(expires=int(time.time())-1)),402)
    def test_future_expiry_402(self): self.assertEqual(self.call(self.ticket(expires=int(time.time())+900)),402)
    def test_unknown_field_402(self): self.assertEqual(self.call(self.ticket(privilege="admin")),402)
    def test_bad_config(self):
        with self.assertRaises(ValueError): Settings("tenant",b"weak","db")
    def test_concurrent_single_redeem(self):
        t=self.ticket()
        with ThreadPoolExecutor(max_workers=16) as pool:
            result=list(pool.map(lambda _:self.call(t),range(64)))
        self.assertEqual(result.count(200),1)
        self.assertEqual(result.count(402),63)
    def test_persists_restart(self):
        t=self.ticket();self.assertEqual(self.call(t),200)
        other=Gateway(self.gateway.settings)
        self.assertEqual(other.handle("POST","/v1/verify",self.body,t)[0],402)
    def test_settlement_id_reuse_denied(self):
        self.assertEqual(self.call(self.ticket()),200)
        self.assertEqual(self.call(self.ticket(nonce="z"*24)),402)
    def test_health(self):
        self.assertEqual(self.gateway.handle("GET","/healthz",b"",None)[0],200)
    def test_oversized_body(self):
        self.assertEqual(self.call(body=b"a"*65537),413)
    def test_malformed_receipt(self):
        self.assertEqual(self.call("not json"),402)

if __name__ == "__main__": unittest.main()
