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
- [x] `editor/Stepper.jsx` — migrated + CSS deleted. shrink-0 now lives on
      the Stepper's own <ol>; removed the temporary wrapper div in
      FormatEditor. ⚠️ needs browser verify — connector line geometry uses
      calc() arbitrary values, check alignment at narrow widths.
- [x] `editor/ParsedPreviewTable.jsx` — migrated + CSS deleted.
      Credit/debit colors were already exact Tailwind palette values
      (green-800/red-800/green-50/red-50) — no approximation needed.
      ⚠️ browser verify: sticky thead border under border-collapse.

### statements feature
- [x] `UploadStatement.jsx` — migrated + CSS deleted.
      ⚠️ Behavioral change: preview-table-wrapper inline styles removed,
      now uses correct flex-fill. Height will differ — browser verify.
      ⚠️ Responsive breakpoints simplified from 3 (desktop-first) to 2
      (mobile-first, md/lg). 992px→lg is +32px shift.
      ⚠️ Account-group switched from flex-row to flex-col (likely
      original bug — format-warning had margin-top in a horizontal flex).
- [x] `ProcessingWarningsPanel.jsx` — migrated + CSS deleted.
      SHARED component: importers are UploadStatement + StepPreview, both
      verified clear. Restored `list-disc pl-5` on samples <ul> (Preflight).
      `pwp-code-*` dynamic class was dead → converted to data-warning-code;
      ⚠️ grep for `pwp-code` before merging.
