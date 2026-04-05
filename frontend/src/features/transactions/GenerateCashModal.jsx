/**
 * @file GenerateCashModal.jsx
 * Lightweight confirmation modal for generating Cash-account
 * counterpart transactions from the current selection.
 *
 * Unlike {@link BulkEditModal} this modal has no inputs — it simply
 * explains what will happen and asks the user to confirm.
 */

import { useState, useEffect } from 'react';

/**
 * Confirmation dialog for the "Generate Cash Transactions" action.
 *
 * @component
 * @param {Object} props
 * @param {boolean} props.isOpen - Visibility flag.
 * @param {() => void} props.onClose - Called to close the modal.
 * @param {() => Promise<void>} props.onConfirm
 *        Async callback that performs the generation. Should throw on
 *        failure; the parent handles toasting.
 * @param {number} props.transactionCount - Number of selected sources.
 * @returns {JSX.Element|null}
 */
export default function GenerateCashModal({
  isOpen,
  onClose,
  onConfirm,
  transactionCount,
}) {
  const [saving, setSaving] = useState(false);

  // Reset spinner each time the modal opens.
  useEffect(() => {
    if (isOpen) setSaving(false);
  }, [isOpen]);

  if (!isOpen) return null;

  /** Invoke the parent's confirm callback. */
  const handleConfirm = async () => {
    setSaving(true);
    try {
      await onConfirm();
      // Parent closes the modal on success.
    } catch {
      setSaving(false);
    }
  };

  /** Close unless a save is in flight. */
  const handleClose = () => {
    if (saving) return;
    onClose();
  };

  /** Close when clicking the overlay backdrop. */
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !saving) handleClose();
  };

  const plural = transactionCount === 1 ? '' : 's';

  return (
    <div className="modal-overlay" onClick={handleBackdropClick}>
      <div
        className="modal-content generate-cash-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2>Generate Cash Transactions</h2>
          <button
            className="modal-close-btn"
            onClick={handleClose}
            disabled={saving}
            aria-label="Close modal"
          >
            ×
          </button>
        </div>

        <div className="bulk-edit-form">
          <div className="form-section">
            <p className="form-hint">
              This will create{' '}
              <strong>
                {transactionCount} new transaction{plural}
              </strong>{' '}
              on the <strong>Cash</strong> account — one for each selected
              transaction, with the amount negated and the date,
              description and party copied from the source.
            </p>
            <p className="form-hint">
              Transactions that already have a cash counterpart will be
              skipped. Transactions already on the Cash account will be
              rejected.
            </p>
          </div>
        </div>

        <div className="modal-actions">
          <button
            className="cancel-button"
            onClick={handleClose}
            disabled={saving}
            type="button"
          >
            Cancel
          </button>
          <button
            className="save-button"
            onClick={handleConfirm}
            disabled={saving || transactionCount === 0}
            type="button"
          >
            {saving
              ? 'Generating…'
              : `Generate ${transactionCount} Transaction${plural}`}
          </button>
        </div>
      </div>
    </div>
  );
}