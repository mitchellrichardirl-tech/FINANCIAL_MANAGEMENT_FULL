# Finance Tracker

Personal finance app for importing bank statements, processing receipts, and
auto-categorizing transactions. Built for Irish banks (AIB, PTSB, Revolut).

## Features

- **Import statements** — upload CSV/Excel exports from your bank; transactions
  are parsed and stored
- **Process receipts** — upload photos; data is extracted and matched against
  existing transactions
- **Auto-categorize** — transactions get categorized based on merchant/party
  name, with manual override and party remapping

## Stack
- **Frontend** — React + Vite
- **Backend** — Flask + SQLite
- **Python** — managed with `uv`
- **Dev env** — VS Code devcontainer
- **Production** — Docker Compose

## Development

Open the repo in VS Code and **Reopen in Container**. The `postCreate.sh`
script handles dependency setup.

Run backend and frontend in separate terminals:

```bash
# Terminal 1 — backend (Flask dev server)
cd backend
uv run python src/run.py
# → http://localhost:5000
```

```bash
# Terminal 2 — frontend (Vite dev server)
cd frontend
npm run dev
# → http://localhost:5173
```

The SQLite database lives at `backend/data-dev/financial_data.db`.
Migrations run automatically when the backend starts.

---

## Production

Production runs from the `release/v1.0` branch via Docker Compose.

```bash
git checkout release/v1.0
docker compose up -d
```

The frontend is served through nginx; the backend runs behind it.

---

## Project layout

```
backend/src/
├── api/          HTTP layer — routes, middleware, services
├── categorizer/  Party extraction & transaction categorization
├── database/     Connection, schema, repositories (data access)
├── models/       Shared dataclasses
├── receipts/     Receipt image → structured data
├── statements/   Bank-specific statement parsers
└── utils/        Image processing, tabular file I/O, logging

frontend/src/
├── components/   Reusable UI primitives
├── features/     Feature slices: receipts/, statements/, transactions/
└── lib/          API client, error handling, logger
```

See [`backend/README.md`](backend/README.md) and
[`frontend/README.md`](frontend/README.md) for architecture details.

---

## Adding a new bank

Currently a developer task — user-facing config is planned.

1. Add a config module in `backend/src/statements/configs/`
2. Register it in `backend/src/statements/registry.py`

Use `aib.py` or `revolut.py` as a reference.