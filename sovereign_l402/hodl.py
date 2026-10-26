"""Educational L402/HODL state model, NOT actual node, HTLC or settlement logic."""
from enum import Enum

class State(str, Enum):
    MINTED_UNPAID = 'MINTED_UNPAID'
    HTLC_ACCEPTED = 'HTLC_ACCEPTED'
    SETTLED = 'SETTLED'
    CANCELED = 'CANCELED'

ALLOWED = {
    State.MINTED_UNPAID: {State.HTLC_ACCEPTED,State.CANCELED},
    State.HTLC_ACCEPTED: {State.SETTLED,State.CANCELED},
    State.SETTLED: set(),
    State.CANCELED: set(),
}

class TransitionError(ValueError):
    pass

class HoldState:
    def __init__(self):
        self.state = State.MINTED_UNPAID
    def advance(self,to: State) -> bool:
        to=State(to)
        if to == self.state:
            return False
        if to not in ALLOWED[self.state]:
            raise TransitionError(f'forbidden: {self.state} -> {to}')
        self.state=to
        return True
