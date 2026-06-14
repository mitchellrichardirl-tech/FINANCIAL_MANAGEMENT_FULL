/**
 * @file ReceiptViewModal.jsx
 * Modal for viewing a receipt linked to a transaction.
 *
 * Shows the receipt image (or PDF via iframe) plus its extracted
 * metadata, and offers an "Unlink" action that detaches the receipt
 * from the transaction (the receipt record itself is left intact).
 *
 * @component
 * @param {Object} props
 * @param {boolean} props.isOpen
 * @param {Function} props.onClose
 * @param {number} props.receiptId
 * @param {string} [props.receiptFilename] - Used to detect PDF vs image.
 * @param {string} [props.receiptVendor]
 * @param {number} [props.receiptAmount]
 * @param {string} [props.receiptDate]
 * @param {number} props.transactionId
 * @param {(updatedTransaction: Object) => void} [props.onReceiptUnlinked]
 *        Called with the updated transaction after a successful unlink.
 */

import { useState, useEffect } from 'react';
import { API_BASE_URL } from '@/lib/apiClient';
import { unlinkReceipt } from './api';
import { useToast } from '@/components/ToastContext';
import { createLogger } from '@/lib/logger';
import './ReceiptViewModal.css';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('ReceiptViewModal');

/** True if the filename looks like a PDF. */
const isPdf = (filename) => !!filename && filename.toLowerCase().endsWith('.pdf');

export default function ReceiptViewModal({
  isOpen,
  onClose,
  receiptId,
  receiptFilename,
  receiptVendor,
  receiptAmount,
  receiptDate,
  transactionId,
  onReceiptUnlinked,
}) {
  const { addToast } = useToast();
  const [isUnlinking, setIsUnlinking] = useState(false);

  // Close on Escape.
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const imageUrl = `${API_BASE_URL}/receipts/${receiptId}/image`;

  const handleUnlink = async () => {
    setIsUnlinking(true);
    try {
      const updated = await unlinkReceipt(transactionId);
      addToast({ message: 'Receipt unlinked', type: 'success', duration: 2000 });
      onReceiptUnlinked?.(updated);
      onClose();
    } catch (err) {
      logger.error('Failed to unlink receipt:', err);
      addToast({
        message: `Failed to unlink receipt: ${err.userMessage || err.message}`,
        type: 'error',
      });
    } finally {
      setIsUnlinking(false);
    }
  };

  const formatAmount = (a) => (a == null ? '—' : parseFloat(a).toFixed(2));
  const formatDate = (d) => (d ? new Date(d).toISOString().split('T')[0] : '—');

  return (
    <div className="receipt-view-overlay" onClick={onClose}>
      <div
        className="receipt-view-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="receipt-view-header">
          <h3>Receipt</h3>
          <button
            className="receipt-view-close"
            onClick={onClose}
            aria-label="Close"
            type="button"
          >
            ✕
          </button>
        </div>

        <div className="receipt-view-meta">
          <div>
            <span className="meta-label">Vendor:</span> {receiptVendor || '—'}
          </div>
          <div>
            <span className="meta-label">Amount:</span> {formatAmount(receiptAmount)}
          </div>
          <div>
            <span className="meta-label">Date:</span> {formatDate(receiptDate)}
          </div>
        </div>

        <div className="receipt-view-image">
          {isPdf(receiptFilename) ? (
            <iframe
              src={imageUrl}
              title={receiptFilename || 'Receipt PDF'}
              className="receipt-view-pdf"
            />
          ) : (
            <img src={imageUrl} alt={receiptFilename || 'Receipt'} />
          )}
        </div>

        <div className="receipt-view-actions">
          <button
            className="btn-unlink"
            onClick={handleUnlink}
            disabled={isUnlinking}
            type="button"
          >
            {isUnlinking ? 'Unlinking…' : 'Unlink receipt'}
          </button>
          <button className="btn-close" onClick={onClose} type="button">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}