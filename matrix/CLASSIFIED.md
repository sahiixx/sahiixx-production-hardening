# Classified repositories (STATUS.md applied)

Updated: 2026-09-29

## canonical

| Repo | Role |
|------|------|
| sahiixx-production-hardening | Contracts + revenue service |
| agentic-harness | Shared runtime + model_router + event_envelope |
| agency-agents | Primary execution platform |
| sahiixx-bus | Event transport |
| sahiixx-agency | Strategic control plane |
| sahiixx-e2e | Release gate |
| sahiixx-os | Operations UI |
| FirstCall | Revenue domain owner |

## adapter

| Repo | Role |
|------|------|
| moltworker | Cloudflare edge gateway |
| ocr-playbook-scanner | Document ingestion |
| friday-tony-stark | Voice channel |
| sahiix-proxy | Edge proxy |
| agentic-harness-integration | Harness consumer layer |
| integrations | External connectors |

## reference

| Repo | Role |
|------|------|
| sovereign-revenue-os | E2E RE OS experiment → use FirstCall |
| sovereign-agents | Pipeline microservices experiment |
| sovereign-prompt-pack | Prompt pack → agency-agents |
| nexus-buyer-recovery | Scoring experiment |
| codex-self | Identity/memory experiment |
| lazy-ai-ops | Revenue-button experiment |

## sandbox

| Repo | Role |
|------|------|
| moltbot-sandbox | OpenClaw CF sandbox |
| orchestrator | Private working |
| workflows | Private working |

## archive-candidate

| Repo | Notes |
|------|-------|
| nextjs-boilerplate | Already archived on GitHub |
| myproject | Already archived |
| mbjv | Already archived |

## Production rule

Only **canonical** repos may own production control planes or revenue state.
Adapters emit events; references/sandboxes feed patterns upward — never the reverse.
