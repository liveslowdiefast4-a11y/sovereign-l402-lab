import json
from pathlib import Path
import unittest
from sovereign_l402.escrow_evm import verify_funded_order,verify_escrow_payout
from sovereign_l402.evm_settlement import ExpectedPayment

class LocalChainReceiptIntegration(unittest.TestCase):
    def test_actual_compiled_contract_deposit_event(self):
        path=Path(__file__).resolve().parents[1]/"artifacts/escrow-funding-local.json"
        if not path.exists():
            self.skipTest("run node scripts/evm-local-test.mjs first")
        doc=json.loads(path.read_text())
        receipt=doc["receipt"]
        responses={
            "eth_chainId":hex(doc["chainId"]),
            "eth_getTransactionReceipt":receipt,
            "eth_blockNumber":receipt["blockNumber"],
            "eth_getBlockByNumber":{"hash":receipt["blockHash"]}
        }
        rpc=lambda method,params:responses[method]
        policy=ExpectedPayment(doc["chainId"],doc["token"],doc["payer"],doc["escrow"],10000,1)
        result=verify_funded_order(rpc,receipt["transactionHash"],policy,
              escrow=doc["escrow"],order_id=doc["orderId"],
              payer=doc["payer"],provider=doc["provider"],commitment=doc["commitment"])
        self.assertEqual(result["order_id"],doc["orderId"].lower())

    def test_actual_compiled_contract_release_and_refund(self):
        path=Path(__file__).resolve().parents[1]/"artifacts/escrow-payout-local.json"
        if not path.exists():
            self.skipTest("run node scripts/evm-local-test.mjs first")
        doc=json.loads(path.read_text())
        for variant in ("release","refund"):
            case=doc[variant];receipt=case["receipt"]
            responses={"eth_chainId":hex(doc["chainId"]),"eth_getTransactionReceipt":receipt,
              "eth_blockNumber":receipt["blockNumber"],
              "eth_getBlockByNumber":{"hash":receipt["blockHash"]}}
            rpc=lambda method,params:responses[method]
            refunded=variant=="refund"
            target=doc["payer"] if refunded else doc["provider"]
            amount=case["amount"] if refunded else case["net"]
            policy=ExpectedPayment(doc["chainId"],doc["token"],doc["escrow"],target,amount,1)
            evidence=verify_escrow_payout(
                rpc,receipt["transactionHash"],policy,
                escrow=doc["escrow"],order_id=case["orderId"],
                refunded=refunded,fee_recipient=doc["feeRecipient"],
                fee_amount=0 if refunded else case["fee"])
            self.assertEqual(evidence["order_id"],case["orderId"].lower())
