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
- [x] `CandidateTransactions.jsx` — migrated + CSS deleted.
      First file requiring custom @keyframes → added --animate-fade-in and
      --animate-highlight-pulse to @theme in index.css.
      All 6 `!important` declarations ELIMINATED: they were defending
      against (a) `.transaction-row td` out-specifying `.amount-cell`, and
      (b) a global `.amount-cell` class collision with ImportResult.css.
      Both causes gone now that cells carry utilities directly.
      Dead CSS dropped: `.transaction-row.selected` (never applied — JSX
      only sets `linked`).
      Minor refactor: extracted duplicated <PanelHeader>.

### transactions feature
- [x] `CategorizeTransactions.jsx` — migrated + CSS deleted.
      ⚠️ `.new-cash-button` had NO CSS rule — it was relying on native
      button chrome, which Preflight removes. Given a neutral secondary
      style (white + border); verify the visual intent.
      Dead CSS dropped: `.loading` (never rendered — the `loading` state
      is set but never consumed, so this page has no loading indicator at
      all), `.error-message` (+ its button; errors go via toast).
      Added `shrink-0` to .filters-section — original omitted it while
      giving it to its siblings.
- [x] `TransactionTable.jsx` — migrated, but CSS NOT deleted.
      TransactionTable.css trimmed to only TransactionRow-owned rules;
      <table> keeps `transaction-table` className as a hook.
      Base cell rule re-scoped to `tbody` so it can't out-specify the
      Tailwind utilities on the thead filter row.
      .filter-cell-center !important eliminated.
      ⚠️ Dead header classes found: .lodgment-header / .kids-header /
      .one-off-header have no CSS — headers are left-aligned while their
      cells are center !important. Kept faithful; fix suggested.
      ⚠️ Sticky filter-row offset (top-11) is hardcoded to the header's
      computed height — fragile if header padding/font changes.
- [x] `TransactionRow.jsx` — migrated.
- [x] `TransactionTable.css` + `TransactionRow.css` — BOTH deleted;
      `transaction-table` hook removed. Zebra + row hover moved onto the
      row itself (even:bg-gray-50 / hover:bg-gray-200).
      ⚠️ BUG FIXED: table's `tbody tr:nth-child(even)` (0,2,2) was
      overriding `.transaction-row.selected` and `.editing` (0,2,0), so
      selection/edit highlights were invisible on every even row. Now
      computed per-state. Hover-wins-over-state preserved.
      ⚠️ `.description-cell` wrapping was indeterminate (load-order
      dependent); settled as truncate + expand-on-hover.
      Party cell restructured: flex moved from the <td> to an inner div
      (display:flex on a td broke table layout, and text-overflow never
      worked on a flex container).
      All 7 remaining !important eliminated. `.amount-cell` collision
      fully closed — all 4 declaring components now migrated.
- [ ] `components/DropdownWithCreate` — NOW URGENT. `.dropdown-with-create
      select` lived in TransactionRow.css; its styling is replicated for
      TransactionRow only. BulkEditModal / RemapPartyModal /
      CreateCashTransactionModal / GenerateCashFromReceiptModal selects
      are currently unstyled.
- [x] `BulkEditModal.jsx` — migrated. CSS deletion GATED on grep.
      ⚠️ BulkEditModal.css contains the app's de-facto modal design system
      (.modal-overlay/.modal-content/.modal-header/.modal-actions/
      .save-button/.cancel-button/.form-field/.form-section/.modal-error).
      ImagePreview.css already documents a conflicting `.modal-content`
      (width:560px) elsewhere — confirmed duplication. Grep all modals
      before deleting; if any depend on this copy, move the generic rules
      to src/styles/legacy-modal.css imported from index.css.
      ⚠️ BUG FIXED: dark-mode-first again (bg #1a1a1a + prefers-color-scheme
      light override). Settled light-only.
      ⚠️ BUG FIXED: .save-button had NO background/border/radius and
      .cancel-button set border-color with no border-width — both depended
      on Vite's deleted global `button` rule. Save given #646cff primary,
      cancel an outline. Judgment call.
      ⚠️ BUG FIXED: .checkbox-field set align-items/gap but not
      flex-direction, so it inherited `column` from .form-field — checkbox
      and Clear button were stacked + centred. Now a row.
      Dead CSS dropped: .party-name-display, .party-name-value.
- [~] `CreateCategoryModal.jsx` — PARTIAL. CreateCategoryModal.css migrated
      + deleted; @/styles/Modal.css import retained (not yet migrated).
      Dropped dead `create-modal` class (empty rule).
      has-error colours were exact Tailwind (red-600/red-50).
      Fixed inert `outline-color` on error focus — ring was staying blue.
