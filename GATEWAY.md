# Sovereign402 Gateway — prototype (2026-11-06)

## Status
Runnable HTTP 402 challenge gateway with strict signed receipts, tenant, path
and body binding, bounded expiry, SQLite WAL replay fence, and fail-closed
behavior. No real payments, live escrow, genuine L402 macaroon, ZK circuit,
hardware attestation, blockchain settlement or distributed consensus.
Sovereign402 is intentionally distinct from Lightning Labs L402.

## Launch (local only)
Supply a 64-character hex secret through SOVEREIGN_RECEIPT_KEY and run
python3 -m sovereign_l402.gateway
This listens on 127.0.0.1 port 8402.
POST /v1/verify requires X-Sovereign-Receipt issued by an independent trusted
verifier. There is no HTTP receipt minting endpoint. A signed settlement
identifier does not itself prove that settlement occurred.

## Tests
python3 -m compileall -q sovereign_l402 tests
PYTHONWARNINGS=error::ResourceWarning python3 -m unittest discover -s tests -v

## Mainnet release gates — all unfulfilled
- Select Lightning L402 or EVM/Solana asset transfer and its real specification.
- Implement verified settlement attestations, chain finality and reorg handling.
- Replace local nonce fence with authoritative durable distributed ledger;
  Redis Redlock is NOT safe financial consensus.
- Audit real noncustodial escrow, USDC decimals, fee accounting, segregated
  reserves, key custody, withdrawal privileges, insolvency and revocation.
- Create and independently verify real ZK circuits; a hash is not a proof.
- Verify TEE measurement and hardware attestation, not merely claimed identity.
- Complete fuzzing, outage testing and 50,000+ concurrency test (not done).
- Obtain contract security/legal reviews; lending/yield disabled by default.
- Obtain explicit owner signoff on networks, addresses, spending and limits.

## EVM settlement evidence verifier (2026-11-06)
`sovereign_l402/evm_settlement.py` contains a pure, dependency-free
ERC-20 transfer receipt checker intended for authenticated EVM testnet JSON-RPC.
It checks chain ID, tx hash, successful status, token address, sender,
recipient, exact base-unit amount, canonical block hash, and configurable
confirmation depth. Failures deny verification. It does not yet make the
gateway accept payments, issue settlement attestations or authorize execution.
An end-to-end payment path needs trusted provider endpoint configuration,
durable atomic transaction/log uniqueness, independent chain observation,
reorg rollback handling, tenant and request-binding and live integration tests.
No chain transaction, funds movement, lender or yield action occurs here.
