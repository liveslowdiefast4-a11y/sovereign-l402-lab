# Two-minute human-narrated video

Target delivery: 120 seconds exactly after editing. The applicant must record the voice; do not use synthetic narration.

**0:00–0:20**

I'm Daniel Marlin, building Sovereign L402 Lab: a public, experimental test harness for one narrow question—can automated services enforce a local Lightning spending budget while failing closed under contention, replay, and payment-state changes?

**0:20–0:45**

The repository is deliberately honest about its boundary. Its original Python tests model a SQLite millisatoshi reservation ledger, synthetic hold states, and L402 credential syntax. Those tests are reproducible, but they are not Lightning settlement, macaroon authentication, or production security.

**0:45–1:15**

The next evidence layer uses an isolated Bitcoin Core regtest and two LND nodes. It generates valueless test coins, opens a private channel, settles a real test invoice, then observes separate hold invoices move through accepted-to-settled and accepted-to-canceled states. The network exposes no host ports, rejects non-regtest chains, removes disposable wallets, and publishes only sanitized state evidence.

**1:15–1:40**

I am asking reviewers to falsify the work: reproduce the exact commit, submit a failing test, identify a protocol mismatch, or document where the claim exceeds the evidence. A hosted CI pass is independent compute, not independent human review. Mainnet and production claims remain prohibited.

**1:40–2:00**

Grant support would fund three to six months of public work: adversarial tests, LND and later Core Lightning interoperability, full specification-aligned authentication research, documented failures, and responsive maintenance. I will apply only after real-node evidence, genuine external review, and two authentic references exist.

## Recording checklist

- Record a real human voice; face may remain hidden.
- Show the public repository, exact commit, licence, CI job, and limitations—not private code.
- Record clean audio in a quiet room; no AI avatar or generated voice.
- Edit to exactly `02:00.000`; verify in two players after export.
- Use captions, but check they do not change or exaggerate claims.
- Host at an accessible link; test it logged out/private-window.
- Do not submit until two references, public evidence, and independent review are real.

