/**
 * @file FormField.jsx
 * Label + help text + error message wrapper around any form control.
 *
 * Purely presentational — owns no state. The child input is rendered
 * via `children` so this works with `TextInput`, `Dropdown`, `Checkbox`,
 * or anything else.
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
    <div className={`flex flex-col gap-[6px] mb-4 ${error ? '[&_input]:border-danger [&_select]:border-danger' : ''}`}>
      <label className="text-[13px] font-semibold text-[#333]" htmlFor={htmlFor}>
        {label}
        {required && <span className="text-danger" aria-hidden="true"> *</span>}
      </label>
      <div>{children}</div>
      {error ? (
        <p className="m-0 text-xs text-danger" role="alert">{error}</p>
      ) : help ? (
        <p className="m-0 text-xs text-[#6c757d]">{help}</p>
      ) : null}
    </div>
  );
}