/**
 * @file UnlinkedReceiptsPanel.jsx
 * Filter bar + paged table for receipts awaiting a link. Purely
 * presentational over the `useUnlinkedReceipts` hook result.
 */
import { useEffect, useState } from 'react';
import SelectableReceiptTable from './SelectableReceiptTable';
import { DEFAULT_FILTERS } from './useUnlinkedReceipts';

const INPUT = [
  'rounded-md border border-gray-300 px-2 py-1.5 text-sm',
  'focus:outline-none focus:border-[#007bff] focus:shadow-[0_0_0_3px_rgba(0,123,255,0.15)]',
  'disabled:bg-gray-100 disabled:cursor-not-allowed',
].join(' ');
const BTN = 'cursor-pointer rounded border px-3 py-1.5 text-[0.8rem] transition-all disabled:cursor-not-allowed disabled:opacity-50';
const BTN_PRIMARY = `${BTN} border-[#007bff] bg-[#007bff] text-white hover:bg-[#0056b3]`;
const BTN_GHOST = `${BTN} border-gray-300 bg-transparent text-gray-600 hover:bg-gray-100`;

export default function UnlinkedReceiptsPanel({
  list,               // result of useUnlinkedReceipts
  selectedReceiptId,
  onSelectReceipt,
  disabled = false,
}) {
  const { rows, total, loading, error, filters, setFilters, offset, setOffset, pageSize, refresh } = list;

  // Draft inputs; applied on submit so every keystroke isn't a request.
  const [draft, setDraft] = useState(filters);
  useEffect(() => setDraft(filters), [filters]);

  const apply = (e) => { e?.preventDefault(); setFilters(draft); };
  const reset = () => { setDraft(DEFAULT_FILTERS); setFilters(DEFAULT_FILTERS); };

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + rows.length, total);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <form onSubmit={apply} className="grid grid-cols-2 gap-2">
        <input
          className={`${INPUT} col-span-2`}
          placeholder="Search vendor or filename"
          value={draft.q}
          onChange={(e) => setDraft({ ...draft, q: e.target.value })}
          disabled={disabled}
        />
        <input type="date" className={INPUT} value={draft.date_from}
          onChange={(e) => setDraft({ ...draft, date_from: e.target.value })} disabled={disabled} title="Date from" />
        <input type="date" className={INPUT} value={draft.date_to}
          onChange={(e) => setDraft({ ...draft, date_to: e.target.value })} disabled={disabled} title="Date to" />
        <input type="number" step="0.01" className={INPUT} placeholder="Min amount" value={draft.amount_min}
          onChange={(e) => setDraft({ ...draft, amount_min: e.target.value })} disabled={disabled} />
        <input type="number" step="0.01" className={INPUT} placeholder="Max amount" value={draft.amount_max}
          onChange={(e) => setDraft({ ...draft, amount_max: e.target.value })} disabled={disabled} />
        <div className="col-span-2 flex items-center gap-2">
          <select
            className={INPUT}
            value={draft.status}
            onChange={(e) => setDraft({ ...draft, status: e.target.value })}
            disabled={disabled}
          >
            <option value="pending,unlinked">Pending + Saved</option>
            <option value="pending">Pending only</option>
            <option value="unlinked">Saved only</option>
            <option value="linked">Linked</option>
          </select>
          <button type="submit" className={BTN_PRIMARY} disabled={disabled || loading}>Apply</button>
          <button type="button" className={BTN_GHOST} onClick={reset} disabled={disabled || loading}>Reset</button>
          <button type="button" className={`${BTN_GHOST} ml-auto`} onClick={refresh} disabled={disabled || loading} title="Reload from server">
            {loading ? '…' : '↻'}
          </button>
        </div>
      </form>

      {error && (
        <div className="rounded border border-danger-border bg-danger-bg px-3 py-2 text-sm text-danger-text" role="alert">
          {error}
        </div>
      )}

      <SelectableReceiptTable
        receipts={rows}
        selectedReceiptId={selectedReceiptId}
        onSelectReceipt={onSelectReceipt}
        disabled={disabled}
        showRemove={false}
        emptyTitle={loading ? 'Loading…' : 'No receipts waiting to be linked'}
        emptyHint={loading ? '' : 'Receipts you save without linking, or leave unprocessed, appear here'}
      />

      <div className="flex shrink-0 items-center justify-between text-xs text-gray-500">
        <span>{from}–{to} of {total}</span>
        <div className="flex gap-2">
          <button className={BTN_GHOST} disabled={disabled || loading || offset === 0}
            onClick={() => setOffset(Math.max(0, offset - pageSize))}>‹ Prev</button>
          <button className={BTN_GHOST} disabled={disabled || loading || offset + pageSize >= total}
            onClick={() => setOffset(offset + pageSize)}>Next ›</button>
        </div>
      </div>
    </div>
  );
}