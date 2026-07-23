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

## Next Steps (statementFormats)
- [ ] `editor/FormatEditor.jsx` — in progress next. Watch the scroll/overflow contract (see watch-out #3).
- [ ] Remaining editor subcomponents (TBD — enumerate as we open them).
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