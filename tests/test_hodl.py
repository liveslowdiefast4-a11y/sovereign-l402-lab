import unittest
from sovereign_l402.hodl import State,HoldState,TransitionError

class HoldTests(unittest.TestCase):
    def test_nominal_state(self):
        h=HoldState()
        self.assertTrue(h.advance(State.HTLC_ACCEPTED))
        self.assertFalse(h.advance(State.HTLC_ACCEPTED))
        self.assertTrue(h.advance(State.SETTLED))
        with self.assertRaises(TransitionError): h.advance(State.CANCELED)
    def test_cancel_before_or_after_accept(self):
        for after in (False,True):
            h=HoldState()
            if after: h.advance(State.HTLC_ACCEPTED)
            h.advance(State.CANCELED)
            with self.assertRaises(TransitionError): h.advance(State.HTLC_ACCEPTED)
    def test_no_direct_settlement(self):
        with self.assertRaises(TransitionError): HoldState().advance(State.SETTLED)
