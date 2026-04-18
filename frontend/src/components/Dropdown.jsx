export default function Dropdown({
  value,
  onChange,
  options = [],
  disabled = false,
  placeholder = 'Select...',
  valueKey = 'id',
  labelKey = 'name',
  includeEmpty = false,
  emptyLabel = 'Please Select',
  className = '',
}) {
  const handleChange = (e) => {
    const newValue = e.target.value;
    onChange(newValue === '' ? null : newValue);
  };

  const isEmpty = value === null || value === '' || value === undefined;
  const emptyTextCls = isEmpty ? 'text-[#888]' : 'text-[#213547]';

  return (
    <select
      value={value === null || value === undefined ? '' : value}
      onChange={handleChange}
      disabled={disabled}
      className={`py-[0.4em] px-[0.8em] border border-[#ddd] rounded bg-[#f9f9f9] text-[0.9em] cursor-pointer w-full box-border hover:border-[#646cff] focus:outline-2 focus:outline-[#646cff] focus:outline-offset-1 disabled:cursor-not-allowed disabled:opacity-50 disabled:border-[#ddd] ${emptyTextCls} ${className}`}
    >
      {includeEmpty && <option value="">{emptyLabel}</option>}
      {!includeEmpty && isEmpty && (
        <option value="" disabled>{placeholder}</option>
      )}
      {options.map((option) => (
        <option key={option[valueKey]} value={option[valueKey]}>
          {option[labelKey]}
        </option>
      ))}
    </select>
  );
}
