# Frontend

React SPA for the finance tracker. Three main workflows: upload statements,
categorize transactions, process receipts.

---

## Stack

- **React 19** + **Vite 7**
- **React Router** (`BrowserRouter`) for navigation
- **No state library** — `useState` + a single `ToastContext`
- **react-pdf** for rendering PDF receipts
- **ESLint** for linting

---

## Running

```bash
npm run dev      # Vite dev server → http://localhost:5173
npm run build    # Production build → dist/
npm run preview  # Serve the production build locally
npm run lint     # ESLint
```

**Environment variables**
- **`VITE_API_URL`** — Backend base URL. Defaults to `http://localhost:5000/api`.

---

## Routes

Defined in `App.jsx`.

- **`/`** — Home (landing page, nav links)
- **`/upload`** — Upload a bank statement, preview, import
- **`/categorize`** — Review transactions, assign/edit party categorization;
  generate Cash-account counterparts from selected rows or enter cash
  transactions manually
- **`/process-receipts`** — Bulk-upload receipt images, match to transactions,
  or generate a Cash-account transaction directly from a receipt

---

## Project layout

```
src/
├── App.jsx           Router + ToastProvider wrapper
├── components/       Shared UI primitives (Dropdown, Toast, Pagination, ErrorBoundary…)
├── features/         One folder per workflow
│   ├── receipts/
│   ├── statements/
│   └── transactions/
└── lib/              Infrastructure: API client, error types, logger
```

Each feature folder contains:
- The page component (e.g. `UploadStatement.jsx`)
- Supporting components used only by that page
- An `api.js` exporting the backend calls that feature needs
- Colocated `.css` files

**Path alias** — `@/` resolves to `src/`. Use `@/components/...`, `@/lib/...`, etc.

---

## API layer

### The pattern

All backend calls go through `lib/apiClient.js` → `apiCall(endpoint, opts)`.

```
Page component
  → features/<feature>/api.js    (named functions: previewFile, importFile, …)
  → lib/apiClient.js             (apiCall — fetch wrapper, error parsing)
  → backend
```

Feature `api.js` files are thin wrappers that give each endpoint a name and
hide the URL/method details from the page.

**Exception:** bulk receipt upload streams progress via SSE and talks to
`fetch` directly (using the exported `API_BASE_URL`) rather than going
through `apiCall`.

### Response envelopes

The backend wraps responses in `{ data: {...} }`. Use `unwrap(response, key)`
from `apiClient.js` to dig the payload out without caring about nesting depth.

---

## Error handling

Errors are routed to one of three places depending on type:

### 1. Inline — structured, recoverable errors
Validation-style failures where the user can fix the input. Rendered directly
in the page with enough detail to act on.

Example: column mismatch on statement import → `ColumnMismatchPanel` shows
expected vs. found columns side-by-side, with buttons to change account or
pick a different file.

These are caught in the page's `try/catch`, identified by `err.code`
(see `lib/apiErrors.js` → `ErrorCode`), and set into local state.

### 2. Toast — operational errors
Something went wrong but there's nothing structured to show. Network errors,
unexpected API failures, "the thing you selected was just deleted."

```js
addToast({ message: err.userMessage, type: 'error' });
```

`err.userMessage` is populated by `apiClient.js` / `apiErrors.js` so pages
don't have to construct user-facing text.

### 3. ErrorBoundary — unhandled render errors
`components/ErrorBoundary.jsx` catches anything that escapes and shows a
generic "something went wrong, try refreshing" fallback. Last line of defense.

### Flow summary

```
fetch() throws           → AppError (network) ──┐
response not OK          → ApiError (parsed)  ──┤
                                                ├─→ page catch → inline or toast
render throws            → ErrorBoundary       ─┘
```

---

## Adding a feature

1. Create `src/features/<name>/`
2. Add an `api.js` exporting named functions that call `apiCall(...)`
3. Build the page component, colocate its CSS
4. Add a `<Route>` in `App.jsx` and a nav `<Link>`