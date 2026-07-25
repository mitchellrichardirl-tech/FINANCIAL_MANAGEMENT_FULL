/**
 * @file SelectableReceiptTable.jsx
 * Sortable list of receipts in the current processing session.
 *
 * Each row shows a thumbnail, status icon, filename, and the
 * OCR-extracted vendor/date/amount. Clicking a row selects it for the
 * detail panel; the ✕ button removes a pending receipt from the list
 * (local only — does not call the API).
 */
import { useState } from 'react';
import ReceiptThumbnail from '@/components/Thumbnail';
// ❌ removed: import './SelectableReceiptTable.css';
/* ── Table cell bases ──────────────────────────────────────────────── */
const TH =
  'sticky top-0 z-10 whitespace-nowrap border-b-2 border-gray-300 ' +
  'bg-gray-50 px-2 py-3 text-left text-[0.8rem] font-semibold text-gray-600';
const TD = 'border-b border-[#eee] px-2 py-2 align-middle';
/* ── Status → left-border accent ───────────────────────────────────── */
const STATUS_BORDER = {
  saved:   'border-l-4 border-l-[#28a745]',
  linked:  'border-l-4 border-l-[#007bff]',
  pending: 'border-l-4 border-l-[#ffc107]',
};
const STATUS_ICON_CLS = {
  saved:   'text-[#28a745]',
  linked:  'text-[#007bff]',
  pending: 'text-[#ffc107]',
};
/* ── Scrollbar (Chromium only) ─────────────────────────────────────── */
const SCROLLBAR = [
  '[&::-webkit-scrollbar]:w-2',
  '[&::-webkit-scrollbar-track]:rounded [&::-webkit-scrollbar-track]:bg-gray-100',
  '[&::-webkit-scrollbar-thumb]:rounded [&::-webkit-scrollbar-thumb]:bg-gray-400',
  '[&::-webkit-scrollbar-thumb:hover]:bg-gray-500',
].join(' ');
/**
 * Compute the full row className from the selection/processing state.
 *
 * The original CSS had 7 overlapping rules whose precedence depended on
 * specificity + source order. This function makes the same result
 * explicit per combination so there are no cascade surprises.
 */
function rowCls(isSelected, isProcessed, status) {
  const base = `cursor-pointer transition-all duration-150 ${STATUS_BORDER[status || 'pending']}`;
  if (isProcessed && isSelected) return `${base} bg-[#e0e7f0] opacity-80`;
  if (isProcessed)               return `${base} bg-gray-50 opacity-60 hover:bg-[#f5f5f5]`;
  if (isSelected)                return `${base} bg-[#e7f1ff] hover:bg-[#d0e3ff]`;
  return `${base} hover:bg-gray-50`;
}
/**
 * @component
 * (docblock unchanged)
 */
export default function SelectableReceiptTable({
  receipts = [],
  selectedReceiptId,
  onSelectReceipt,
  onRemoveReceipt,
  disabled = false,
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
        aVal = aData.vendor || '';
        bVal = bData.vendor || '';
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
    if (amount == null) return '-';
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
  const getStatusIcon = (status) => {
    switch (status) {
      case 'saved':  return '✓';
      case 'linked': return '🔗';
      default:       return '○';
    }
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
        <p className="text-base font-medium">No receipts uploaded yet</p>
        <p className="text-[0.85rem] text-[#aaa]">
          Upload receipts using the dropzone above
        </p>
      </div>
    );
  }
  return (
    <div className={`max-h-[calc(100vh-380px)] flex-1 overflow-y-auto ${SCROLLBAR}`}>
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className={`${TH} w-[70px]`}>Image</th>
            <th className={`${TH} w-9 text-center`}>
              <span title="Status">●</span>
            </th>
            <SortableHeader field="filename">File</SortableHeader>
            <SortableHeader field="vendor">Vendor</SortableHeader>
            <SortableHeader field="date">Date</SortableHeader>
            <SortableHeader field="amount">Amount</SortableHeader>
            <th className={`${TH} w-9`}></th>
          </tr>
        </thead>
        <tbody>
          {sortedReceipts.map((receipt) => {
            const isSelected = receipt.receipt_id === selectedReceiptId;
            const isProcessed = receipt.status === 'saved' || receipt.status === 'linked';
            const extracted = receipt.extracted_data || {};
            return (
              <tr
                key={receipt.receipt_id}
                className={rowCls(isSelected, isProcessed, receipt.status)}
                onClick={() => !disabled && onSelectReceipt(receipt.receipt_id)}
              >
                {/* Thumbnail — custom padding, wraps ReceiptThumbnail
                    with the overflow/bg the old CSS put on .receipt-thumbnail-container */}
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
                    className={`inline-block text-[0.85rem] ${STATUS_ICON_CLS[receipt.status || 'pending']}`}
                    title={receipt.status || 'pending'}
                  >
                    {getStatusIcon(receipt.status)}
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
                {/* Vendor — truncated, muted when processed */}
                <td className={`${TD} min-w-[100px] max-w-[130px]`}>
                  <span
                    className={`block truncate font-medium ${isProcessed ? 'text-muted' : ''}`}
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
                {/* Remove action */}
                <td className={`${TD} w-9 text-center`}>
                  {receipt.status === 'pending' && (
                    <button
                      className="cursor-pointer rounded bg-transparent px-2 py-1 text-sm leading-none text-[#bbb] transition-all duration-150 hover:bg-[#ffeeee] hover:text-[#dc3545] disabled:cursor-not-allowed disabled:opacity-50"
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemoveReceipt(receipt.receipt_id);
                      }}
                      disabled={disabled}
                      title="Remove from list"
                    >
                      ✕
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}