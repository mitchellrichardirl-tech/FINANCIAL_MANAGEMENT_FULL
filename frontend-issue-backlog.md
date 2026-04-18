# Frontend Issue Backlog

Issues discovered during the frontend framework migration.

## Bugs

### 1. Case-sensitive import paths break production builds
**Severity:** High  
**Files:** `src/features/statementFormats/editor/FormatEditor.jsx`, `src/features/statementFormats/editor/stepper.jsx`  
**Description:** The file `stepper.jsx` is lowercase, but imports referenced it as `./Stepper` and `./Stepper.css`. This works on case-insensitive filesystems (macOS, Windows) but breaks on Linux and in production Docker builds. Fixed during migration by correcting the casing.

### 2. Thumbnail className concatenation missing space
**Severity:** Low  
**File:** `src/components/Thumbnail.jsx`  
**Description:** Line `className={\`receipt-thumbnail${isLoading ? 'hidden' : ''}\`}` is missing a space before `hidden`, resulting in `receipt-thumbnailhidden` instead of `receipt-thumbnail hidden`. The `hidden` class would never apply correctly.

### 3. Logger namespace mismatch in UploadStatement
**Severity:** Informational  
**File:** `src/features/statements/UploadStatement.jsx`  
**Description:** `createLogger('DropdownWithCreate')` uses the wrong namespace — should be `createLogger('UploadStatement')`. This causes misleading log output during debugging.

### 4. BulkEditModal error message double-wrapping
**Severity:** Low  
**File:** `src/features/transactions/CategorizeTransactions.jsx`  
**Description:** In `handleBulkUpdate`, the catch block references `msg.userMessage || msg.message` where `msg` is already a string from `err.message`. The fallback chain `msg.userMessage` will always be `undefined` since strings don't have a `userMessage` property. Should be `err.userMessage || err.message || 'Failed to update transactions'`.

### 5. Pagination total estimate can show misleading counts
**Severity:** Low  
**File:** `src/features/transactions/CategorizeTransactions.jsx`  
**Description:** The total count is estimated by checking if the returned page is full (`data.length === ITEMS_PER_PAGE`). If exactly 100 items exist, the UI shows "of 101" and enables a Next button that returns an empty page. The backend should return a proper total count.

## Security Risks

### 1. API base URL falls back to hardcoded localhost
**Severity:** Medium  
**File:** `src/lib/apiClient.js`  
**Description:** `API_BASE_URL` falls back to `'http://localhost:5000/api'` when `VITE_API_URL` is not set. In production, if the env var is accidentally missing, all API calls would go to localhost (i.e. fail silently or hit a different service). The fallback should be removed or replaced with a relative path for production builds.

### 2. No CSRF protection on mutations
**Severity:** Medium  
**File:** `src/lib/apiClient.js`  
**Description:** POST/PUT/DELETE requests don't include CSRF tokens. Since the app uses cookie-based session state implicitly (via same-origin fetch), a malicious page could trigger state-changing requests. Should add CSRF token headers to mutation requests.

### 3. Receipt image URLs constructed from user-controlled IDs
**Severity:** Low  
**File:** `src/features/receipts/ProcessReceipts.jsx`  
**Description:** Image preview URLs are built as `` `/api/receipts/${selectedReceipt.receipt_id}/image` ``. While the ID comes from the server response (not direct user input), there's no validation that the ID is numeric. The backend should validate receipt IDs strictly.

### 6. `accounts` prop unused in TransactionRow
**Severity:** Informational  
**File:** `src/features/transactions/TransactionRow.jsx`  
**Description:** The `accounts` prop is destructured but never referenced in the component body. It's passed from TransactionTable for parity but adds noise. Should be removed if not needed.

### 7. Pre-existing lint warnings: setState in useEffect
**Severity:** Low  
**Files:** `FilterBar.jsx`, `GenerateCashModal.jsx`, `RemapPartyModal.jsx`, `BulkEditModal.jsx`, `CreateCashTransactionModal.jsx`  
**Description:** Multiple components call `setState` directly inside `useEffect` bodies (e.g., resetting form state when `isOpen` changes). React 19's `react-hooks/set-state-in-effect` rule flags these. They should be refactored to use event handlers or `useMemo`/derived state where possible.

## Code Quality

### 1. Duplicated taxonomy cascade logic
**Severity:** Medium (maintenance burden)  
**Files:** `BulkEditModal.jsx`, `CreateCashTransactionModal.jsx`, `GenerateCashFromReceiptModal.jsx`, `FilterBar.jsx`  
**Description:** The category → subcategory → type → party cascading dropdown logic (filtered lists, parent auto-fill, child clearing) is duplicated across 4+ components with subtle differences. Should be extracted into a shared `useTaxonomyCascade` hook.

### 2. Duplicated `makeCreateHandler` factory
**Severity:** Low  
**Files:** `CategorizeTransactions.jsx`, `ProcessReceipts.jsx`  
**Description:** The `makeCreateHandler` factory function is copy-pasted between CategorizeTransactions and ProcessReceipts with identical logic. Should be a shared utility.

### 3. No error boundary around individual routes
**Severity:** Low  
**File:** `src/App.jsx`  
**Description:** The single `ErrorBoundary` wraps the entire app. A render error in one feature crashes all features. Each route should have its own error boundary so navigation to other features still works.
