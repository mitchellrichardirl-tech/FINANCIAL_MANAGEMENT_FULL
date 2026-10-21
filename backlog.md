Three distinct drift points, none blocking Phase 1:

1. **`Receipt` dataclass vs `receipts` table.** The dataclass is a pipeline working object, not a row model. Field names differ (`extracted_text` ↔ `raw_text`), types differ (`confidence: float` ↔ `INTEGER 0–3`), DB columns absent from the dataclass (`metadata`, `created_at`, `updated_at`), and the repository hand-maps scalars in `save()`/`update()`. Phase 1 adds `status` to the table — it will have no dataclass counterpart, widening the gap. Backlog: split into `ReceiptPipelineState` (numpy etc.) and a `ReceiptRecord` row model that the repository reads/writes; or adopt a single `row_to_model` path.
2. **`Transaction` dataclass vs table.** Closer, but typed loosely (`deleted_at: str`), and `receipt_id` will become a denormalised mirror of `receipt_links` after Phase 1. Backlog: mark it derived in the docstring; drop it when split-receipts lands.
3. **Frontend `ErrorCode` mirrors backend enum by hand** — already missing `CONFLICT` and `UNSUPPORTED_FILE_TYPE`. Backlog: generate from backend or add a test that diffs them.

# Receipt lifecycle

## Phase 1 — Recoverable & Retro-linkable Receipts

**Goal:** every uploaded receipt is persisted with an explicit status, listable when not linked, and linkable from Process Receipts after the fact. Single server-side writer for links. Join table ready for split transactions.

### 1. Config

- [ ] Add `RECEIPT_MATCH_DATE_TOLERANCE_DAYS` (env, default `5`) to `create_app` config.
- [ ] Add `RECEIPT_AUTO_LINK_THRESHOLD` (env, default `0.98`) — unused in Phase 1, reserved.
- [ ] Add `RECEIPT_MATCH_AMOUNT_TOLERANCE` (env, default `0.01`).
- [ ] Log the three values in the existing config debug line.

### 2. Schema & migrations (`migrations.py`)

- [ ] Add `_has_table(table)` guard helper alongside `_has_column`.
- [ ] Append migration `receipts.status`: `ALTER TABLE receipts ADD COLUMN status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','unlinked','linked'))`.
- [ ] Append migration `receipts.confirmed_at`: nullable `TIMESTAMP DEFAULT NULL`.
- [ ] Append migration `receipt_links`:
  ```
  CREATE TABLE receipt_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id INTEGER NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    linked_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
    link_source TEXT NOT NULL DEFAULT 'manual',   -- manual | auto | import
    UNIQUE (uq_receipt_links_receipt_id),         -- relax for split receipts later
    UNIQUE (uq_receipt_links_transaction_id)      -- relax for split transactions later
  )
  ```
- [ ] Append migration `receipts.backfill_status_and_links` (same migration as above or next entry):
  - `INSERT OR IGNORE INTO receipt_links (receipt_id, transaction_id, link_source) SELECT receipt_id, id, 'manual' FROM transactions WHERE receipt_id IS NOT NULL ORDER BY deleted_at`
  - `UPDATE receipts SET status='linked', confirmed_at=updated_at WHERE id IN (SELECT receipt_id FROM receipt_links)`
  - `UPDATE receipts SET status='unlinked', confirmed_at=updated_at WHERE status='pending' AND vendor IS NOT NULL` (pre-existing confirmed-but-unlinked rows)
- [ ] Add indexes to `INDEXES`: `receipt_links(transaction_id)`, `receipts(status)`, partial `receipts(date) WHERE status != 'linked'`.
- [ ] Leave `transactions.receipt_id` in place as a mirror (export view, `find_matching_transactions`, formatters all read it). Add `# derived from receipt_links` comment to `Transaction` dataclass.
- [ ] Add backlog note: drop `transactions.receipt_id` + rewrite `export` view when split receipts land.

### 3. Repository layer

#### `ReceiptRepository`
~~- [ ] Include `status`, `confirmed_at`, and `linked_transaction_id` (via `LEFT JOIN receipt_links`) in `get_by_id` and all row reads.~~
- [ ] Extend `update()` with `status` and `confirmed_at` sentinel params.
- [ ] Add `list(status: list[str] | None, vendor, date_from, date_to, amount_min, amount_max, q, limit, offset, sort, direction)` → `(rows, total)`.
- [ ] Add `count_by_status()` → `{pending, unlinked, linked}`.
- [ ] Ensure `save()` (called from stream processors) writes `status='pending'` explicitly.

ReceiptLinkService owns the SQL - it's the single write to the table
~~### New `ReceiptLinkRepository`~~
~~- [ ] `get_by_receipt(receipt_id)`, `get_by_transaction(transaction_id)`.~~
~~- [ ] `create(receipt_id, transaction_id, link_source)`.~~
~~- [ ] `delete_by_receipt(receipt_id)`, `delete_by_transaction(transaction_id)`.~~

#### `TransactionRepository`
- [ ] Change `find_matching_transactions` default `date_tolerance_days` to read from config at call site (route), not hard-coded `7`.
- [ ] Route `link_receipt_to_transaction` through the new link service (or deprecate and delegate).
- [ ] Check soft-delete / unsplit paths: verify soft-delete paths leave receipt_links untouched; add test.

### 4. New service: `ReceiptLinkService`

Single writer for all link state. Wrap in one `db.transaction()`.

- [ ] `link(receipt_id, transaction_id, source='manual')`:
  - validate receipt exists, status ∈ {pending, unlinked}; else `AppError(CONFLICT, entity='Receipt')`.
  - validate source ∈ {manual, auto, import}
  - validate transaction exists, live, has no existing link; else `AppError(CONFLICT, entity='Transaction')`.
  - insert `receipt_links`; set `transactions.receipt_id`; set `receipts.status='linked'`, `confirmed_at` if null.
  - return `{receipt, transaction}` formatted.
- [ ] `unlink_receipt(receipt_id)`: delete link, null `transactions.receipt_id`, set `status='unlinked'`.
- [ ] `unlink_transaction(transaction_id)`: same, keyed by transaction (used by transaction delete paths).
- [ ] `confirm(receipt_id, fields)`: existing `confirm_receipt` logic + set `status='unlinked'` if currently `pending`, set `confirmed_at`.
- [ ] Unlinked view filter "linked to a deleted transaction" with a Release action, since those receipts are otherwise stranded if the transaction is never restored.

### 5. Routes — `receipts.bp`

- [ ] `GET /receipts` — query params from §3 `list()`; default `status=pending,unlinked`; response `{receipts: [...], total, limit, offset}`. Validate `status` values → `invalid_value(field='status')`.
- [ ] `GET /receipts/summary` — `count_by_status()`.
- [ ] `GET /receipts/<id>` — full receipt via `ReceiptFormatter.detail()` (add formatter method; include `extracted_data` shape the frontend already consumes: `vendor, date, amount, confidence, selected_method, raw_text`).
- [ ] `PATCH /receipts/<id>` — edit vendor/date/amount on `pending`/`unlinked`; reject on `linked` with `CONFLICT`.
- [ ] `GET /receipts/<id>/candidates` — call `find_matching_transactions` using stored receipt fields, `amount * -1`, config tolerances, `include_matched=False`.
- [ ] `POST /receipts/<id>/link` — body `{transaction_id}`; `ReceiptLinkService.link`; 200.
- [ ] `DELETE /receipts/<id>/link` — `unlink_receipt`.
- [ ] Modify `POST /receipts/confirm` → delegate to `ReceiptLinkService.confirm`; return `status` in payload.
- [ ] Modify `DELETE /receipts/<id>` → refuse when `linked` (`HAS_DEPENDENCIES`, dependency `'transaction'`) unless `?force=true`, which unlinks first.
- [ ] Reconcile `/receipts/<id>/cancel` vs `DELETE /receipts/<id>`: keep one, alias the other, update `api.js`.
- [ ] Pass config tolerances into `/transactions/search` handler.
- [ ] Modify `POST /transactions/<id>/link-receipt` → delegate to `ReceiptLinkService.link`.
- [ ] Modify `PUT /transactions/<id>` (used by `updateTransaction`): if `receipt_id` present in body, delegate to link service (or unlink on `null`); strip from generic update.
- [ ] Add `CONFLICT` handling: ensure 409 status in `AppError` for new uses.

### 6. Formatters

- [ ] `ReceiptFormatter.summary` — add `status`, `confirmed_at`, `linked_transaction_id`.
- [ ] `ReceiptFormatter.detail` — summary + `extracted_data` block + `file_path`/`stored_filename`.
- [ ] Transaction formatter — add `receipt_status` where `receipt_*` fields already appear.

### 7. Frontend — `features/receipts/api.js`

- [ ] Add `listReceipts(params)`, `getReceipt(id)`, `updateReceipt(id, fields)`, `getReceiptCandidates(id)`, `linkReceipt(id, transactionId)`, `unlinkReceipt(id)`, `getReceiptsSummary()`.
- [ ] Fix `deleteReceipt` to match the retained backend route.
- [ ] Remove or fix `getReceiptImage` (binary endpoint behind JSON `apiCall`).
- [ ] Add `CONFLICT` and `UNSUPPORTED_FILE_TYPE` to `lib/apiErrors.js` `ErrorCode` + message templates.

### 8. Frontend — `ProcessReceipts.jsx`

