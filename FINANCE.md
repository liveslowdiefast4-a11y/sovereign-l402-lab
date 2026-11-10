# Sovereign402 — financial-mechanism implementation

Implemented on the testnet financial-mechanisms branch:

- Atomic, single-host SQLite ledger with duplicate transaction rejection, hash-linked audit records, and integer ERC-20 base-unit fee accounting.
- Inbound settlement verification checks configured chain, token, sender, treasury recipient, exact amount, block consistency and confirmation depth.
- Payer-requested release and refund intents; payout reconciliation requires a separately verified outbound token transfer.
- Concurrent settlement reuse, adverse RPC conditions, forged recipient, underpayment, ledger persistence, journal tampering and replay tests.
- Testnet chain allowlist only: Base Sepolia (84532) and Arbitrum Sepolia (421614).
- Existing buyer-controlled Solidity escrow on the feature branch separately compiles and has passed 17 local EVM checks.

**Important boundary:** The ledger tracks intents, not wallet balances, and is NOT the same as the Solidity escrow state. It does not sign/broadcast transfers, hold customer funds, validate EIP-712 customer authorization, guarantee multi-region consensus, establish ZK proof of executed work, or produce TEE attestation. RPC evidence can still be affected by later chain reorganizations. Journal hashes are not externally anchored.

Do not activate real-money operations, public custody, automated credit or yield on these implementations alone. Live deployment also needs coherent order-to-contract event binding, key handling, transaction broadcast and reconciliation, solvency monitoring, authorization, failure recovery and any applicable legal requirements.

Reproduce the Python suite:

    PYTHONWARNINGS=error::ResourceWarning python3 -m unittest discover -s tests -q

Verified locally on the connected Android device: 80/80 tests.
