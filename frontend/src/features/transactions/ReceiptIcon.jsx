/**
 * @file ReceiptIcon.jsx
 * Clickable receipt indicator for the transaction table.
 *
 * Renders a small receipt SVG icon — coloured (green) when a receipt
 * is attached, grey when not. Accepts an optional `onClick` handler
 * wired up in later commits to open upload or view modals.
 *
 * @component
 * @param {Object} props
 * @param {boolean} props.hasReceipt - Whether a receipt is linked.
 * @param {Function} [props.onClick] - Click handler (wired in commits 3/4).
 */

import './ReceiptIcon.css';

export default function ReceiptIcon({ hasReceipt, onClick }) {
  return (
    <button
      className={`receipt-icon ${hasReceipt ? 'receipt-icon--attached' : 'receipt-icon--empty'}`}
      onClick={onClick}
      title={hasReceipt ? 'View receipt' : 'Attach receipt'}
      type="button"
      aria-label={hasReceipt ? 'View receipt' : 'Attach receipt'}
    >
      <svg
        viewBox="0 0 24 24"
        width="18"
        height="18"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M6 2v20l3-2 3 2 3-2 3 2V2H6z" />
        <path d="M9 7h6" />
        <path d="M9 11h6" />
        <path d="M9 15h3" />
      </svg>
    </button>
  );
}