- [ ] Rename UI status `'saved'` → `'unlinked'` everywhere (`SelectableReceiptTable` borders/icons, badges, `selectNextReceipt`, counts). Treat server `status` as source of truth for server-loaded rows.
- [ ] Normalise receipt objects to one shape: `{receipt_id, filename, status, extracted_data, linked_transaction_id, source: 'session' | 'server'}` via a `toReceiptRow()` helper used by both upload stream and `listReceipts`.
- [ ] Replace left-column "Receipts" card body with a tabbed component `ReceiptListTabs`:
  - **Session** tab — existing behaviour.
  - **Unlinked (N)** tab — `listReceipts({status:'pending,unlinked'})`, filters (vendor text, date range, amount), pagination; refresh on link/delete/confirm.
- [ ] On select of a server-sourced receipt, hydrate `editableData` from `getReceipt(id)`.
- [ ] Enable vendor/date/amount inputs, Save, Generate Cash, Delete, and candidate list when `status ∈ {pending, unlinked}`; read-only only when `linked`.
- [ ] Change Save: for `unlinked`, call `updateReceipt` instead of `confirmReceipt`.
- [ ] Change `handleSelectTransaction`: `confirm/update` then `linkReceipt(receiptId, txn.id)`; drop `updateTransaction(..., {receipt_id})`.
- [ ] Add "Unlink" button for `linked` receipts → `unlinkReceipt`; return row to `unlinked`.
- [ ] Handle `CONFLICT` from link: toast + `setCandidateRefreshKey`.
- [ ] Change status badge for `unlinked`: amber, label "Saved — not linked".
- [ ] Change "Clear All" → "Clear session" with tooltip "Receipts stay available under Unlinked".
- [ ] Update header count: `{pending} pending, {unlinked} unlinked, {linked} linked` (session tab) — reuse `summary` for Unlinked tab.

### 9. Frontend — `SelectableReceiptTable.jsx`

- [ ] Accept `status` values `pending | unlinked | linked`; update `STATUS_BORDER`, `STATUS_ICON_CLS`, `getStatusIcon`.
- [ ] Make remove (✕) column optional via prop `showRemove` (hidden on Unlinked tab).
- [ ] Accept `emptyMessage` prop.

### 10. Frontend — nav badge (`App.jsx`)

- [ ] Add `ReceiptsNavLink` component: fetches `getReceiptsSummary()` on mount and on `receipts:changed` custom window event; renders `Process Receipts (N)` when `pending+unlinked > 0`.
- [ ] Dispatch `receipts:changed` after confirm/link/unlink/delete in `ProcessReceipts` and `ReceiptUploadModal`.

### 11. Frontend — `ReceiptUploadModal.jsx` (Transactions page)

- [ ] No UI change. Verify `linkReceipt` still works through the refactored `/transactions/<id>/link-receipt`.
- [ ] Dispatch `receipts:changed` on success.

### 12. Tests

Backend
- [ ] Migration: fresh DB and legacy DB (with linked `transactions.receipt_id`) both reach correct `status` and `receipt_links` rows; `user_version` stamped.
- [ ] `ReceiptLinkService.link`: happy path; receipt already linked → 409; transaction already linked → 409; deleted transaction → 404; mirror column set.
- [ ] `unlink_receipt` / `unlink_transaction`: status returns to `unlinked`, mirror nulled.
- [ ] Transaction soft-delete releases receipt.
- [ ] `GET /receipts` filters, pagination, invalid status → 400 with `field='status'`.
- [ ] `GET /receipts/<id>/candidates` uses config date tolerance (assert 5-day window, 6-day excluded).
- [ ] `DELETE /receipts/<id>` on linked → 409 `HAS_DEPENDENCIES`; with `force=true` unlinks then deletes.
- [ ] `confirm` sets `unlinked` + `confirmed_at`.

Frontend
- [ ] `ReceiptListTabs` renders server receipts; selecting hydrates detail panel.
- [ ] `unlinked` receipt has enabled inputs and candidate list; `linked` is read-only with Unlink.
- [ ] Link flow calls `linkReceipt` not `updateTransaction`.
- [ ] Nav badge count updates after link.

### 13. Acceptance criteria

- [ ] Upload receipts, Save one without linking, refresh browser → receipt appears under **Unlinked**.
- [ ] Upload receipts, navigate away mid-session without Saving → receipts appear under **Unlinked** (as `pending`).
- [ ] Import a statement containing the matching transaction → open Unlinked receipt → candidate appears within 5 days → link succeeds → receipt disappears from Unlinked, badge decrements.
- [ ] Deleting a transaction leaves its receipt linked; restoring the transaction restores the relationship with no further action.
- [ ] Existing Transactions-page "Attach receipt" flow unchanged.
- [ ] `pay_months` and `export` views still queryable on startup.

### 14. Out of scope (later phases)

- `receipt_matching` scorer / party-name scoring / reverse suggestions (Phase 2).
- Import hook, `POST /receipts/match`, review modal, auto-link threshold in use (Phase 3).
- Dropping `transactions.receipt_id`; relaxing `receipt_links` UNIQUE constraints; stale-pending sweep (Phase 4 / split-transactions work).
- child-inherits-parent-receipt display resolution — split project

## Undo Delete Transaction

When we add an action slot to our Toast implementation we can add undo delete functionality to the front end. The undo path is straightforward — each deleted_id needs a restore call, and the cascade-restore in the backend handles children automatically:

```javascript
addToast({
  message: `${result.deleted_count} transaction(s) deleted`,
  type: 'success',
  duration: 8000,
  action: {
    label: 'Undo',
    onClick: async () => {
      try {
        // Restore in parallel — each one restores its own cascade children.
        await Promise.all(
          result.deleted_ids.map((id) => restoreTransaction(id))
        );
        await loadTransactions();
        addToast({ message: 'Transactions restored', type: 'success', duration: 3000 });
      } catch (err) {
        addToast({
          message: `Failed to undo: ${err.userMessage || err.message}`,
          type: 'error',
        });
      }
    },
  },
});
```

## Model / schema drift

### Phase 1

- [ ] **`Receipt` dataclass vs `receipts` table** — dataclass is a pipeline working object, not a row model: field name mismatches (`extracted_text` ↔ `raw_text`), type mismatches (`confidence` float ↔ INTEGER 0–3), DB columns with no dataclass counterpart (`metadata`, `created_at`, `updated_at`, and now `status`, `confirmed_at`). Split into `ReceiptPipelineState` + `ReceiptRecord`, or adopt a single `row_to_model` path.
- [ ] **`Transaction.receipt_id` is a derived mirror** — maintained by `ReceiptLinkService` from `receipt_links`. Add docstring note now; drop the column (and rewrite the `export` view + hierarchy joins) when split-receipts work lands.
- [ ] **`validate_receipt_update` ↔ `ReceiptRepository.update` parameter agreement** — currently enforced only by `TypeError` on unknown kwargs plus one route test. Add an explicit shared field list or agreement test (same pattern as `TRANSACTION_UPDATABLE_FIELDS`).
- [ ] **Frontend/backend `ErrorCode` agreement** — mirror maintained by hand; was missing `CONFLICT`, `UNSUPPORTED_FILE_TYPE`, `INSUFFICIENT_CAPACITY`. Add a test that diffs `apiErrors.js` against `errors.py`, or generate one from the other.

### Small code-quality fixes

- [ ] **Cast `MAX_WORKERS` and `GEMINI_MAX_CONCURRENCY` with `int()`** in `create_app` — currently `str` when set via env, `int` when defaulted; `ThreadPoolExecutor(max_workers="4")` will raise.
- [ ] **Remove/gate the `url_map` `print()` loop in `create_app`** — noisy in tests; should be `logger.debug` behind a flag.
- [ ] **sqlite3 datetime adapter deprecation** — `find_matching_transactions` (and anywhere else) binds `datetime` objects relying on the default adapter, deprecated in 3.12. Normalise to ISO strings before binding (pattern: `ReceiptRepository._to_date_str`).
- [ ] **Migrations module docstring** — note that `INDEXES` may reference columns introduced by `MIGRATIONS` and are applied after all migrations, never in between (bit us in the legacy-fixture test setup).

### Documentation updates

- [ ] **Revise split-transaction design notes (receipt handling)** — do *not* copy `receipt_id` to children. Children inherit the parent's receipt for display via `source_transaction_id` (resolution: own link → parent link → none); parent keeps its link when superseded. Affects `export` view, `find_matching_transactions`, transaction formatters. If one-receipt-many-transactions is later preferred: drop `uq_receipt_links_receipt_id` index (one-line migration, no table rebuild) and extend `VALID_LINK_SOURCES`.

## Phase 2 — match both directions

- [ ] Extract `receipt_matching` service (scorer + finder) from the candidate-search logic; score on amount, date proximity (config tolerance), and **party name** (via `matchParty`-style resolution, not raw description).
- [ ] `GET /transactions/<id>/receipt-suggestions` — reverse lookup: ranked unlinked receipts for a transaction.
- [ ] Transactions page: "Attach receipt" control gains *Suggested receipts* + *Browse unlinked…* picker alongside upload.

## Phase 3 — proactive matching on import

- [ ] `POST /receipts/match` + `POST /receipts/link-batch` endpoints.
- [ ] Statement import hook: run `match_batch` over new transactions × unlinked receipts; return `receipt_matches` summary in import response.
- [ ] `ReceiptMatchReviewModal` — accept/reject suggested pairs, bulk accept above threshold, undo auto-links.
- [ ] Enable `RECEIPT_AUTO_LINK_THRESHOLD` (config already in place, default 0.98; conservative, off-by-default behaviour until scorer trusted).

## Phase 4 — polish

