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
| Auth | **None** — service ignores `Authorization` headers (see FIRSTCALL_TOKEN note below) |

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

## 6. Wire sahiixx-os (Cloudflare Pages)

In the **sahiixx-os** Pages project → Settings → Environments → Production, set:

```text
FIRSTCALL_URL   = https://sahiixx-firstcall.fly.dev/v1/leads
FIRSTCALL_TOKEN =
```

- `FIRSTCALL_URL` must be the **full lead endpoint** (`…/v1/leads`) per this repo's Worker
  convention (`stubs/typescript/cloudflare-ingress.ts` treats `FIRSTCALL_URL` as the complete
  target). If the sahiixx-os frontend appends `/v1/leads` itself, set only
  `https://sahiixx-firstcall.fly.dev` — check its source first.
- `FIRSTCALL_TOKEN`: **the service has no auth layer** (verified — no token/bearer check in
  `service/`). Leave empty, or set a non-empty placeholder if the frontend requires a value to
  fire requests; it is not validated server-side. Adding bearer enforcement to `app.py` is
  follow-up hardening before real traffic.
- Save → redeploy Pages (Deployments → Retry deployment) so the var takes effect.

## 7. Confirm the OS bridge is active

```powershell
# a) endpoint reachable with the headers the edge sends:
curl.exe -s -X POST https://sahiixx-firstcall.fly.dev/v1/leads -H "Content-Type: application/json" -H "Idempotency-Key: bridge-check-1" -H "X-Tenant-Id: default-tenant" -d "{\"full_name\":\"Bridge Check\",\"source\":\"web_form\"}"
#    -> HTTP 200, "duplicate": false first call, true on repeat (idempotency proven)

# b) end-to-end: trigger a lead capture in the sahiixx-os UI, then:
curl.exe -s "https://sahiixx-firstcall.fly.dev/v1/metrics?tenant_id=default-tenant"
#    -> funnel_event_counts shows lead.received / lead.qualified from the Pages path
```

When (a) and (b) return data, `FIRSTCALL_URL` is live and the OS bridge is active.

## Rollback / ops

- Logs: `fly logs` · status: `fly status` · machines: `fly machines list`
- Rollback = redeploy a previous commit: `git checkout <sha> && fly deploy`
- Cost control: `fly machines stop <id>` (volume data survives)

## Known blockers on this machine

1. **flyctl not installed** → step 1 (blocking for deploy).
2. **Fly app name `sahiixx-firstcall` unverified** (global namespace; needs authenticated API) → step 2 handles rejection.
3. **Docker daemon stopped** → blocks only *local* `docker compose` smoke tests; Fly remote build unaffected. To test locally: start Docker Desktop, then `docker compose -f service/docker-compose.yml up -d --build`.
4. Local non-container smoke already verified (health 200, POST /v1/leads 200, /docs 200).
