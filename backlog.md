## SQLite write hardening (busy_timeout + WAL)
**Priority:** Medium · **Area:** backend/database · **Size:** S

### Context
The async multimodal receipt path performs concurrent DB saves via
`asyncio.to_thread` (each on its own connection). SQLite permits one
writer at a time; without a busy timeout, simultaneous saves fail
immediately with `database is locked`, causing intermittent per-receipt
failures that scale with batch size and `GEMINI_MAX_CONCURRENCY`.

### Tasks
- [ ] Set `PRAGMA busy_timeout = 5000` in the connection factory
      (`database/connection.py` / repository base), so it applies to
      every connection, including the connection-per-save path.
- [ ] Enable `PRAGMA journal_mode = WAL` once at startup (migrations or
      app init). Note: WAL is persistent per database file; document
      this in the backend README.
- [ ] Add a regression test: batch of ~10 receipts with concurrency 10
      against a temp DB, assert zero `database is locked` failures.

### Acceptance criteria
Large multimodal batches at max concurrency complete with no
lock-related receipt failures.

## Fence temp-file cleanup against active receipt batches
**Priority:** Medium · **Area:** backend/scheduler · **Size:** M

### Context
`api/scheduler.py` runs hourly cleanup of stale temp files. A large
multimodal batch slowed by API rate limiting / retry backoff can run
longer than the staleness threshold, at which point cleanup deletes
temp files for receipts **not yet processed**. Symptom: early receipts
in a big batch succeed, later ones fail with file-not-found. Only
reproduces on long runs, so it looks like random flakiness.

### Tasks
- [ ] Add an in-flight registry: batch processors register their temp
      paths (or a per-batch temp subdirectory) on start and deregister
      in a `finally` on completion/disconnect.
- [ ] Cleanup job skips registered paths/directories regardless of age.
- [ ] Keep age-based deletion as the fallback for orphans (e.g. process
      killed mid-batch and never deregistered) — raise the orphan
      threshold to comfortably exceed the max plausible batch duration
      given `MAX_RECEIPT_BATCH_SIZE` and worst-case per-receipt latency.
- [ ] Log every deletion with file age, to make any future recurrence
      diagnosable.

### Acceptance criteria
A batch whose runtime exceeds the cleanup interval completes with no
mid-batch file-not-found failures; orphaned temp files from crashed
runs are still eventually removed.

### Notes
Simplest robust shape: one subdirectory per batch
(`tmp/batch_<uuid>/`), registered at creation, deleted by the
processor itself on completion — cleanup job then only handles
orphaned batch dirs older than the fallback threshold.# Receipt icon in transactions table

## Summary

Add a receipt indicator icon to each row of the main transactions table. Icon state:

- Green when a receipt is attached.
- Grey when no receipt is attached.

Interactions:

- Clicking grey opens an upload modal.
- Clicking green opens the receipt view (image or PDF) with an option to unlink.

## Status

Status: 4 of 5 commits landed, one bug fix applied mid-stream.

### Completed
- [x] **Commit 1** — feat(transactions): add receipt API wrappers
	- Added `linkReceipt`, `unlinkReceipt`, `uploadReceipt` to `features/transactions/api.js`.
- [x] **Commit 2** — feat(transactions): show receipt indicator icon in table
	- New `ReceiptIcon.jsx` + `.css` (inline SVG, green/grey states).
	- Receipt column added to `TransactionTable.jsx` (header + filter row).
	- Receipt cell added to `TransactionRow.jsx` (display only).
- [x] **Commit 3** — feat(transactions): view linked receipt from table
	- New `ReceiptViewModal.jsx` + `.css` (image/PDF display, metadata, unlink button).
	- Coloured-icon click wired in `TransactionRow.jsx`.
	- `onReceiptChange` prop added to `TransactionRow` (unused until Commit 5).
- [x] **Commit 4** — feat(transactions): upload & attach receipt from table
	- New `ReceiptUploadModal.jsx` + `.css` (file picker, upload + link flow).
	- Grey-icon click wired in `TransactionRow.jsx`.

**Bug fix (receipts):** `process_receipt_images()` in `api/routes/receipts.py` was called with `yield_pages=True`, returning a generator where a list was expected (caused `len()` to fail). Fixed by removing `yield_pages=True` from `process_receipt_images()` and the `/process` endpoint (loader defaults to returning a list). This exposed a pre-existing untested failure in the single-upload endpoint.

### Remaining
- [ ] **Commit 5** — feat(transactions): reflect receipt link changes in state
	- Add `handleReceiptChange` handler in `CategorizeTransactions.jsx` that patches a single transaction in the local transactions array using the updated transaction returned by link/unlink endpoints.
	- Thread handler down: `CategorizeTransactions` → `TransactionTable` (new prop) → `TransactionRow` (`onReceiptChange` already accepted).
	- Goal: icon flips colour immediately on link/unlink without a full page refetch.

## Design decisions

- Inline SVG icon (no new dependency).
- Column positioned just before Actions.
- Use `<img>` for images and `<iframe>` for PDFs in the view modal.
- Unlink detaches only (receipt record remains in DB).
- State is patched in place from API response (no full refetch).
- Backend required no changes for the feature — endpoints already existed.
# Tailwind CSS Migration — Progress Note

**Branch:** `feature/tailwind-css` (worktree: `wt-tailwind-css`)