- [x] `src/styles/Modal.css` — MIGRATED into `src/styles/modalClasses.js`.
      CSS file deleted. All modal chrome now lives as importable Tailwind
      const strings: BACKDROP, PANEL, HEADER, TITLE, CLOSE_BTN, BODY,
      FOOTER, ERROR_BANNER, BTN_PRIMARY, BTN_SECONDARY.
      CSS custom properties (--color-surface, --color-border, --color-error,
      --color-primary) were aspirational — never defined at :root, fallbacks
      always won. Replaced with direct Tailwind matching the fallback values.
      border-gray-200 ↔ border-gray-300 inconsistency within the same file
      preserved (header/footer vs. form inputs).
- [x] `CreateCategoryModal.jsx` — FULLY MIGRATED. Both CSS imports removed.
      Uses shared M.* constants for modal chrome + own FIELD/FIELD_ERR for
      form styling. Focus ring uses blue-600 (the file's own --color-primary
      fallback — a 6th primary blue, see notes).
      Delete CreateCategoryModal.css.
- [x] `ReceiptIcon.jsx` — migrated + CSS deleted. Clean file: no dead rules,
      no !important, no collisions. `currentColor` pattern preserved —
      text-* utilities drive the SVG stroke including on hover.
      Material green pair (#4caf50/#388e3c) matches TransactionRow's
      btn-save, so the transactions feature is internally consistent.



		
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
- **Unscoped class names caused real collisions:** `.amount-cell` was
  defined globally by BOTH ImportResult.css and CandidateTransactions.css
  with conflicting font-weight, forcing !important. Worth grepping for
  other generic names still live in unmigrated CSS (.date-cell,
  .party-cell, .actions-cell, .table-header, .btn-remove, .empty-state,
  .hidden) — each is a latent cross-feature collision.
- **THREE scrollbar variants:** #888/#555 (ProcessReceipts,
  SelectableReceiptTable) vs #c1c1c1/#a1a1a1 (CandidateTransactions).
  Consolidate into a single `@utility scrollbar-thin` in index.css.
- **TransactionTable owns this page's scroll region.** CategorizeTransactions
  is `flex flex-col overflow-hidden` with shrink-0 header + filters, so
  TransactionTable must be `flex-1 min-h-0`. It currently gets that from its
  own CSS — when migrating it, carry those utilities over or the scroll dies
  (same failure mode as the ImportResult bug).
- **h1 sizes inconsistent:** 24px (UploadStatement, ProcessReceipts) vs 28px
  (CategorizeTransactions). Candidate for --text-page-title or a shared
  <PageHeader>.
- **Focus ring width drift:** 3px (UploadStatement, ProcessReceipts) vs 2px
  (CategorizeTransactions). Candidate for a single --shadow-focus-ring token.
- **Unstyled buttons from the deleted Vite `button` rule — now 4 found:**
  .new-cash-button, .clear-filters-button, .save-button, .cancel-button.
  The tell is a rule that sets only padding/margin/border-color with no
  background, border-width, or border-radius. Grep remaining CSS for
  `border-color:` without an adjacent `border:` declaration.
- **TWO modal systems, colliding on .modal-content + .modal-header:**
  (a) @/styles/Modal.css — .modal-backdrop / .modal-content / .modal-header /
      .modal-close / .modal-body / .modal-footer / .btn-primary /
      .btn-secondary. Used by CreateCategoryModal (explicit import).
      Likely source of the `width:560px; overflow:hidden` that ImagePreview
      documented fighting.
  (b) BulkEditModal.css — .modal-overlay / .modal-content / .modal-header /
      .modal-close-btn / .modal-actions / .save-button / .cancel-button.
      A rogue duplicate, NOT the shared system (corrects my earlier note).
  Resolution: migrate Modal.css into a <Modal> component, then convert
  BulkEditModal to use it and delete its generic classes.
- **Cross-feature CSS leakage confirmed:** CreateCategoryModal.css was
  supplying `.field-error` and `.form-group.has-error` to ProcessReceipts,
  which declared neither. Both now explicit. Worth assuming any
  "class used in JSX with no local rule" is being fed by another feature's
  stylesheet.
- **SIX primary blues found.** Running tally:
  #007bff (Stepper, BulkUpload — Bootstrap),
  #2196f3 (ImportResult, CandidateTransactions, CategorizeTransactions,
           Modal.css btn-primary — Material),
  #4a90e2 (UploadStatement, CategorizeTransactions focus — bespoke),
  #2563eb (Modal.css form focus — Tailwind blue-600),
  #646cff (FilterBar — Vite template),
  #1976d2 (hover shade of #2196f3).
  The Button migration is the natural convergence point. #007bff wins
  on frequency (3 files); #2563eb (blue-600) wins on being an actual
  Tailwind value; #2196f3 wins on being the modal/action-button standard.
  Pick one.

