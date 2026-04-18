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

/**
 * Receipt session table.
 *
 * Sorting is client-side over the `receipts` array, using values from
 * `extracted_data` for vendor/date/amount. Rows carry CSS hooks for
 * selection and status (`selected`, `status-<x>`, `processed`).
 *
 * @component
 * @param {Object} props
 * @param {Array<import('./ProcessReceipts').LocalReceipt>} [props.receipts=[]]
 *        Receipts in the current session.
 * @param {?number|string} props.selectedReceiptId
 *        Id of the receipt currently shown in the detail panel.
 * @param {(receiptId: number|string) => void} props.onSelectReceipt
 *        Called when a row is clicked.
 * @param {(receiptId: number|string) => void} props.onRemoveReceipt
 *        Called when the ✕ button is clicked for a pending receipt.
 * @param {boolean} [props.disabled=false]
 *        Disable row clicks and the ✕ button (e.g. while saving).
 * @returns {JSX.Element}
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

  /** Locale-formatted date, or `-`. */
  const formatDate = (dateString) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString();
  };

  /** `$12.34`-style amount, or `-`. */
  const formatAmount = (amount) => {
    if (amount == null) return '-';
    return `$${parseFloat(amount).toFixed(2)}`;
  };

  /**
   * Truncate long filenames to ~20 chars while preserving the
   * extension for recognizability.
   */
  const formatFilename = (filename) => {
    if (!filename) return '-';
    if (filename.length > 20) {
      const ext = filename.split('.').pop();
      return `${filename.substring(0, 15)}...${ext}`;
    }
    return filename;
  };

  /** Status → glyph for the narrow status column. */
  const getStatusIcon = (status) => {
    switch (status) {
      case 'saved':
        return '✓';
      case 'linked':
        return '🔗';
      default:
        return '○';
    }
  };

  /** Status → color class for the icon. */
  const getStatusIconColor = (status) => {
    switch (status) {
      case 'saved':
        return 'text-success';
      case 'linked':
        return 'text-primary';
      default:
        return 'text-[#ffc107]';
    }
  };

  /** Status → border-left color for the row. */
  const getStatusBorderClass = (status) => {
    switch (status) {
      case 'saved':
        return 'border-l-4 border-l-success';
      case 'linked':
        return 'border-l-4 border-l-primary';
      default:
        return 'border-l-4 border-l-[#ffc107]';
    }
  };

  /**
   * Clickable column header with asc/desc indicator.
   * @param {{field: string, children: React.ReactNode}} props
   */
  const SortableHeader = ({ field, children }) => (
    <th
      onClick={() => handleSort(field)}
      className="sticky top-0 z-10 cursor-pointer select-none whitespace-nowrap border-b-2 border-[#dee2e6] bg-[#f8f9fa] px-2 py-3 text-left text-[0.8rem] font-semibold text-[#555] transition-colors hover:bg-[#e9ecef]"
    >
      {children}
      {sortConfig.key === field && (
        <span className="ml-[3px] text-[0.7rem] opacity-70">{sortConfig.direction === 'asc' ? ' ↑' : ' ↓'}</span>
      )}
    </th>
  );

  if (receipts.length === 0) {
    return (
      <div className="px-6 py-12 text-center text-text-light">
        <p className="m-0 text-base font-medium">No receipts uploaded yet</p>
        <p className="mt-2 text-[0.85rem] text-[#aaa]">Upload receipts using the dropzone above</p>
      </div>
    );
  }

  return (
    <div className="max-h-[calc(100vh-380px)] flex-1 overflow-y-auto [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:rounded [&::-webkit-scrollbar-track]:bg-[#f1f1f1] [&::-webkit-scrollbar-thumb]:rounded [&::-webkit-scrollbar-thumb]:bg-text-light [&::-webkit-scrollbar-thumb:hover]:bg-[#555]">
      <table className="w-full border-collapse text-[0.9rem]">
        <thead>
          <tr>
            <th className="sticky top-0 z-10 w-[70px] whitespace-nowrap border-b-2 border-[#dee2e6] bg-[#f8f9fa] p-[0.375rem] text-left text-[0.8rem] font-semibold text-[#555]">Image</th>
            <th className="sticky top-0 z-10 w-9 whitespace-nowrap border-b-2 border-[#dee2e6] bg-[#f8f9fa] px-2 py-3 text-center text-[0.8rem] font-semibold text-[#555]">
              <span title="Status">●</span>
            </th>
            <SortableHeader field="filename">File</SortableHeader>
            <SortableHeader field="vendor">Vendor</SortableHeader>
            <SortableHeader field="date">Date</SortableHeader>
            <SortableHeader field="amount">Amount</SortableHeader>
            <th className="sticky top-0 z-10 w-9 whitespace-nowrap border-b-2 border-[#dee2e6] bg-[#f8f9fa] px-2 py-3 text-center text-[0.8rem] font-semibold text-[#555]"></th>
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
                className={`cursor-pointer transition-all duration-150 ${getStatusBorderClass(receipt.status || 'pending')} ${
                  isProcessed
                    ? `opacity-60 bg-surface-alt ${isSelected ? 'bg-[#e0e7f0] opacity-80' : 'hover:bg-[#f5f5f5]'}`
                    : isSelected
                      ? 'bg-[#e7f1ff] hover:bg-[#d0e3ff]'
                      : 'hover:bg-[#f8f9fa]'
                }`}
                onClick={() => !disabled && onSelectReceipt(receipt.receipt_id)}
              >
                <td className="w-[70px] border-b border-[#eee] p-[0.375rem] align-middle">
                  <div className="overflow-hidden rounded bg-[#f5f5f5]">
                    <ReceiptThumbnail
                      src={`/api/receipts/${receipt.receipt_id}/image`}
                      alt={`Receipt from ${extracted.vendor || 'Unknown'}`}
                      maxWidth="60px"
                      maxHeight="45px"
                    />
                  </div>
                </td>
                <td className="w-9 border-b border-[#eee] p-2 text-center align-middle">
                  <span
                    className={`inline-block text-[0.85rem] ${getStatusIconColor(receipt.status || 'pending')}`}
                    title={receipt.status || 'pending'}
                  >
                    {getStatusIcon(receipt.status)}
                  </span>
                </td>
                <td className="min-w-[100px] max-w-[140px] border-b border-[#eee] p-2 align-middle">
                  <span
                    className="block overflow-hidden text-ellipsis whitespace-nowrap font-mono text-[0.8rem] text-text-muted"
                    title={receipt.filename}
                  >
                    {formatFilename(receipt.filename)}
                  </span>
                </td>
                <td className="min-w-[100px] max-w-[130px] border-b border-[#eee] p-2 align-middle">
                  <span
                    className={`block overflow-hidden text-ellipsis whitespace-nowrap font-medium ${isProcessed ? 'text-text-muted' : ''}`}
                    title={extracted.vendor || 'Unknown'}
                  >
                    {extracted.vendor || 'Unknown'}
                  </span>
                </td>
                <td className="min-w-[85px] whitespace-nowrap border-b border-[#eee] p-2 align-middle">{formatDate(extracted.date)}</td>
                <td className="min-w-[80px] whitespace-nowrap border-b border-[#eee] p-2 text-right font-mono text-[0.85rem] align-middle">{formatAmount(extracted.amount)}</td>
                <td className="w-9 border-b border-[#eee] p-2 text-center align-middle">
                  {receipt.status === 'pending' && (
                    <button
                      className="cursor-pointer rounded border-none bg-transparent px-2 py-1 text-[0.9rem] leading-none text-[#bbb] transition-all duration-150 hover:enabled:bg-[#fee] hover:enabled:text-danger-alt disabled:cursor-not-allowed disabled:opacity-50"
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
