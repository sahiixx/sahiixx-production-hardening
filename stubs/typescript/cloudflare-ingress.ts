/**
 * Cloudflare Worker — edge ingress → FirstCall / bus
 *
 * Env:
 *   FIRSTCALL_URL  e.g. https://api.example.com/v1/leads   (preferred)
 *   BUS_URL        e.g. https://bus.example.com/v1/events
 *   BUS_TOKEN      optional bearer
 */

export interface Env {
  FIRSTCALL_URL?: string;
  BUS_URL?: string;
  BUS_TOKEN?: string;
}

const CHANNELS = new Set([
  "telegram", "web_form", "crm", "api", "voice", "whatsapp", "email", "internal",
]);

function utcNow(): string {
  return new Date().toISOString();
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "GET") {
      return new Response(
        JSON.stringify({
          service: "sahiixx-edge-ingress",
          firstcall: Boolean(env.FIRSTCALL_URL),
          bus: Boolean(env.BUS_URL),
        }),
        { status: 200, headers: { "content-type": "application/json" } }
      );
    }

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

    const channel = String(body.source_channel || body.source || "web_form");
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
    const idempotencyKey = String(
      body.idempotency_key || request.headers.get("Idempotency-Key") || `lead.received:${leadId}`
    );

    const target = env.FIRSTCALL_URL || env.BUS_URL;
    if (target) {
      try {
        const isFirstCall = Boolean(env.FIRSTCALL_URL);
        const payload = isFirstCall
          ? {
              lead_id: leadId,
              tenant_id: tenantId,
              full_name: body.full_name || body.name,
              name: body.name,
              email: body.email,
              phone: body.phone,
              transaction_type: body.transaction_type || "buy",
              budget_min: body.budget_min,
              budget_max: body.budget_max,
              currency: body.currency || "AED",
              contact_consent: body.contact_consent !== false,
              marketing_consent: Boolean(body.marketing_consent),
              source: channel,
              cohort: body.cohort || "ai_assisted",
            }
          : {
              event_id: eventId,
              event_type: "lead.received",
              event_version: "1.0",
              occurred_at: utcNow(),
              ingested_at: utcNow(),
              tenant_id: tenantId,
              correlation_id: correlationId,
              causation_id: body.causation_id ? String(body.causation_id) : null,
              idempotency_key: idempotencyKey,
              source: {
                channel,
                system: "cloudflare-worker",
                actor_id: body.actor_id ? String(body.actor_id) : "worker",
              },
              entities: { lead_id: leadId },
              payload: { lead: { lead_id: leadId, ...body } },
            };

        const res = await fetch(target, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            "Idempotency-Key": idempotencyKey,
            "X-Tenant-Id": tenantId,
            ...(env.BUS_TOKEN ? { authorization: `Bearer ${env.BUS_TOKEN}` } : {}),
          },
          body: JSON.stringify(payload),
        });

        const text = await res.text();
        let data: unknown = text;
        try {
          data = JSON.parse(text);
        } catch {
          /* keep */
        }

        if (!res.ok) {
          return new Response(
            JSON.stringify({ accepted: false, error: "upstream_reject", status: res.status, data }),
            { status: 502, headers: { "content-type": "application/json" } }
          );
        }

        return new Response(
          JSON.stringify({ accepted: true, via: isFirstCall ? "firstcall" : "bus", data }),
          { status: 202, headers: { "content-type": "application/json" } }
        );
      } catch (e) {
        return new Response(
          JSON.stringify({ accepted: false, error: "upstream_unreachable", detail: String(e) }),
          { status: 502, headers: { "content-type": "application/json" } }
        );
      }
    }

    return new Response(
      JSON.stringify({
        accepted: true,
        via: "local_only",
        warning: "Set FIRSTCALL_URL or BUS_URL for production",
        event: {
          event_id: eventId,
          event_type: "lead.received",
          tenant_id: tenantId,
          idempotency_key: idempotencyKey,
          entities: { lead_id: leadId },
        },
      }),
      { status: 202, headers: { "content-type": "application/json" } }
    );
  },
};
