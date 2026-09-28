# Phase 4 — Scale Safely

**Goal:** Higher volume without losing control or correctness.

- [ ] vLLM or equivalent local inference for high-volume classify/extract.
- [ ] Hosted reasoning reserved for plan / judge / exceptions.
- [ ] Queue backpressure and circuit breakers on the bus and model router.
- [ ] Canary model releases (default 5% traffic) with automatic rollback on quality drop.
- [ ] Automated regression evaluations (agentic-harness evaluators) on every release.
- [ ] Incident replay from event history (by correlation_id or time range).
- [ ] Disaster-recovery restore tests (memory + ledger + bus) on a schedule.
- [ ] Load tests against the FirstCall → bus → agency-agents path.
