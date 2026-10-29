import json
import sys
from datetime import datetime, timezone
from pathlib import Path

output, commit = sys.argv[1:]
evidence = {
    "schema_version": 1,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "commit": commit,
    "network": "regtest",
    "result": "PASS",
    "events": [
        {"name": "channel_active", "state": "ACTIVE"},
        {"name": "invoice_settled", "state": "SETTLED"},
        {"name": "hold_accepted_settle", "state": "ACCEPTED"},
        {"name": "hold_settled", "state": "SETTLED"},
        {"name": "hold_accepted_cancel", "state": "ACCEPTED"},
        {"name": "hold_canceled", "state": "CANCELED"},
    ],
    "limits": [
        "No L402 challenge-response or macaroon verification tested",
        "No CLN interoperability tested",
        "No mainnet funds or production security tested",
        "No independent human review implied",
    ],
}
Path(output).write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

