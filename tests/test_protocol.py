"""L402 syntax and hash vectors, not macaroon or settlement verification."""
import base64
import hashlib
import unittest
from sovereign_l402.protocol import CredentialError, parse_authorization, matches_payment_hash

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.preimage = bytes(range(32))
        self.hash = hashlib.sha256(self.preimage).digest()
        self.token = base64.b64encode(b"synthetic-not-a-real-macaroon").decode("ascii")
        self.header = f"L402 {self.token}:{self.preimage.hex()}"

    def test_parse_and_hash_reference_vector(self):
        cred = parse_authorization(self.header)
        self.assertEqual(cred.preimage, self.preimage)
        self.assertEqual(cred.macaroon_bytes, b"synthetic-not-a-real-macaroon")
        self.assertTrue(matches_payment_hash(cred, self.hash))

    def test_wrong_preimage_rejected_by_hash(self):
        cred = parse_authorization(self.header)
        self.assertFalse(matches_payment_hash(cred, bytes(32)))

    def test_bad_headers_fail_closed(self):
        for header in (
            "", "Bearer x", self.header + "\r\nX-Injected:1",
            "L402 bogus:nothex", f"L402 {self.token}:{self.preimage.hex()[:-2]}",
            f"L402 {self.token},second:{self.preimage.hex()}",
            f"L402 !!!:{self.preimage.hex()}",
            "L402 "+("A"*9000)+":"+self.preimage.hex(),
        ):
            with self.subTest(header=header[:60]):
                with self.assertRaises(CredentialError):
                    parse_authorization(header)

    def test_bad_expected_hash_length(self):
        with self.assertRaises(CredentialError):
            matches_payment_hash(parse_authorization(self.header), bytes(31))
