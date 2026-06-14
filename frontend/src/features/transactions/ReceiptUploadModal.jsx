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
import './ReceiptUploadModal.css';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('ReceiptUploadModal');

const ACCEPT = 'image/png,image/jpeg,image/jpg,application/pdf,.png,.jpg,.jpeg,.pdf';

export default function ReceiptUploadModal({
  isOpen,
  onClose,
  transactionId,
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
      const receipt = await uploadReceipt(file);
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
    <div className="receipt-upload-overlay" onClick={handleBackdrop}>
      <div
        className="receipt-upload-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="receipt-upload-header">
          <h3>Attach receipt</h3>
          <button
            className="receipt-upload-close"
            onClick={onClose}
            disabled={isUploading}
            aria-label="Close"
            type="button"
          >
            ✕
          </button>
        </div>

        <div className="receipt-upload-body">
          <label htmlFor="receipt-file" className="receipt-upload-label">
            Choose a receipt image or PDF
          </label>
          <input
            id="receipt-file"
            type="file"
            accept={ACCEPT}
            disabled={isUploading}
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          {file && <p className="receipt-upload-filename">{file.name}</p>}
        </div>

        <div className="receipt-upload-actions">
          <button
            className="btn-upload"
            onClick={handleSubmit}
            disabled={!file || isUploading}
            type="button"
          >
            {isUploading ? 'Uploading…' : 'Upload & attach'}
          </button>
          <button
            className="btn-cancel"
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