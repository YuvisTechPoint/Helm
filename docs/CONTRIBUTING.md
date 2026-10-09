# Contributing

## Setup

```bash
git clone <repo>
cd youtube-channel-engine
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"
cp .env.example .env
```

## Development

```bash
# API only
python run_api.py

# API + dashboard
python scripts/dev.py

# Tests
pytest -q

# E2E smoke
python run_e2e.py
```

## Project conventions

1. **Imports** — flat package names from `src/`: `from core.X`, `from youtube.X`
2. **Paths** — use `core.paths.REPO_ROOT`, `DATA_DIR`, `ARTIFACTS_DIR`; never hardcode `./data` or `./artifacts`
3. **State** — topic transitions go through state machines in `topic_state.py`
4. **Events** — business events use `Outbox.publish()` for transactional consistency
5. **Providers** — no silent fakes in production; use `provider_plane.manifest()` for health
6. **Tests** — add tests in `tests/`; run `pytest -q` before PR

## Adding a feature

1. Domain logic in `src/youtube`
2. Shared infra in `src/core`
3. HTTP route in `youtube/http.py` or `src/api` for cross-cutting
4. Dashboard page in `apps/dashboard/app/`
5. Migration in `alembic/versions/` if schema changes

## Migrations

```bash
# Dev (auto create_all) or explicit:
RUN_MIGRATIONS=true python run_api.py
```

Production always sets `RUN_MIGRATIONS=true` or `ENGINE_MODE=production`.
