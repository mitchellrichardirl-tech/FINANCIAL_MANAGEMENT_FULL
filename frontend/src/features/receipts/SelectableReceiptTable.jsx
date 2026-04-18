import { useState } from 'react';
import ReceiptThumbnail from '@/components/Thumbnail';

export default function SelectableReceiptTable({
  receipts = [],
  selectedReceiptId,
  onSelectReceipt,
  onRemoveReceipt,
  disabled = false,
}) {
  const [sortConfig, setSortConfig] = useState({ key: 'date', direction: 'desc' });

  const handleSort = (key) =>
    setSortConfig((prev) => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc',
    }));

  const sortedReceipts = [...receipts].sort((a, b) => {
    const aData = a.extracted_data || {};
    const bData = b.extracted_data || {};
    let aVal, bVal;
    switch (sortConfig.key) {
      case 'filename': aVal = a.filename || ''; bVal = b.filename || ''; break;
      case 'vendor':   aVal = aData.vendor || ''; bVal = bData.vendor || ''; break;
      case 'date':     aVal = aData.date || ''; bVal = bData.date || ''; break;
      case 'amount':   aVal = parseFloat(aData.amount) || 0; bVal = parseFloat(bData.amount) || 0; break;
      case 'status':   aVal = a.status || ''; bVal = b.status || ''; break;
      default: return 0;
    }
    if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
    if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
    return 0;
  });

  const formatDate = (s) => (s ? new Date(s).toLocaleDateString() : '-');
  const formatAmount = (a) => (a == null ? '-' : `$${parseFloat(a).toFixed(2)}`);
  const formatFilename = (n) => {
    if (!n) return '-';
    if (n.length > 20) {
      const ext = n.split('.').pop();
      return `${n.substring(0, 15)}...${ext}`;
    }
    return n;
  };
  const getStatusIcon = (status) => {
    if (status === 'saved') return '✓';
    if (status === 'linked') return '🔗';
    return '○';
  };

  const thBase =
    'sticky top-0 bg-[#f8f9fa] py-3 px-2 text-left font-semibold text-[0.8rem] text-[#555] border-b-2 border-[#dee2e6] whitespace-nowrap z-10';
  const sortableThCls = `${thBase} cursor-pointer select-none transition-[background] duration-150 hover:bg-[#e9ecef]`;

  const SortableHeader = ({ field, children }) => (
    <th onClick={() => handleSort(field)} className={sortableThCls}>
      {children}
      {sortConfig.key === field && (
        <span className="text-[0.7rem] ml-[3px] opacity-70">
          {sortConfig.direction === 'asc' ? ' ↑' : ' ↓'}
        </span>
      )}
    </th>
  );

  if (receipts.length === 0) {
    return (
      <div className="text-center py-12 px-6 text-[#888]">
        <p className="my-2 text-base font-medium">No receipts uploaded yet</p>
        <p className="my-2 text-[0.85rem] text-[#aaa]">
          Upload receipts using the dropzone above
        </p>
      </div>
    );
  }

  const tdBase = 'p-2 border-b border-[#eee] align-middle';

  const statusBorder = (s) => {
    if (s === 'saved') return 'border-l-4 border-l-[#28a745]';
    if (s === 'linked') return 'border-l-4 border-l-[#007bff]';
    if (s === 'pending') return 'border-l-4 border-l-[#ffc107]';
    return '';
  };
  const statusIconColor = (s) => {
    if (s === 'saved') return 'text-[#28a745]';
    if (s === 'linked') return 'text-[#007bff]';
    return 'text-[#ffc107]';
  };

  return (
    <div className="flex-1 overflow-y-auto max-h-[calc(100vh-380px)]">
      <table className="w-full border-collapse text-[0.9rem]">
        <thead>
          <tr>
            <th className={`${thBase} w-[70px] !p-1.5`}>Image</th>
            <th className={`${thBase} w-9 text-center`}><span title="Status">●</span></th>
            <SortableHeader field="filename">File</SortableHeader>
            <SortableHeader field="vendor">Vendor</SortableHeader>
            <SortableHeader field="date">Date</SortableHeader>
            <SortableHeader field="amount">Amount</SortableHeader>
            <th className={`${thBase} w-9 text-center`} />
          </tr>
        </thead>
        <tbody>
          {sortedReceipts.map((receipt) => {
            const isSelected = receipt.receipt_id === selectedReceiptId;
            const isProcessed = receipt.status === 'saved' || receipt.status === 'linked';
            const extracted = receipt.extracted_data || {};

            let rowCls = 'cursor-pointer transition-all duration-150 ease-in-out';
            if (isSelected) {
              rowCls += isProcessed ? ' bg-[#e0e7f0] opacity-80' : ' bg-[#e7f1ff] hover:bg-[#d0e3ff]';
            } else if (isProcessed) {
              rowCls += ' opacity-60 bg-[#fafafa] hover:bg-[#f5f5f5]';
            } else {
              rowCls += ' hover:bg-[#f8f9fa]';
            }
            rowCls += ' ' + statusBorder(receipt.status);

            return (
              <tr
                key={receipt.receipt_id}
                className={rowCls}
                onClick={() => !disabled && onSelectReceipt(receipt.receipt_id)}
              >
                <td className={`${tdBase} w-[70px] !p-1.5`}>
                  <div className="rounded overflow-hidden bg-[#f5f5f5]">
                    <ReceiptThumbnail
                      src={`/api/receipts/${receipt.receipt_id}/image`}
                      alt={`Receipt from ${extracted.vendor || 'Unknown'}`}
                      maxWidth="60px"
                      maxHeight="45px"
                    />
                  </div>
                </td>
                <td className={`${tdBase} w-9 text-center`}>
                  <span
                    className={`text-[0.85rem] inline-block ${statusIconColor(receipt.status)}`}
                    title={receipt.status || 'pending'}
                  >
                    {getStatusIcon(receipt.status)}
                  </span>
                </td>
                <td className={`${tdBase} min-w-[100px] max-w-[140px]`}>
                  <span
                    className="block text-[0.8rem] text-[#666] whitespace-nowrap overflow-hidden text-ellipsis font-mono"
                    title={receipt.filename}
                  >
                    {formatFilename(receipt.filename)}
                  </span>
                </td>
                <td className={`${tdBase} min-w-[100px] max-w-[130px]`}>
                  <span
                    className={`block whitespace-nowrap overflow-hidden text-ellipsis font-medium ${isProcessed ? 'text-[#666]' : ''}`}
                    title={extracted.vendor || 'Unknown'}
                  >
                    {extracted.vendor || 'Unknown'}
                  </span>
                </td>
                <td className={`${tdBase} whitespace-nowrap min-w-[85px]`}>
                  {formatDate(extracted.date)}
                </td>
                <td className={`${tdBase} text-right whitespace-nowrap font-mono text-[0.85rem] min-w-[80px]`}>
                  {formatAmount(extracted.amount)}
                </td>
                <td className={`${tdBase} w-9 text-center`}>
                  {receipt.status === 'pending' && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemoveReceipt(receipt.receipt_id);
                      }}
                      disabled={disabled}
                      title="Remove from list"
                      className="py-1 px-2 bg-transparent border-0 text-[#bbb] cursor-pointer text-[0.9rem] leading-none rounded transition-all duration-150 hover:enabled:text-[#dc3545] hover:enabled:bg-[#fee] disabled:cursor-not-allowed disabled:opacity-50"
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
