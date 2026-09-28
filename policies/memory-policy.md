# SAHIIXX Memory Policy — Business Correctness

**Owner:** `sahiixx-titans-memory`  
**Version:** 1.0  
**Status:** Authoritative  

## Core rule

> Never let an unverified model inference overwrite a verified CRM value.

Memory is not a flat key-value store. Every write must declare its type, source, confidence, and verification status.

## Memory types

| Type | Meaning | Can overwrite verified CRM? | Default retention |
|------|---------|-----------------------------|-------------------|
| `crm_fact` | Value pulled from or written to the system-of-record CRM | Yes (is the source of truth) | Indefinite until CRM deletes |
| `verified_human` | Explicit human instruction or correction | Yes | Indefinite |
| `lead_state` | Current workflow status of a lead | Only via official state machine | Until lead archived + 90d |
| `interaction` | Historical message / call / event | No | 2 years |
| `preference_inferred` | Model-derived preference | No | 180 days or until contradicted |
| `hypothesis` | Speculative model output | No | 30 days |
| `procedure` | Agent playbook / skill | No (versioned) | Until superseded |
| `system` | Runtime metadata | N/A | 90 days |

## Required fields on every memory record

```text
memory_id          UUID
tenant_id          string          # isolation boundary
subject_id         string          # lead_id | contact_id | agent_id | ...
memory_type        enum (above)
content            object | string
source             { system, actor_id, event_id? }
confidence         float 0.0–1.0
verified_by        null | "crm" | "human:{id}" | "system"
created_at         ISO-8601
expires_at         ISO-8601 | null
supersedes         memory_id | null
deletion_status    "active" | "soft_deleted" | "hard_deleted" | "legal_hold"
provenance         { model?, prompt_hash?, retrieval_refs? }
```

## Write rules

1. **Conflict resolution**
   - `crm_fact` and `verified_human` always win over inferred types.
   - Within the same type, higher `confidence` + newer `created_at` wins unless an explicit `supersedes` link exists.
   - A write that would overwrite a higher-precedence type is rejected and emitted as `memory.write_rejected`.

2. **Tenant isolation**
   - Every query and write is scoped by `tenant_id`. Cross-tenant reads are impossible without a break-glass audit trail.

3. **Deletion & retention**
   - Soft-delete is the default. Hard-delete only after legal/compliance review or automated expiry.
   - `legal_hold` freezes all deletion paths.

4. **Provenance**
   - Any memory written by a model must record `model`, `agent_run_id`, and optional `prompt_hash`.
   - Retrieval must be able to answer: “Why does the system believe X about this lead?”

5. **Read path**
   - Prefer the highest-precedence, non-expired, non-deleted record per `(tenant_id, subject_id, key)`.
   - Surface `confidence` and `verified_by` to the calling agent so it can decide whether to act or ask for confirmation.

## Integration contract

- Writers: FirstCall API, agency-agents (via agentic-harness), human operators.
- Readers: agency-agents, hermes-agent, friday-os, analytics.
- All writes go through the memory service; direct DB writes are forbidden.

## Anti-patterns (forbidden)

- Treating model output as CRM truth.
- Shared global memory across tenants.
- Silent overwrites without `supersedes` or audit event.
- Infinite retention of `hypothesis` or `preference_inferred`.