- [x] `ImportResult.jsx` — migrated + CSS deleted.
      `.import-error` consolidated onto existing danger tokens (text shifts
      #721c24 → #842029 — intentional convergence).
      Table font-family now uses the --font-sans token. #666 → text-muted.
- [x] FIXED latent scroll bug: ImportResult root changed h-full → flex-1
      min-h-0, and UploadStatement's import-result wrapper given a definite
      height via the new shared PAGE_BODY_H const (also applied to the
      preview branch). Internal table scroll + pinned summary now work.
      ⚠️ behaviour change — browser verify.
      Known limitation: warnings panel is shrink-0, so many expanded
      warnings squeeze the table. Cap with max-h + overflow-y-auto if it
      becomes a problem.
- [x] `components/ColumnMismatchPanel.jsx` — migrated + CSS deleted.
      SHARED component: importers are UploadStatement + StepPreview.
      ⚠️ grep for `cmp-` / `column-mismatch-panel` before merging.
      Notable: all 12 colors were already exact Tailwind palette values —
      zero arbitrary values required.
      <ul> needed NO Preflight restoration (list-style:none was already
      the intent) — contrast with ProcessingWarningsPanel.

### receipts feature
- [x] `ProcessReceipts.jsx` — migrated. CSS deletion BLOCKED on
      .radio-row / .radio-option / .checkbox-option — grep child
      components before removing file.
      Dead CSS dropped: .receipt-error, .receipt-success (unused),
      .has-error (classname with no rule), .form-error/.field-error
      (no rule in this file — replaced with Tailwind).
      4 responsive grid breakpoints preserved via min-[] arbitrary values.
      Webkit scrollbar kept via [&::-webkit-scrollbar*] arbitrary variants.
- [x] `BulkUploadReceipts.jsx` — migrated + CSS deleted.
      ⚠️ REQUIRED refactor: drag-over state lifted from
      `currentTarget.classList.add('drag-over')` into React state
      (`isDragOver`). classList manipulation is incompatible with utility
      CSS. Browser-verify drag highlight still works.
      Note: the `.compact .dropzone-text` override (0.875rem vs 0.9rem)
      was imperceptible — collapsed to a single `text-sm`.
- [x] `SelectableReceiptTable.jsx` — migrated + CSS deleted.
      Row-state cascade (7 overlapping rules) replaced with explicit
      `rowCls()` function. Thumbnail styling moved from descendant
      selector to a wrapper div. Scrollbar same pattern as ProcessReceipts.
- [x] `ImagePreview.jsx` — migrated + CSS deleted. Kept react-pdf vendor
      CSS imports.
      ⚠️ BEHAVIOUR CHANGE: the old CSS had `.image-preview-img`
      (display:block) defined after `.hidden` (display:none), so
      hiding-the-image-while-loading never worked. Now explicit
      `isLoading ? 'hidden' : 'block'`. Image is genuinely hidden during
      load — verify this is desired.
		
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
- **Preflight button cursor:** v4 dropped `cursor: pointer` on buttons.
  Any migrated component with a bare <button> needs it added explicitly.
- **New hardcoded hex:** `#28a745` (success) and `#007bff` (primary) now
  appear as arbitrary values in Stepper. Grep both before migrating
  `Button` — promote to @theme tokens at that point.
- **Duplicated dashed placeholder:** same empty-state recipe now appears in
  StepDefaults (p-10, #868e96) and ParsedPreviewTable (p-6, text-muted).
  Fold into the <ErrorBanner>/<Alert> extraction work as an <EmptyState>,
  and standardise on text-muted.
- **Raw buttons in UploadStatement:** btn-remove and btn-import are styled
  <button> elements, not <Button>. Swap to <Button variant="danger/success">
  when Button is migrated.
- **Warning color tokens:** #fff3cd / #ffc107 / #856404 (Bootstrap warning
  palette) now appear as arbitrary values. Promote to @theme alongside
  the existing danger/info token pattern.
- **TWO warning palettes (resolve during token sweep):**
  UploadStatement `.format-warning` uses Bootstrap (#fff3cd/#ffc107/#856404);
  ProcessingWarningsPanel uses a bespoke warmer family
  (#fef9e7/#f0c36d/#6b5a2a + divider/muted/chip shades). Both render on the
  same page. Pick one — the PWP family is more complete — and promote to
  @theme, then retrofit .format-warning.
- **Money in/out colors disagree:** ParsedPreviewTable uses green-800/red-800
  (#166534/#991b1b); ImportResult uses Bootstrap #28a745/#dc3545. Same
  semantic, two palettes. Introduce --color-money-in/out and keep them
  distinct from --color-success/--color-danger even if hex matches.
- **THREE primary blues:** #007bff (Stepper), #4a90e2 (UploadStatement
  focus/info), #2196f3+#1976d2 (ImportResult button). Resolve before
  migrating Button.
- **Success alert family:** #d4edda / #c3e6cb / #155724 / #a3cfbb (divider)
  in ImportResult completes the bg/border/text set alongside the existing
  danger + info tokens. Promote as --color-success-bg/border/text/divider.
- **PAGE_BODY_H magic number:** `calc(100vh-200px)` is hardcoded in
  UploadStatement and anchors every internal scroll region on the page.
  It's a guess at app chrome + padding + h1. If the nav/header height
  changes it'll silently drift. Longer-term fix is a proper app-shell flex
  layout so pages inherit height instead of computing it from 100vh.
- **House palette = Tailwind defaults (decided):** ColumnMismatchPanel and
  ParsedPreviewTable independently use the identical green-800/red-800 on
  green-50/red-50 recipe for positive/negative status. Standardise on this.
  Retire the Bootstrap hexes in ImportResult's amount cells + summary stats
  (#28a745/#dc3545 → green-800/red-800). Keep Bootstrap only where it's UI
  chrome not status (Stepper done-state, remove button) and promote those
  to --color-success / --color-danger.
- **#007bff is the winner (3 files):** Stepper, ProcessReceipts,
  BulkUploadReceipts. BulkUploadReceipts also gives the hover shade
  (#0056b3). Promote both as --color-primary / --color-primary-hover when
  migrating Button; retire #4a90e2 and #2196f3/#1976d2.
- **`.hidden` collision resolved:** ImagePreview.css defined its own
  `.hidden { display: none }`, duplicating Tailwind's utility. Harmless
  (identical declaration) but it masked a source-order bug. If other
  components rely on a locally-defined `.hidden`, Tailwind's utility now
  covers them — but check for the same block/hidden ordering trap.