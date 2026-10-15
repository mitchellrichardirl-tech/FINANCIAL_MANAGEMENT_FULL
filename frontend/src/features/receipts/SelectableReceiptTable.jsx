/**
 * @file SelectableReceiptTable.jsx
 * Sortable list of receipts with a server-authoritative status column.
 *
 * Used by both left-column tabs on the Process Receipts page:
 *  - *This session* — rows from the current upload session
 *    (`showRemove` enabled so pending rows can be dismissed locally).
 *  - *Unlinked*     — server-backed rows from any session
 *    (`showRemove={false}`; removal is a real delete handled elsewhere).
 *
 * Each row shows a thumbnail, status icon, filename, and the extracted
 * vendor/date/amount. Clicking a row selects it for the detail panel;
 * the ✕ button (when shown) removes a pending receipt from the list —
 * local only, it does not call the API.
 *
 * Status vocabulary (server-authoritative, see ./model.js):
 *   'pending'  → uploaded, not yet confirmed        (amber)
 *   'unlinked' → confirmed, awaiting a transaction  (orange)
 *   'linked'   → attached to a transaction          (blue, de-emphasised)
 */
import { useState } from 'react';
import ReceiptThumbnail from '@/components/Thumbnail';
import { RECEIPT_STATUS } from './model';

/* ── Table cell bases ──────────────────────────────────────────────── */
const TH =
  'sticky top-0 z-10 whitespace-nowrap border-b-2 border-gray-300 ' +
  'bg-gray-50 px-2 py-3 text-left text-[0.8rem] font-semibold text-gray-600';
const TD = 'border-b border-[#eee] px-2 py-2 align-middle';

/* ── Status → left-border accent ───────────────────────────────────── */
const STATUS_BORDER = {
  [RECEIPT_STATUS.PENDING]:  'border-l-4 border-l-[#ffc107]',
  [RECEIPT_STATUS.UNLINKED]: 'border-l-4 border-l-[#fd7e14]',
  [RECEIPT_STATUS.LINKED]:   'border-l-4 border-l-[#007bff]',
};
const STATUS_ICON_CLS = {
  [RECEIPT_STATUS.PENDING]:  'text-[#ffc107]',
  [RECEIPT_STATUS.UNLINKED]: 'text-[#fd7e14]',
  [RECEIPT_STATUS.LINKED]:   'text-[#007bff]',
};
const STATUS_TITLE = {
  [RECEIPT_STATUS.PENDING]:  'Pending — not yet saved',
  [RECEIPT_STATUS.UNLINKED]: 'Saved — not linked to a transaction',
  [RECEIPT_STATUS.LINKED]:   'Linked to a transaction',
};
const STATUS_ICON = {
  [RECEIPT_STATUS.PENDING]:  '○',
  [RECEIPT_STATUS.UNLINKED]: '◐',
  [RECEIPT_STATUS.LINKED]:   '🔗',
};

/* ── Scrollbar (Chromium only) ─────────────────────────────────────── */
const SCROLLBAR = [
  '[&::-webkit-scrollbar]:w-2',
  '[&::-webkit-scrollbar-track]:rounded [&::-webkit-scrollbar-track]:bg-gray-100',
  '[&::-webkit-scrollbar-thumb]:rounded [&::-webkit-scrollbar-thumb]:bg-gray-400',
  '[&::-webkit-scrollbar-thumb:hover]:bg-gray-500',
].join(' ');

/**
 * Compute the full row className from the selection/status state.
 *
 * Only 'linked' rows are de-emphasised — an 'unlinked' receipt is still
 * actionable (editable + linkable), so it renders at full strength.
 */
