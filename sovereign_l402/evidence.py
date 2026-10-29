"""Validation for sanitized real-node regtest evidence.

This validates a test report, not Lightning security or L402 correctness.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


class EvidenceError(ValueError):
    pass


_REQUIRED = {
    "channel_active": "ACTIVE",
    "invoice_settled": "SETTLED",
    "hold_accepted_settle": "ACCEPTED",
    "hold_settled": "SETTLED",
    "hold_accepted_cancel": "ACCEPTED",
    "hold_canceled": "CANCELED",
}
_SECRET_KEYS = {"preimage", "payment_request", "macaroon", "seed", "private_key"}


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).lower()
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def validate_evidence(evidence: dict) -> int:
    if not isinstance(evidence, dict):
        raise EvidenceError("evidence must be a JSON object")
    if evidence.get("network") != "regtest":
        raise EvidenceError("only regtest evidence is accepted")
    if evidence.get("result") != "PASS":
        raise EvidenceError("result is not PASS")
    if _SECRET_KEYS.intersection(_walk_keys(evidence)):
        raise EvidenceError("secret-bearing field present in evidence")
    events = evidence.get("events")
    if not isinstance(events, list):
        raise EvidenceError("events must be a list")
    observed = {}
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get("name"), str):
            raise EvidenceError("malformed event")
        if event["name"] in observed:
            raise EvidenceError(f"duplicate event: {event['name']}")
        observed[event["name"]] = event.get("state")
    for name, expected in _REQUIRED.items():
        if observed.get(name) != expected:
            raise EvidenceError(f"{name} must be {expected}")
    return len(_REQUIRED)


def build_evidence(events: list, commit: str, images: dict) -> dict:
    """Build a PASS report only after the supplied observations validate."""
    evidence = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": commit,
        "network": "regtest",
        "result": "PASS",
        "images": images,
        "events": events,
        "limits": [
            "No L402 challenge-response or macaroon verification tested",
            "No CLN interoperability tested",
            "No mainnet funds or production security tested",
            "No independent human review implied",
        ],
    }
    validate_evidence(evidence)
    return evidence


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m sovereign_l402.evidence EVIDENCE.json", file=sys.stderr)
        return 2
    try:
        evidence = json.loads(Path(args[0]).read_text(encoding="utf-8"))
        count = validate_evidence(evidence)
    except (OSError, json.JSONDecodeError, EvidenceError) as exc:
        print(f"evidence rejected: {exc}", file=sys.stderr)
        return 1
    print(f"evidence accepted: {count} required real-node events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
