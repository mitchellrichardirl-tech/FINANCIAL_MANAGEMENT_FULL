/**
 * @file Dropdown.jsx
 * Styled controlled `<select>` that renders options from an array of
 * objects and normalizes the "nothing selected" state to `null`.
 */

import './Dropdown.css';

/**
 * Controlled select input backed by an array of option objects.
 *
 * Key behaviors:
 *  - **Null handling** — `value` may be `null`/`undefined`; the component
 *    maps that to an empty-string `<option>` internally and emits `null`
 *    (not `''`) back through `onChange` when the empty option is chosen.
 *  - **Placeholder vs. empty option** — when `includeEmpty` is `false`
 *    and nothing is selected, a disabled placeholder row is shown so the
 *    user must pick a real value. When `includeEmpty` is `true`, a
 *    selectable "clear" row (`emptyLabel`) is rendered instead.
 *  - **Configurable shape** — `valueKey` / `labelKey` let callers use
 *    their domain objects directly without reshaping to `{id, name}`.
 *
 * @component
 * @param {Object} props
 * @param {string|number|null|undefined} props.value
 *        Currently selected option value (matched against
 *        `option[valueKey]`). `null`/`undefined` means nothing selected.
 * @param {(value: string|null) => void} props.onChange
 *        Called with the selected option's value, or `null` when the
 *        empty option is chosen. Note: native `<select>` values are
 *        strings, so numeric ids come back as strings.
 * @param {Object[]} [props.options=[]]
 *        Option objects to render.
 * @param {boolean} [props.disabled=false]
 *        Disables the control.
 * @param {string} [props.placeholder='Select...']
 *        Text for the non-selectable placeholder row shown when
 *        `includeEmpty` is `false` and no value is selected.
 * @param {string} [props.valueKey='id']
 *        Property of each option object used as the `<option value>`.
 * @param {string} [props.labelKey='name']
 *        Property of each option object used as the visible label.
 * @param {boolean} [props.includeEmpty=false]
 *        When `true`, renders a selectable empty row (lets the user
 *        clear the selection back to `null`).
 * @param {string} [props.emptyLabel='Please Select']
 *        Label for the selectable empty row when `includeEmpty` is `true`.
 * @returns {JSX.Element}
 *
 * @example
 * <Dropdown
 *   value={txn.category_id}
 *   onChange={(id) => updateTxn(txn.id, { category_id: id })}
 *   options={categories}
 *   includeEmpty
 *   emptyLabel="Uncategorized"
 * />
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