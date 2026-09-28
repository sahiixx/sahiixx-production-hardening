# sahiixx-bus Production Requirements

**Current state:** FastAPI + Pydantic service  
**Target state:** Durable event bus with production delivery guarantees  

## Must-have capabilities

| Capability | Requirement |
|------------|-------------|
| Durable storage | Events survive process restarts; stored in Postgres or equivalent with retention policy |
| Event versioning | Every event carries `event_version`; consumers declare supported versions |
| Idempotency | `idempotency_key` (or derived from `event_id`) enforced; duplicates rejected or de-duplicated within retention window |
| Consumer offsets | At-least-once delivery with explicit ack; consumers own their offset |
| Retry policy | Configurable exponential backoff + max attempts; dead-letter after exhaustion |
| Dead-letter queue (DLQ) | Failed events after retries land in DLQ with reason and original payload |
| Replay | Ability to re-emit events from a point-in-time or by correlation_id / tenant_id |
| Ordering | Per-partition / per-correlation_id ordering guarantee for related events |
| Correlation & causation | Required fields on every envelope (`correlation_id`, `causation_id`) |
| Tenant isolation | All queries and subscriptions scoped by `tenant_id`; no cross-tenant leakage |
| Inter-service auth | mTLS or signed JWT between producers/consumers and the bus |
| Schema compatibility | Registry of event_type → JSON Schema; produce-time and consume-time validation |
| Backpressure | Publisher throttling when consumers lag beyond threshold |
| Delivery metrics | Published, delivered, failed, DLQ, lag, end-to-end latency per event_type |

## Canonical event envelope

See `contracts/event-envelope.json`. All producers MUST conform.

## Recommended implementation path

1. Keep the existing FastAPI surface as the produce/consume HTTP API.
2. Add a durable store (Postgres + LISTEN/NOTIFY or Outbox pattern, or migrate to NATS JetStream / Redpanda / Kafka if volume demands it).
3. Implement the offset + ack + DLQ semantics on top of the store.
4. Register every event schema in a versioned registry (can live in this repo or a dedicated `sahiixx-schemas` package).
5. Expose replay and lag metrics via the existing observability stack.

## Anti-patterns

- Fire-and-forget HTTP posts with no persistence.
- Relying on in-memory queues for revenue events.
- Letting n8n / Activepieces / Motia own the primary event stream for FirstCall workflows.
