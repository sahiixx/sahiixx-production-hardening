/**
 * Cloudflare Worker — edge ingress for lead.received
 *
 * Aligns with contracts/event-envelope.json.
 * Accepts JSON body, builds canonical event, returns 202 + event.
 * Wire upstream to sahiixx-bus produce endpoint in production.
 */

export interface Env {
  BUS_URL?: string;
  BUS_TOKEN?: string;
}

const CHANNELS = new Set([
  "telegram",
  "web_form",
  "crm",
  "api",
  "voice",
  "whatsapp",
  "email",
  "internal",
]);

function utcNow(): string {
  return new Date().toISOString();
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== "POST") {
      return new Response(JSON.stringify({ error: "method_not_allowed" }), {
        status: 405,
        headers: { "content-type": "application/json" },
      });
    }

    let body: Record<string, unknown> = {};
    try {
      body = (await request.json()) as Record<string, unknown>;
    } catch {
      return new Response(JSON.stringify({ error: "invalid_json" }), {
        status: 400,
        headers: { "content-type": "application/json" },
      });
    }

    const channel = String(body.source_channel || "web_form");
    if (!CHANNELS.has(channel)) {
      return new Response(JSON.stringify({ error: "invalid_channel", channel }), {
        status: 400,
        headers: { "content-type": "application/json" },
      });
    }

    const tenantId = String(body.tenant_id || "default-tenant");
    const leadId = String(body.lead_id || crypto.randomUUID());
    const eventId = crypto.randomUUID();
    const correlationId = String(body.correlation_id || crypto.randomUUID());

    const event = {
      event_id: eventId,
      event_type: "lead.received",
      event_version: "1.0",
      occurred_at: utcNow(),
      ingested_at: utcNow(),
      tenant_id: tenantId,
      correlation_id: correlationId,
      causation_id: body.causation_id ? String(body.causation_id) : null,
      idempotency_key: String(body.idempotency_key || `lead.received:${leadId}`),
      source: {
        channel,
        system: "cloudflare-worker",
        actor_id: body.actor_id ? String(body.actor_id) : "worker",
      },
      agent: {
        agent_run_id: null,
        agent_id: null,
        workflow_id: "cloudflare-edge-ingress",
        model: null,
        cost_usd: 0,
        human_approved: false,
        tokens_in: 0,
        tokens_out: 0,
      },
      entities: {
        lead_id: leadId,
      },
      payload: {
        lead: {
          lead_id: leadId,
          ...body,
        },
      },
    };

    if (env.BUS_URL) {
      try {
        const res = await fetch(env.BUS_URL, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            ...(env.BUS_TOKEN ? { authorization: `Bearer ${env.BUS_TOKEN}` } : {}),
          },
          body: JSON.stringify(event),
        });
        if (!res.ok) {
          return new Response(
            JSON.stringify({ accepted: false, error: "bus_reject", status: res.status, event }),
            { status: 502, headers: { "content-type": "application/json" } }
          );
        }
      } catch (e) {
        return new Response(
          JSON.stringify({ accepted: false, error: "bus_unreachable", event }),
          { status: 502, headers: { "content-type": "application/json" } }
        );
      }
    }

    return new Response(JSON.stringify({ accepted: true, event }), {
      status: 202,
      headers: { "content-type": "application/json" },
    });
  },
};