- [ ] Unlinked view filter: **"linked to a deleted transaction"** + explicit *Release* action (`unlink_transaction` exists and supports soft-deleted rows; nothing calls it automatically by design).
- [ ] Stale-`pending` sweep — scheduled job to promote (or flag) pending receipts older than N days so abandoned uploads surface in the Unlinked view.
- [ ] Match-dismissals table (`receipt_match_dismissals`) so rejected suggestions aren't re-shown.
- [ ] Thumbnail endpoint for receipt pickers (avoid full-size image loads in lists).
- [ ] "Find matches" button on the Unlinked tab (runs `POST /receipts/match` with no transaction filter).

# Split Transaction — Implementation Notes

## Overview

Allow a user to split a single transaction into two or more child transactions whose amounts sum to the original. The parent is hidden (not deleted) and the children take its place in every view. Reversible via an "unsplit" operation that discards the children and restores the parent.

---

## Data model

No schema changes required. Uses fields already in place:

| Field (on child) | Value |
|---|---|
| `source_transaction_id` | Parent's `id` |
| `source_relationship` | `'split'` |
| `transaction_date` | Inherited from parent |
| `account_id` | Inherited from parent |
| `upload_id` | Inherited from parent |
| `is_credit` | Inherited from parent |

| Field (on parent) | Value |
|---|---|
| `deleted_at` | Stamped at split time |
| `deleted_reason` | `'superseded'` |

The user supplies per-child: `amount`, `party_id`, and optionally `description`, `cleaned_description`, `is_kids`, `is_one_off`.

---

## Invariants to enforce

**Amount conservation.** `sum(child.amount) == parent.amount`. Validate before writing. Use exact decimal comparison — convert both sides to `round(x, 2)` or `Decimal` before comparing, because IEEE 754 floats will betray you on splits like £10.00 → £3.33 + £3.33 + £3.34. If the amounts don't sum, reject with a clear error — do not silently adjust.

**Minimum children.** A split must produce ≥ 2 children. A single child is a no-op that just hides the original.

**Depth limit.** The parent must have `source_transaction_id IS NULL`. Splitting a child of a split (or a generated cash lodgement) would create depth > 1 and make cascade delete/restore recursive. Reject with a message pointing the user to the root transaction.

**Parent must be live.** `parent.deleted_at IS NULL`. You can't split something that's already deleted or already superseded (i.e. already split). Reject both.

**Credit/debit consistency.** Every child must inherit the parent's `is_credit` value. A debit can't be split into a debit and a credit — that's a different operation (a transfer, or a correction).

---

## Service: `split_transaction(parent_id, parts)`

### Input

```python
parent_id: int
parts: List[Dict]   # each dict has at least {amount, party_id}
```

### Flow

```
1.  Read parent row (must exist, must be live, must have source_transaction_id IS NULL).
2.  Validate len(parts) >= 2.
3.  Validate sum(part.amount) == parent.amount   (after rounding).
4.  Validate each part.amount > 0.
5.  Inside a single db transaction:
      a.  INSERT each child:
            - Copy transaction_date, account_id, upload_id, is_credit from parent.
            - Set source_transaction_id = parent.id
            - Set source_relationship = 'split'
            - Set amount, party_id, description, is_kids, is_one_off from the part dict.
            - Set cleaned_description from part dict or NULL.
      b.  UPDATE parent:
            - deleted_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
            - deleted_reason = 'superseded'
      c.  Collect child IDs from lastrowid.
6.  Return { parent_id, child_ids, child_count }.
```

**Do not call `delete_transaction()` in step 5b.** That method stamps `deleted_reason = 'user'` (which would put the parent in the recycle bin) and cascades to generated children (which would destroy any cash lodgement derived from this transaction). Write the UPDATE directly, within the same cursor. Worth a code comment explaining why.

### Receipt handling (revised)

Do not copy receipt_id to children. Receipt linkage lives in receipt_links; the parent's link is left intact when the parent is superseded (deleted transactions keep their receipts). Children inherit the receipt for display via source_transaction_id; a child may also hold its own link. Resolution order: own link → parent link → none. transactions.receipt_id on a child is therefore NULL unless it has its own link.


Affects: export view, find_matching_transactions receipt join, transaction formatters — each needs a LEFT JOIN receipt_links parent_rl ON parent_rl.transaction_id = t.source_transaction_id and a COALESCE.


Unsplit: children keep any child-specific links (consistent with the deleted-keeps-receipt rule). These receipts show as "linked to a deleted transaction" in the Unlinked view filter (Phase 4 backlog) with a Release action. No warning needed before unsplit.


If a one-receipt-many-transactions model is later preferred, drop uq_receipt_links_receipt_id in a migration and add link_source = 'split' handling in ReceiptLinkService. No table rebuild required.

### Suggested location

`src/services/split_transaction.py` alongside the existing cash generation service. Depends on `TransactionRepository` for reads and the connection manager for the write transaction. Alternatively add a `split_transaction` method directly to the repository — either works, but a service is consistent with how cash generation is structured.

---

## Service: `unsplit_transaction(parent_id)`

### Input

```python
parent_id: int
```

### Flow

```
1.  Read parent row.
      - Must exist.
      - Must have deleted_reason = 'superseded'.
        (If it's live → it was never split. If reason is 'user' → the user
         deleted it independently after it was already split, which shouldn't
         happen because delete_transaction rejects rows that are already
         deleted, but guard anyway.)
2.  Read children: source_transaction_id = parent_id
                    AND source_relationship = 'split'.
      - Children should all be live (deleted_at IS NULL).
        If any child has been manually deleted, something unexpected
        happened — log a warning but proceed. The goal is to restore
        the parent and hide all children regardless of their current state.
3.  Inside a single db transaction:
      a.  UPDATE children:
            - deleted_at = now
            - deleted_reason = 'unsplit'
          Use a single UPDATE ... WHERE source_transaction_id = ? AND source_relationship = 'split'
          (don't filter on deleted_at — catch any straggler state).
      b.  UPDATE parent:
            - deleted_at = NULL
            - deleted_reason = NULL
4.  Return { parent_id, removed_child_ids }.
```

The frontend needs `removed_child_ids` to pull them out of the transaction list and insert the restored parent.

### What about receipts on children?

If the user attached a *different* receipt to a child (not inherited from the parent), unsplitting hides the child and that receipt becomes effectively orphaned in the UI. Options:

- **Do nothing.** Receipts stay in the receipts table; they're just not linked to any visible transaction. The user can re-link them later. Simplest, and fine for a personal app.
- **Warn before unsplitting** if any child has a `receipt_id` that differs from the parent's. Return the warning, let the frontend confirm.

Recommend option 1 initially, option 2 as a polish pass.

---

## What split children can and can't do

| Operation | Allowed? | Reason |
|---|---|---|
| View / list | ✅ | They're live rows |
| Edit `party_id`, `description`, `is_kids`, `is_one_off` | ✅ | Recategorisation is the whole point |
| Edit `amount` | ❌ | Breaks conservation; unsplit and re-split instead |
| Edit `transaction_date`, `account_id`, `is_credit` | ❌ | Inherited from parent, must stay in sync |
| Delete | ❌ | `delete_transaction` rejects `source_relationship = 'split'` (already implemented) |
| Link receipt | ✅ | Useful — the clothing portion has a different receipt |
| Split again | ❌ | Depth limit: `source_transaction_id IS NOT NULL` → reject |
| Generate cash | ❌ | Same depth limit check |

Enforce the edit restrictions in `update_transaction` by checking `source_relationship = 'split'` and rejecting writes to the locked fields. Suggest a new set:

```python
SPLIT_LOCKED_FIELDS = {'amount', 'transaction_date', 'account_id', 'is_credit'}
```

If any kwargs key is in `SPLIT_LOCKED_FIELDS` and the row has `source_relationship = 'split'`, raise `TransactionRuleError`.

---

## API routes

| Verb | Path | Body | Returns |
|---|---|---|---|
| `POST` | `/api/transactions/<id>/split` | `{ "parts": [{amount, party_id, ...}, ...] }` | `{ parent_id, child_ids }` — 201 |
| `POST` | `/api/transactions/<id>/unsplit` | (empty) | `{ parent_id, removed_child_ids }` — 200 |

Error responses:

| Condition | Status | Message |
|---|---|---|
| Parent not found / already deleted | 404 | Transaction not found |
| Already split (`deleted_reason = 'superseded'`) | 409 | Transaction is already split |
| Is itself a child | 409 | Cannot split a child transaction; split the root instead |
| Amounts don't sum | 422 | Split amounts (£X) do not equal transaction amount (£Y) |
| Fewer than 2 parts | 422 | A split must produce at least 2 transactions |
| Unsplit a non-split row | 409 | Transaction is not split |

---

## Frontend sketch

**Split dialog:** user sees the parent amount and adds rows. Each row has amount + party selector (and optionally the other editable fields). A running total and remainder are shown. Submit is disabled until remainder = 0 and parts ≥ 2. On success, remove the parent row from the list and insert the children.

**Unsplit button:** visible on any transaction where `source_relationship = 'split'`. Confirms, calls unsplit, removes children from the list, inserts the restored parent. If the parent had a different `party_id` / category, the row visually changes — expected, because it's reverting to the original.

**Visual indicator:** split children could show a small "split" badge or icon linking back to siblings. Clicking it filters to all children of the same parent. Low priority but nice for orientation.

---

## Testing checklist

