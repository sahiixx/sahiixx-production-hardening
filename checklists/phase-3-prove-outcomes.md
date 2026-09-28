# Phase 3 — Prove Outcomes

**Goal:** Cohort-based proof that AI assistance improves revenue, not just lead volume.

## Funnel metrics (instrument)

- [ ] lead acceptance rate
- [ ] duplicate rate
- [ ] qualification precision (vs human label sample)
- [ ] contact rate
- [ ] reply rate
- [ ] appointment rate
- [ ] show-up rate
- [ ] deal conversion rate
- [ ] revenue per lead
- [ ] cost per qualified lead
- [ ] cost per appointment
- [ ] agent-attributed revenue
- [ ] human override rate

## Cohort dashboard

- [ ] AI-assisted cohort vs human-only cohort
- [ ] before vs after automation
- [ ] per-source conversion
- [ ] per-agent conversion
- [ ] per-model cost and quality

## Data requirements

- [ ] Every revenue event joins on lead_id / correlation_id.
- [ ] Attribution fields on Deal (`ai_assisted`, primary agent_run_ids).
- [ ] Cost roll-up from agent.run.* events.

## Exit criteria

A single dashboard answers: “Does the AI path produce more revenue per lead at an acceptable cost, and where do humans still need to intervene?”
