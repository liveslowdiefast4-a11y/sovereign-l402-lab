# Isolated real-node reproduction

## Claim boundary

This optional harness tests one private Bitcoin Core regtest and two LND nodes. It observes an active channel, ordinary invoice settlement, hold-invoice acceptance then settlement, and a separate hold-invoice acceptance then cancellation. It does **not** test mainnet, CLN, full L402 authentication, macaroon caveats, production security, or human independence.

## Prerequisites and command

- Docker Engine with Compose v2
- Bash, Git and Python 3.10+
- Approximately 4 GB RAM, 5 GB free disk, and up to 20 minutes

```bash
bash regtest/run.sh
```

The script pulls pinned images, creates an internal network with no host ports, generates valueless regtest blocks, initializes disposable wallets, opens a private channel, runs the six required lifecycle observations, validates `regtest-evidence.json`, then removes containers and volumes even after failure.

## Required evidence

The validator accepts exactly the required semantic observations: `channel_active=ACTIVE`, `invoice_settled=SETTLED`, two separate `ACCEPTED` hold states, `hold_settled=SETTLED`, and `hold_canceled=CANCELED`. Run:

```bash
python -m sovereign_l402.evidence regtest-evidence.json
```

Evidence is rejected when the network is not `regtest`, the result is not `PASS`, a required state is absent/wrong/duplicated, or a secret-bearing field appears.

## Falsification targets

- Change either node to any non-regtest chain; the run must abort before funding.
- Prevent the channel becoming active; no evidence artifact may claim a pass.
- Settle or cancel before the invoice reaches `ACCEPTED`; the run must fail.
- Corrupt a terminal state in the artifact; the validator must reject it.
- Interrupt the run; `docker compose ... down --volumes` must leave no project containers or volumes.

Report a reproducible counterexample on issue #1. Never attach wallet seeds, macaroons, TLS keys, payment requests, preimages, or live invoices.

