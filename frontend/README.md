# Frontend

React SPA for the finance tracker. Main workflows: upload statements,
categorize transactions, process receipts, manage statement formats and the
category hierarchy.

---

## Stack

- **React 19** + **Vite 7**
- **Tailwind CSS v4** (via `@tailwindcss/vite`) — see [Styling](#styling)
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
- **`/process-receipts`** — Bulk-upload receipt images with a choice of
  extraction engine (OCR or AI/multimodal), match to transactions, or
  generate a Cash-account transaction directly from a receipt
- **`/statement-formats`** — List, clone, edit and delete bank statement
  formats
- **`/statement-formats/new`** · **`/statement-formats/:id`** ⚠️ *paths inferred —
  confirm* — Five-step format editor wizard (sample file → identity →
  columns → defaults → preview)
- **`/categories`** ⚠️ *path inferred — confirm* — Category hierarchy browser
  and editor

---

## Project layout

```
src/
├── App.jsx           Router + ToastProvider wrapper
├── components/       Shared UI primitives (Dropdown, Toast, Pagination, ErrorBoundary…)
├── features/         One folder per workflow
│   ├── hierarchy/
│   ├── receipts/
│   ├── statementFormats/
│   ├── statements/
│   └── transactions/
├── lib/              Infrastructure: API client, error types, logger
└── styles/           Shared style constants (modalClasses.js)
```

Each feature folder contains:
- The page component (e.g. `UploadStatement.jsx`)
- Supporting components used only by that page
- An `api.js` exporting the backend calls that feature needs

**Path alias** — `@/` resolves to `src/`. Use `@/components/...`, `@/lib/...`, etc.

---

## Styling

All feature pages and their leaf components use **Tailwind utility classes
directly in JSX**. There are no colocated `.css` files in `features/`.

### Tailwind v4 setup

v4 differs from v3 in ways that trip people up:

- **No `tailwind.config.js`, no `postcss.config.js`.** Configuration lives in
  CSS.
- Enabled by the **`@tailwindcss/vite`** plugin in `vite.config.js`.
- A single **`@import "tailwindcss";`** in `src/index.css` — *not* the old
  `@tailwind base/components/utilities` directives.
- **Theme customization via `@theme {}`** in `src/index.css`, not a JS config.

### Design tokens

Defined in `@theme {}` in `src/index.css`. Use them instead of arbitrary hex
wherever one exists:

| Token | Utility |
|---|---|
| `--font-sans` | `font-sans` |
| `--color-muted` | `text-muted` |
| `--color-danger-bg/border/text` | `bg-danger-bg`, `border-danger-border`, `text-danger-text` |
| `--color-info-bg/border/text` | `bg-info-bg`, `border-info-border`, `text-info-text` |
| `--animate-fade-in`, `--animate-highlight-pulse` | `animate-fade-in`, `animate-highlight-pulse` |

Prefer **Tailwind's default palette** over arbitrary hex for new work — it's
the house convention for status colours (e.g. `text-green-800` / `bg-green-50`
for positive, `text-red-800` / `bg-red-50` for negative). A token sweep to
consolidate the remaining Bootstrap/Material hex values is pending; see the
migration progress note.

### Shared class strings

When several elements need the same long utility string, extract a `const` at
module scope rather than repeating it:

```js
const TD = 'border-b border-gray-200 px-3 py-2 align-middle';
const TH = `${TD} sticky top-0 bg-gray-50 font-semibold`;
```

Keep `text-align` (and other single-property overrides) *out* of the base
const and set them per-element — two utilities for the same CSS property on
one element resolve by stylesheet order, which is not something you want to
reason about.

### Modal chrome

Modal shell styling lives in **`src/styles/modalClasses.js`** as exported
constants. Don't hand-roll a modal:

```jsx
import * as M from '@/styles/modalClasses';

<div className={M.BACKDROP} onClick={onBackdropClick}>
  <div className={`${M.PANEL} ${M.W_MD}`} onClick={(e) => e.stopPropagation()}>
    <div className={M.HEADER}>
      <h2 className={M.TITLE}>Title</h2>
      <button className={M.CLOSE_BTN} aria-label="Close">×</button>
    </div>
    <div className={M.BODY}>…</div>
    <div className={M.FOOTER}>
      <button className={M.BTN_SECONDARY}>Cancel</button>
      <button className={M.BTN_PRIMARY}>Save</button>
    </div>
  </div>
</div>
```

Pair `PANEL` with exactly one width variant (`W_SM` 440px, `W_MD` 520px,
`W_LG` 560px, `W_XL` 640px). Also available: `SECTION`, `SECTION_TITLE`,
`HINT`, `FIELD`, `FIELD_LABEL`, `ERROR_BANNER`, `ERROR_DISMISS`.

### Preflight gotchas

Tailwind's Preflight resets more than you'd expect. These bite repeatedly:

| Reset | What you must add back |
|---|---|
| Buttons lose `cursor: pointer` (new in v4) | `cursor-pointer` on every `<button>` |
| Headings lose font-size **and** weight | e.g. `text-lg font-semibold` on every `<h1>`–`<h6>` |
| `<p>` margins zeroed | `space-y-*` on the container for stacked paragraphs |
| `ul`/`ol` lose bullets, margin, padding | `list-disc pl-5` for real bullet lists |
| Buttons lose background + border | Set both explicitly — there is **no** global `button` rule |

The last one matters: Vite's template `button { … }` rule was removed from
`index.css`. Any button styled only with layout properties will render as bare
text.

### Flex scroll contracts

Several pages have a fixed-height shell with an internal scroll region. The
pattern:

```jsx
<div className="flex h-full flex-col overflow-hidden">
  <div className="shrink-0">{/* header */}</div>
  <div className="min-h-0 flex-1 overflow-y-auto">{/* scrolls */}</div>
  <div className="shrink-0">{/* footer */}</div>
</div>
```

**`min-h-0` is load-bearing.** A flex child's automatic minimum size prevents
it shrinking below its content, which silently disables `overflow-y-auto`.
Every ancestor between the height source and the scroll region must be either
definite-height or `flex-1 min-h-0`. Break the chain anywhere and the scrollbar
vanishes and the page grows instead — a failure mode that's easy to miss and
has already been fixed twice.

(`overflow-*` also zeroes the automatic minimum, so `min-h-0` is sometimes
redundant — but it's cheap and documents intent.)

### Migration status

Feature pages and leaf components are fully migrated. **Shared components in
`components/` are still on raw CSS** and are being migrated next. If you touch
one, check the progress note for known blast-radius issues first — several
shared stylesheets were supplying styles to components that declared none.

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
through `apiCall`. The request is a `multipart/form-data` POST carrying
the queued files plus an `extraction_method` field — `'ocr'` or
`'multimodal'` — set by the "AI extraction" checkbox in
`BulkUploadReceipts` (unchecked ⇒ `'ocr'`; the choice persists for the
session, not per batch). The field is always sent explicitly; the backend
defaults to OCR if it's absent. The SSE event stream is identical for both
engines, so the stream-parsing code has no engine-specific branches.

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

Field-scoped validation errors can be narrowed further — see
`ProcessReceipts`' `FIELD_MAP` / `routeError`, which puts an error under the
specific input that caused it and falls back to a general banner otherwise.

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

Extraction-engine failures (including multimodal/LLM API errors) surface as
per-receipt failure events in the SSE stream, reported through
`onProcessingComplete({failures})` — not as transport errors.

---

## Adding a feature

1. Create `src/features/<name>/`
2. Add an `api.js` exporting named functions that call `apiCall(...)`
3. Build the page component using Tailwind utilities — **no `.css` file**
4. Reuse `@/styles/modalClasses` for any modals
5. Add a `<Route>` in `App.jsx` and a nav `<Link>`