# Frontend Issue Backlog

Issues identified while reading the frontend codebase ahead of the
TanStack Query / React Hook Form / Zustand / Tailwind migration.

These are documented only — the migration PR does not fix them.

## Bugs

### B1. Race condition in `ProcessReceipts` candidate search
**Where:** `src/features/receipts/ProcessReceipts.jsx`
**Symptom:** A 500 ms debounced `getCandidateTransactions()` runs after
every edit to vendor/date/amount. There is no `AbortController`, so when
the user types quickly, several requests are in-flight simultaneously.
If the second response arrives before the first, the candidate list
ends up showing stale matches that don't correspond to the currently
visible form values.
**Risk:** Wrong transaction may be linked to a receipt.

### B2. `setState`-after-unmount in `ProcessReceipts` taxonomy load
**Where:** `src/features/receipts/ProcessReceipts.jsx` (initial taxonomy
`useEffect`)
**Symptom:** Four parallel taxonomy fetches run on mount with no
cancellation flag. If the user navigates away before they resolve,
React logs an unmounted-`setState` warning and the responses are
wasted.
**Risk:** Memory pressure under fast navigation; misleading console noise.

### B3. Inconsistent API envelope handling
**Where:** Multiple `features/*/api.js` callers (e.g. `UploadStatement`
reads `result.data` directly while other endpoints return either
`{ data: {...} }`, `{...}` or arrays).
**Symptom:** Code accesses `.data` without checking for existence; if
the backend changes envelope shape, callers crash silently or produce
`undefined`-derived UI bugs.
**Risk:** Brittle coupling to backend response shape.

### B4. Cascade dropdown not fully cleared in `BulkEditModal`
**Where:** `src/features/transactions/BulkEditModal.jsx`
**Symptom:** When the category dropdown is cleared, the sub-category
clears but a previously selected `party_id` may remain even though its
parent type is no longer reachable. Submitting then sends a party that
is inconsistent with the now-empty category.
**Risk:** User can apply nonsensical updates.

### B5. Stale `selectedAccount` reference in `UploadStatement`
**Where:** `src/features/statements/UploadStatement.jsx`
**Symptom:** `accounts.find(...)` is called synchronously during render.
If the account list changes between selection and import (e.g. another
tab deletes it), the variable becomes `undefined` and the import
handler shows a generic "NOT_FOUND" toast instead of guiding the user
to pick again.
**Risk:** Confusing error UX.

### B6. No cancellation for `previewFormat` in the format editor
**Where:** `src/features/statementFormats/editor/useFormatEditor.js`
**Symptom:** When the user changes columns or defaults rapidly, the
preview refresh fires repeatedly with no abort. Out-of-order responses
can leave a stale preview rendered against the latest config.
**Risk:** User trusts a preview that no longer matches their settings.

### B7. PDF.js worker URL is configured per component
**Where:** `src/components/FilePreview.jsx` /
`src/features/receipts/ImagePreview.jsx`
**Symptom:** PDF.js worker setup is duplicated and worker URL hard-coded
in places. If the worker version drifts from the bundled `pdfjs-dist`
the previewer silently fails to render.
**Risk:** Receipt previews break after a `pdfjs-dist` upgrade.

## Security

### S1. No client-side input validation on receipt fields
**Where:** `src/features/receipts/ProcessReceipts.jsx`
**Symptom:** `vendor`, `amount`, `date` are sent to the backend without
length, type or range checks. Backend enforces them but the user gets
no feedback until the request round-trips.
**Risk:** Low — primarily UX, but users can paste oversized strings or
non-numeric amounts.

### S2. File MIME type only checked client-side for receipt uploads
**Where:** `src/features/receipts/BulkUploadReceipts.jsx`
**Symptom:** Only `image/*` and `application/pdf` are filtered in the
browser. MIME types are trivially spoofable. The backend must
re-validate. This must be confirmed.
**Risk:** Medium if backend trusts client MIME — could allow uploading
arbitrary files into the receipts pipeline.

### S3. No upload size limit in the browser
**Where:** `src/features/statements/UploadStatement.jsx`,
`src/features/receipts/BulkUploadReceipts.jsx`
**Symptom:** Browser will POST arbitrarily large files until the server
rejects them, wasting bandwidth and giving a long-running spinner
before failure.
**Risk:** Low; degrades UX and could be used to harass the server.

### S4. Error messages rendered without sanitization
**Where:** Toast and inline error displays everywhere using
`err.userMessage`.
**Symptom:** If the backend ever echoes user-supplied content in an
error message and the frontend later switches from text-only rendering
to anything HTML-aware, that becomes an XSS vector. Currently fine
because React escapes string children, but future refactors should
remember this constraint.
**Risk:** Latent — depends on future changes.

### S5. `VITE_API_URL` baked at build time
**Where:** `src/lib/apiClient.js`
**Symptom:** The base URL is embedded in the bundle at build time. A
single artifact cannot serve multiple environments and there is no way
to override it at runtime without a rebuild.
**Risk:** Operational; not directly a security issue but constrains
deployment flexibility.

### S6. Toast messages currently never auto-escape rich content
**Where:** `src/components/ToastContext.jsx`
**Symptom:** Same caveat as S4 — fine while the renderer uses text
nodes, but worth pinning down with a lint rule that bans
`dangerouslySetInnerHTML` in toast/error rendering.
**Risk:** Latent.
