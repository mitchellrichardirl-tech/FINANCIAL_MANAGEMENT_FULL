import './Dropdown.css';

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
      className={`dropdown ${value === null || value === '' ? 'dropdown-empty' : ''}`}
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