export default function TextInput({
  value,
  onChange,
  placeholder = '',
  disabled = false,
  id,
  type = 'text',
  maxLength,
  className = '',
}) {
  return (
    <input
      id={id}
      type={type}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      maxLength={maxLength}
      className={`w-full box-border py-2 px-[10px] text-sm border border-[#ced4da] rounded bg-white text-[#212529] focus:outline-none focus:border-[#4a90e2] focus:shadow-[0_0_0_2px_rgba(74,144,226,0.2)] disabled:bg-[#f1f3f5] disabled:text-[#868e96] disabled:cursor-not-allowed ${className}`}
    />
  );
}
