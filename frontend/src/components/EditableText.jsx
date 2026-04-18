/**
 * @file EditableText.jsx
 * Inline text input that commits on blur/Enter and reverts on Escape.
 *
 * Used for lightweight in-place editing (e.g. renaming a transaction
 * description in a table row) without a dedicated form or save button.
 */

import { useState } from 'react';

/**
 * Inline-editable text field.
 *
 * Holds a local draft (`localValue`) while focused so keystrokes don't
 * fire `onChange` on every character. The draft is committed via
 * `onChange` only on blur, and only if it differs from the incoming
 * `value`. Pressing **Enter** blurs (and thus commits); pressing
 * **Escape** discards the draft and restores `value` before blurring.
 *
 * While not focused, the input displays the authoritative `value` prop
 * rather than the stale draft, so external updates (e.g. a server
 * round-trip) are reflected without remounting.
 *
 * When `disabled`, renders a plain `<span>` instead of an input.
 *
 * @component
 * @param {Object} props
 * @param {string|number|null|undefined} props.value
 *        Current committed value. Nullish is displayed as an empty string.
 * @param {(newValue: string) => void} props.onChange
 *        Called once, on blur, with the edited string — only when it
 *        differs from `value`.
 * @param {boolean} [props.disabled=false]
 *        When `true`, renders read-only text with no input element.
 * @param {string} [props.type='text']
 *        `type` attribute for the underlying `<input>` (e.g. `'number'`,
 *        `'date'`).
 * @param {string} [props.placeholder='']
 *        Placeholder shown when the field is empty.
 * @returns {JSX.Element}
 *
 * @example
 * <EditableText
 *   value={txn.description}
 *   onChange={(v) => updateTxn(txn.id, { description: v })}
 *   placeholder="Add a description…"
 * />
 */
export default function EditableText({
  value,
  onChange,
  disabled = false,
  type = 'text',
  placeholder = ''
}) {
  const [localValue, setLocalValue] = useState(value || '');
  const [isEditing, setIsEditing] = useState(false);

  const handleBlur = () => {
    setIsEditing(false);
    if (localValue !== value) {
      onChange(localValue);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.target.blur();
    } else if (e.key === 'Escape') {
      setLocalValue(value || '');
      e.target.blur();
    }
  };

  if (disabled) {
    return <span className="block p-[0.4em_0.6em] text-text-light text-[0.9em]">{value}</span>;
  }

  return (
    <input
      type={type}
      value={isEditing ? localValue : (value || '')}
      onChange={(e) => setLocalValue(e.target.value)}
      onFocus={() => setIsEditing(true)}
      onBlur={handleBlur}
      onKeyDown={handleKeyDown}
      placeholder={placeholder}
      className="p-[0.4em_0.6em] border border-transparent rounded bg-transparent text-inherit text-[0.9em] w-full box-border transition-all duration-200 hover:bg-ghost/10 hover:border-ghost focus:outline-none focus:bg-surface-dark focus:border-ghost light:focus:bg-white"
    />
  );
}