"""Fail-closed ERC-20 settlement evidence checker (EVM testnets; no funds movement).

The caller MUST provide authenticated JSON-RPC from a trusted chain endpoint.
This module does not mint payment attestations, establish financial consensus,
or make the existing gateway accept payments.
"""
from dataclasses import dataclass

TRANSFER_TOPIC = "0x" + "ddf252ad" + "1be2c89b" + "69c2b068" + "fc378daa" + "952ba7f1" + "63c4a116" + "28f55a4d" + "f523b3ef"

class SettlementDenied(ValueError):
    pass

def quantity(value):
    if not isinstance(value, str) or not value.startswith("0x") or not value[2:]:
        raise SettlementDenied("bad RPC quantity")
    try:
        parsed = int(value, 16)
    except ValueError as exc:
        raise SettlementDenied("bad RPC quantity") from exc
    if parsed < 0:
        raise SettlementDenied("negative quantity")
    return parsed

def address(value):
    if not isinstance(value, str) or len(value) != 42 or not value.startswith("0x"):
        raise SettlementDenied("bad address")
    try:
        int(value[2:], 16)
    except ValueError as exc:
        raise SettlementDenied("bad address") from exc
    return value.lower()

def topic_address(value):
    if not isinstance(value, str) or len(value) != 66 or not value.startswith("0x"):
        raise SettlementDenied("bad address topic")
    if value[2:26] != "0" * 24:
        raise SettlementDenied("noncanonical address topic")
    return address("0x" + value[26:])

@dataclass(frozen=True)
class ExpectedPayment:
    chain_id: int
    token: str
    sender: str
    recipient: str
    amount_base_units: int
    min_confirmations: int = 12

    def __post_init__(self):
        for a in (self.token, self.sender, self.recipient):
            address(a)
        if self.chain_id <= 0 or self.amount_base_units <= 0 or self.min_confirmations < 1:
            raise SettlementDenied("unsafe payment policy")

def verify_transfer(rpc, transaction_hash, expected):
    """Verify finalized-enough ERC20 transfer; fail closed on missing/malformed RPC data.

    rpc(method, params) returns the JSON-RPC 'result' (not the response envelope).
    Callers MUST protect endpoint authenticity and independently guard tx replay.
    """
    if not isinstance(transaction_hash, str) or len(transaction_hash) != 66 or not transaction_hash.startswith("0x"):
        raise SettlementDenied("invalid transaction hash")
    try:
        int(transaction_hash[2:], 16)
    except ValueError as exc:
        raise SettlementDenied("invalid transaction hash") from exc

    try:
        chain = quantity(rpc("eth_chainId", []))
        if chain != expected.chain_id:
            raise SettlementDenied("wrong chain")
        receipt = rpc("eth_getTransactionReceipt", [transaction_hash])
        if not isinstance(receipt, dict):
            raise SettlementDenied("unmined transaction")
        if receipt.get("transactionHash", "").lower() != transaction_hash.lower():
            raise SettlementDenied("receipt mismatch")
        if quantity(receipt.get("status")) != 1:
            raise SettlementDenied("reverted transaction")
        height = quantity(receipt.get("blockNumber"))
        blockhash = receipt.get("blockHash")
        if not isinstance(blockhash, str) or len(blockhash) != 66:
            raise SettlementDenied("missing block hash")
        head = quantity(rpc("eth_blockNumber", []))
        if head < height or head - height + 1 < expected.min_confirmations:
            raise SettlementDenied("insufficient confirmations")
        block = rpc("eth_getBlockByNumber", [hex(height), False])
        if not isinstance(block, dict) or block.get("hash", "").lower() != blockhash.lower():
            raise SettlementDenied("receipt block is not canonical")
        logs = receipt.get("logs")
        if not isinstance(logs, list):
            raise SettlementDenied("missing transaction logs")
        matches = []
        for log in logs:
            if not isinstance(log, dict) or log.get("removed") is True:
                continue
            topics = log.get("topics")
            if not isinstance(topics, list) or len(topics) != 3:
                continue
            if not isinstance(topics[0], str) or topics[0].lower() != TRANSFER_TOPIC:
                continue
            if address(log.get("address")) != address(expected.token):
                continue
            if topic_address(topics[1]) != address(expected.sender):
                continue
            if topic_address(topics[2]) != address(expected.recipient):
                continue
            if quantity(log.get("data")) == expected.amount_base_units:
                matches.append(log)
        if len(matches) != 1:
            raise SettlementDenied("expected unique token transfer not found")
        # Re-read canonical head after parsing; still not a guarantee against later reorgs.
        latest = rpc("eth_getBlockByNumber", [hex(height), False])
        if not isinstance(latest, dict) or latest.get("hash", "").lower() != blockhash.lower():
            raise SettlementDenied("chain reorganized during verification")
        return {"chain_id": chain, "transaction_hash": transaction_hash.lower(),
                "block_hash": blockhash.lower(), "block_number": height,
                "confirmations_at_check": head - height + 1, "amount_base_units": expected.amount_base_units}
    except SettlementDenied:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, OSError, TimeoutError, ConnectionError) as exc:
        raise SettlementDenied("malformed or unavailable RPC evidence") from exc
