/**
 * @file TextInput.jsx
 * Styled controlled text input. Unlike {@link EditableText}, this fires
 * `onChange` on every keystroke — use it inside forms that need live
 * validation.
 */

import './TextInput.css';

/**
 * @component
 * @param {Object} props
 * @param {string|null|undefined} props.value
 * @param {(value: string) => void} props.onChange - Receives the raw string.
 * @param {string} [props.placeholder]
 * @param {boolean} [props.disabled=false]
 * @param {string} [props.id]      - For pairing with `FormField`'s `htmlFor`.
 * @param {string} [props.type='text']
 * @param {number} [props.maxLength]
 */
export default function TextInput({
  value,
  onChange,
  placeholder = '',
  disabled = false,
  id,
  type = 'text',
  maxLength,
}) {
  return (
    <input
      id={id}
      type={type}
      className="text-input"
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      maxLength={maxLength}
    />
  );
}