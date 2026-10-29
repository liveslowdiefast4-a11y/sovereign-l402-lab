"""Validation for sanitized real-node regtest evidence.

This validates a test report, not Lightning security or L402 correctness.
"""

import json
import sys
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
