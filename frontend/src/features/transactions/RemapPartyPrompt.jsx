/**
 * @file RemapPartyPrompt.jsx
 * Inline conflict-resolution dialog shown by {@link TransactionRow}
 * when the user changes a parent level (category/subcat/type) while a
 * party is already selected.
 *
 * The prompt offers two paths:
 *  1. **Remap entire party** — open {@link RemapPartyModal} to move the
 *     party (and all its transactions) to the new type globally.
 *  2. **This transaction only** — create/find a party with the same
 *     name under the new type and assign just this transaction to it.
 *
 * Rendered via `createPortal` into `document.body` so it overlays the
 * table correctly.
 */

import { createPortal } from 'react-dom';
/**
 * Shared chrome for the two option buttons. The base `:hover` background
 * from the old CSS is omitted — both instances carry a variant hover that
 * always overrode it, so it was dead.
 */
const OPTION_BASE =
  'flex w-full cursor-pointer items-start gap-3 rounded-lg border-2 border-gray-200 ' +
  'bg-white px-4 py-3 text-left transition-[border-color,background] duration-150';
const OPTION_LABEL = 'text-[0.9rem] font-semibold text-gray-900';
const OPTION_HINT = 'text-[0.78rem] leading-[1.4] text-gray-500';
const OPTION_ICON = 'shrink-0 text-xl leading-[1.4]';
const OPTION_BODY = 'flex flex-col gap-[0.2rem]';
/**
 * Conflict dialog for party/type mismatch during inline edit.
 * (full docblock unchanged)
 */
export default function RemapPartyPrompt({ partyName, onRemapAll, onThisOnly, onCancel }) {
  return createPortal(
    <div
      className="fixed inset-0 z-[1100] flex items-center justify-center bg-black/45 p-4"
      onClick={onCancel}
    >
      <div
        className="flex w-full max-w-[420px] flex-col gap-4 rounded-[10px] bg-white p-6 shadow-[0_8px_32px_rgba(0,0,0,0.22)]"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="remap-prompt-title"
      >
        <h3 id="remap-prompt-title" className="text-base font-semibold text-gray-900">
          Party category has changed
        </h3>
        <p className="text-sm leading-normal text-gray-700">
          <strong>{partyName}</strong> is currently mapped to a different category. How would you
          like to handle this?
        </p>
        <div className="flex flex-col gap-2">
          {/* Option 1: global remap */}
          <button
            className={`${OPTION_BASE} hover:border-blue-600 hover:bg-blue-50`}
            onClick={onRemapAll}
            type="button"
          >
            <span className={OPTION_ICON}>🔁</span>
            <span className={OPTION_BODY}>
              <span className={OPTION_LABEL}>Remap entire party</span>
              <span className={OPTION_HINT}>
                Move <em>all</em> transactions for "{partyName}" to the new category
              </span>
            </span>
          </button>
          {/* Option 2: single-transaction reassign */}
          <button
            className={`${OPTION_BASE} hover:border-emerald-600 hover:bg-emerald-50`}
            onClick={onThisOnly}
            type="button"
          >
            <span className={OPTION_ICON}>1️⃣</span>
            <span className={OPTION_BODY}>
              <span className={OPTION_LABEL}>This transaction only</span>
              <span className={OPTION_HINT}>
                Create a separate "{partyName}" entry in the new category for this transaction
              </span>
            </span>
          </button>
        </div>
        <button
          className="cursor-pointer rounded p-1 text-center text-[0.82rem] text-gray-500 underline transition-colors duration-150 hover:text-gray-700"
          onClick={onCancel}
          type="button"
        >
          Cancel — keep editing
        </button>
      </div>
    </div>,
    document.body
  );
}