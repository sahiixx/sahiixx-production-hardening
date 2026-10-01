# DEPLOY.md — FirstCall Revenue API → Fly.io (step-by-step)

Complements `docs/DEPLOY.md` (generic runbook). This is the exact **Fly.io** sequence for the
`service/` FastAPI app. Artifacts prepared in this repo: `fly.toml` (root),
`.dockerignore` (root), and a PORT-configurable CMD in `service/Dockerfile.compose`
(existing repo container convention — no second deploy system introduced).

## What gets deployed

| Item | Value |
|------|-------|
| App | `service/` — FastAPI "SAHIIXX FirstCall Revenue API" (`uvicorn app:app`) |
| Entrypoint | `uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}` (cwd `/app/service`) |
| Container | `service/Dockerfile.compose` (python:3.12-slim, build context = repo root) |
| Port | 8080 (configurable via `PORT` env; `internal_port = 8080` in `fly.toml`) |
| Health check | `GET /health` → `{"status":"ok","service":"firstcall-revenue"}`; also `/docs`, `/v1/metrics` |
| Env vars | `SAHIIXX_DB` (DB path), `PORT`. **No secrets required to boot.** |
| Persistence | SQLite at `$SAHIIXX_DB` → Fly volume mounted at `/data` (`sahiixx_data`, 1 GB) |
| Auth | **None** — service ignores `Authorization` headers (see §6a for the client-side token) |

## Tool availability (checked 2026-10-01, this box)