function rowCls(isSelected, status) {
  const base = `cursor-pointer transition-all duration-150 ${
    STATUS_BORDER[status] || STATUS_BORDER[RECEIPT_STATUS.PENDING]
  }`;
  const isDone = status === RECEIPT_STATUS.LINKED;
  if (isDone && isSelected) return `${base} bg-[#e0e7f0] opacity-80`;
  if (isDone)               return `${base} bg-gray-50 opacity-60 hover:bg-[#f5f5f5]`;
  if (isSelected)           return `${base} bg-[#e7f1ff] hover:bg-[#d0e3ff]`;
  return `${base} hover:bg-gray-50`;
}

/**
 * Sortable receipt list.
 *
 * @component
 * @param {Object} props
 * @param {Array<import('./model').ReceiptRow>} [props.receipts]
 * @param {?number} props.selectedReceiptId
 * @param {(receiptId: number) => void} props.onSelectReceipt
 * @param {(receiptId: number) => void} [props.onRemoveReceipt]
 *        Local-only removal of a pending row. Ignored when
 *        `showRemove` is false.
 * @param {boolean} [props.disabled=false]
 * @param {boolean} [props.showRemove=true]
 *        Whether to render the ✕ column (session list only).
 * @param {string} [props.emptyTitle]
 * @param {string} [props.emptyHint]
 * @returns {JSX.Element}
 */
