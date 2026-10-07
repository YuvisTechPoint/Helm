# Owner Dashboard

Control plane for the **Dual Engine** monorepo — Faceless YouTube + Lead-to-Client acquisition.

## Quick start

```bash
# Terminal 1 — API
python run_api.py

# Terminal 2 — Dashboard
cd apps/owner-web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` | FastAPI backend URL |

## Pages

| Route | Purpose |
|-------|---------|
| `/` | Dashboard overview — funnel, spend, YouTube status |
| `/profile` | Service profile onboarding + approval |
| `/youtube` | YouTube engine state and exceptions |
| `/health` | Mailbox send caps and deliverability |
| `/threads` | Read-only conversation threads |
| `/money` | Spend and CPCC metrics |
| `/experiments` | Outreach A/B variants |
| `/escalations` | Human-in-the-loop queue |
| `/actions` | Run engine pipelines |

## Design

- Dark control-plane theme with amber accent (`#f0a202`)
- No UI framework dependency — pure CSS custom properties
- Server components for data fetching, client components for forms and actions

## Production

```bash
npm run build
npm start
```

Serve behind the same origin as the API or set `NEXT_PUBLIC_API_URL` to your deployed API.
