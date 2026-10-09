# YouTube Channel Engine

Autonomous **faceless YouTube** production platform — niche scouting through private publish, analytics, and one-change optimisation.

## Repository layout

```
youtube-channel-engine/
├── src/                    # Python packages (single install root)
│   ├── core/               # Shared platform: config, DB, outbox, Temporal, vault
│   ├── youtube/            # YouTube engine (niche → publish → optimize)
│   └── api/                # FastAPI composition layer
├── apps/
│   └── dashboard/          # Next.js owner control plane
├── scripts/                # CLI entrypoints (api, worker, e2e)
├── tests/                  # Integration & unit tests
├── alembic/                # Database migrations
├── docs/                   # PRDs and engineering notes
├── data/                   # Local SQLite (dev only, gitignored)
└── artifacts/              # Rendered media (gitignored)
```

## Quick start

```bash
pip install -e ".[dev]"
cp .env.example .env

# API + dashboard together
python scripts/dev.py

# Or separately:
python run_api.py              # http://127.0.0.1:8000
cd apps/dashboard && npm i && npm run dev   # http://localhost:3000

# Worker (optional — requires Temporal)
python run_worker.py

# Full E2E smoke
python run_e2e.py
```

Or use installed CLI commands after `pip install -e .`:

```bash
youtube-engine-api
youtube-engine-worker
youtube-engine-e2e
```

## Configuration

Copy `.env.example` → `.env`. Key variables:

| Variable | Purpose |
|----------|---------|
| `ENGINE_MODE` | `dev` / `staging` / `production` |
| `DATABASE_URL` | Postgres in prod; SQLite auto in dev |
| `TEMPORAL_ADDRESS` | Durable workflows (`localhost:7233`) |
| `API_KEY` | Required in production |
| `CHANNEL_ID` | Logical channel tenant id (default `local`) |

## Docker

```bash
docker compose up --build
```

Services: API `:8000`, dashboard `:3000`, Temporal UI `:8080`.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Contributing](docs/CONTRIBUTING.md)
- [YouTube engine PRD](docs/prd/youtube-engine.md)
- [Platform engineering](docs/engineering/PLATFORM.md)
- [Automation](docs/engineering/AUTOMATION.md)

## Tests

```bash
pytest -q
```
