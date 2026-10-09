# Owner Dashboard

Next.js control plane for the YouTube channel engine.

## Development

```bash
# From repo root — start API first
python run_api.py

# Dashboard
cd apps/dashboard
npm install
npm run dev
```

Open http://localhost:3000. Browser API calls proxy through `/api` → `http://127.0.0.1:8000`.

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | `/api` (browser) | Override API base |
| `API_PROXY_TARGET` | `http://127.0.0.1:8000` | Next.js dev proxy target |
| `NEXT_PUBLIC_API_KEY` | — | Optional `x-api-key` header |
