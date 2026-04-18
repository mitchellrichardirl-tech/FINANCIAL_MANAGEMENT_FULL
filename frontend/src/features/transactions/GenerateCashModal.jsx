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

  useEffect(() => {
    if (isOpen) setSaving(false);
  }, [isOpen]);

  if (!isOpen) return null;

  const handleConfirm = async () => {
    setSaving(true);
    try {
      await onConfirm();
    } catch {
      setSaving(false);
    }
  };

  const handleClose = () => {
    if (saving) return;
    onClose();
  };

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !saving) handleClose();
  };

  const plural = transactionCount === 1 ? '' : 's';

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-[1000] p-[1rem]"
      onClick={handleBackdropClick}
    >
      <div
        className="bg-white rounded-[8px] shadow-[0_4px_24px_rgba(0,0,0,0.18)] flex flex-col max-h-[90vh] w-full max-w-[560px] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-[1.5rem] pt-[1.25rem] pb-[1rem] border-b border-[#e5e7eb] shrink-0">
          <h2 className="m-0 text-[1.2rem] font-semibold text-[#111827]">Generate Cash Transactions</h2>
          <button
            className="bg-none border-none text-[1.5rem] leading-[1] cursor-pointer text-[#6b7280] px-[0.25rem] rounded-[4px] transition-[color,background] duration-150 hover:not-disabled:text-[#111827] hover:not-disabled:bg-[#f3f4f6] disabled:opacity-40 disabled:cursor-not-allowed"
            onClick={handleClose}
            disabled={saving}
            aria-label="Close modal"
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-[1.5rem] py-[1rem] flex flex-col gap-[1.25rem]">
          <div className="flex flex-col gap-[0.75rem]">
            <p className="m-0 text-[0.8rem] text-[#6b7280] leading-[1.4]">
              This will create{' '}
              <strong>
                {transactionCount} new transaction{plural}
              </strong>{' '}
              on the <strong>Cash</strong> account — one for each selected
              transaction, with the amount negated and the date,
              description and party copied from the source.
            </p>
            <p className="m-0 text-[0.8rem] text-[#6b7280] leading-[1.4]">
              Transactions that already have a cash counterpart will be
              skipped. Transactions already on the Cash account will be
              rejected.
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-[0.75rem] px-[1.5rem] py-[1rem] border-t border-[#e5e7eb] shrink-0">
          <button
            className="py-[0.5rem] px-[1.1rem] border border-[#d1d5db] rounded-[6px] bg-white text-[#374151] text-[0.9rem] cursor-pointer transition-[background,border-color] duration-150 hover:not-disabled:bg-[#f9fafb] hover:not-disabled:border-[#9ca3af] disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={handleClose}
            disabled={saving}
            type="button"
          >
            Cancel
          </button>
          <button
            className="py-[0.5rem] px-[1.25rem] border-none rounded-[6px] bg-[#2563eb] text-white text-[0.9rem] font-medium cursor-pointer transition-colors duration-150 hover:not-disabled:bg-[#1d4ed8] disabled:bg-[#93c5fd] disabled:cursor-not-allowed"
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
