/**
 * @file ReceiptUploadModal.jsx
 * Modal for uploading a receipt and attaching it to a transaction.
 *
 * Two-step flow on submit:
 *   1. uploadReceipt(file)  → server OCRs/stores it, returns receipt id
 *   2. linkReceipt(txnId, receiptId) → attaches it, returns updated txn
 *
 * On success, `onReceiptLinked` is called with the updated transaction
 * so the parent can patch its state (wired through in Commit 5).
 *
 * @component
 * @param {Object} props
 * @param {boolean} props.isOpen
 * @param {Function} props.onClose
 * @param {number} props.transactionId
 * @param {(updatedTransaction: Object) => void} [props.onReceiptLinked]
 */

import { useState, useEffect } from 'react';
import { uploadReceipt, linkReceipt } from './api';
import { useToast } from '@/components/ToastContext';
import { createLogger } from '@/lib/logger';
// ❌ removed: import './ReceiptUploadModal.css';
/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('ReceiptUploadModal');
const ACCEPT = 'image/png,image/jpeg,image/jpg,application/pdf,.png,.jpg,.jpeg,.pdf';
const FOOTER_BTN = 'cursor-pointer rounded px-4 py-2 disabled:cursor-not-allowed';
export default function ReceiptUploadModal({
  isOpen,
  onClose,
  transactionId,
  transaction,
  onReceiptLinked,
}) {
  const { addToast } = useToast();
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  // Reset state whenever the modal opens.
  useEffect(() => {
    if (isOpen) {
      setFile(null);
      setIsUploading(false);
    }
  }, [isOpen]);
  // Close on Escape (ignored while an upload is in flight).
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e) => {
      if (e.key === 'Escape' && !isUploading) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, isUploading, onClose]);
  if (!isOpen) return null;
  const handleSubmit = async () => {
    if (!file) return;
    setIsUploading(true);
    try {
      const receipt = await uploadReceipt(file, {
        skipOcr: true,
        vendor:
          transaction?.party_name ||
          transaction?.cleaned_description ||
          transaction?.description ||
          null,
        amount: transaction?.amount != null ? Math.abs(transaction.amount) : null,
        date: transaction?.transaction_date
          ? String(transaction.transaction_date).slice(0, 10)
          : null,
      });
      const receiptId = receipt?.id;
      if (!receiptId) {
        throw new Error('Upload succeeded but no receipt id was returned');
      }
      const updated = await linkReceipt(transactionId, receiptId);
      addToast({ message: 'Receipt attached', type: 'success', duration: 2000 });
      onReceiptLinked?.(updated);
      onClose();
    } catch (err) {
      logger.error('Failed to upload/attach receipt:', err);
      addToast({
        message: `Failed to attach receipt: ${err.userMessage || err.message}`,
        type: 'error',
      });
    } finally {
      setIsUploading(false);
    }
  };
  const handleBackdrop = () => {
    if (!isUploading) onClose();
  };
  return (
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/50 p-4"
      onClick={handleBackdrop}
    >
      <div
        className="flex w-full max-w-[440px] flex-col rounded-lg bg-white shadow-[0_10px_40px_rgba(0,0,0,0.2)]"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between border-b border-[#eee] px-5 py-4">
          <h3 className="text-lg font-bold">Attach receipt</h3>
          <button
            className="cursor-pointer text-[1.1rem] leading-none text-gray-500 hover:text-black disabled:cursor-not-allowed disabled:opacity-50"
            onClick={onClose}
            disabled={isUploading}
            aria-label="Close"
            type="button"
          >
            ✕
          </button>
        </div>
        <div className="flex flex-col gap-2 p-5">
          <label htmlFor="receipt-file" className="text-sm text-gray-600">
            Choose a receipt image or PDF
          </label>
          {/* Native file input — was unstyled in the CSS too. See note. */}
          <input
            id="receipt-file"
            type="file"
            accept={ACCEPT}
            disabled={isUploading}
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          {file && (
            <p className="text-[0.85rem] break-all text-[#888]">{file.name}</p>
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-[#eee] px-5 py-4">
          <button
            className={`${FOOTER_BTN} bg-[#4caf50] text-white hover:bg-[#388e3c] disabled:opacity-60`}
            onClick={handleSubmit}
            disabled={!file || isUploading}
            type="button"
          >
            {isUploading ? 'Uploading…' : 'Upload & attach'}
          </button>
          <button
            className={`${FOOTER_BTN} bg-[#e0e0e0] hover:bg-[#d0d0d0] disabled:opacity-50`}
            onClick={onClose}
            disabled={isUploading}
            type="button"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}