| Tool | Status | Version / note |
|------|--------|----------------|
| flyctl | ❌ not installed | install in step 1 |
| docker | ⚠️ CLI only | 29.8.0 at `C:\Program Files\Docker\Docker`; **daemon not running** (start Docker Desktop only if you want a local image build — Fly's remote build does not need it) |
| railway | ❌ not installed | not needed (no railway config in repo) |
| wrangler | ❌ not on PATH | not installed globally; only via slow `npx` — needed for the Worker, not for this API |
| gh | ✅ | 2.101.0, authenticated as sahiixx |
| git | ✅ | clone of `sahiixx/sahiixx-production-hardening` |

## 0. Commit the deploy artifacts (repo currently has them uncommitted)

```powershell
cd C:\Users\sahii\sahiixx-production-hardening
git add fly.toml .dockerignore DEPLOY.md service/Dockerfile.compose
git commit -m "Add Fly.io deploy artifacts (fly.toml, DEPLOY.md, configurable PORT)"
# push when ready: git push origin main   (deploy itself works from the local clone, no push required)
```

## 1. Install + authenticate flyctl (once)

```powershell
winget install Fly.io.flyctl        # or: iwr https://fly.io/install.ps1 -UseBasicParsing | iex
# restart the shell so flyctl is on PATH, then:
fly auth login                       # opens browser OAuth
fly auth whoami                      # must print your account
```

## 2. Create app + volume (once)

```powershell
cd C:\Users\sahii\sahiixx-production-hardening
fly apps create sahiixx-firstcall
#  - if the name is globally taken: edit `app = ...` in fly.toml, then re-run with the new name
fly volumes create sahiixx_data --app sahiixx-firstcall --region fra --size 1
#  - same region as primary_region in fly.toml (default fra); if 1 GB rejected, use --size 3
```

## 3. Deploy (remote build — local Docker daemon NOT required)

```powershell
fly deploy
# builds service/Dockerfile.compose on Fly's servers, env from fly.toml,
# mounts sahiixx_data at /data, health-checks GET /health on :8080
fly status
fly logs
```

## 4. Optional — seed the 170k AED cohort proof into the live SQLite volume

```powershell
fly ssh console -C "cd /app/service && python demo_seed.py"
# expected tail: Commission total: 170,000 AED (AI 128,000 / Human 42,000)
```

## 5. Verify the public host

```powershell
curl.exe -s https://sahiixx-firstcall.fly.dev/health
# {"status":"ok","service":"firstcall-revenue"}
curl.exe -s https://sahiixx-firstcall.fly.dev/docs -o NUL -w "%{http_code}"     # 200
curl.exe -s "https://sahiixx-firstcall.fly.dev/v1/metrics?tenant_id=tenant-dubai-re"
```

## 6. Wire the OS — READ FIRST: `FIRSTCALL_URL` is NOT a sahiixx-os variable

**Verified 2026-10-01 against the live deploy and the source at `F:\repos\sahiixx-os`
(HEAD `a071c5f`, v4.3.0). Do not set `FIRSTCALL_URL` on the Pages project — nothing
reads it and it will silently do nothing.**

Evidence (source-wide grep of `api/ src/ scripts/ db/ mcp/`, excluding `node_modules`):
`0` hits for `FIRSTCALL`. The bundled `dist/boot.js` has `FIRSTCALL -> 0`,
`v1/leads -> 0`, `REVENUE_API -> 7`.

`sahiixx-os` has exactly **one** outbound revenue bridge, and it targets a
**different app**:

| Fact | Value |
|---|---|
| Env vars | `REVENUE_API_URL` + `REVENUE_API_KEY` (`api/lib/env.ts:142`, injected at `api/boot.ts:157`) |
| Client | `api/sovereign.ts` → `POST ${REVENUE_API_URL}/pipeline/process` |
| Auth header | `X-API-Key: <REVENUE_API_KEY>` |
| Gated on | **both** vars set, else every call returns `null` and the push is skipped |
| UI probe | `sahiixx.sovereignStatus` (public tRPC) |
| Call sites | `api/sahiixx-router.ts:305,319` (signal create) and `:481` (`ingestLead` mutation) |

### 6a. To point the OS at THIS service (`sahiixx-firstcall`)

`sovereign.ts` is hardcoded to `/pipeline/process`, which this service does not
have — its routes are `/health /v1/leads /v1/appointments /v1/deals /v1/commissions
/v1/metrics`. Setting `REVENUE_API_URL=https://sahiixx-firstcall.fly.dev` would
therefore make every signal-create push **404** (verified: `POST /pipeline/process
-> 404`). It needs a code change:

1. Add a `firstcall` client (mirror `api/sovereign.ts`): `POST ${FIRSTCALL_URL}/v1/leads`
   with `Idempotency-Key` + `X-Tenant-Id` headers and the `sovereign.ts` payload
   shape (`full_name`/`name`/`email`/`phone`/`budget_min`/`budget_max`/`source`).
2. Read it from `api/lib/env.ts` (+ a `setFirstcallUrl` setter) and inject it in
   `api/boot.ts` next to the `setRevenueApiUrl` pair.
3. Call it from the same two sites, wrapped in the existing `try/catch` so a
   downstream failure never breaks the local write.
4. Then set the Pages production env vars and redeploy.

### 6b. To wire the EXISTING bridge (different service, already deployed)

```text
REVENUE_API_URL = https://sovereign-revenue-os.fly.dev
REVENUE_API_KEY = <its X-API-Key>
```

Caveat verified 2026-10-01: `sovereign-revenue-os` is **live but its pipeline is
broken** — `GET /health` returns `{"status":"healthy","services":["redis"]}` while
both `POST /pipeline/process` and `GET /pipeline/health` return **HTTP 500**. So
wiring 6b produces `configured: true, error: "…500…"`. Fix that app first.

### 6c. Cloudflare access note

This box has **no Cloudflare credentials** — no `wrangler` on PATH, no
`CLOUDFLARE_API_TOKEN`, and `%APPDATA%\xdg.config\.wrangler` holds only
`metrics.json` + logs (no `config/default.toml` → no OAuth token). Env vars must
be set in the **dashboard**, or a token must be created and provided. Deploys are
**not** automated: `.github/workflows/ci.yml` only *smokes* the live Pages URL on
push to `main`; it never runs `wrangler pages deploy`. A redeploy is a manual
dashboard action (or a local `wrangler` run).

## 7. Confirm this service is healthy (and, if 6a was done, that the OS bridge is live)

```powershell
# a) service reachable with the headers the edge sends:
curl.exe -s -X POST https://sahiixx-firstcall.fly.dev/v1/leads -H "Content-Type: application/json" -H "Idempotency-Key: bridge-check-1" -H "X-Tenant-Id: default-tenant" -d "{\"full_name\":\"Bridge Check\",\"source\":\"web_form\"}"
#    -> HTTP 200, "duplicate": false first call, true on repeat (idempotency proven)

# b) end-to-end, ONLY after the 6a code change is deployed:
#    trigger a lead capture in the sahiixx-os UI, then:
curl.exe -s "https://sahiixx-firstcall.fly.dev/v1/metrics?tenant_id=default-tenant"
#    -> funnel_event_counts shows lead.received / lead.qualified from the Pages path

# c) does the OS consider its bridge configured? (public tRPC, no auth)
curl.exe -s https://sahiixx-os.pages.dev/api/trpc/sahiixx.sovereignStatus
#    -> {"available":false,...} means no bridge env vars are set (expected today)
```

## Rollback / ops

- Logs: `fly logs` · status: `fly status` · machines: `fly machines list`
- Rollback = redeploy a previous commit: `git checkout <sha> && fly deploy`
- Cost control: `fly machines stop <id>` (volume data survives)

## Known blockers on this machine

1. **flyctl not installed** → step 1 (blocking for deploy).
2. **Fly app name `sahiixx-firstcall` unverified** (global namespace; needs authenticated API) → step 2 handles rejection.
3. **Docker daemon stopped** → blocks only *local* `docker compose` smoke tests; Fly remote build unaffected. To test locally: start Docker Desktop, then `docker compose -f service/docker-compose.yml up -d --build`.
4. Local non-container smoke already verified (health 200, POST /v1/leads 200, /docs 200).
