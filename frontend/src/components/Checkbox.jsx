/**
 * @file Checkbox.jsx
 * Styled controlled checkbox with an optional inline text label.
 */

import './Checkbox.css';

/**
 * Controlled checkbox input.
 *
 * Thin wrapper around `<input type="checkbox">` that:
 *  - Normalizes `onChange` to receive a plain boolean instead of the
 *    DOM event.
 *  - Wraps the input in a `<label>` so clicking the text toggles it.
 *
 * @component
 * @param {Object} props
 * @param {boolean} props.checked
 *        Current checked state (controlled).
 * @param {(checked: boolean) => void} props.onChange
 *        Called with the new boolean value when toggled.
 * @param {boolean} [props.disabled=false]
 *        Disables interaction and applies disabled styling.
 * @param {string} [props.label='']
 *        Optional text rendered to the right of the box. Omitted from
 *        the DOM entirely when empty.
 * @returns {JSX.Element}
 *
 * @example
 * <Checkbox
 *   checked={row.selected}
 *   onChange={(v) => toggleRow(row.id, v)}
 *   label="Include in import"
 * />
 */
export default function Checkbox({ checked, onChange, disabled = false, label = '' }) {
  return (
    <label className="checkbox-container">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        className="checkbox-input"
      />
      {label && <span className="checkbox-label">{label}</span>}
    </label>
  );
}