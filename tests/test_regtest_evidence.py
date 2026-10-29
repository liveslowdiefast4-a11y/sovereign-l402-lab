import json
import tempfile
import unittest
from pathlib import Path

from sovereign_l402.evidence import EvidenceError, validate_evidence


class RegtestEvidenceTests(unittest.TestCase):
    def valid_evidence(self):
        return {
            "schema_version": 1,
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
        }

    def test_accepts_complete_regtest_lifecycle(self):
        self.assertEqual(validate_evidence(self.valid_evidence()), 6)

    def test_rejects_non_regtest_network(self):
        evidence = self.valid_evidence()
        evidence["network"] = "mainnet"
        with self.assertRaisesRegex(EvidenceError, "regtest"):
            validate_evidence(evidence)

    def test_rejects_missing_or_wrong_terminal_state(self):
        for event, state in (("hold_settled", "ACCEPTED"), ("hold_canceled", "SETTLED")):
            with self.subTest(event=event):
                evidence = self.valid_evidence()
                next(item for item in evidence["events"] if item["name"] == event)["state"] = state
                with self.assertRaises(EvidenceError):
                    validate_evidence(evidence)

    def test_rejects_secret_bearing_fields(self):
        for forbidden in ("preimage", "payment_request", "macaroon", "seed"):
            with self.subTest(forbidden=forbidden):
                evidence = self.valid_evidence()
                evidence[forbidden] = "must-not-appear"
                with self.assertRaisesRegex(EvidenceError, "secret"):
                    validate_evidence(evidence)

    def test_cli_validates_json_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_text(json.dumps(self.valid_evidence()), encoding="utf-8")
            self.assertEqual(validate_evidence(json.loads(path.read_text(encoding="utf-8"))), 6)


if __name__ == "__main__":
    unittest.main()
