# Tailwind CSS Migration — Progress Note

**Branch:** `feature/tailwind-css` (worktree: `wt-tailwind-css`)

## Context
Migrating the frontend from individual CSS files to Tailwind CSS v4. Note: this project uses Tailwind v4, which differs from v3 in a few key ways:

- No `tailwind.config.js` or `postcss.config.js`.
- Setup is done via the `@tailwindcss/vite` plugin in `vite.config.js`.
- Use a single `@import "tailwindcss";` in the CSS (instead of the older `@tailwind base/components/utilities` directives).
- Theme customization is done in CSS via `@theme {}` rather than a JS config file.

## Done
- [x] Installed `tailwindcss` + `@tailwindcss/vite` (removed the initial incorrect install of `postcss`/`autoprefixer`).
- [x] Configured `vite.config.js` with the `tailwindcss()` plugin.
- [x] Added `@import "tailwindcss";` to `frontend/src/index.css`.
- [x] Verified Tailwind is working (a test class rendered correctly).
- [x] Cleaned up `index.css` — removed the default Vite template styles (dark background, demo button/link/h1 styles, body flex-centering). Kept only the `:root` font-family/rendering block above the Tailwind import. App renders with a white background and dark text.
- [x] Migrated `CategoryHierarchyPage.jsx` (page-level layout):
	- Removed `import './CategoryHierarchyPage.css'`.
	- Converted page/header/body/sidebar/detail classes to Tailwind utility classes.
	- Deleted `CategoryHierarchyPage.css`.

> ⚠️ TODO: verify this renders correctly in a browser — testing was interrupted.

## Next Steps (Hierarchy feature)
Migrate child components' CSS files one at a time, then delete the `.css` file after migration:

- [ ] `HierarchyTree` (sidebar) — migrate CSS + JSX
- [ ] `HierarchyDetailPanel` (breadcrumb + stats + table)
- [ ] `EditNodeModal`

## Notes / Watch-outs
- CSS variables like `--border-color` (`#e0e0e0`) and `--sidebar-bg` (`#fafafa`) are defined in other shared components/features but are NOT used in Hierarchy. For the Hierarchy page I used explicit values (e.g. `border-[#e0e0e0]`, `bg-[#fafafa]`) instead of theme tokens.
- Future decision: when migrating shared components, consider defining `--border-color` etc. as Tailwind theme tokens in `index.css` via `@theme` (for example, `bg-border`, `border-border`) to make them reusable. You may want to retroactively update the Hierarchy page to use those tokens for consistency.
- Migration order so far: leaf/page components first, then shared components.