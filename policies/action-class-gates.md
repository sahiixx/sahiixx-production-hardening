# SAHIIXX Action Class & Remediation Gates

**Owner:** agency-agents + agentic-harness  
**Version:** 1.0  

Automatic remediation is safe only when every action is classified and gated.

## Action classes

| Class | Examples | Policy | Audit |
|-------|----------|--------|-------|
| **Read-only** | Health check, metrics query, log fetch, state inspection | Automatic | Optional (sampled) |
| **Reversible** | Restart worker, clear temporary queue, scale replica, rotate non-secret config | Automatic with audit | Mandatory |
| **Risky** | Change routing weights, canary percentage, feature flag, model slot mapping | Approval required (human or dual-control) | Mandatory + notification |
| **Irreversible** | Delete records, send mass outreach, change deal state, record commission, contact customer | Human approval required; never automatic | Mandatory + immutable ledger entry |

## Watchdog / self-healing rules

1. The watchdog may only execute **Read-only** and **Reversible** actions without a human.
2. Any action that mutates revenue data (`lead`, `appointment`, `deal`, `commission`, `payment`) or contacts a customer is **Irreversible** by definition.
3. Risky actions require an approval token issued by a designated human or a dual-control process.
4. Every automatic remediation emits a `system.remediation` event with:
   - action class
   - target
   - before/after state
   - triggering condition
   - actor (`watchdog` + version)

## Implementation sketch (agentic-harness)

```python
# Pseudocode — enforce at the tool-dispatcher boundary
ACTION_CLASS = {
    "health.check": "read_only",
    "worker.restart": "reversible",
    "routing.set_weights": "risky",
    "lead.delete": "irreversible",
    "outreach.send": "irreversible",
    "deal.update_status": "irreversible",
}

def dispatch(tool, args, context):
    cls = ACTION_CLASS[tool]
    if cls == "irreversible":
        require_human_approval(context)
    elif cls == "risky":
        require_approval_or_dual_control(context)
    # reversible & read_only proceed with audit
    return execute(tool, args)
```

## Forbidden

- Watchdog rewriting lead status, qualification score, or deal state.
- Automatic mass messaging of any kind.
- Silent model or routing changes without canary + audit.
