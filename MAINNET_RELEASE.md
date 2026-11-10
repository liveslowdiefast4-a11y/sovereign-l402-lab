# Sovereign402 Base Mainnet release gate

**Release state:** Customer funds OFF. Do not describe this branch as deployed or production-ready.

## Reproducible local acceptance

Run inside the repository:

```sh
npm install --ignore-scripts --no-audit --no-fund
npm run contracts:compile
npm run security:test
npm run contracts:test
npm run python:test
```

- Solidity escrow compiles on solc 0.8.24.
- Local EVM test performs actual mock-token escrow deposits, customer-authorized
  release with a 1% fee split, expiry-based full refund, and negative authorization tests.
- The read-only path verifier re-reads all transaction receipts, events, token
  Transfers, canonical blocks, confirmation counts, and terminal order state.
- The local integration test also rejects wrong provider, duplicate transaction
  evidence and insufficient confirmations.
- Local EVM is **not** Base Mainnet. It does not prove live connectivity, USDC
  settlement, contract deployment or customer-fund recovery.

## Read-only Base Mainnet preflight

The mainnet preflight requires an already-deployed contract and secure,
out-of-band approved runtime code hash. No private key is needed:

```sh
export SOVEREIGN_MAINNET_RPC_URL="https://<trusted-base-rpc-host>"
export SOVEREIGN_MAINNET_ESCROW_ADDRESS="0x<deployed-escrow-address>"
export SOVEREIGN_MAINNET_FEE_RECIPIENT="0x<business-controlled-fee-wallet>"
export SOVEREIGN_APPROVED_RUNTIME_HASH="0x<64-hex-digit-approved-runtime-keccak256>"
npm run mainnet:preflight
```

The preflight fails closed unless chain ID is 8453, native Base USDC contract
is present, its decimals/symbol match, the escrow runtime matches the locally
compiled code after masking compiler-defined immutable slots, the exact
runtime hash matches the separately approved pin, and escrow constructor
values match the token, approved fee wallet and 1% fee.

An approved hash must be **reviewed and recorded independently of the current
RPC result**. Copying the live hash automatically into the approved pin
does not establish supply-chain integrity.

## Mainnet acceptance evidence

After an owner-controlled on-chain deployment and explicit, low-value,
owner-funded test transactions, record TWO unique escrow orders:

- Order A: native USDC deposit, then payer-authorized provider release.
- Order B: native USDC deposit, then payer refund after expiry.

Construct a *local* JSON file outside source control with this shape:

```json
{
  "ctx": {
    "escrow": "0x...",
    "token": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "payer": "0x...",
    "provider": "0x...",
    "feeRecipient": "0x...",
    "feeBps": 100
  },
  "release": {
    "id": "0x...64 hex digits",
    "commitment": "0x...64 hex digits",
    "amount": "1000000",
    "fundTx": "0x...64 hex digits",
    "terminalTx": "0x...64 hex digits"
  },
  "refund": {
    "id": "0x...64 hex digits",
    "commitment": "0x...64 hex digits",
    "amount": "1000000",
    "fundTx": "0x...64 hex digits",
    "terminalTx": "0x...64 hex digits"
  }
}
```

Then run:

```sh
export SOVEREIGN_MAINNET_ACCEPTANCE_EVIDENCE="/absolute/local/path/evidence.json"
npm run mainnet:path-audit
```

The verifier demands both completed workflows, correct fees, transfers, order
states and at least 12 Base block confirmations. A pass is a historical,
bounded observation, not irreversible L1 finality, available liquidity,
regulatory approval, an external audit, or proof of future uptime.

## Non-negotiable release blockers

- No verified Base Mainnet contract address or signer/wallet provisioning exists
  in the current development environment; never create or expose private keys
  in a public repository, chat, or test log.
- The current gateway is loopback/testnet-only, and the SQLite financial ledger
  is single-host. There is no production customer authorization middleware,
  multi-host serializable financial store, secure key management, or production
  recovery system.
- No actual Base USDC deposit / release / refund transaction has been executed
  and reconciled on Base Mainnet.
- The buyer-approved escrow is a technical primitive, not an audited escrow
  service or legally authorized custodial, credit, or managed-investment business.
- Hardware TEE attestation, genuine business-specific ZK proofs, Solana
  settlement, regulated lending, and automated yield remain separate unfinished
  capabilities.

**Production funds activation requires owner-controlled signing, a deployment
and operational runbook, verified financial services permissions for the exact
business model, and real end-to-end exercise with recoverable funds.** The
live-path checker must never be treated as an automatic activation switch.
