# Backend

Flask API for the finance tracker. Handles statement imports, receipt
processing (OCR), transaction-to-party matching, and data persistence.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  api/routes/       Flask blueprints         │  HTTP + orchestration
├─────────────────────────────────────────────┤
│  api/services/     Parallel batch jobs      │  (receipts only)
├─────────────────────────────────────────────┤
│  categorizer/      Domain logic             │
│  receipts/         (Flask-independent)      │
│  statements/                                │
├─────────────────────────────────────────────┤
│  database/repositories/   Data access       │
├─────────────────────────────────────────────┤
│  SQLite                                     │
└─────────────────────────────────────────────┘
         models/ ──── shared across all layers
```

**Routes** currently handle both HTTP concerns and most orchestration logic.
There is no general service layer — `api/services/` exists specifically for
parallel batch processing of receipts. Extracting a proper service layer is
a known refactoring opportunity.

**Domain modules** (`categorizer/`, `receipts/`, `statements/`) have no Flask
dependencies and can be driven from a notebook or script.

**Repositories** are the only code that touches the database. One repository
per entity, all inheriting from `repositories/base.py`.

---

## Domain model

Transactions are organized through a four-level hierarchy:

```
Party  →  Type  →  Sub-category  →  Category
```

A **party** is a merchant/counterparty (e.g. "Tesco Metro Rathmines").
Each party is assigned a **type**, which rolls up into a **sub-category**,
which rolls up into a **category**.

The backend automatically matches transactions to parties. The user assigns
parties to types/sub-categories/categories via the frontend.

---

## Data flows

### Statement import
```
CSV/Excel upload
  → utils/tabular_files/readers.py      (read into rows)
  → statements/registry.py              (pick config by bank)
  → statements/configs/<bank>.py        (map columns → Transaction)
  → repositories/transactions.py        (persist)
  → categorizer/                        (match transaction → party)
```

### Receipt processing
```
Image upload
  → utils/image_processor.py            (normalize/preprocess)
  → Tesseract OCR
  → receipts/receipt_extractor.py       (parse text → Receipt model)
  → repositories/receipts.py            (persist)
  → match against existing transactions
```
Progress is streamed to the frontend via Server-Sent Events
(`api/utils/sse.py`).

### Party matching
```
Transaction description
  → categorizer/party_extractor.py      (extract party name from text)
  → categorizer/party_matcher.py        (fuzzy-match against known parties)
  → assign existing party, or create a new one
```
Categorization of the party itself (assigning it a type/sub-category/category)
is done by the user in the frontend.

---

## Configuration

Config is set in `create_app()` (`src/api/app.py`). Defaults can be
overridden via environment variables.

**Environment variables**
- **`DATABASE_PATH`** — SQLite file location. Default: `backend/data/financial_data.db`
- **`UPLOAD_FOLDER`** — Where uploaded files land. Default: `backend/data/uploads/`

In development, both are overridden in `devcontainer.json` to point at
`backend/data-dev/`, keeping dev data isolated from production.

**Other config (hardcoded)**
- **Max upload size** — 50 MB
- **Allowed extensions** — `png jpg jpeg pdf csv xlsx xls tsv txt`
- **CORS** — Open on `/api/*`, all origins (fine for local/personal use)

---

## Running

### Dev server
```bash
uv run python src/run.py
```
Migrations run automatically on startup. **The reloader is not enabled** —
restart the process after code changes.

### Tests
```bash
uv run pytest
```
Test layout mirrors `src/` — e.g. `tests/test_categorizer/` tests
`src/categorizer/`. Shared fixtures live in the nearest `conftest.py`.

---

## API surface

- **`health`** → `/api` — Liveness check
- **`accounts`** → `/api/accounts` — Bank account CRUD
- **`categories`** → `/api` — Category hierarchy CRUD
- **`transactions`** → `/api/transactions` — List, filter, bulk-edit
- **`uploads`** → `/api/uploads` — Upload tracking / history
- **`receipts`** → `/api` — Receipt upload & processing
- **`tabular_files`** → `/api/tabular` — Statement file upload & preview

The full route map is printed to stdout on startup.

---

## Scheduled jobs

`api/scheduler.py` runs APScheduler in the background.

- **Temp file cleanup** — runs hourly, deletes stale temporary files

The scheduler is skipped in the Werkzeug reloader's parent process
(`WERKZEUG_RUN_MAIN` check) — a safeguard in case the reloader is ever
enabled, to prevent duplicate job execution.

---

## Module reference

- **`api/app.py`** — App factory. Registers blueprints, inits DB, starts scheduler.
- **`api/middleware/error_handlers.py`** — Converts exceptions → JSON error responses.
- **`api/services/parallel_processor.py`** — Runs receipt jobs concurrently.
- **`api/utils/sse.py`** — Server-Sent Events helpers for streaming progress.
- **`categorizer/party_extractor.py`** — Extracts party name from a transaction description.
- **`categorizer/party_matcher.py`** — Fuzzy-matches extracted names against known parties; creates new parties for unmatched names.
- **`categorizer/party_matcher_raw.py`** — Same matching algorithm, no DB integration. No party import, no party creation. Used primarily for testing.
- **`database/connection.py`** — SQLite connection manager, registered on the Flask app.
- **`database/migrations.py`** — Schema migrations, run on startup.
- **`statements/base.py`** — Abstract base for statement parsers. Defines the contract.
- **`statements/registry.py`** — Maps bank identifier → config class.
- **`statements/processors/revolut.py`** — Revolut-specific preprocessing beyond column mapping.
- **`utils/logging.py`** — `ContextLogger`, structured logging wrapper.

---

## Adding a new bank

1. Create `src/statements/configs/<bank>.py` — subclass the base config and
   define column mappings. Use `aib.py` as the simplest reference.
2. Register it in `src/statements/registry.py`.
3. If the bank's export needs preprocessing (e.g. Revolut), add a processor
   in `src/statements/processors/`.

User-facing bank config is on the roadmap — for now this is a code change.