## Context
Migrating the frontend from individual CSS files to Tailwind CSS v4. Note: this project uses Tailwind v4, which differs from v3 in a few key ways:
- No `tailwind.config.js` or `postcss.config.js`.
- Setup is done via the `@tailwindcss/vite` plugin in `vite.config.js`.
- Use a single `@import "tailwindcss";` in the CSS (instead of the older `@tailwind base/components/utilities` directives).
- Theme customization is done in CSS via `@theme {}` rather than a JS config file.

## Done
- [x] Installed `tailwindcss` + `@tailwindcss/vite` (removed the initial incorrect install of postcss/autoprefixer).
- [x] Configured `vite.config.js` with the `tailwindcss()` plugin.
- [x] Added `@import "tailwindcss";` to `frontend/src/index.css`.
- [x] Verified Tailwind is working (a test class rendered correctly).
- [x] Cleaned up `index.css` — removed default Vite template styles. Kept only the `:root` font-family/rendering block above the Tailwind import. App renders white background, dark text.
- [x] Defined `@theme` tokens so far: `--font-sans`, danger tokens (`--color-danger-bg/border/text`), `--color-muted`, info tokens (`--color-info-bg/border/text`).

### Hierarchy feature
- [x] `CategoryHierarchyPage.jsx` — migrated + CSS deleted. ⚠️ still needs a browser verify (testing was interrupted).
- [x] `HierarchyTree` (sidebar) — migrated.
- [x] `HierarchyDetailPanel` (breadcrumb + stats + table) — migrated.
- [x] `EditNodeModal` — migrated. (Note: does **not** use the shared `ConfirmDialog`.)

### statementFormats feature
- [x] `StatementFormatsPage.jsx` — migrated, `.sfp` CSS deleted.
- [x] `FormatList.jsx` — migrated, `FormatList.css` deleted.
- [x] `FormatEditorPage.jsx` — migrated, `FormatEditorPage.css` deleted.
- [~] `DeleteFormatDialog.jsx` — no dedicated CSS. Only remaining tweak: add `list-disc pl-5` to the linked-accounts `<ul>` (Preflight strips bullets/indent). Decide whether body spacing lives here or in `ConfirmDialog`'s body — **deferred until ConfirmDialog is migrated** (see below).
- [x] `FormatEditor.jsx` — migrated + CSS deleted. Stepper wrapped in
      shrink-0 div (Stepper itself not yet migrated).
- [x] Shared step scaffolding (`fe-step`, `fe-step__sub`,
      `fe-step__placeholder`) — inlined into all 5 step components,
      rules removed from FormatEditor.css.
- [x] `StepSampleFile` — was already on Tailwind; CSS deleted.
- [x] `StepColumns` — was already on Tailwind; CSS deleted.
- [x] `StepDefaults` — was already on Tailwind; CSS deleted.
- [x] `StepPreview` — was already on Tailwind; CSS deleted.
      Fixed info banner to use @theme tokens instead of hardcoded hex.

## Next Steps (statementFormats)
- [ ] Revisit `DeleteFormatDialog` `<ul>` + body spacing once `ConfirmDialog` is done.

## Deferred: shared components
Migration order is leaf/page first, then shared components. Shared components flagged but intentionally **not yet migrated**:
- [ ] `components/ConfirmDialog` (+ `ConfirmDialog.css`) — used by `DeleteFormatDialog`. Still on raw CSS. **Check blast radius** (grep other importers) before migrating/deleting its CSS, since it affects every consumer.
- [ ] `components/Button` — used everywhere; confirm whether it's already migrated or still raw CSS.

## Notes / Watch-outs
- **Preflight resets:** `p` margins and `ul/ol` list-style/margin/padding are zeroed. Restore intentionally where the old look relied on UA defaults (e.g. `space-y-*` between stacked `<p>`, `list-disc pl-5` on real bullet lists). This is why `DeleteFormatDialog`'s `<ul>` needs attention.
- **Duplicated danger error box:** the same error-banner markup now appears verbatim in `.sfp__error` and `.format-editor-page__error` (border `#f5c2c7`, bg `#f8d7da`, text `#842029`, flex layout). Currently using explicit hex. **TODO:** consolidate onto the already-defined danger `@theme` tokens (`border-danger-border bg-danger-bg text-danger-text`), and consider extracting a small `<ErrorBanner>`/`<Alert>` component.
- **Muted color consistency:** `#6c757d` is the `--color-muted` token but has been rendered as `text-gray-500` (actually `#6b7280`) in `StatementFormatsPage`, `FormatList`, and `FormatEditorPage` for now. **TODO (token sweep):** switch these to `text-muted` for exact + consistent color.
- **Shared color tokens:** `--border-color` (`#e0e0e0`) and `--sidebar-bg` (`#fafafa`) are used by shared components but were hardcoded as arbitrary values in Hierarchy. When migrating shared components, consider promoting these (and the muted/danger usages above) to `@theme` tokens, then retrofit Hierarchy + statementFormats pages for consistency.
- **Editor scroll contract:** `FormatEditorPage` is `flex flex-col overflow-hidden`; the header is `shrink-0`. `FormatEditor` is expected to own its internal scroll region. When migrating it, ensure the scrollable child has `min-h-0` + `overflow-y-auto` (flex children won't shrink below content size without `min-h-0`), or content will clip instead of scroll. Related: the `__table` region uses `h-[50vh] min-h-[320px] overflow-hidden`.
- **Stepper component:** Still un-migrated. Currently wrapped in a
  `shrink-0` div inside FormatEditor. When migrating Stepper, put
  `shrink-0` on its own root and remove the wrapper.