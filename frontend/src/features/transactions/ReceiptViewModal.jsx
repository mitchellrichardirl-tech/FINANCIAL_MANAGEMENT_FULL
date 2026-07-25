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
/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('ReceiptViewModal');
/** True if the filename looks like a PDF. */
const isPdf = (filename) => !!filename && filename.toLowerCase().endsWith('.pdf');
const FOOTER_BTN = 'cursor-pointer rounded px-4 py-2';
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
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-[640px] flex-col rounded-lg bg-white shadow-[0_10px_40px_rgba(0,0,0,0.2)]"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between border-b border-[#eee] px-5 py-4">
          <h3 className="text-lg font-bold">Receipt</h3>
          <button
            className="cursor-pointer text-[1.1rem] leading-none text-gray-500 hover:text-black"
            onClick={onClose}
            aria-label="Close"
            type="button"
          >
            ✕
          </button>
        </div>
        <div className="flex flex-wrap gap-6 border-b border-[#f0f0f0] px-5 py-3 text-sm">
          <div>
            <span className="mr-1 text-[#888]">Vendor:</span> {receiptVendor || '—'}
          </div>
          <div>
            <span className="mr-1 text-[#888]">Amount:</span> {formatAmount(receiptAmount)}
          </div>
          <div>
            <span className="mr-1 text-[#888]">Date:</span> {formatDate(receiptDate)}
          </div>
        </div>
        {/* min-h-[200px] is a floor AND the flex minimum — see note */}
        <div className="flex min-h-[200px] flex-1 items-center justify-center overflow-auto bg-gray-50 px-5 py-4">
          {isPdf(receiptFilename) ? (
            <iframe
              src={imageUrl}
              title={receiptFilename || 'Receipt PDF'}
              className="h-[60vh] w-full"
            />
          ) : (
            <img
              src={imageUrl}
              alt={receiptFilename || 'Receipt'}
              className="max-h-[60vh] max-w-full object-contain"
            />
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-[#eee] px-5 py-4">
          <button
            className={`${FOOTER_BTN} bg-[#f44336] text-white hover:bg-[#d32f2f] disabled:cursor-not-allowed disabled:opacity-60`}
            onClick={handleUnlink}
            disabled={isUnlinking}
            type="button"
          >
            {isUnlinking ? 'Unlinking…' : 'Unlink receipt'}
          </button>
          <button
            className={`${FOOTER_BTN} bg-[#e0e0e0] hover:bg-[#d0d0d0]`}
            onClick={onClose}
            type="button"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}