# Architecture

## Overview

YouTube Channel Engine is a **modular monolith**: one deployable API with a clear YouTube domain boundary that can be extracted into services later.

```
┌─────────────────────────────────────────────────────────────┐
│  apps/dashboard (Next.js)          HTTP                       │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│  src/api — FastAPI composition, autopilot routes              │
├──────────────────────────────┬──────────────────────────────┤
│ src/youtube                  │  src/core                     │
│ produce loop                 │  platform                     │
└──────────────┬───────────────┴───────────────┬───────────────┘
               │                               │
               ▼                               ▼
           Postgres/SQLite                 Temporal
           Object store (S3)               Workers
           Redis (quota)
```

## Package boundaries

| Package | Responsibility |
|---------|----------------|
| `core` | Config, DB, vault, kill switches, circuit breakers, outbox, events, observability, Temporal gateway |
| `youtube` | Niche scout → research → script → gate → render → publish → metrics → optimize |
| `api` | HTTP surface, lifespan/bootstrap |

## Data flow

### YouTube (per video)

```
Topic → Research → Script → Quality Gate → Voice → Render → Publish → Analytics → Diagnose → One-change optimize
```

State persisted in `topics`, `published_videos`, `metric_snapshots`, `optimization_changes`.

## Runtime modes

| Mode | Temporal | Providers | API key |
|------|----------|-----------|---------|
| `dev` | Optional (in-process fallback) | Simulated when no credentials | Optional |
| `staging` | Required | Mixed | Required |
| `production` | Required | Live only | Required |

## Key paths

All runtime paths resolve from `core.paths` — never depend on process CWD:

- `DATA_DIR` — SQLite, local state
- `ARTIFACTS_DIR` — rendered media
- `REPO_ROOT` — alembic.ini, docs

## Automation maintenance

All workflows are registered in `core/workflow_registry.py` and executed via
`core/automation.py` (daily/tick), Temporal worker, or sync fallback.
See [engineering/AUTOMATION.md](engineering/AUTOMATION.md).

## Platform configuration

Runtime posture is resolved in `core.platform.PlatformConfig` — tier-specific resilience,
security, and observability settings separate from secrets in `.env`.

See [engineering/PLATFORM.md](engineering/PLATFORM.md) for probes, logging, and tier matrix.

## Deployment

```bash
docker compose up --build   # postgres, redis, minio, temporal, api, worker, dashboard
```

Scale workers independently: `docker compose up --scale worker=3`

| Probe | Path | Use |
|-------|------|-----|
| Liveness | `/live` | Process alive |
| Readiness | `/ready` | Dependencies OK (503 when not) |
| Manifest | `/platform` | CI/GitOps — non-secret config |
