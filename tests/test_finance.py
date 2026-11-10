import pathlib
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from sovereign_l402.finance import FinancialLedger, Policy, FinanceDenied
from sovereign_l402.evm_settlement import TRANSFER_TOPIC

TOKEN='0x'+'11'*20
PAYER='0x'+'22'*20
TREASURY='0x'+'33'*20
PROVIDER='0x'+'44'*20
TX='0x'+'ab'*32
BLOCK='0x'+'cd'*32
def topic(x):return '0x'+'0'*24+x[2:]

class FinancialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.ledger=FinancialLedger(str(pathlib.Path(self.tmp.name)/'finance.sqlite3'),
                                    Policy(84532,TOKEN,TREASURY,100))
        self.receipt={"transactionHash":TX,"status":"0x1","blockNumber":"0x64","blockHash":BLOCK,
                      "logs":[{"address":TOKEN,"topics":[TRANSFER_TOPIC,topic(PAYER),topic(TREASURY)],"data":"0x2710"}]}
        self.rpc_data={"eth_chainId":"0x14a34","eth_getTransactionReceipt":self.receipt,
                       "eth_blockNumber":"0x6f","eth_getBlockByNumber":{"hash":BLOCK}}
    def rpc(self,method,params):return self.rpc_data[method]
    def hold(self,**kw):
        args=dict(order_id="order-001",tenant="agency-001",sender=PAYER,recipient=TREASURY,
                  provider=PROVIDER,amount=10000,tx_hash=TX,rpc=self.rpc)
        args.update(kw)
        return self.ledger.hold_verified(**args)
    def test_hold_fee(self):
        got=self.hold()
        self.assertEqual((got["provider_liability"],got["fee_liability"]),(9900,100))
        self.assertTrue(self.ledger.verify_journal())
    def test_no_double_spend(self):
        self.hold()
        with self.assertRaises(FinanceDenied):self.hold(order_id="order-002")
    def test_concurrent_settlement_once(self):
        with ThreadPoolExecutor(max_workers=16) as pool:
            outputs=list(pool.map(lambda i:self.try_hold("order-%03d"%i),range(30)))
        self.assertEqual(outputs.count("HELD"),1)
        self.assertEqual(outputs.count("BLOCKED"),29)
    def try_hold(self,order):
        try:return self.hold(order_id=order)["status"]
        except FinanceDenied:return "BLOCKED"
    def test_payer_release_intent(self):
        self.hold()
        result=self.ledger.request_disbursement("order-001",PAYER,"x"*24)
        self.assertEqual((result["amount"],result["treasury_fee"]),(9900,100))
        self.assertEqual(self.ledger.snapshot()[0]["status"],"RELEASE_PENDING")
    def test_payer_refund_intent(self):
        self.hold()
        result=self.ledger.request_disbursement("order-001",PAYER,"x"*24,refund=True)
        self.assertEqual(result["amount"],10000)
    def test_untrusted_cannot_release(self):
        self.hold()
        with self.assertRaises(FinanceDenied):
            self.ledger.request_disbursement("order-001",PROVIDER,"x"*24)
    def test_decision_replay_denied(self):
        self.hold()
        self.ledger.request_disbursement("order-001",PAYER,"x"*24)
        with self.assertRaises(FinanceDenied):
            self.ledger.request_disbursement("order-001",PAYER,"y"*24)
    def test_chain_mismatch(self):
        self.rpc_data["eth_chainId"]="0x1"
        with self.assertRaises(FinanceDenied):self.hold()
    def test_underpayment(self):
        self.receipt["logs"][0]["data"]="0x270f"
        with self.assertRaises(FinanceDenied):self.hold()
    def test_wrong_treasury(self):
        with self.assertRaises(FinanceDenied):self.hold(recipient=PROVIDER)
    def test_no_fake_reconciliation(self):
        self.hold()
        with self.assertRaises(FinanceDenied):
            self.ledger.reconcile("order-001",TX,True,{"tx_hash":TX,"verified":True})
    def test_journal_tampering_detected(self):
        self.hold()
        with self.ledger._db() as db:
            db.execute("UPDATE journal SET payload='{}'")
        self.assertFalse(self.ledger.verify_journal())
    def test_persists_restart(self):
        self.hold()
        other=FinancialLedger(self.ledger.path,self.ledger.policy)
        self.assertEqual(other.snapshot()[0]["gross"],10000)
    def test_emergency_pause_blocks_deposits(self):
        self.ledger.emergency_pause()
        self.assertTrue(self.ledger.is_paused())
        with self.assertRaises(FinanceDenied): self.hold()
    def test_emergency_pause_blocks_payout(self):
        self.hold()
        self.ledger.emergency_pause()
        with self.assertRaises(FinanceDenied):
            self.ledger.request_disbursement("order-001",PAYER,"x"*24)
    def test_deposit_cap(self):
        self.ledger=FinancialLedger(self.ledger.path,
             Policy(84532,TOKEN,TREASURY,100,max_single_amount=9999))
        with self.assertRaises(FinanceDenied): self.hold()
    def test_outstanding_cap(self):
        self.ledger=FinancialLedger(self.ledger.path,
             Policy(84532,TOKEN,TREASURY,100,max_outstanding=9999))
        with self.assertRaises(FinanceDenied): self.hold()
    def test_max_payout_cap(self):
        self.ledger=FinancialLedger(self.ledger.path,
             Policy(84532,TOKEN,TREASURY,100,max_payout=5000))
        self.hold()
        with self.assertRaises(FinanceDenied):
            self.ledger.request_disbursement("order-001",PAYER,"x"*24)
    def test_fee_below_ten_bps_blocked(self):
        with self.assertRaises(FinanceDenied): Policy(84532,TOKEN,TREASURY,0)
    def test_strict_escrow_requires_event(self):
        self.ledger=FinancialLedger(self.ledger.path,
             Policy(84532,TOKEN,TREASURY,100,escrow_contract=TREASURY,fee_recipient=PROVIDER))
        with self.assertRaises(FinanceDenied):
            self.hold(order_id="0x"+"ab"*32,commitment="0x"+"99"*32)
    def test_mainnet_disallowed(self):
        with self.assertRaises(FinanceDenied):Policy(8453,TOKEN,TREASURY)
