"""Research-only L402 credential syntax and preimage hash helpers.

NOT a macaroon validator, BOLT11 decoder, wallet, payment authorization,
or proof of settlement. NEVER grant API access based solely on these utilities.
Reference: https://github.com/lightninglabs/L402
"""
import base64
import binascii
import hashlib
import hmac
import re
from dataclasses import dataclass

_CREDENTIAL = re.compile(r"^L402 ([A-Za-z0-9+/]+={0,2}):([0-9a-fA-F]{64})$", re.ASCII | re.IGNORECASE)

class CredentialError(ValueError):
    """Malformed or unsupported credential."""

@dataclass(frozen=True)
class Credential:
    macaroon_bytes: bytes
    preimage: bytes

def parse_authorization(header: str) -> Credential:
    """Parse single-macaroon subset; reject ambiguous header content."""
    if not isinstance(header, str) or len(header) > 8192:
        raise CredentialError("invalid header")
    found = _CREDENTIAL.fullmatch(header)
    if not found:
        raise CredentialError("malformed or unsupported L402 credential")
    macaroon_text, preimage_hex = found.groups()
    try:
        macaroon = base64.b64decode(macaroon_text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CredentialError("invalid macaroon encoding") from exc
    if not macaroon or len(macaroon) > 4096:
        raise CredentialError("invalid macaroon length")
    return Credential(macaroon_bytes=macaroon, preimage=bytes.fromhex(preimage_hex))

def matches_payment_hash(credential: Credential, payment_hash: bytes) -> bool:
    """SHA256(preimage) comparison ONLY; this cannot authorize payment access."""
    if not isinstance(payment_hash, bytes) or len(payment_hash) != 32:
        raise CredentialError("expected exactly 32 payment-hash bytes")
    return hmac.compare_digest(hashlib.sha256(credential.preimage).digest(), payment_hash)
