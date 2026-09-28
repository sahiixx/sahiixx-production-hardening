# Phase 1 — Establish Truth

**Goal:** One source of truth for ownership, schemas, events, and routing.  
**Exit criteria:** Every repo classified, FirstCall schemas locked, event envelope and model router published, CRM SoT identified.

## 1. Repository inventory & classification

- [ ] Enumerate all repositories under `github.com/sahiixx` (use GitHub API / pagination until complete).
- [ ] For each repo apply exactly one label: `canonical` | `adapter` | `reference` | `sandbox` | `archive-candidate`.
- [ ] Add `STATUS.md` (or equivalent) to each repo with label + rationale.
- [ ] Freeze archive-candidates (disable issues if empty, add topic).
- [ ] Publish the classification matrix (see `matrix/repo-classification.md`).

## 2. Identify source of truth

- [ ] Locate the production FirstCall database and CRM system of record.
- [ ] Document connection strings, ownership, backup, and restore procedure (private).
- [ ] Confirm no other system is allowed to write lead / appointment / deal / commission state.

## 3. Lock revenue schemas

- [ ] Adopt `schemas/lead-appointment-deal.json` (or refine and version it).
- [ ] Publish JSON Schema (or Prisma / SQL equivalent) in a shared package or FirstCall repo.
- [ ] Map existing tables/columns to the canonical fields; record gaps.
- [ ] Define migration plan for any divergent fields.

## 4. Canonical event envelope

- [ ] Adopt `contracts/event-envelope.json` as v1.0.
- [ ] Register event types and versioned payload schemas.
- [ ] Instrument FirstCall API and agency-agents to emit events using the envelope.
- [ ] Reject any produce that fails schema or missing required fields.

## 5. Model routing interface

- [ ] Adopt `contracts/model-routing.yaml`.
- [ ] Implement the resolve(task_class, context) → ModelBinding interface inside agentic-harness.
- [ ] Remove hardcoded Azure deployment names from application code.
- [ ] Wire cost and model identity into every agent.run.* event.

## 6. Documentation & ownership

- [ ] Update sahiixx-agency README with the production path diagram.
- [ ] Assign CODEOWNERS for each canonical repo.
- [ ] Announce the freeze of competing orchestrators to the team.

**Done when:** A single dashboard or doc can answer “Who owns lead state?”, “What is the event contract?”, and “How is a model chosen for classification?”.
