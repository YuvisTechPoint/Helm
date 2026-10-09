# Platform configuration

YouTube Channel Engine separates **secrets** (`Settings` / `.env`) from **posture** (`PlatformConfig`).

## Layers

| Layer | Module | Purpose |
|-------|--------|---------|
| Secrets & URLs | `core.config.Settings` | API keys, DSNs, provider credentials |
| Platform posture | `core.platform.PlatformConfig` | Tier, resilience, security, observability |
| Provider modes | `core.provider_plane` | Live vs simulated per integration |
| Readiness | `core.readiness` | Deep dependency probes for `/ready` |

## Runtime tiers

| Tier | `ENGINE_MODE` | Simulated providers | API key | Temporal |
|------|---------------|---------------------|---------|----------|
| Dev | `dev` | Allowed | Optional | Optional |
| Staging | `staging` | Blocked for missing creds | Required | Recommended |
| Production | `production` | Blocked | Required | Required |

Tier-specific defaults (circuit thresholds, timeouts) are applied in `build_platform()`.

## Endpoints

| Path | K8s probe | Behavior |
|------|-----------|----------|
| `/live` | Liveness | Process is up |
| `/ready` | Readiness | DB + cache + providers (+ Temporal in prod) |
| `/health` | Ops dashboard | Full component status |
| `/platform` | CI / GitOps | Non-secret platform manifest |
| `/metrics` | Prometheus | In-process counters |

## Operations

```bash
# JSON logs (production)
LOG_FORMAT=json LOG_LEVEL=INFO python run_api.py

# Auto-migrate on boot (staging/prod)
RUN_MIGRATIONS=true ENGINE_MODE=staging python run_api.py

# Full stack
docker compose up --build
docker compose up --scale worker=3
```

## Structured logging

Every log line includes `tenant_id` and `request_id` from `core.context` ContextVars.
Use `LOG_FORMAT=json` for log aggregation (Datadog, CloudWatch, Loki).

## Future: request-scoped sessions

Current design uses one SQLAlchemy session per API process with per-request rollback.
Production hardening path: migrate repositories to `scoped_session` per request (documented in ARCHITECTURE.md).
