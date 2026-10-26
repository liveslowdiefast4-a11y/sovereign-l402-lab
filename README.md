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

The 12-test suite includes 8-worker/40-request contention, 30-thread replay, idempotency collisions, state-transition denials, malformed credentials, and synthetic preimage-hash vectors. Tests validate covered cases only.

GitHub Actions runs the exact published source on Python 3.10, 3.12 and 3.13. A passing CI run is external test infrastructure, NOT a security audit or independent human attestation.

## What this cannot do

No real LND/CLN node, live Bitcoin network, actual HTLC, BOLT11 decoding, macaroon signature/caveat verification, invoice binding, preimage custody, real settlement, or trusted payment authorization is implemented. Never grant access solely because a preimage hash matches; the L402 macaroon must be authenticated against the invoice and caveats checked.

## References and collaboration

Canonical [Lightning Labs L402 specification](https://github.com/lightninglabs/L402/blob/master/protocol-specification.md).
See [Verification](VERIFY.md), [Roadmap](ROADMAP.md), and [Security](SECURITY.md).
Publicly reproducible tests are proof of initial development effort, NOT a funded grant, peer review, or production certification.

## Licence and commercial boundary

MIT licence applies to this standalone research project only. No licence to the separate private GenieOS codebase is implied. Any grant-funded work should remain openly available under appropriate open-source licences, separate from private paid services.
