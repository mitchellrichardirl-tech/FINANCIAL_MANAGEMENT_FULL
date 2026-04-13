/**
 * @file FormField.jsx
 * Label + help text + error message wrapper around any form control.
 *
 * Purely presentational — owns no state. The child input is rendered
 * via `children` so this works with `TextInput`, `Dropdown`, `Checkbox`,
 * or anything else.
 */

import './FormField.css';

/**
 * @component
 * @param {Object} props
 * @param {string} props.label              - Visible field label.
 * @param {React.ReactNode} props.children  - The input control.
 * @param {string} [props.help]             - Optional hint text shown below the control.
 * @param {string} [props.error]            - Validation error. When present, help text
 *                                            is hidden and the field gets error styling.
 * @param {boolean} [props.required=false]  - Adds a visual required marker.
 * @param {string} [props.htmlFor]          - Forwarded to the `<label>` for a11y when
 *                                            the child input has a matching `id`.
 */
export default function FormField({
  label,
  children,
  help,
  error,
  required = false,
  htmlFor,
}) {
  return (
    <div className={`form-field ${error ? 'form-field--error' : ''}`}>
      <label className="form-field__label" htmlFor={htmlFor}>
        {label}
        {required && <span className="form-field__required" aria-hidden="true"> *</span>}
      </label>
      <div className="form-field__control">{children}</div>
      {error ? (
        <p className="form-field__error" role="alert">{error}</p>
      ) : help ? (
        <p className="form-field__help">{help}</p>
      ) : null}
    </div>
  );
}