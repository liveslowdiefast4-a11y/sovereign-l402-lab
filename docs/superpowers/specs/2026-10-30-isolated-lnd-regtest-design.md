# Isolated LND Regtest Evidence Design

## Intent

Create public, independently rerunnable evidence that this research repository can drive real Bitcoin Core regtest and LND invoice/HTLC lifecycles without implying mainnet readiness, production security, L402 authentication, or external human review.

## Goals

- Run Bitcoin Core regtest and two pinned LND nodes inside an isolated container network.
- Fund and open a private regtest channel using generated coins only.
- Prove an ordinary invoice reaches `SETTLED` after a real LND payment.
- Prove hold invoices reach `ACCEPTED`, then independently `SETTLED` and `CANCELED`, using LND invoice RPC state.
- Emit machine-readable, commit-bound evidence and fail CI on every missing assertion.
- Give reviewers one bounded command and a falsification guide.

## Non-goals and anti-goals

- No mainnet, testnet, signet, live funds, public ports, wallet seed export, production deployment, or paid service.
- No claim that LND lifecycle evidence implements or validates the full L402 protocol.
- No fabricated human endorsement, reference, reproduced result, or CI pass.
- No CLN parity claim. CLN is a later interoperability gate after the LND evidence is stable.
- No changes to private GenieOS source; only its private tracking issue may receive evidence-linked status.

## Constraints

- Pin Bitcoin Core and LND image versions; never use `latest`.
- Use only an internal Docker network and ephemeral named volumes.
- Reject any chain other than `regtest` before tests begin.
- Use generated regtest coins and deterministic test-only credentials.
- Always tear down containers and volumes, including on failure.
- Preserve existing 12 synthetic tests as a separate evidence tier.

## Approaches considered

1. **LND-first Docker Compose (selected):** Bitcoin Core plus two LND nodes. Native hold-invoice RPCs provide direct `OPEN`, `ACCEPTED`, `SETTLED`, and `CANCELED` observations. This is the shortest path to honest HTLC evidence.
2. **CLN-first:** simpler JSON-RPC administration but native hold-invoice semantics are not equivalent; a plugin or offer-specific design would add another unverified layer.
3. **Dual LND/CLN matrix:** strongest eventual interoperability evidence, but doubles topology and failure surface before a single real-node lifecycle is proven.

## Architecture

`docker compose` starts one Bitcoin Core regtest node and two LND nodes on an internal bridge. A bounded shell harness initializes/unlocks wallets, mines only regtest blocks, connects peers, opens and confirms one channel, then executes ordinary and hold-invoice flows. The harness captures sanitized JSON summaries with image versions, commit SHA, network, invoice state transitions, and pass/fail status; it never persists seeds, macaroons, TLS keys, payment requests, or preimages in artifacts.

## Acceptance boundary

- **Verified by automation:** container isolation, regtest-only chain, channel active, real LND invoice settlement, hold HTLC acceptance, explicit settle, explicit cancel, cleanup.
- **Still blocked:** local real-node execution on this Windows host (Docker absent), CLN interoperability, macaroon/caveat verification, L402 challenge-response, independent human review, two references, exact two-minute human recording, production/mainnet claims.

