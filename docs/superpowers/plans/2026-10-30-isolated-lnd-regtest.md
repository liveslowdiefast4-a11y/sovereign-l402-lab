# Isolated LND Regtest Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fail-closed, publicly reproducible Bitcoin Core + two-LND regtest harness that proves real invoice and hold-HTLC lifecycle transitions without mainnet funds or production claims.

**Architecture:** A pinned Docker Compose topology exposes no host ports and runs only on an internal network. A bounded Bash driver performs node initialization, regtest mining, channel setup, ordinary payment, hold-invoice settle/cancel flows, sanitized evidence output, and unconditional cleanup.

**Tech Stack:** Docker Compose, Bitcoin Core, LND/lncli, Bash, Python 3 standard library, GitLab CI.

**Spec:** `docs/superpowers/specs/2026-10-30-isolated-lnd-regtest-design.md`

## Global Constraints

- Network must equal `regtest`; abort otherwise.
- No host ports, mainnet/testnet/signet, external peers, live funds, seeds, macaroons, TLS keys, invoices, or preimages in artifacts.
- Image tags are immutable version pins, never `latest`.
- Existing 12 synthetic tests remain separate and must stay green.
- Every failure tears down containers and volumes.

## Review Focus

- A misconfigured chain must abort before wallet or channel actions.
- A payment that reports command success but leaves the invoice non-terminal must fail.
- A hold invoice settled before `ACCEPTED` must fail.
- A canceled hold invoice that later settles must fail.
- Interrupted/failed runs must remove containers and ephemeral volumes.

---

### Task 1: Regtest topology and fail-closed preflight

**Files:**
- Create: `regtest/docker-compose.yml`
- Create: `regtest/run.sh`
- Create: `tests/test_regtest_contract.py`

**Interfaces:**
- Produces: `regtest/run.sh preflight`, exit 0 only when every node reports `regtest` and no host port is published.

- [ ] Write the failing contract test that invokes the preflight with controlled invalid network metadata and expects non-zero exit.
- [ ] Run `python -m unittest tests.test_regtest_contract -v`; expect failure because the harness does not exist.
- [ ] Add pinned internal-only services and the minimal preflight/cleanup harness.
- [ ] Re-run the contract test and the complete Python suite; expect all pass.

### Task 2: Channel bootstrap and ordinary invoice settlement

**Files:**
- Modify: `regtest/run.sh`
- Modify: `tests/test_regtest_contract.py`

**Interfaces:**
- Produces: sanitized event records `channel_active` and `invoice_settled`.

- [ ] Add a failing parser/contract test for missing or non-`SETTLED` invoice state.
- [ ] Run the focused test; expect the intended failure.
- [ ] Implement wallet initialization, generated-coin funding, peer connection, channel open/confirmation, invoice creation/payment, and state assertion.
- [ ] Run focused and full Python suites.

### Task 3: Real hold-invoice accepted/settled/canceled lifecycles

**Files:**
- Modify: `regtest/run.sh`
- Modify: `tests/test_regtest_contract.py`

**Interfaces:**
- Produces: sanitized events `hold_accepted`, `hold_settled`, `hold_canceled` from LND RPC states.

- [ ] Add failing tests that reject settle-before-accept, cancel-without-accept, and terminal-state mismatch.
- [ ] Run focused tests; expect failures for missing lifecycle logic.
- [ ] Implement add-hold-invoice, background payment, subscription/polling, settle, cancel, and terminal assertions with bounded timeouts.
- [ ] Run focused and full Python suites.

### Task 4: Reproducibility guide and evidence schema

**Files:**
- Create: `REGTEST.md`
- Create: `regtest/evidence.schema.json`
- Modify: `README.md`
- Modify: `VERIFY.md`
- Modify: `SECURITY.md`

**Interfaces:**
- Produces: one-command reproduction instructions and a secret-free evidence contract.

- [ ] Document prerequisites, exact command, resource expectations, teardown, expected events, falsification targets, and evidence limitations.
- [ ] Add an evidence validation test using a hand-written valid and invalid fixture.
- [ ] Run focused and full Python suites.

### Task 5: Hosted CI evidence without false success

**Files:**
- Modify: `.gitlab-ci.yml`
- Create: `regtest/ci.sh`

**Interfaces:**
- Produces: a CI job that runs the real-node harness or fails; never marks an unexecuted integration test as passed.

- [ ] Add a CI entry that requires a working Docker daemon, records exact image digests, runs the harness, validates evidence, and uploads only sanitized JSON/log summaries.
- [ ] Add unconditional cleanup and short timeouts.
- [ ] Push the feature branch to GitLab, inspect the exact pipeline/job logs, and record pass or blocker without retry camouflage.

### Task 6: Public review packet and private tracker

**Files:**
- Create: `REVIEWING.md`
- Create: `docs/grant/video-script.md`
- Create: `docs/grant/reference-request.md`

**Interfaces:**
- Produces: honest reviewer instructions, personalized outreach basis, exactly two-minute human narration target, and reference-letter request criteria.

- [ ] Publish the commit-bound reproduction/falsification guide and update issue #1 with exact evidence.
- [ ] Draft reviewer requests that state current limitations and ask for either reproduction or a counterexample.
- [ ] Draft reference requests that ask only people able to describe firsthand work; never ask for generic praise.
- [ ] Draft a timed 120-second script plus recording checklist; do not synthesize voice or fabricate endorsement.
- [ ] Update private GenieOS issue #49 with tested/blocked gates and the production-claim kill switch.

