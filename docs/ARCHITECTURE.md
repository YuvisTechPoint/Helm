# Architecture

## Overview

Dual Engine is a **modular monolith**: one deployable API with clear domain boundaries that can be extracted into services later.

```
┌─────────────────────────────────────────────────────────────┐
│  apps/dashboard (Next.js)          HTTP / WebSocket         │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│  src/api — FastAPI composition, webhooks, autopilot routes  │
├──────────────┬──────────────────────────────┬───────────────┤
│ src/youtube  │  src/acquisition             │  src/core     │
│ produce loop │  lead-to-client pipeline     │  platform     │
└──────┬───────┴──────────────┬───────────────┴───────┬──────┘
       │                      │                       │
       ▼                      ▼                       ▼
   Postgres/SQLite        Redis counters         Temporal
   Object store (S3)      Outbox → CRM           Workers
```

## Package boundaries

| Package | Responsibility |
|---------|----------------|
| `core` | Config, DB, vault, kill switches, circuit breakers, outbox, events, observability, Temporal gateway |
| `youtube` | Niche scout → research → script → gate → render → publish → metrics → optimize |
| `acquisition` | ICP → source → score → outreach → reply → qualify → close |
| `api` | HTTP surface, webhook ingress, lifespan/bootstrap |

## Data flow

### YouTube (per video)

```
Topic → Research → Script → Quality Gate → Voice → Render → Publish → Analytics → Diagnose → One-change optimize
```

State persisted in `topics`, `published_videos`, `metric_snapshots`, `optimization_changes`.

### Acquisition (per lead)

```
Source → Score → Outreach → Reply classify → Qualify → Proposal → Sign → Pay → Convert
```

State machines enforce valid transitions on `leads`, `deals`, `conversations`. Events go through transactional outbox.

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

## Deployment

```bash
docker compose up --build   # postgres, redis, minio, temporal, api, worker, dashboard
```

Scale workers independently: `docker compose up --scale worker=3`