export default function SelectableReceiptTable({
  receipts = [],
  selectedReceiptId,
  onSelectReceipt,
  onRemoveReceipt,
  disabled = false,
  showRemove = true,
  emptyTitle = 'No receipts uploaded yet',
  emptyHint = 'Upload receipts using the dropzone above',
}) {
  /** Active sort column + direction. */
  const [sortConfig, setSortConfig] = useState({ key: 'date', direction: 'desc' });

  /** Toggle sort direction or switch column (defaults to asc). */
  const handleSort = (key) => {
    setSortConfig((prev) => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc',
    }));
  };

  /** Receipts sorted by `sortConfig`. */
  const sortedReceipts = [...receipts].sort((a, b) => {
    const aData = a.extracted_data || {};
    const bData = b.extracted_data || {};
    let aVal, bVal;
    switch (sortConfig.key) {
      case 'filename':
        aVal = a.filename || '';
        bVal = b.filename || '';
        break;
      case 'vendor':
        aVal = (aData.vendor || '').toLowerCase();
        bVal = (bData.vendor || '').toLowerCase();
        break;
      case 'date':
        aVal = aData.date || '';
        bVal = bData.date || '';
        break;
      case 'amount':
        aVal = parseFloat(aData.amount) || 0;
        bVal = parseFloat(bData.amount) || 0;
        break;
      case 'status':
        aVal = a.status || '';
        bVal = b.status || '';
        break;
      default:
        return 0;
    }
    if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
    if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
    return 0;
  });

  // ── Display helpers ───────────────────────────────────────────────
  const formatDate = (dateString) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString();
  };
  const formatAmount = (amount) => {
    if (amount == null || amount === '') return '-';
    return `$${parseFloat(amount).toFixed(2)}`;
  };
  const formatFilename = (filename) => {
    if (!filename) return '-';
    if (filename.length > 20) {
      const ext = filename.split('.').pop();
      return `${filename.substring(0, 15)}...${ext}`;
    }
    return filename;
  };

  /**
   * Clickable column header with asc/desc indicator.
   * @param {{field: string, children: React.ReactNode}} props
   */
  const SortableHeader = ({ field, children }) => (
    <th
      onClick={() => handleSort(field)}
      className={`${TH} cursor-pointer select-none hover:bg-gray-200`}
    >
      {children}
      {sortConfig.key === field && (
        <span className="ml-[3px] text-[0.7rem] opacity-70">
          {sortConfig.direction === 'asc' ? ' ↑' : ' ↓'}
        </span>
      )}
    </th>
  );

  if (receipts.length === 0) {
    return (
      <div className="space-y-2 px-6 py-12 text-center text-[#888]">
        <p className="text-base font-medium">{emptyTitle}</p>
        {emptyHint && <p className="text-[0.85rem] text-[#aaa]">{emptyHint}</p>}
      </div>
    );
  }

  return (
    <div className={`max-h-[calc(100vh-380px)] flex-1 overflow-y-auto ${SCROLLBAR}`}>
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className={`${TH} w-[70px]`}>Image</th>
            <SortableHeader field="status">
              <span title="Status">●</span>
            </SortableHeader>
            <SortableHeader field="filename">File</SortableHeader>
            <SortableHeader field="vendor">Vendor</SortableHeader>
            <SortableHeader field="date">Date</SortableHeader>
            <SortableHeader field="amount">Amount</SortableHeader>
            {showRemove && <th className={`${TH} w-9`}></th>}
          </tr>
        </thead>
        <tbody>
          {sortedReceipts.map((receipt) => {
            const isSelected = receipt.receipt_id === selectedReceiptId;
            const status = receipt.status || RECEIPT_STATUS.PENDING;
            const extracted = receipt.extracted_data || {};
            return (
              <tr
                key={receipt.receipt_id}
                className={rowCls(isSelected, status)}
                onClick={() => !disabled && onSelectReceipt(receipt.receipt_id)}
              >
                {/* Thumbnail */}
                <td className="w-[70px] border-b border-[#eee] p-1.5 align-middle">
                  <div className="overflow-hidden rounded bg-gray-100">
                    <ReceiptThumbnail
                      src={`/api/receipts/${receipt.receipt_id}/image`}
                      alt={`Receipt from ${extracted.vendor || 'Unknown'}`}
                      maxWidth="60px"
                      maxHeight="45px"
                    />
                  </div>
                </td>
                {/* Status icon */}
                <td className={`${TD} w-9 text-center`}>
                  <span
                    className={`inline-block text-[0.85rem] ${
                      STATUS_ICON_CLS[status] || STATUS_ICON_CLS[RECEIPT_STATUS.PENDING]
                    }`}
                    title={STATUS_TITLE[status] || status}
                  >
                    {STATUS_ICON[status] || STATUS_ICON[RECEIPT_STATUS.PENDING]}
                  </span>
                </td>
                {/* Filename — mono, truncated */}
                <td className={`${TD} min-w-[100px] max-w-[140px]`}>
                  <span
                    className="block truncate font-mono text-[0.8rem] text-muted"
                    title={receipt.filename}
                  >
                    {formatFilename(receipt.filename)}
                  </span>
                </td>
                {/* Vendor — truncated, muted when linked */}
                <td className={`${TD} min-w-[100px] max-w-[130px]`}>
                  <span
                    className={`block truncate font-medium ${
                      status === RECEIPT_STATUS.LINKED ? 'text-muted' : ''
                    }`}
                    title={extracted.vendor || 'Unknown'}
                  >
                    {extracted.vendor || 'Unknown'}
                  </span>
                </td>
                {/* Date */}
                <td className={`${TD} min-w-[85px] whitespace-nowrap`}>
                  {formatDate(extracted.date)}
                </td>
                {/* Amount — mono, right-aligned */}
                <td className={`${TD} min-w-[80px] whitespace-nowrap text-right font-mono text-[0.85rem]`}>
                  {formatAmount(extracted.amount)}
                </td>
                {/* Remove action — session list only, pending rows only */}
                {showRemove && (
                  <td className={`${TD} w-9 text-center`}>
                    {status === RECEIPT_STATUS.PENDING && (
                      <button
                        className="cursor-pointer rounded bg-transparent px-2 py-1 text-sm leading-none text-[#bbb] transition-all duration-150 hover:bg-[#ffeeee] hover:text-[#dc3545] disabled:cursor-not-allowed disabled:opacity-50"
                        onClick={(e) => {
                          e.stopPropagation();
                          onRemoveReceipt?.(receipt.receipt_id);
                        }}
                        disabled={disabled}
                        title="Remove from this list (stays available under Unlinked)"
                      >
                        ✕
                      </button>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}