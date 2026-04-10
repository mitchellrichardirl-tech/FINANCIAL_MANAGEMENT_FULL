/**
 * @file NumberInput.jsx
 * Styled controlled numeric input that emits a `number` (or `null` when
 * cleared) instead of a string.
 */

import './TextInput.css'; // shares base input styling

/**
 * @component
 * @param {Object} props
 * @param {number|null|undefined} props.value
 * @param {(value: number|null) => void} props.onChange
 *        Called with the parsed number, or `null` when the field is
 *        cleared. `NaN` is never emitted.
 * @param {number} [props.min]
 * @param {number} [props.max]
 * @param {number} [props.step=1]
 * @param {boolean} [props.disabled=false]
 * @param {string} [props.id]
 */
export default function NumberInput({
  value,
  onChange,
  min,
  max,
  step = 1,
  disabled = false,
  id,
}) {
  const handleChange = (e) => {
    const raw = e.target.value;
    if (raw === '') {
      onChange(null);
      return;
    }
    const n = Number(raw);
    if (Number.isNaN(n)) return; // ignore unparsable intermediate states
    onChange(n);
  };

  return (
    <input
      id={id}
      type="number"
      className="text-input number-input"
      value={value ?? ''}
      onChange={handleChange}
      min={min}
      max={max}
      step={step}
      disabled={disabled}
    />
  );
}