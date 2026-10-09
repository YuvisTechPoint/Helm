# Automation & workflow maintenance

All automation flows through a single maintained surface. Do not add workflows without
updating the registry and sync handler.

## Maintenance contract

| Component | File | Responsibility |
|-----------|------|----------------|
| **Registry** | `core/workflow_registry.py` | Canonical list of every workflow |
| **Sync runner** | `youtube/orchestrator.py` → `run_sync_workflow()` | In-process fallback when Temporal is down |
| **Daily cycle** | `core/automation.py` → `run_daily()` | YouTube daily automation |
| **Background tick** | `core/autopilot.py` | Sweep + outbox every 15m; full daily once per UTC day |
| **Temporal worker** | `youtube/worker.py` | Registers all workflows + activities |
| **Schedules** | `youtube/schedules.py` | Cron definitions |

## Workflow inventory

`GET /autopilot/workflows` returns the live registry.

CI test `test_every_workflow_has_sync_handler` fails if any registered workflow lacks a sync path.

## Running automation

| Action | Command / endpoint |
|--------|-------------------|
| Background loop | Automatic on API start (15 min interval) |
| Manual daily | `POST /autopilot/daily` or dashboard Autopilot page |
| Force tick | `POST /autopilot/tick` |
| Register crons | `POST /autopilot/bootstrap` |
| Full dev stack | `make dev` (API + worker + dashboard) |
| API only | `make dev-lite` or `START_WORKER=0 make dev` |
| Production stack | `make docker-up` |

## Adding a new workflow

1. Define Temporal workflow in `youtube/workflows.py`
2. Add activity handlers
3. Register on worker in `youtube/worker.py`
4. Add `WorkflowSpec` to `core/workflow_registry.py`
5. Add sync branch in `run_sync_workflow()`
6. Wire schedule or API trigger
7. Run `pytest tests/test_automation_workflows.py`
