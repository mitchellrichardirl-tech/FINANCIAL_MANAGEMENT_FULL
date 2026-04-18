export default function FormField({
  label,
  children,
  help,
  error,
  required = false,
  htmlFor,
}) {
  return (
    <div className={`flex flex-col gap-[6px] mb-4 ${error ? '[&_input]:border-[#d9363e] [&_select]:border-[#d9363e]' : ''}`}>
      <label className="text-[13px] font-semibold text-[#333]" htmlFor={htmlFor}>
        {label}
        {required && <span className="text-[#d9363e]" aria-hidden="true"> *</span>}
      </label>
      <div>{children}</div>
      {error ? (
        <p className="m-0 text-xs text-[#d9363e]" role="alert">{error}</p>
      ) : help ? (
        <p className="m-0 text-xs text-[#6c757d]">{help}</p>
      ) : null}
    </div>
  );
}