- [ ] Split a transaction into 2 parts — parent hidden, children visible, amounts sum correctly.
- [ ] Split into 3+ parts.
- [ ] Reject split where amounts don't sum.
- [ ] Reject split of an already-split parent.
- [ ] Reject split of a child (depth limit).
- [ ] Reject split of a deleted transaction.
- [ ] Unsplit — parent restored, children hidden.
- [ ] Unsplit when a child has been edited (party changed) — parent still has original values.
- [ ] Reject deleting a split child via `delete_transaction`.
- [ ] Reject deleting a split child via `bulk_delete_transactions`.
- [ ] `update_transaction` on a split child: allow `party_id`, reject `amount`.
- [ ] Verify aggregates (sum, count, charts) count children but not the superseded parent.
- [ ] Receipt copied from parent to children on split.
- [ ] Receipt survives unsplit on parent.
- [ ] Generate cash from a transaction, then split it → reject (depth limit on the cash lodgement) or → reject the split (parent has generated children and cascading superseded + cascade would conflict). Decide which guard fires first and test it.


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

# Tailwind CSS Migration — Progress Note

**Branch:** `feature/tailwind-css` (worktree: `wt-tailwind-css`)

## Context

Migrating the frontend from individual CSS files to Tailwind CSS v4:
- No `tailwind.config.js` or `postcss.config.js`.
- Setup via the `@tailwindcss/vite` plugin in `vite.config.js`.
- Single `@import "tailwindcss";` in `frontend/src/index.css`.
- Theme customization in CSS via `@theme {}`.

**App is light-mode only.** Vite's dark-mode template styles were removed from `index.css`. Several CSS files still had `prefers-color-scheme: dark` as the base with a light override — all settled as light-only during migration.

## Done — Infrastructure

- [x] Installed `tailwindcss` + `@tailwindcss/vite`.
- [x] Configured `vite.config.js` with the `tailwindcss()` plugin.
- [x] `@import "tailwindcss"` in `frontend/src/index.css`.
- [x] `index.css` cleaned — only `:root` font-family/rendering block above the import.
- [x] `@theme` tokens: `--font-sans`, `--color-danger-bg/border/text`, `--color-muted`, `--color-info-bg/border/text`, `--animate-fade-in`, `--animate-highlight-pulse`.
- [x] `src/styles/modalClasses.js` — canonical shared modal chrome (Tailwind const strings). Derived from RemapPartyModal.css, which was the best-specified modal CSS (all-Tailwind palette, light-only, correct scroll contract). Width variants `W_SM`/`W_MD`/`W_LG`/`W_XL` catalogue the five widths found.

## Done — Feature pages & leaf components

### Hierarchy feature
- [x] `CategoryHierarchyPage`, `HierarchyTree`, `HierarchyDetailPanel`, `EditNodeModal` — all migrated + CSS deleted.

### statementFormats feature
- [x] `StatementFormatsPage`, `FormatList`, `FormatEditorPage`, `FormatEditor`, `Stepper`, `ParsedPreviewTable` — all migrated + CSS deleted.
- [x] Step components (`StepSampleFile`, `StepIdentity`, `StepColumns`, `StepDefaults`, `StepPreview`) — all migrated + CSS deleted. Shared `fe-step` scaffolding inlined.
- [~] `DeleteFormatDialog` — no dedicated CSS; deferred `list-disc pl-5` fix until `ConfirmDialog` is migrated.

### statements feature
- [x] `UploadStatement` — migrated + CSS deleted. Preview-table-wrapper conflict resolved (inline styles removed → flex-fill). `PAGE_BODY_H` const shared between branches.
- [x] `ImportResult` — migrated + CSS deleted. Scroll bug fixed (`h-full` → `flex-1 min-h-0`).
- [x] `ProcessingWarningsPanel` (shared) — migrated + CSS deleted. `list-disc pl-5` restored on `<ul>`. `pwp-code-*` → `data-warning-code`.
- [x] `ColumnMismatchPanel` (shared) — migrated + CSS deleted. All 12 colours were exact Tailwind values.

### receipts feature
- [x] `ProcessReceipts` — migrated. **CSS deletion BLOCKED** on `.radio-row`/`.radio-option`/`.checkbox-option` — grep child components before removing.
- [x] `BulkUploadReceipts` — migrated + CSS deleted. Drag-over state lifted from `classList` to React state.
- [x] `SelectableReceiptTable` — migrated + CSS deleted. Row-state cascade replaced with `rowCls()`.
- [x] `ImagePreview` — migrated + CSS deleted. Kept react-pdf vendor imports. Image-hidden-during-load bug fixed.
- [x] `CandidateTransactions` — migrated + CSS deleted. Custom `@keyframes` added to `@theme`.
- [x] `ReceiptIcon` — migrated + CSS deleted.

### transactions feature
- [x] `CategorizeTransactions` — migrated + CSS deleted.
- [x] `TransactionTable` + `TransactionRow` — both migrated, both CSS files deleted. Zebra-beats-selection specificity bug fixed. All `!important` eliminated. Party-cell flex restructured.
- [x] `BulkEditModal` — migrated. **Needs correction** to use `M.*` constants (my initial migration used BulkEditModal.css values, but RemapPartyModal.css was winning at runtime — see modal notes). **CSS deletion GATED** on grep for generic class consumers.
- [x] `CreateCategoryModal` — fully migrated (both its own CSS + Modal.css). Uses `M.*` + own form consts.
- [x] `RemapPartyModal` — migrated + CSS deleted. Source of the `overflow: hidden` ImagePreview was fighting. Design promoted to canonical `modalClasses.js`.
- [x] `RemapPartyPrompt` — migrated + CSS deleted. All 9 colours exact Tailwind. Standalone (not a `modalClasses.js` consumer).
- [x] `ReceiptViewModal` — migrated + CSS deleted.
- [x] `ReceiptUploadModal` — migrated + CSS deleted.
- [?] `FilterBar` — migrated, but **may be dead code**. `CategorizeTransactions` doesn't import it; `TransactionTable` has its own inline filter row. Grep `FilterBar` — if orphaned, delete component instead.

## Done — Bugs found & fixed

| Bug | Where | Fix |
|---|---|---|
| Selection/edit highlights invisible on even rows | TransactionTable + TransactionRow | Zebra (specificity 0,2,2) beat `.selected`/`.editing` (0,2,0). Now computed per-state. |
| `display:flex` on `<td>` broke table layout + killed ellipsis | TransactionRow `.party-cell` | Flex moved to inner `<div>`. |
| Image never hidden during load | ImagePreview | `.image-preview-img { display:block }` defined after `.hidden { display:none }`, winning by source order. Now explicit `isLoading ? 'hidden' : 'block'`. |
| ImportResult scroll contract inert | UploadStatement + ImportResult | `h-full` → `flex-1 min-h-0`; wrapper given definite height via `PAGE_BODY_H`. |
| `.checkbox-field` stacked vertically | BulkEditModal | `flex-direction` inherited from `.form-field { column }` — never reset. Now `flex-row`. |
| Dark inputs on light page | FilterBar, BulkEditModal | Vite template dark-mode-first CSS. Settled light-only. |
| 4 buttons relying on deleted Vite global `button` rule | `.new-cash-button`, `.clear-filters-button`, `.save-button`, `.cancel-button` | Each given explicit styling. |
| `.description-cell` wrapping load-order-dependent | TransactionTable | Settled as truncate + expand-on-hover. |
| Error focus ring stayed blue | CreateCategoryModal | `outline-color` on `outline: none` was inert. Switched to red box-shadow. |

## CSS files not yet deletable

| File | Blocker |
|---|---|
| `ProcessReceipts.css` | `.radio-row`/`.radio-option`/`.checkbox-option` may be consumed by child components (GenerateCashFromReceiptModal, etc.). Grep before deleting. |
| `BulkEditModal.css` | Generic `.modal-overlay`/`.modal-content`/etc. may be consumed by other modals. Grep before deleting. Likely safe now that `modalClasses.js` + per-modal migrations cover the same classes. |

## Next — shared components (next PR)

Priority order based on blast radius and what's currently broken:

| Component | Priority | Why |
|---|---|---|
| `DropdownWithCreate` | **P0** | `.dropdown-with-create select` styling lived in deleted TransactionRow.css. Replicated for TransactionRow only; selects in BulkEditModal / RemapPartyModal / CreateCashTransactionModal / GenerateCashFromReceiptModal are currently unstyled. |
| `ConfirmDialog` + CSS | **P1** | Used by `DeleteFormatDialog`; still on raw CSS. Blocks the deferred `list-disc pl-5` fix. Check blast radius first. |
| `Button` | **P1** | Used everywhere. Natural convergence point for the primary-blue decision and the `--color-success`/`--color-danger` tokens. |
| `Pagination` | P2 | Used by CategorizeTransactions. |
| `Dropdown` | P2 | Used by FilterBar (if not dead). |
| `FileDropzone` | P2 | Used by UploadStatement + StepSampleFile. |
| `FilePreview` | P3 | Used by BulkUploadReceipts. |
| `Checkbox` | P3 | Used widely — but may already be unstyled / headless. Confirm. |
| `FormField`, `TextInput`, `NumberInput`, `ChipInput` | P3 | Format-editor field components. |
| `Thumbnail` | P3 | Used by SelectableReceiptTable. |
| Remaining modals: `GenerateCashModal`, `CreateCashTransactionModal`, `GenerateCashFromReceiptModal` | P2 | Swap `import '@/styles/Modal.css'` → `import * as M from '@/styles/modalClasses'`. Mechanical — follow the consumer migration guide in the RemapPartyModal notes. |

### Also pending
- [~] `DeleteFormatDialog` `<ul>` + body spacing — deferred until `ConfirmDialog` migrated.
- [ ] Correct `BulkEditModal.jsx` to use `M.*` constants (diff provided in RemapPartyModal session).
- [ ] Delete `ProcessReceipts.css` and `BulkEditModal.css` once greps pass.
- [ ] Verify `FilterBar` is still imported; if not, delete the component.

