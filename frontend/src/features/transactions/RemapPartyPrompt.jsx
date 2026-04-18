import { createPortal } from 'react-dom';

export default function RemapPartyPrompt({ partyName, onRemapAll, onThisOnly, onCancel }) {
  return createPortal(
    <div
      onClick={onCancel}
      className="fixed inset-0 bg-black/45 flex items-center justify-center z-[1100] p-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="remap-prompt-title"
        className="bg-white rounded-[10px] shadow-[0_8px_32px_rgba(0,0,0,0.22)] p-6 w-full max-w-[420px] flex flex-col gap-4"
      >
        <h3 id="remap-prompt-title" className="m-0 text-base font-semibold text-[#111827]">
          Party category has changed
        </h3>
        <p className="m-0 text-sm text-[#374151] leading-normal">
          <strong>{partyName}</strong> is currently mapped to a different category. How would you
          like to handle this?
        </p>
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={onRemapAll}
            className="flex items-start gap-3 py-3 px-4 border-2 border-[#e5e7eb] rounded-lg bg-white cursor-pointer text-left transition-[border-color,background] duration-150 w-full hover:bg-[#f9fafb] hover:border-[#2563eb] hover:bg-[#eff6ff]"
          >
            <span className="text-xl shrink-0 leading-tight">🔁</span>
            <span className="flex flex-col gap-[0.2rem]">
              <span className="text-[0.9rem] font-semibold text-[#111827]">
                Remap entire party
              </span>
              <span className="text-[0.78rem] text-[#6b7280] leading-normal">
                Move <em>all</em> transactions for &quot;{partyName}&quot; to the new category
              </span>
            </span>
          </button>

          <button
            type="button"
            onClick={onThisOnly}
            className="flex items-start gap-3 py-3 px-4 border-2 border-[#e5e7eb] rounded-lg bg-white cursor-pointer text-left transition-[border-color,background] duration-150 w-full hover:bg-[#f9fafb] hover:border-[#059669] hover:bg-[#ecfdf5]"
          >
            <span className="text-xl shrink-0 leading-tight">1️⃣</span>
            <span className="flex flex-col gap-[0.2rem]">
              <span className="text-[0.9rem] font-semibold text-[#111827]">
                This transaction only
              </span>
              <span className="text-[0.78rem] text-[#6b7280] leading-normal">
                Create a separate &quot;{partyName}&quot; entry in the new category for this transaction
              </span>
            </span>
          </button>
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="bg-none border-0 text-[#6b7280] text-[0.82rem] cursor-pointer text-center p-1 rounded underline hover:text-[#374151]"
        >
          Cancel — keep editing
        </button>
      </div>
    </div>,
    document.body
  );
}
