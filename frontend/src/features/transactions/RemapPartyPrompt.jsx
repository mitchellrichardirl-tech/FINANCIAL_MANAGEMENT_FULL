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
 * Conflict dialog for party/type mismatch during inline edit.
 *
 * @component
 * @param {Object} props
 * @param {string} props.partyName
 * @param {() => void} props.onRemapAll
 * @param {() => void} props.onThisOnly
 * @param {() => void} props.onCancel
 * @returns {JSX.Element}
 */
export default function RemapPartyPrompt({ partyName, onRemapAll, onThisOnly, onCancel }) {
  return createPortal(
    <div
      className="fixed inset-0 bg-black/45 flex items-center justify-center z-[1100] p-[1rem]"
      onClick={onCancel}
    >
      <div
        className="bg-white rounded-[10px] shadow-[0_8px_32px_rgba(0,0,0,0.22)] p-[1.5rem] w-full max-w-[420px] flex flex-col gap-[1rem]"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="remap-prompt-title"
      >
        <h3 id="remap-prompt-title" className="m-0 text-[1rem] font-semibold text-[#111827]">Party category has changed</h3>

        <p className="m-0 text-[0.875rem] text-[#374151] leading-[1.5]">
          <strong>{partyName}</strong> is currently mapped to a different category. How would you
          like to handle this?
        </p>

        <div className="flex flex-col gap-[0.5rem]">
          {/* Option 1: global remap */}
          <button
            className="flex items-start gap-[0.75rem] py-[0.75rem] px-[1rem] border-2 border-[#e5e7eb] rounded-[8px] bg-white cursor-pointer text-left transition-[border-color,background] duration-150 w-full hover:bg-[#eff6ff] hover:border-[#2563eb]"
            onClick={onRemapAll}
            type="button"
          >
            <span className="text-[1.25rem] shrink-0 leading-[1.4]">🔁</span>
            <span className="flex flex-col gap-[0.2rem]">
              <span className="text-[0.9rem] font-semibold text-[#111827]">Remap entire party</span>
              <span className="text-[0.78rem] text-[#6b7280] leading-[1.4]">
                Move <em>all</em> transactions for "{partyName}" to the new category
              </span>
            </span>
          </button>

          {/* Option 2: single-transaction reassign */}
          <button
            className="flex items-start gap-[0.75rem] py-[0.75rem] px-[1rem] border-2 border-[#e5e7eb] rounded-[8px] bg-white cursor-pointer text-left transition-[border-color,background] duration-150 w-full hover:bg-[#ecfdf5] hover:border-[#059669]"
            onClick={onThisOnly}
            type="button"
          >
            <span className="text-[1.25rem] shrink-0 leading-[1.4]">1️⃣</span>
            <span className="flex flex-col gap-[0.2rem]">
              <span className="text-[0.9rem] font-semibold text-[#111827]">This transaction only</span>
              <span className="text-[0.78rem] text-[#6b7280] leading-[1.4]">
                Create a separate "{partyName}" entry in the new category for this transaction
              </span>
            </span>
          </button>
        </div>

        <button
          className="bg-none border-none text-[#6b7280] text-[0.82rem] cursor-pointer text-center py-[0.25rem] rounded-[4px] underline transition-colors duration-150 hover:text-[#374151]"
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
