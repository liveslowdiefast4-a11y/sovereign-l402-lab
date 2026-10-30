# Sovereign L402 Lab

**Public Python Bitcoin/Lightning research harness — experimental, no real payments.**

An independent, standard-library-only testbed for:
- A single-database SQLite WAL millisatoshi reservation ledger with contention/replay tests.
- A synthetic four-state HODL lifecycle model (not a Lightning HTLC adapter).
- L402 Authorization header syntax and SHA-256(preimage) comparison tests.

**Nothing here authenticates an invoice or performs Lightning settlement.**
The source was written as a separate research prototype, not copied from the private Sovereign Reliability/GenieOS commercial application. No API keys, wallets or paid services are required.

## Reproduce

Requires Python 3.10+.

    python3 -m compileall -q sovereign_l402 tests
    python3 -m unittest discover -s tests -v

The 17-test local suite includes 8-worker/40-request contention, 30-thread replay, idempotency collisions, state-transition denials, malformed credentials, synthetic preimage-hash vectors, and fail-closed validation of sanitized real-node evidence. These local tests do not run LND. Tests validate covered cases only.

Automatic hosted runner verification is configured in the public [GitLab pipeline](https://gitlab.com/Dan2221994/sovereign-l402-lab/-/pipelines) (Python 3.12). The GitHub Actions workflow remains manual-only because GitHub reports an account billing lock; a prior run was rejected before any steps. A successful CI run is independent compute infrastructure, NOT a security audit or human attestation.

An isolated Bitcoin Core + two-LND regtest harness is under active validation. See [REGTEST.md](REGTEST.md). Its existence is not evidence that it passed: only a successful commit-bound `real-lnd-regtest` job and its validated artifact count as real-node evidence.

## What this cannot do

No live Bitcoin network, CLN interoperability, BOLT11 implementation, macaroon signature/caveat verification, L402 invoice binding, production preimage custody, mainnet settlement, or trusted payment authorization is implemented. The optional regtest harness exercises LND RPC lifecycle states only. Never grant access solely because a preimage hash matches; the L402 macaroon must be authenticated against the invoice and caveats checked.

## References and collaboration

Canonical [Lightning Labs L402 specification](https://github.com/lightninglabs/L402/blob/master/protocol-specification.md).
See [Verification](VERIFY.md), [Roadmap](ROADMAP.md), and [Security](SECURITY.md).
Publicly reproducible tests are proof of initial development effort, NOT a funded grant, peer review, or production certification.

## Licence and commercial boundary

MIT licence applies to this standalone research project only. No licence to the separate private GenieOS codebase is implied. Any grant-funded work should remain openly available under appropriate open-source licences, separate from private paid services.