## Token sweep (do alongside or after shared components)

These are deliberate decisions deferred to avoid blocking leaf migrations. Resolve in one pass.

### Primary blue — pick one

| Hex | Source | Files |
|---|---|---|
| `#007bff` / `#0056b3` | Bootstrap | Stepper, ProcessReceipts, BulkUploadReceipts |
| `#2196f3` / `#1976d2` | Material | ImportResult, CandidateTransactions, CategorizeTransactions, old Modal.css |
| `#4a90e2` | Bespoke | UploadStatement focus, CategorizeTransactions focus |
| `#2563eb` / `#1d4ed8` | Tailwind blue-600/700 | modalClasses.js (canonical), CreateCategoryModal focus, RemapPartyModal |
| `#646cff` | Vite template | FilterBar (possibly dead) |

**Recommendation:** `#2563eb` (blue-600). It's the canonical modal standard now, it's an actual Tailwind value (no arbitrary hex needed), and it has a natural hover shade (`blue-700`). Promote as `--color-primary` / `--color-primary-hover`. The `Button` migration is the right moment.

### Status greens — pick one

| Hex | Source | Usage |
|---|---|---|
| `green-800` / `green-50` | Tailwind | ParsedPreviewTable credit, ColumnMismatchPanel present (2 files, byte-identical) |
| `#28a745` / `#218838` | Bootstrap | Stepper done, UploadStatement import-btn, TransactionRow save-btn |
| `#4caf50` / `#388e3c` | Material | TransactionRow save-btn, ReceiptIcon attached, ReceiptUploadModal upload-btn |
| `#43a047` / `#2e7d32` | Material (darker) | ProcessReceipts generate-cash-btn, CategorizeTransactions generate-cash-btn |
| `emerald-600` / `emerald-50` | Tailwind | RemapPartyPrompt "this txn only" (semantically distinct) |

