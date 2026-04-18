/**
 * @file Dropdown.jsx
 * Styled controlled `<select>` that renders options from an array of
 * objects and normalizes the "nothing selected" state to `null`.
 */

export default function Dropdown({
  value,
  onChange,
  options = [],
  disabled = false,
  placeholder = 'Select...',
  valueKey = 'id',
  labelKey = 'name',
  includeEmpty = false,
  emptyLabel = 'Please Select'
}) {
  const handleChange = (e) => {
    const newValue = e.target.value;
    // Pass empty string as null, otherwise pass the actual value
    onChange(newValue === '' ? null : newValue);
  };

  return (
    <select
      value={value === null || value === undefined ? '' : value}
      onChange={handleChange}
      disabled={disabled}
      className={`p-[0.4em_0.8em] border border-border-dark rounded bg-surface-dark text-white/87 text-[0.9em] cursor-pointer w-full box-border hover:border-ghost focus:outline-2 focus:outline-ghost focus:outline-offset-1 disabled:cursor-not-allowed disabled:opacity-50 disabled:border-border-dark light:bg-surface-alt light:border-border light:text-text light:hover:border-ghost light:disabled:border-border ${value === null || value === '' ? 'text-text-light' : ''}`}
    >
      {includeEmpty && (
        <option value="">{emptyLabel}</option>
      )}
      {!includeEmpty && (value === null || value === '' || value === undefined) && (
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