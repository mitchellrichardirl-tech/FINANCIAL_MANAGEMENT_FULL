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
/** Shared chrome. Colour is supplied per-state and drives the SVG via `currentColor`. */
const BASE =
  'inline-flex cursor-pointer items-center justify-center rounded p-0.5 leading-none ' +
  'transition-[transform,color] duration-150 hover:scale-115';
export default function ReceiptIcon({ hasReceipt, onClick }) {
  return (
    <button
      className={`${BASE} ${
        hasReceipt
          ? 'text-[#4caf50] hover:text-[#388e3c]'
          : 'text-[#bdbdbd] hover:text-[#9e9e9e]'
      }`}
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