**Recommendation:** Tailwind defaults (`green-800`/`green-50`) for *semantic* status; promote Bootstrap `#28a745` as `--color-success` for *UI chrome* (buttons, badges). Keep emerald separate (it's contextual, not status).

### Status reds — already mostly converged

- Danger tokens (`--color-danger-bg/border/text`) use the Bootstrap family.
- ColumnMismatchPanel, TransactionRow, and the canonical modal error use Tailwind `red-*` values.
- **Action:** add `--color-error: theme(colors.red.600)` and `--color-error-bg: theme(colors.red.50)` for the Tailwind-native family. Keep danger tokens for the heavier Bootstrap-style alert banners. Or consolidate onto one family — but the two serve different visual weights.

### Warning palettes — pick one

| Family | Files |
|---|---|
| Bootstrap (`#fff3cd`/`#ffc107`/`#856404`) | UploadStatement `.format-warning` |
| Bespoke warm (`#fef9e7`/`#f0c36d`/`#6b5a2a` + divider/muted/chip) | ProcessingWarningsPanel |

**Recommendation:** the PWP family is more complete. Promote as `--color-warning-bg/border/text/divider/muted/chip-border`.

### Other token candidates

| Token | Value | Used in |
|---|---|---|
| `--color-success` | `#28a745` | Stepper, UploadStatement, btn-save |
| `--color-success-hover` | `#218838` | hover shades of above |
| `--color-success-bg/border/text` | `#d4edda`/`#c3e6cb`/`#155724` | ImportResult success banner |
| `--color-money-in` | `green-800` | ParsedPreviewTable, ColumnMismatchPanel |
| `--color-money-out` | `red-800` | ParsedPreviewTable, ColumnMismatchPanel |
| `--spacing-page-body` | `calc(100vh - 200px)` | UploadStatement (`PAGE_BODY_H`), TransactionTable container |
| `--text-page-title` | `text-2xl` (24px) or `text-[28px]` | UploadStatement/ProcessReceipts (24) vs CategorizeTransactions (28) |
| `--shadow-focus-ring` | `0 0 0 3px …` | UploadStatement (3px), CategorizeTransactions (2px) |

### Muted grey — one sweep

`#6c757d` is the `--color-muted` token. Several files still use `text-gray-500` (`#6b7280`). One pass to replace with `text-muted` for exact consistency.

## Watch-outs — still active

### Preflight
- **`p` margins / `ul` list-style zeroed.** Restore with `space-y-*` / `list-disc pl-5` where the old look relied on UA defaults.
- **`cursor: pointer` removed from buttons in v4.** Must be explicit on every `<button>`.
- **Heading size + weight zeroed.** Every `<h1>`–`<h6>` needs explicit classes.

### Scroll contracts
- **`min-h-0` (or `overflow-*`) is required on every flex child that should shrink below content.** Missing it silently kills scrolling. This caused the ImportResult bug and is the reason `ReceiptViewModal`'s `min-h-[200px]` is load-bearing.
- **`PAGE_BODY_H` (`calc(100vh - 200px)`)** is a hardcoded guess at app-chrome height, used in UploadStatement and TransactionTable container. A proper app-shell flex layout would eliminate it.

### Sticky thead + `border-collapse`
- Borders on sticky `<th>` cells can visually detach in Chromium because collapsed borders aren't owned by the cell. `ParsedPreviewTable` offered a `shadow-[inset_…]` fix; not yet applied anywhere.
- `TransactionTable`'s filter row offset (`top-11` = 44px) is hardcoded to the header row's computed height — fragile.

### Modal system
- **`modalClasses.js` is the single source of truth** for modal chrome. Derived from RemapPartyModal.css (the design that was actually winning at runtime for both it and BulkEditModal).
- **BulkEditModal needs correcting** to use `M.*` constants (diff provided).
- **Remaining modals** (`GenerateCashModal`, `CreateCashTransactionModal`, `GenerateCashFromReceiptModal`) need mechanical `Modal.css` → `M.*` swap.
- **`<Modal>` component extraction** would collapse five implementations into one with size variants and is the natural next step after the mechanical swaps. Also resolves the deferred `ConfirmDialog`.

### Scrollbar styling
- Three nearly-identical `SCROLLBAR` const definitions (ProcessReceipts, SelectableReceiptTable, CandidateTransactions) with slightly different thumb colours. Consolidate into a single `@utility` or shared const.

### `!important` syntax
- `ImagePreview`'s canvas guard uses v4's trailing-`!` syntax (`max-w-full!`). Verify it compiles; fall back to prefix `!max-w-full` if not.

### Cross-feature CSS leakage
- Now largely resolved, but assume any "class used in JSX with no local rule" was being fed by another feature's stylesheet. The `DropdownWithCreate` select styling (P0) is the last confirmed case.

### Vite template residue
- `#646cff` (Vite purple) appears in FilterBar. If FilterBar is dead, this disappears. Otherwise replace with `--color-primary`.
- Grep `#1a1a1a`, `#213547`, `rgba(255,255,255,0.87)`, `#646cff` across remaining unmigrated CSS to catch more dark-mode-first files.

### Generic class-name collisions
- `.amount-cell` collision (ImportResult × CandidateTransactions × TransactionTable × TransactionRow) is **fully closed** — all four components migrated.
- Worth grepping for other generic names still live in unmigrated CSS: `.date-cell`, `.party-cell`, `.actions-cell`, `.table-header`, `.btn-remove`, `.empty-state`.

# Test drift
- TestDataFactory.create_upload was inserting only filename, so any API test touching transactions has been failing against the current schema since original_filename/file_type were made NOT NULL. Worth a quick pytest tests/test_api -x after this fix to see what else in that suite is stale before we rely on it for the service tests — I'd rather know now than debug schema drift disguised as link-service bugs.
- Single schema-build entry point in src/database/ — e.g. build_schema(db_path) that runs initialize_schema + migrate, called by both connection.init_app() and tests. Then "schema without migrations" becomes impossible to construct by accident.

# Async processor
- `self.max_concurrency = int(max_concurrency or cfg.get("GEMINI_MAX_CONCURRENCY") or DEFAULT_MAX_CONCURRENCY)` — the `int()` here papers over the un-cast env var we backlogged, but `GEMINI_MAX_CONCURRENCY="0"` would be falsy-after-int… actually `"0"` is truthy as a string, then `int("0")` → `Semaphore(0)` deadlocks until stream timeout. Degenerate config, but the config validator from our earlier work is the natural home for a `>= 1` check on it.
- The worker thread runs `ReceiptRepository()` under `self.app.app_context()` — with the lazy `db` property this resolves the right manager per test. Worth confirming the *memory branch* didn't add its own `self.db = get_manager()`-style capture anywhere in `receipt_worker_async`'s dependencies; the test will catch it (writes would go to a previous test's DB and `fetch_one` would miss), which is another reason these tests are worth having.

# Repository bugs found during the unit-test migration

Found while moving `backend/tests/test_database/test_repositories/` onto the
shared DB fixtures in `backend/tests/conftest.py`. Each one has a test already
written and marked `xfail(strict=True)` with a matching reason string, so the
test flips from xfail to a hard failure the moment the bug is fixed — remove
the marker in the same commit as the fix.

Source was left untouched; these are the fixes, not the diagnoses.

## 1. `list()` never re-raises — silently returns `None`
- **Where:** `src/database/repositories/receipts.py`, `ReceiptRepository.list()`.
- **Symptom:** the `except` block ends after `logger.error(...)`, so any DB
  failure returns `None` instead of raising. Callers do
  `rows, total = repo.list(...)` and get `TypeError: cannot unpack
  non-sequence NoneType` instead of a clean `DatabaseError`.
- **Fix:** add `raise DatabaseError(f"Failed to list receipts: {e}") from e`
  to match every other method on the class.
- **Test:** `test_receipts.py::TestErrorWrapping::test_list_failure_surfaces_as_database_error`.
- **Risk:** low. One line. The Unlinked-receipts route is the only caller.

## 2. `delete_party()` guard disagrees with the FK constraint
- **Where:** `src/database/repositories/categories.py`, `delete_party()`.
- **Symptom:** the pre-delete count filters on `deleted_at IS NULL`, so a party
  whose transactions are *all* soft-deleted passes the guard, then fails on
  `ON DELETE RESTRICT` and surfaces as a generic
  `DatabaseError: Failed to delete party: FOREIGN KEY constraint failed`
  rather than the intended "has N associated transaction(s)" message.
- **Fix:** decide the intended rule first, then make guard and schema agree:
  - (a) soft-deleted transactions *should* block deletion → drop
    `AND deleted_at IS NULL` from the count query, and the user gets the clear
    message; or
  - (b) they *shouldn't* → the rows have to be hard-deleted or re-pointed
    inside the same transaction before the `DELETE`, since the FK counts them
    regardless of `deleted_at`.
  (a) is the smaller change and is consistent with `delete_category` /
  `delete_sub_category` / `delete_type`, which all count children unfiltered.
- **Test:** `test_categories.py::TestDeleteParty::test_soft_deleted_transactions_do_not_block_delete`
  (currently asserts (b); flip the assertion if (a) is chosen).
- **Risk:** low, but it's a product decision, not just a code fix.

## 3–5. Three dead-and-broken methods on `TransactionRepository`
All three raise on *every* call. None has a caller anywhere in `src/` — the
listing route uses `get_transactions_with_hierarchy()` and the upload route
uses the DataFrame variant — which is why this has gone unnoticed.

**Decide delete-vs-fix before doing the work.** If they're genuinely dead,
deleting them (plus their tests and xfail markers) is the better outcome;
fixing unused code just creates more surface to maintain. Noted individually
below in case any is wanted.

### 3. `get_transactions()` / `get_transaction_by_id()` — model mismatch
- **Where:** `src/database/repositories/transactions.py`.
- **Symptom:** both `SELECT` `account_name`, `related_party_name` and
  `receipt_filename`, then do `Transaction(**dict(row))`. The dataclass has no
  such fields → `TypeError: unexpected keyword argument 'account_name'`, wrapped
  as `DatabaseError`. Only the empty-result path works.
- **Fix:** either drop the three joined columns from the projection, or add
  them to `Transaction` as non-persisted display fields. Note this is the same
  dataclass-vs-table drift already recorded at the top of this file for
  `Receipt` — worth solving once, in the same style, for both.
- **Tests:** `test_transactions.py`, marker `MODEL_MISMATCH` (7 tests).

### 4. `find_receipt_match_candidates()` — unfinished SQL
- **Where:** `src/database/repositories/transactions.py`.
- **Symptom:** `base_query` starts with a literal `...` where the column list
  should be, so every call raises `sqlite3.OperationalError: near ".": syntax
  error`. Looks like an interrupted edit that was never completed.
- **Fix:** restore the projection (the `t.*` + accounts/parties/receipts joins
  used by `get_transactions()`). Same model-mismatch caveat as #3 applies —
  it also builds `Transaction(**dict(row))`, so it needs #3 resolved to
  actually work end-to-end.
- **Tests:** `test_transactions.py`, marker `BROKEN_SQL` (7 tests).
- **Note:** `find_matching_transactions()` is the live, working equivalent and
  is a superset of this method's behaviour. Deleting this one and pointing any
  future caller at that is probably the right call.

### 5. `bulk_add_transactions_from_objects()` — `lastrowid` after `executemany()`
- **Where:** `src/database/repositories/transactions.py`.
- **Symptom:** derives the inserted IDs from `cursor.lastrowid` after
  `executemany()`. That is `None` on Python 3.12+, so it raises
  `TypeError: unsupported operand type(s) for -: 'NoneType' and 'int'` and the
  whole batch rolls back. The project requires `>=3.11`, so this is live
  breakage on any current interpreter.
- **Fix:** stop inferring contiguous ID ranges. Either `RETURNING id` with
  `executemany` (SQLite 3.35+ / Python 3.10+ supports `RETURNING`, but not
  reliably via `executemany` — verify), or loop `execute()` and collect each
  `lastrowid`, or re-`SELECT` by a batch marker. The sibling
  `bulk_add_transactions()` (DataFrame) infers from `MAX(id)` instead — also
  unsafe under concurrent inserts, per its own docstring note. Worth fixing
  both with one approach.
- **Tests:** `test_transactions.py`, marker `LASTROWID_AFTER_EXECUTEMANY` (1 test).
- **Risk:** the DataFrame variant *is* live (upload route), so if you touch the
  shared ID-inference approach, `tests/test_api` upload paths need a re-run.

## 6. Related, not a bug: `bulk_add_transactions()` date parsing
- **Where:** `src/database/repositories/transactions.py`, DataFrame variant.
- **Symptom:** `pd.to_datetime(...)` with no `format`/`dayfirst` emits
  `UserWarning: Parsing dates in %d/%m/%Y format when dayfirst=False ... was
  specified` for UK/IE-style dates. It currently parses them correctly by
  inference, but inference is per-column and can silently flip on an ambiguous
  batch (e.g. a file where every day ≤ 12).
- **Fix:** pass the format explicitly. The statement config already carries
  `date_format` per bank — thread it through rather than guessing.
- **Risk:** medium if left alone — a silent `05/06` month/day swap is the kind
  of bug that only shows up in reports months later.

## 7. `StatementFormatRepository` not-found inconsistency (no test marker)
Not a bug — no test is xfailed for this — but it surfaced while writing
`test_statement_format.py` and is cheap to tidy.

- **Where:** `src/database/repositories/statement_format.py`.
- **Symptom:** the class docstring claims "Not-found is signaled by returning
  None (reads) or False (deletes), matching the `AccountRepository`
  convention", but `get_format_by_id()` raises `RecordNotFound` instead. Worse,
  `update_format(id)` with *no* fields delegates to `get_format_by_id()` and so
  raises, while `update_format(id, bank_name=...)` returns `None` for the same
  missing ID.
- **Fix:** pick one convention per operation and make the docstring match.
  `RecordNotFound` is arguably the better behaviour (it maps cleanly to a 404
  and can't be ignored), in which case the other repositories are the ones out
  of step — but at minimum the two `update_format` paths should agree.
- **Tests:** `test_statement_format.py::TestGetFormatById` and
  `TestUpdateFormat::test_no_fields_on_missing_format_raises_not_found` pin
  current behaviour, so they'll fail loudly if it changes. Update them with
  the fix.

# Statement pipeline bugs found while adding tests for `statements/base.py`

## 8. A statement with zero surviving rows crashes the pipeline
- **Where:** `src/statements/base.py`, `StatementProcessor._categorize()`.
- **Symptom:** if every row is removed by `exclude_patterns`, or every row is
  dropped for an unparseable date, `_categorize()` is still called with an
  empty frame. `pd.DataFrame([])` has no columns, so
  `df[['cleaned_description', 'party_id', 'confidence']] = ...` raises
  `ValueError: Columns must be same length as key`. The user sees a 500 rather
  than "0 transactions imported".
  The real `TransactionCategorizer.categorize()` also raises
  `ValueError("No transactions data provided")` on an empty list, so the live
  path fails slightly earlier but just as hard.
- **Repro:** a statement containing only rows matching an exclude pattern
  (e.g. an AIB export with nothing but an OPENING BALANCE line), or a file
  where the date column is entirely blank.
- **Fix:** short-circuit in `_categorize()` when `df.empty` — assign the three
  columns as empty/NA and return — then let `_finalize_columns()` produce a
  correctly-shaped empty DataFrame. Worth also deciding whether "file parsed
  but produced 0 transactions" should be a `ProcessingWarning` so the user
  isn't left wondering why nothing imported.
- **Tests:** `tests/test_statements/test_base.py`, marker
  `EMPTY_AFTER_FILTERING` (2 tests).
- **Risk:** low to fix, and it's a plausible real-world file.

## 9. Date fallbacks can return timezone-aware timestamps
- **Where:** `src/statements/base.py`, `_attempt_date_parse()`.
- **Symptom:** the `ISO8601` and `%Y-%m-%dT%H:%M:%S%z` candidates preserve the
  UTC offset, so `transaction_date` comes back tz-aware
  (`Timestamp('2022-10-13 01:02:03+0000', tz='UTC')`) while every other
  candidate yields tz-naive values. Those then go into a SQLite `TEXT` column
  via `bulk_add_transactions`, so the stored string gains a `+00:00` suffix for
  some files and not others — which breaks `transaction_date >= ?` range
  filters comparing against plain `YYYY-MM-DD`.
- **Fix:** normalise at the end of `_attempt_date_parse()` — if the result is
  tz-aware, convert to UTC and drop the tz, or `.dt.date` it, since the rest of
  the system only ever uses the date part.
- **Test:** `test_base.py::TestDateParsing::test_falls_back_when_configured_format_is_wrong`
  currently asserts the tz-aware value, i.e. it documents present behaviour.
  Update it with the fix.
- **Risk:** low to fix; silently wrong query results if left.

## 10. `amount_column=''` passes validation, then dies on `KeyError: ''`
- **Where:** `src/statements/base.py`, `StatementConfig.__post_init__` and
  `StatementConfig.required_columns`.
- **Symptom:** the two branches of the amount check disagree. The split-column
  branch uses truthiness (`amt.credit_column and amt.debit_column`), but the
  single-column branch uses `amt.amount_column is not None`. So an empty
  string satisfies `has_single` and the config is accepted.
  It then fails open all the way down:
  - `required_columns` filters on `if c` and silently drops the blank name, so
    the column list is `['Date', 'Description']`;
  - `_validate_required_columns` therefore finds nothing missing and passes;
  - `_parse_single_amount` does `df['']` and the import dies on a bare
    `KeyError: ''` with no context about which config is at fault.
  A config with a blank amount column is always a configuration error — it
  should never reach the parser.
- **How it gets in:** `StatementConfig.from_dict()` is how user-defined formats
  are loaded from `statement_formats.config_json`, so any UI or API path that
  submits an empty string for the amount column persists a permanently broken
  format that only fails at import time.
- **Fix:** make both branches use the same test. Simplest is
  `has_single = bool(amt.amount_column)`, which makes `''` behave like `None`
  and raises the existing "must specify either credit_column/debit_column or
  amount_column" message at construction. Worth doing the same for
  `credit_indicator_column` and for `description_column` /
  `date_config.column`, which have the same blank-name hazard and no
  validation at all today.
- **Tests:** `tests/test_statements/test_base.py`, marker
  `BLANK_AMOUNT_COLUMN_ACCEPTED` (2 tests) — one asserts construction should
  raise, one asserts the import shouldn't die on a raw `KeyError`.
- **Risk:** low. Validation-only change. Check no builtin config in
  `configs/` relies on a falsy column name first (none do today).

## 11. Credit/debit indicator matching is case- and whitespace-sensitive
- **Where:** `src/statements/base.py`, `_parse_single_amount()`.
- **Symptom:** the indicator is compared with a bare `==`:
  `df[cfg.credit_indicator_column] == cfg.credit_indicator_value`.
  Any row whose indicator doesn't match exactly is treated as a **debit**, and
  with the default `debit_is_negative=True` its amount is multiplied by `-1`.
  So a file using `cr`/`dr` instead of `CR`/`DR`, or one with padded values
  like `' CR '` (common in fixed-width exports converted to CSV), silently
  flips the sign of every credit. No error, no warning — salary lands as a
  -2000.00 expense and every report is wrong.
- **Why it's worse than it looks:** the failure is silent and plausible-looking.
  Unlike a missing column, nothing in the pipeline flags it, and the numbers
  are only obviously wrong if someone reconciles against the bank.
- **Fix:** normalise both sides before comparing — strip and casefold, e.g.
  `df[col].astype(str).str.strip().str.casefold() == str(value).strip().casefold()`.
  Then consider warning on values that match **neither** the credit indicator
  nor an expected debit indicator, since "unrecognised indicator" currently
  falls through to "debit" indistinguishably from a real debit. That would
  need a `debit_indicator_value` on `AmountConfig` to do properly.
- **Tests:** `tests/test_statements/test_base.py`, marker
  `CREDIT_INDICATOR_CASE_SENSITIVE` (2 tests: lowercase `cr`, padded `' CR '`).
  `test_unrecognised_indicator_treated_as_debit` is left passing and
  unmarked — it pins the genuine fall-through behaviour, which is a separate
  decision from the normalisation fix.
- **Risk:** low to fix, high impact if left. No builtin config in `configs/`
  currently sets `credit_indicator_column` (AIB uses split columns; both PTSB
  configs use split or signed amounts), so the exposure today is entirely via
  user-defined formats loaded through `from_dict()` — which is also the path
  with no review step.

## 12. `get("user:abc")` raises a bare `ValueError` instead of an `AppError`
- **Where:** `src/statements/registry.py`, `StatementFormatRegistry.get()`.
- **Symptom:** the user branch is
  `return self._get_user(int(identifier[len(self.USER_PREFIX):]))` with no
  guard. Any non-numeric suffix (`"user:abc"`, `"user:"`, `"user:1.5"`)
  escapes as `ValueError: invalid literal for int() with base 10: 'abc'`.
  Every other lookup failure in this class raises a structured `AppError` with
  a status code, which the API layer surfaces directly — so a malformed
  identifier becomes an unhandled 500 rather than a 404/400 with a useful
  message.
- **How it gets in:** `accounts.statement_format` is a free-form TEXT column
  (see item 7), so a typo or hand-edited row reaches `get()` unvalidated. The
  upload route calls `get_processor(identifier=account['statement_format'], …)`
  with whatever is stored.
- **Fix:** wrap the parse and raise `AppError(NOT_FOUND, …)` — or `BAD_REQUEST`
  if you'd rather distinguish "malformed identifier" from "no such format".
  The bare-key fall-through below it already produces exactly the right error
  for unrecognised input, so the simplest fix is to let a non-numeric suffix
  fall through to it.
- **Tests:** `tests/test_statements/test_registry.py`, marker
  `NON_NUMERIC_USER_ID` (2 tests). They assert `AppError` with a 400 or 404, so
  either choice passes.
- **Risk:** low.

## 13. Injected empty dicts are silently replaced by the module defaults
- **Where:** `src/statements/registry.py`,
  `StatementFormatRegistry.__init__()`.
- **Symptom:** all three dependencies use `or` for their defaults:
  `self._builtin = builtin_configs or STATEMENT_CONFIGS`. An empty dict is
  falsy, so `StatementFormatRegistry(builtin_configs={})` — "I want no
  built-ins" — silently gets the real `STATEMENT_CONFIGS` instead. Same for
  `custom_processors={}`.
- **Why it matters:** the class docstring advertises all three as injectable
  for testing, and this is the one injection that silently does the opposite
  of what's asked. A test that registers no built-ins to check empty-state
  behaviour would pass against the real configs and prove nothing. It's also
  a live footgun if a caller ever wants a deliberately empty registry.
- **Fix:** use an explicit None check:
  `self._builtin = STATEMENT_CONFIGS if builtin_configs is None else builtin_configs`.
  `statement_format_repo` has the same shape but no practical failure mode —
  worth changing all three for consistency.
- **Test:** `tests/test_statements/test_registry.py`, marker
  `EMPTY_INJECTION_IGNORED` (1 test).
- **Risk:** very low. Nothing in `src/` passes an empty dict today.

## 14. Revolut `_parse_description` — dead `fillna` that breaks in pandas 3.0
- **Where:** `src/statements/processors/revolut.py`, `_parse_description()`.
- **Symptom:** `df['Merchant'].fillna('', inplace=True)` is chained assignment
  on a temporary Series. It already does nothing, and pandas says so:
  > FutureWarning: A value is trying to be set on a copy of a DataFrame or
  > Series through chained assignment using an inplace method. The behavior
  > will change in pandas 3.0. This inplace method will never work because the
  > intermediate object on which we are setting values always behaves as a copy.

  The code is correct today only because the `lambda` below it re-checks with
  `pd.notna(row.get('Merchant'))`, so the no-op `fillna` is never load-bearing.
  The project pins `pandas>=2.3.3`, so a 3.0 bump would turn the warning into
  an error.
- **Fix:** delete the line — the `pd.notna` guard already covers nulls. If you
  prefer to keep the normalisation, write it as
  `df['Merchant'] = df['Merchant'].fillna('')`.
  While in here, the `df.apply(..., axis=1)` is a row-wise Python loop over the
  whole statement; a vectorised version would be both faster and simpler:
  ```python
  merchant = df['Merchant'].fillna('').astype(str).str.strip()
  df['description'] = df['description'].where(
      merchant == '', df['description'] + ' - ' + merchant
  )
  ```
  That also fixes #15 and drops the trailing-whitespace oddity pinned in
  `test_merchant_whitespace_is_not_stripped_from_the_output`.
- **Tests:** none marked — current behaviour is correct, so this is a latent
  failure. `tests/test_statements/test_processors_revolut.py` emits the
  FutureWarning on every merchant test, which is the visible signal.
- **Risk:** low now, breaks on a pandas major bump. Worth pairing with a
  `filterwarnings = error::FutureWarning` entry in `pytest.ini` so the next
  one of these is caught at write time rather than at upgrade time.

## 15. Revolut merchant enrichment crashes on a numeric merchant value
- **Where:** `src/statements/processors/revolut.py`, `_parse_description()`.
- **Symptom:** the guard is
  `pd.notna(row.get('Merchant')) and row.get('Merchant', '').strip()`.
  `.strip()` is called on the raw cell value, so if pandas types the Merchant
  column as numeric — a CSV where the merchant is something like `7874`, or a
  column that is mostly blank with a few numeric-looking entries — the row
  raises `AttributeError: 'int' object has no attribute 'strip'`.
  Because this happens inside `df.apply`, one bad cell aborts the entire
  import with a 500; the user loses the whole file over one row.
- **Fix:** coerce before testing — `str(row.get('Merchant', '')).strip()` — or
  adopt the vectorised rewrite in #14, which casts with `.astype(str)` and
  fixes both at once.
- **Tests:** `tests/test_statements/test_processors_revolut.py`, marker
  `NUMERIC_MERCHANT` (2 tests: the value should be coerced, and one bad row
  shouldn't take down the rest of the file).
- **Risk:** low likelihood, total failure when hit. Untriggerable today because
  `RevolutStatementProcessor` isn't wired up (see #16).

## 16. Revolut custom processor is written but not registered
- **Where:** `src/statements/registry.py`, `CUSTOM_PROCESSORS`.
- **Symptom:** the dict is empty with `'revolut_current': RevolutStatementProcessor`
  commented out, so `get_processor('builtin:revolut_current', …)` returns a
  plain `ConfigurableStatementProcessor`. Revolut imports therefore get no
  currency filtering and no merchant enrichment, and `list_all()` reports
  `has_custom_processor: False` for Revolut in the UI picker.
- **Decide:** if the processor is meant to be live, uncomment it (and import
  the class) — but fix #15 first, since registering it is what makes that
  crash reachable. If it was deliberately parked, say so in a comment, because
  right now it reads as an oversight.
- **Tests:** `tests/test_statements/test_processors_revolut.py` covers the
  class directly, so it's tested either way.
  `test_registry.py::TestListAll::test_has_custom_processor_flag` uses an
  injected mapping, so it won't change when this is switched on.
- **Risk:** behavioural change for Revolut imports — multi-currency rows would
  start being dropped rather than imported at face value. Worth checking
  against a real export before flipping.

## 17. `MAX_WORKERS` / `GEMINI_MAX_CONCURRENCY` aren't validated as >= 1
- **Where:** `src/config.py` `_validate()`; surfaces in
  `src/api/services/parallel_processor.py` and `async_processor.py`.
- **Symptom:** `_validate()` checks the three receipt-matching settings but not
  the concurrency ones. `MAX_WORKERS=0` passes config load, flows through
  `get_optimal_workers()` unchanged (`0 is not None`, so the "calculate a
  sensible default" branch is skipped), and finally dies inside
  `ProcessPoolExecutor(max_workers=0)` with
  `ValueError: max_workers must be greater than 0` — at upload time, mid-stream,
  after the user has picked their files. A negative value does the same.
  `GEMINI_MAX_CONCURRENCY=0` is the async equivalent already noted at the end
  of the "Async processor" section: it yields `Semaphore(0)` and deadlocks
  until the stream timeout, which is worse because it looks like a hang.
- **Fix:** add to `_validate()`:
  ```python
  if s.max_workers < 1:
      raise ConfigError("MAX_WORKERS must be >= 1")
  if s.gemini_max_concurrency < 1:
      raise ConfigError("GEMINI_MAX_CONCURRENCY must be >= 1")
  ```
  Failing at boot is the right behaviour for a misconfigured deployment.
- **Related:** `src/api/constants.py` defines `MAX_WORKERS_LIMIT = 8` and
  `DEFAULT_MAX_WORKERS = 2`, neither of which is referenced anywhere. Either
  wire `MAX_WORKERS_LIMIT` into the same validation as an upper bound, or
  delete both — `config.py` already hardcodes the default of 2 separately,
  so today there are two sources of truth that nothing keeps in sync.
- **Tests:** `tests/test_api/test_services/test_parallel_processor.py`:
  `test_zero_is_treated_as_explicit` and
  `test_zero_workers_blows_up_when_the_pool_is_built` pin current behaviour.
  Update them to a config-level `ConfigError` test when fixed.
- **Risk:** low. Deployment-config only, no runtime path change for valid values.

# Cash transaction service bugs found while adding tests

## 18. Generated counterparts are missing `source_relationship='generated'`
- **Where:** `src/services/cash_transactions.py`,
  `generate_cash_transactions()` — the bulk `executemany` INSERT.
- **Symptom:** the batch insert sets `source_transaction_id` but **not**
  `source_relationship`, so counterparts land with `source_relationship = NULL`.
  Every soft-delete rule in `TransactionRepository` keys off that column:
  - `_live_generated_children()` filters `source_relationship = 'generated'`,
    so `delete_transaction(source)` reports `cascaded_ids: []` and leaves the
    cash-side mirror live. The user deletes an ATM withdrawal and the Cash
    account keeps a phantom +100.00, silently unbalancing the Cash balance.
  - `bulk_delete_transactions()` has the same blind spot.
  - `restore_transaction()` only restores children with
    `deleted_reason='cascade'`, which these never get.
  The sibling write path `_insert_cash_transaction()` (used by
  `create_cash_transaction` and `generate_cash_transaction_from_receipt`)
  *does* pass `'generated'` — so the two paths disagree, and the bulk path is
  the one the Generate Cash flow actually uses.
- **Fix:** add the column and a literal `'generated'` to the `executemany`
  INSERT, matching `_insert_cash_transaction()`. Then decide on a backfill:
  existing rows with `source_transaction_id IS NOT NULL AND
  source_relationship IS NULL` are all from this path, so a one-line migration
  can set them — worth doing, otherwise historic cash rows stay un-cascadeable.
- **Tests:** `tests/test_services/test_cash_transactions.py`, marker
  `GENERATED_MISSING_RELATIONSHIP` (2 tests: the column is set; deleting the
  source cascades).
- **Risk:** low to fix, and it closes a real data-integrity hole. The cascade
  machinery and its tests already exist — this path just never opted in.

## 19. `generate_cash_transactions()` ignores soft deletes entirely
- **Where:** `src/services/cash_transactions.py`,
  `generate_cash_transactions()` — the source `SELECT` and the
  "already generated" `SELECT`.
- **Symptom:** neither query filters `deleted_at IS NULL`, giving two wrong
  behaviours:
  1. **Deleted sources are mirrored.** Selecting a soft-deleted transaction
     generates a live Cash counterpart for a transaction the user has already
     deleted. (Reachable via any caller that passes stale IDs — the recycle-bin
     view lists deleted transactions by design.)
  2. **Deleted counterparts block regeneration forever.** The
     `already_generated` check matches soft-deleted rows, so once a user
     deletes a generated cash row, the source is permanently reported as
     `skipped` and can never be regenerated. There is no UI path to undo that
     short of restoring the deleted counterpart.
  (2) is the more likely to be hit, and there's no workaround.
- **Fix:** add `AND deleted_at IS NULL` to both queries. For (1), consider
  whether a deleted source should be *rejected* (with its ID in
  `rejected_ids`) rather than silently absent from the result — a caller
  passing a deleted ID has a stale view and probably wants to be told.
  Note the interaction with #18: once the cascade works, deleting a source
  also deletes its counterpart, so a later "undelete and regenerate" flow
  should go through `restore_transaction()` rather than regenerating.
- **Tests:** `tests/test_services/test_cash_transactions.py`, marker
  `SOFT_DELETE_IGNORED` (2 tests). They assert the desired behaviour, so
  pick the rejection semantics before unmarking the first one.
- **Risk:** low to fix. Fix alongside #18 — both are in the same method and
  both are about the soft-delete contract.

## 20. `BatchProcessor` (src/api/utils/sse.py) is dead code that has drifted
- **Where:** `src/api/utils/sse.py`, `BatchProcessor`.
- **Status:** no callers anywhere in `src/` (only a pdoc search-index hit in
  `backend/docs/`). Every live streaming path goes through
  `StreamEventReporter` plus `ParallelStreamProcessor` /
  `AsyncReceiptStreamProcessor`.
- **Why it's a liability rather than harmless:** it emits the same SSE
  protocol as the live path, but has drifted from it, so anyone who revives it
  for a new batch endpoint inherits subtly broken streaming:
  - **`completed` omits the tally.** It calls
    `SSEEventBuilder.completed(self.processed_count)` with no `successes` /
    `errors`, while `StreamEventReporter.completed()` supplies both. A client
    written against the receipts stream reads `undefined` for each.
  - **No abort path.** Nothing reports files that were announced as
    `processing` but never produced a result, so a failure mid-batch leaves
    the UI with rows stuck on the spinner forever.
  - **No heartbeat.** A long sequential batch sits silent until a proxy or
    gunicorn kills the connection.
  - **`max_workers` is accepted and ignored.** The constructor stores it;
    `process_sequential()` always reports `workers=1` and runs serially. A
    caller passing `max_workers=8` gets no parallelism and no warning.
  - **Counters aren't thread-safe**, unlike `StreamEventReporter` — fine while
    it's sequential, a trap if someone adds a `process_parallel()`.
- **Recommended fix: delete the class.** If a second batch endpoint is ever
  needed, `StreamEventReporter` already owns the protocol correctly and
  `ParallelStreamProcessor` already does the execution; a sequential variant
  would be a handful of lines on top of the reporter rather than a parallel
  implementation of the same protocol.
- **Tests:** `tests/test_api/test_utils/test_sse_batch_processor.py` pins
  current behaviour (31 tests), including a `TestProtocolDrift` class that
  asserts each divergence above. Delete the file alongside the class.
- **Risk:** none to delete — nothing imports it. The only cost is if there's
  an unmerged branch depending on it, worth checking before removal.

## 21. `result_data` can overwrite the SSE event envelope
- **Where:** `src/api/utils/sse.py`, `SSEEventBuilder.success()`.
- **Symptom:** the payload is spread last:
  ```python
  {"status": "success", "file_index": ..., "filename": ..., **result_data, **extra}
  ```
  so a worker payload containing `status`, `file_index`, `filename`,
  `progress` or `timestamp` silently overwrites the envelope. A payload with
  `status` set turns a success event into something the client won't
  recognise as a success at all.
- **Current exposure:** none — `worker_common.success()` uses `receipt_id`,
  `receipt_status`, `original_filename`, `stored_filename`, `extracted_data`,
  and there's already a test pinning that it avoids the reserved keys
  (`test_receipt_stream_processor.py::test_result_data_cannot_clobber_event_envelope`).
  So this is a latent trap for the *next* worker payload, not a live bug.
- **Fix:** make the envelope win, by spreading `result_data` first, or nest the
  payload under a `result` key (a frontend change), or assert in
  `_format_event()` that the payload and envelope keys don't intersect. The
  nested option is cleanest but touches the client; the first is a one-line
  reorder.
- **Tests:** `test_sse_batch_processor.py::TestProtocolDrift::test_result_data_can_clobber_the_event_envelope`
  documents the current behaviour.
- **Risk:** low now, annoying to debug if it ever fires.
