import { useState } from 'react';
import ReceiptThumbnail from '@/components/Thumbnail';
import './SelectableReceiptTable.css';

export default function SelectableReceiptTable({
  receipts = [],
  selectedReceiptId,
  onSelectReceipt,
  onRemoveReceipt,
  disabled = false
}) {
  const [sortConfig, setSortConfig] = useState({ key: 'date', direction: 'desc' });

  const handleSort = (key) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

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
    // Truncate long filenames but show extension
    if (filename.length > 20) {
      const ext = filename.split('.').pop();
      return `${filename.substring(0, 15)}...${ext}`;
    }
    return filename;
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'saved': return '✓';
      case 'linked': return '🔗';
      default: return '○';
    }
  };

  const SortableHeader = ({ field, children }) => (
    <th
      onClick={() => handleSort(field)}
      className="sortable-header"
    >
      {children}
      {sortConfig.key === field && (
        <span className="sort-indicator">
          {sortConfig.direction === 'asc' ? ' ↑' : ' ↓'}
        </span>
      )}
    </th>
  );

  if (receipts.length === 0) {
    return (
      <div className="empty-receipt-list">
        <p>No receipts uploaded yet</p>
        <p className="hint">Upload receipts using the dropzone above</p>
      </div>
    );
  }

  return (
    <div className="selectable-receipt-table-container">
      <table className="selectable-receipt-table">
        <thead>
          <tr>
            <th className="thumbnail-col">Image</th>
            <th className="status-col">
              <span title="Status">●</span>
            </th>
            <SortableHeader field="filename">File</SortableHeader>
            <SortableHeader field="vendor">Vendor</SortableHeader>
            <SortableHeader field="date">Date</SortableHeader>
            <SortableHeader field="amount">Amount</SortableHeader>
            <th className="actions-col"></th>
          </tr>
        </thead>
        <tbody>
          {sortedReceipts.map(receipt => {
            const isSelected = receipt.receipt_id === selectedReceiptId;
            const isProcessed = receipt.status === 'saved' || receipt.status === 'linked';
            const extracted = receipt.extracted_data || {};
            
            return (
              <tr
                key={receipt.receipt_id}
                className={`receipt-row ${isSelected ? 'selected' : ''} status-${receipt.status || 'pending'} ${isProcessed ? 'processed' : ''}`}
                onClick={() => !disabled && onSelectReceipt(receipt.receipt_id)}
              >
                <td className="thumbnail-col">
                  <ReceiptThumbnail
                    src={`/api/receipts/${receipt.receipt_id}/image`}
                    alt={`Receipt from ${extracted.vendor || 'Unknown'}`}
                    maxWidth="60px"
                    maxHeight="45px"
                  />
                </td>
                <td className="status-col">
                  <span 
                    className={`status-icon status-${receipt.status || 'pending'}`}
                    title={receipt.status || 'pending'}
                  >
                    {getStatusIcon(receipt.status)}
                  </span>
                </td>
                <td className="filename-col">
                  <span className="filename" title={receipt.filename}>
                    {formatFilename(receipt.filename)}
                  </span>
                </td>
                <td className="vendor-col">
                  <span className="vendor-name" title={extracted.vendor || 'Unknown'}>
                    {extracted.vendor || 'Unknown'}
                  </span>
                </td>
                <td className="date-col">
                  {formatDate(extracted.date)}
                </td>
                <td className="amount-col">
                  {formatAmount(extracted.amount)}
                </td>
                <td className="actions-col">
                  {receipt.status === 'pending' && (
                    <button
                      className="btn-remove"
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