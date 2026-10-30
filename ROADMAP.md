# 12-week proposed open-source roadmap (not funded)

Phase A: adversarial property and fuzz tests for integer edge cases, SQLite crash/restart and L402 error handling; publish every reproducible failure.
Phase B: opt-in ephemeral Bitcoin/Lightning regtest integration, with explicit node mocks vs real-node validation and no real funds.
Phase C: genuine independent technical review, repaired findings, source-bound signed test reports, and public documentation.

**Hard stop:** do not accept deposits, generate live-network Lightning hold invoices, authorize paid access, or manage production preimage secrets with this prototype. Disposable regtest-only hold invoices are permitted solely inside the isolated harness. The full spec requires verified macaroons, correct BOLT11 invoice/payment-hash binding, realistic HTLC state management, timeout controls and node restart recovery.
