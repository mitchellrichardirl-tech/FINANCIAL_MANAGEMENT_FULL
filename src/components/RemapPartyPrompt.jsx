import './RemapPartyPrompt.css';

/**
 * Shown when the user saves a transaction row after changing the type
 * while a party is already selected.
 *
 * Props:
 *   partyName      – name of the affected party
 *   onRemapAll     – user wants to move the whole party to the new type
 *   onThisOnly     – user wants only this transaction reassigned
 *   onCancel       – user wants to go back and keep editing
 */
export default function RemapPartyPrompt({
  partyName,
  onRemapAll,
  onThisOnly,
  onCancel,
}) {
  return (
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
          <strong>{partyName}</strong> is currently mapped to a different
          category. How would you like to handle this?
        </p>

        <div className="remap-prompt-options">
          <button
            className="remap-option remap-option--all"
            onClick={onRemapAll}
            type="button"
          >
            <span className="remap-option__icon">🔁</span>
            <span className="remap-option__body">
              <span className="remap-option__label">
                Remap entire party
              </span>
              <span className="remap-option__hint">
                Move <em>all</em> transactions for "{partyName}" to the new
                category
              </span>
            </span>
          </button>

          <button
            className="remap-option remap-option--one"
            onClick={onThisOnly}
            type="button"
          >
            <span className="remap-option__icon">1️⃣</span>
            <span className="remap-option__body">
              <span className="remap-option__label">
                This transaction only
              </span>
              <span className="remap-option__hint">
                Create a separate "{partyName}" entry in the new category for
                this transaction
              </span>
            </span>
          </button>
        </div>

        <button
          className="remap-prompt-cancel"
          onClick={onCancel}
          type="button"
        >
          Cancel — keep editing
        </button>
      </div>
    </div>
  );
}