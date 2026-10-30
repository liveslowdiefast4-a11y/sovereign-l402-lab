# Security policy

This is an experiment. No payments, wallets, secrets or consumer-facing payment services. Never paste a private key, a live invoice, customer data or a cloud token in a public issue.

A local budget invariant does not prove financial authority. The preimage-hash helper MUST NOT be used to authorize a payment or grant access.

The regtest harness must never be repointed. It publishes no host ports, rejects any chain other than `regtest`, uses generated coins only, removes ephemeral volumes, and forbids seeds, macaroons, payment requests, preimages, or private keys in evidence artifacts.

For a vulnerability with sensitive impact, use private vulnerability reporting if enabled, or contact the repository owner privately via GitHub profile before disclosing confidential details.
