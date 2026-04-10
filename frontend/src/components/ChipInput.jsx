/**
 * @file ChipInput.jsx
 * Editable list of short strings rendered as removable chips. Enter
 * commits the current draft; click × to remove. Used for
 * `currency_symbols` and `exclude_patterns`.
 */

import { useState } from 'react';
import './ChipInput.css';

/**
 * @component
 * @param {Object} props
 * @param {string[]} props.value
 * @param {(next: string[]) => void} props.onChange
 * @param {string} [props.placeholder='Add…']
 * @param {boolean} [props.disabled=false]
 * @param {boolean} [props.allowDuplicates=false]
 */
export default function ChipInput({
  value = [],
  onChange,
  placeholder = 'Add…',
  disabled = false,
  allowDuplicates = false,
}) {
  const [draft, setDraft] = useState('');

  const commit = () => {
    const v = draft.trim();
    if (!v) return;
    if (!allowDuplicates && value.includes(v)) {
      setDraft('');
      return;
    }
    onChange([...value, v]);
    setDraft('');
  };

  const removeAt = (idx) => {
    onChange(value.filter((_, i) => i !== idx));
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commit();
    } else if (e.key === 'Backspace' && draft === '' && value.length > 0) {
      removeAt(value.length - 1);
    }
  };

  return (
    <div className={`chip-input ${disabled ? 'chip-input--disabled' : ''}`}>
      {value.map((chip, i) => (
        <span key={`${chip}-${i}`} className="chip-input__chip">
          {chip}
          <button
            type="button"
            className="chip-input__remove"
            onClick={() => removeAt(i)}
            disabled={disabled}
            aria-label={`Remove ${chip}`}
          >
            ×
          </button>
        </span>
      ))}
      <input
        className="chip-input__field"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={commit}
        placeholder={placeholder}
        disabled={disabled}
      />
    </div>
  );
}