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
import './RemapPartyPrompt.css';

/**
 * Conflict dialog for party/type mismatch during inline edit.
 *
 * @component
 * @param {Object} props
 * @param {string} props.partyName
 *        Display name of the party that's affected.
 * @param {() => void} props.onRemapAll
 *        User chose to remap the whole party globally.
 * @param {() => void} props.onThisOnly
 *        User chose to reassign only this transaction (a new party with
 *        the same name will be created under the new type if needed).
 * @param {() => void} props.onCancel
 *        User cancelled — revert the draft and keep editing.
 * @returns {JSX.Element}
 *
 * @example
 * {conflict && (
 *   <RemapPartyPrompt
 *     partyName={conflict.oldPartyName}
 *     onRemapAll={handleRemapAll}
 *     onThisOnly={handleThisOnly}
 *     onCancel={handleCancelConflict}
 *   />
 * )}
 */
export default function RemapPartyPrompt({ partyName, onRemapAll, onThisOnly, onCancel }) {
  return createPortal(
    <div className="remap-prompt-overlay" onClick={onCancel}>
      <div
        className="remap-prompt"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="remap-prompt-title"
      >
        <h3 id="remap-prompt-title">Party category has changed</h3>

        <p>
          <strong>{partyName}</strong> is currently mapped to a different category. How would you
          like to handle this?
        </p>

        <div className="remap-prompt-options">
          {/* Option 1: global remap */}
          <button className="remap-option remap-option--all" onClick={onRemapAll} type="button">
            <span className="remap-option__icon">🔁</span>
            <span className="remap-option__body">
              <span className="remap-option__label">Remap entire party</span>
              <span className="remap-option__hint">
                Move <em>all</em> transactions for "{partyName}" to the new category
              </span>
            </span>
          </button>

          {/* Option 2: single-transaction reassign */}
          <button className="remap-option remap-option--one" onClick={onThisOnly} type="button">
            <span className="remap-option__icon">1️⃣</span>
            <span className="remap-option__body">
              <span className="remap-option__label">This transaction only</span>
              <span className="remap-option__hint">
                Create a separate "{partyName}" entry in the new category for this transaction
              </span>
            </span>
          </button>
        </div>

        <button className="remap-prompt-cancel" onClick={onCancel} type="button">
          Cancel — keep editing
        </button>
      </div>
    </div>,
    document.body
  );
}