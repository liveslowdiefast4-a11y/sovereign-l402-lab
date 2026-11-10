"""Check that the ERC-20 payment was deposited THROUGH the pinned escrow contract.

A bare ERC-20 transfer into a contract is not evidence an escrow order exists.
The contract's Funded event must match the token transfer and order identity.
"""
from .evm_settlement import SettlementDenied, ExpectedPayment, verify_transfer, address, quantity

FUNDED_TOPIC = "0x8363bf1c8871b5b2cad437b606f92c98bc8fd760d243ec3beb6069b673c833d1"

def _topic_address(value):
    if not isinstance(value,str) or len(value)!=66 or not value.startswith("0x") or value[2:26]!="0"*24:
        raise SettlementDenied("invalid topic-address")
    return address("0x"+value[26:])

def verify_funded_order(rpc, transaction_hash, expected, *, escrow, order_id, payer, provider, commitment):
    """Verify one pinned escrow event plus exact underlying token Transfer.

    expected.recipient MUST be the same immutable escrow address.
    """
    if address(escrow)!=address(expected.recipient):
        raise SettlementDenied("escrow address does not match token recipient")
    for label,value in (("order ID",order_id),("commitment",commitment)):
        if not isinstance(value,str) or len(value)!=66 or not value.startswith("0x"):
            raise SettlementDenied("invalid "+label)
        try: int(value[2:],16)
        except ValueError as exc: raise SettlementDenied("invalid "+label) from exc
    if address(payer)!=address(expected.sender) or address(provider)==address(payer):
        raise SettlementDenied("escrow payer mismatch")
    evidence=verify_transfer(rpc,transaction_hash,expected)
    try:
        receipt=rpc("eth_getTransactionReceipt",[transaction_hash])
        if not isinstance(receipt,dict) or receipt.get("transactionHash","").lower()!=transaction_hash.lower():
            raise SettlementDenied("escrow receipt mismatch")
        if receipt.get("blockHash","").lower()!=evidence["block_hash"]:
            raise SettlementDenied("escrow block mismatch")
        matches=[]
        for log in receipt.get("logs",[]):
            if not isinstance(log,dict) or log.get("removed") is True:
                continue
            if address(log.get("address"))!=address(escrow):
                continue
            topics=log.get("topics")
            if not isinstance(topics,list) or len(topics)!=4:
                continue
            if not isinstance(topics[0],str) or topics[0].lower()!=FUNDED_TOPIC:
                continue
            if topics[1].lower()!=order_id.lower() or _topic_address(topics[2])!=address(payer) or _topic_address(topics[3])!=address(provider):
                continue
            data=log.get("data")
            if not isinstance(data,str) or len(data)!=194 or not data.startswith("0x"):
                raise SettlementDenied("invalid Funded event data")
            amount=int(data[2:66],16)
            expires=int(data[66:130],16)
            recorded_commitment="0x"+data[130:194]
            if amount!=expected.amount_base_units or not 0<expires<2**64 or recorded_commitment.lower()!=commitment.lower():
                raise SettlementDenied("escrow event values differ from request")
            matches.append(expires)
        if len(matches)!=1:
            raise SettlementDenied("unique escrow Funded event absent")
    except SettlementDenied:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, OSError) as exc:
        raise SettlementDenied("malformed escrow event") from exc
    return {**evidence,"escrow":address(escrow),"order_id":order_id.lower(),
            "provider":address(provider),"commitment":commitment.lower(),
            "expiry":matches[0]}

RELEASED_TOPIC = "0x086f561142bc4bdbe9350bd28b5eb74b4b2a64b0c54d97c83bea294393d8beb8"
REFUNDED_TOPIC = "0x1535ab411323bb41ad642ccf14068bbd78818ed38dd9b4421c927cc6eeb07e2d"

def verify_escrow_payout(rpc, tx_hash, expected, *, escrow, order_id,
                         refunded, fee_recipient=None, fee_amount=0):
    """Verify escrow event AND token transfer(s) before settlement reconciliation."""
    if address(escrow)!=address(expected.sender):
        raise SettlementDenied("payout sender must be pinned escrow")
    if not isinstance(order_id,str) or len(order_id)!=66 or not order_id.startswith("0x"):
        raise SettlementDenied("invalid payout order id")
    try:int(order_id[2:],16)
    except ValueError as exc:raise SettlementDenied("invalid payout order id") from exc
    if type(fee_amount) is not int or fee_amount<0 or fee_amount>2**63-1:
        raise SettlementDenied("invalid payout fee")
    if refunded and fee_amount!=0:
        raise SettlementDenied("refund must return entire original amount")
    evidence=verify_transfer(rpc,tx_hash,expected)
    try:
        receipt=rpc("eth_getTransactionReceipt",[tx_hash])
        if not isinstance(receipt,dict) or receipt.get("transactionHash","").lower()!=tx_hash.lower() or receipt.get("blockHash","").lower()!=evidence["block_hash"]:
            raise SettlementDenied("payout receipt mismatch")
        target=REFUNDED_TOPIC if refunded else RELEASED_TOPIC
        match_count=0
        for log in receipt.get("logs",[]):
            if not isinstance(log,dict) or log.get("removed") is True:
                continue
            if address(log.get("address"))!=address(escrow):
                continue
            topics=log.get("topics")
            if not isinstance(topics,list) or len(topics)!=2 or topics[0].lower()!=target or topics[1].lower()!=order_id.lower():
                continue
            data=log.get("data")
            if not isinstance(data,str) or not data.startswith("0x"):
                raise SettlementDenied("missing payout event data")
            if refunded:
                if len(data)!=66 or int(data[2:],16)!=expected.amount_base_units:
                    raise SettlementDenied("refund event amount mismatch")
            else:
                if len(data)!=130 or int(data[2:66],16)!=expected.amount_base_units or int(data[66:130],16)!=fee_amount:
                    raise SettlementDenied("released amount or fee mismatch")
            match_count+=1
        if match_count!=1:
            raise SettlementDenied("unique payout event absent")
        if not refunded and fee_amount:
            if fee_recipient is None:
                raise SettlementDenied("missing configured fee recipient")
            fee_transfer=ExpectedPayment(expected.chain_id,expected.token,escrow,
                                         fee_recipient,fee_amount,expected.min_confirmations)
            verify_transfer(rpc,tx_hash,fee_transfer)
        return {**evidence,"escrow":address(escrow),"order_id":order_id.lower(),
                "refunded":refunded,"fee_amount":fee_amount}
    except SettlementDenied:
        raise
    except (ValueError,TypeError,AttributeError,KeyError,OSError) as exc:
        raise SettlementDenied("malformed payout event") from exc
