# Independent reproduction, falsification and confidence limits

## What to check
1. Download or git-clone the PUBLIC repository. Pin the exact commit SHA.
2. Read source and MIT license; check the CI config before trusting workflow results.
3. Run: python3 -m unittest discover -s tests -v
4. Compare test inventory and counts with the GitLab hosted pipeline for the exact mirrored commit. GitHub-hosted runners are blocked by an account billing issue.
5. Try counterexamples: duplicate request with different amount, wrong preimage, incorrect header length, illegal HODL state transition, or cap-exceeding concurrent reservations. Failures should fail closed.

## Scope
SQLite WAL makes local reservations serializable for this fixture. The state machine does not observe Lightning or an actual HTLC. The L402 header parser supports ONE macaroon and checks only structural syntax; the preimage hash helper is not a payment-authentication or trusted-macaroon verifier.

## Evidence tiers
- Public source + license: inspectable, forkable, and runnable.
- Local tests: repeatable scenarios only, not mathematical or production proof.
- GitLab CI: third-party compute after a successful pipeline, not external human audit. GitHub Actions: currently blocked by billing lock.
- Independent maintainer review: NOT YET OBTAINED.
- Lightning regtest integration with LND/CLN: NOT YET IMPLEMENTED.
- Production security / real settlement: NOT CLAIMED.

External reviewers are invited to independently reproduce results and supply failing tests. No self-attestation should be described as outside verification.
