import { useState } from 'react';
/**
 * Confirmation modal for bulk soft-delete.
 *
 * @component
 * @param {object} props
 * @param {boolean} props.isOpen
 * @param {() => void} props.onClose
 * @param {() => Promise<void>} props.onConfirm - Throws on failure; parent toasts.
 * @param {number} props.transactionCount
 * @returns {JSX.Element | null}
 */
export default function DeleteTransactionsModal({
  isOpen,
  onClose,
  onConfirm,
  transactionCount,
}) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  if (!isOpen) return null;
  const handleConfirm = async () => {
    setIsSubmitting(true);
    try {
      await onConfirm();
    } catch {
      // Parent surfaces the toast; keep the modal open so the user can retry.
    } finally {
      setIsSubmitting(false);
    }
  };
  const plural = transactionCount === 1 ? '' : 's';
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <h2 className="mb-3 text-xl font-semibold text-gray-800">
          Delete {transactionCount} transaction{plural}?
        </h2>
        <div className="mb-6 space-y-3 text-sm text-gray-600">
          <p>
            Deleted transactions are hidden from all views and excluded from
            totals, but they are retained in the database and can be restored.
          </p>
          <p className="rounded border border-amber-200 bg-amber-50 p-3 text-amber-900">
            Any cash transactions generated from these transactions will be
            deleted alongside them.
          </p>
        </div>
        <div className="flex justify-end gap-2.5">
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="cursor-pointer rounded border border-gray-300 bg-white px-5 py-2.5 text-sm font-medium text-gray-800 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={isSubmitting}
            className="cursor-pointer rounded bg-[#e53935] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#c62828] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting
              ? 'Deleting…'
              : `Delete ${transactionCount} transaction${plural}`}
          </button>
        </div>
      </div>
    </div>
  );
}