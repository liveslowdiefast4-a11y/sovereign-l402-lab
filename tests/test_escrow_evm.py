import unittest
from sovereign_l402.escrow_evm import verify_funded_order,FUNDED_TOPIC
from sovereign_l402.evm_settlement import ExpectedPayment,SettlementDenied,TRANSFER_TOPIC

TOKEN="0x"+"11"*20; PAYER="0x"+"22"*20
ESCROW="0x"+"33"*20; PROVIDER="0x"+"44"*20
ORDER="0x"+"ab"*32; HASH="0x"+"ef"*32; BLOCK="0x"+"cd"*32
COMMITMENT="0x"+"99"*32
def topic(a):return "0x"+"0"*24+a[2:]
def word(n):return hex(n)[2:].rjust(64,"0")

class EscrowReceiptTests(unittest.TestCase):
    def setUp(self):
        self.expected=ExpectedPayment(84532,TOKEN,PAYER,ESCROW,10000,12)
        self.funded={"address":ESCROW,"topics":[FUNDED_TOPIC,ORDER,topic(PAYER),topic(PROVIDER)],
             "data":"0x"+word(10000)+word(9999999999)+COMMITMENT[2:]}
        self.transfer={"address":TOKEN,"topics":[TRANSFER_TOPIC,topic(PAYER),topic(ESCROW)],"data":"0x2710"}
        self.receipt={"transactionHash":HASH,"status":"0x1","blockNumber":"0x64","blockHash":BLOCK,
                      "logs":[self.transfer,self.funded]}
        self.responses={"eth_chainId":"0x14a34","eth_getTransactionReceipt":self.receipt,
                        "eth_blockNumber":"0x6f","eth_getBlockByNumber":{"hash":BLOCK}}
    def rpc(self,m,p):return self.responses[m]
    def verify(self):
        return verify_funded_order(self.rpc,HASH,self.expected,
                   escrow=ESCROW,order_id=ORDER,payer=PAYER,provider=PROVIDER,commitment=COMMITMENT)
    def denied(self):
        with self.assertRaises(SettlementDenied):self.verify()
    def test_pinned_escrow_payment(self):
        self.assertEqual(self.verify()["expiry"],9999999999)
    def test_direct_token_transfer_not_escrow(self):
        self.receipt["logs"]=[self.transfer];self.denied()
    def test_fake_escrow_address(self):
        self.funded["address"]=TOKEN;self.denied()
    def test_forged_provider(self):
        self.funded["topics"][3]=topic(PAYER);self.denied()
    def test_wrong_order(self):
        self.funded["topics"][1]=HASH;self.denied()
    def test_wrong_commitment(self):
        self.funded["data"]="0x"+word(10000)+word(9999999999)+"ff"*32;self.denied()
    def test_wrong_amount(self):
        self.funded["data"]="0x"+word(9999)+word(9999999999)+COMMITMENT[2:];self.denied()
    def test_wrong_chain(self):
        self.responses["eth_chainId"]="0x1";self.denied()
    def test_reorg(self):
        self.responses["eth_getBlockByNumber"]={"hash":HASH};self.denied()
    def test_duplicate_funded_event(self):
        self.receipt["logs"].append(self.funded.copy());self.denied()
