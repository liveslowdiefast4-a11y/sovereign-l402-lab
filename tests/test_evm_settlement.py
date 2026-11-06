import unittest
from sovereign_l402.evm_settlement import ExpectedPayment, SettlementDenied, TRANSFER_TOPIC, verify_transfer

A = "0x" + "11"*20
B = "0x" + "22"*20
C = "0x" + "33"*20
TX = "0x" + "ab"*32
BLOCK = "0x" + "cd"*32

def topic(a):
    return "0x" + "0"*24 + a[2:]

class SettlementTests(unittest.TestCase):
    def setUp(self):
        self.p = ExpectedPayment(84532, A, B, C, 100, 12)
        self.receipt = {
            "transactionHash": TX, "status": "0x1", "blockNumber": "0x64", "blockHash": BLOCK,
            "logs": [{"address": A, "topics": [TRANSFER_TOPIC, topic(B), topic(C)], "data": "0x64"}]
        }
        self.responses = {"eth_chainId": "0x14a34", "eth_getTransactionReceipt": self.receipt,
                          "eth_blockNumber": "0x6f", "eth_getBlockByNumber": {"hash": BLOCK}}
        # Base Sepolia chain ID 84532 = 0x14a34
    def rpc(self, method, params):
        return self.responses[method]
    def test_valid_transfer(self):
        self.assertEqual(verify_transfer(self.rpc, TX, self.p)["amount_base_units"], 100)
    def reject(self):
        with self.assertRaises(SettlementDenied):
            verify_transfer(self.rpc, TX, self.p)
    def test_wrong_chain(self):
        self.responses["eth_chainId"] = "0xa4b1"; self.reject()
    def test_revert(self):
        self.receipt["status"] = "0x0"; self.reject()
    def test_not_enough_confirmations(self):
        self.responses["eth_blockNumber"] = "0x6e"; self.reject()
    def test_wrong_recipient(self):
        self.receipt["logs"][0]["topics"][2] = topic(B); self.reject()
    def test_wrong_amount(self):
        self.receipt["logs"][0]["data"] = "0x63"; self.reject()
    def test_wrong_token(self):
        self.receipt["logs"][0]["address"] = B; self.reject()
    def test_removed_log(self):
        self.receipt["logs"][0]["removed"] = True; self.reject()
    def test_missing_receipt(self):
        self.responses["eth_getTransactionReceipt"] = None; self.reject()
    def test_wrong_block_hash(self):
        self.responses["eth_getBlockByNumber"] = {"hash": TX}; self.reject()
    def test_duplicate_transfer(self):
        self.receipt["logs"].append(self.receipt["logs"][0].copy()); self.reject()
    def test_unavailable_rpc(self):
        def unavailable(*args): raise TimeoutError()
        with self.assertRaises(SettlementDenied):
            verify_transfer(unavailable, TX, self.p)

    def test_missing_logs(self):
        self.receipt.pop("logs"); self.reject()
    def test_malformed_log(self):
        self.receipt["logs"] = [{"address": A, "topics": [TRANSFER_TOPIC, "0x", topic(C)], "data": "0x64"}]
        self.reject()
