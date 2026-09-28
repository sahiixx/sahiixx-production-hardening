# SAHIIXX Repository Classification Matrix

**Date:** 2026-09-29  
**Rule:** Do not delete anything automatically. Mark first, then migrate or archive.

## Legend

| Label | Meaning |
|-------|---------|
| **canonical** | Production source of truth — invest here |
| **adapter** | Allowed to talk to the platform; must not own business state |
| **reference** | Upstream / experiment kept for patterns; not a dependency |
| **sandbox** | Personal or throwaway experiments |
| **archive-candidate** | Duplicate, empty, or superseded; freeze and later archive |

---

## Canonical (keep and harden)

| Repository | Role |
|------------|------|
| sahiixx-agency | Strategic control plane / platform ownership |
| agency-agents | Primary execution platform, agent registry, presets |
| agentic-harness | Shared runtime library (bounded execution, retries, guardrails, eval) |
| sahiixx-bus | Event transport (must gain production semantics) |
| sahiixx-titans-memory | Durable memory with business correctness policy |
| sahiixx-e2e | Release verification gate (Playwright / Prisma / Postgres) |
| sahiixx-os / sahiix-os | Operations UI |
| FirstCall + revenue systems (private) | Business domain owner — lead → deal → commission |

## Adapters (integrate, never own state)

| Repository | Role |
|------------|------|
| friday-os | Voice channel (LiveKit, MCP, Tauri) |
| hermes-agent | Operator / personal assistant channel |
| openclaw | Edge / cross-platform assistant (adapter only) |
| moltworker | Cloudflare Worker gateway / edge adapter |
| n8n | External automation adapter only |
| activepieces | External automation adapter only |
| motia | External automation adapter only |
| OpenWA | WhatsApp channel adapter |
| Agent-Reach | Research / enrichment adapter |
| lift, Dolphin, ocr-playbook-scanner | Document ingestion adapters |
| bifrost | Model gateway candidate |
| sahiixx-graph-sight | Graph visualization + future lineage API |

## Reference (keep, do not depend on in production)

| Repository | Notes |
|------------|-------|
| sovereign-swarm-v2 | Modular multi-agent OS — consolidate ideas into agency-agents |
| ruflo | Experiment / upstream fork |
| autogen | Upstream fork |
| swarm | Upstream fork |
| OpenManus and similar chatbot/workflow forks | Pattern reference |

## Archive-candidate / freeze

| Pattern | Action |
|---------|--------|
| sahiixx-bus-backup | Freeze; confirm no unique data then archive |
| Placeholder / empty repos (`7`, `H`, `Bag`, `Big`, `Bvvh`, `Hh`, etc.) | Mark archive-candidate |
| Duplicate sandbox forks of OpenManus, chatbot, workflow | Freeze |
| Any second implementation of the same orchestrator | Freeze |

## Classification process

For every remaining repository under github.com/sahiixx:

1. Open the repo.
2. Decide the single label above.
3. Add a top-level `STATUS.md` (or update README) with the label and one-line rationale.
4. If `archive-candidate`, also add a GitHub topic `archive-candidate` and disable issues/PRs if empty.

Do not run mass deletes. Revisit archive-candidates after Phase 1 inventory is complete.
